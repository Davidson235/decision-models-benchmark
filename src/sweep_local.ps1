# Sweep every downloaded local decision model: text corpus + vision corpus.
# Skips models whose files are not downloaded yet, so it can be run repeatedly
# while downloads are still in flight.
#
#   pwsh -File src/sweep_local.ps1
#   pwsh -File src/sweep_local.ps1 -Only vllm-d3-mini

param(
    [string[]]$Only = @(),
    [int]$Port = 9940
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$vpy = Join-Path $root '.venv\Scripts\python.exe'
$server = Join-Path $root '.tools\cuda12\llama-server.exe'

$models = @(
    @{ n = 'vllm-d3-edge';  f = 'vllm-d3-edge-Q8_0.gguf';  mm = 'mmproj-vllm-d3-edge-Q8_0.gguf';  ctx = 8192 },
    @{ n = 'vllm-d3-lite';  f = 'vllm-d3-lite-Q8_0.gguf';  mm = 'mmproj-vllm-d3-lite-Q8_0.gguf';  ctx = 8192 },
    @{ n = 'Julia-1';       f = 'Julia-1-Q8_0.gguf';       mm = $null;                              ctx = 4096 },
    @{ n = 'vllm-d3-nano';  f = 'vllm-d3-nano-Q8_0.gguf';  mm = 'mmproj-vllm-d3-nano-Q8_0.gguf';  ctx = 8192 },
    @{ n = 'vllm-d3-mini';  f = 'vllm-d3-mini-Q4_K_M.gguf'; mm = 'mmproj-vllm-d3-mini-Q8_0.gguf'; ctx = 8192 },
    @{ n = 'Kev-9B';        f = 'Kev-9B-Q4_K_M.gguf';      mm = $null;                              ctx = 4096 },
    @{ n = 'Clef-Flash';    f = 'Clef-Flash-Q4_K_M.gguf';  mm = 'mmproj-Clef-Flash-Q8_0.gguf';    ctx = 8192 },
    @{ n = 'vllm-d3-flash'; f = 'vllm-d3-flash-Q4_K_M.gguf'; mm = 'mmproj-vllm-d3-flash-Q8_0.gguf'; ctx = 8192 }
)

$results = @()

foreach ($m in $models) {
    if ($Only.Count -gt 0 -and $Only -notcontains $m.n) { continue }

    $mp = Join-Path $root ".tools\$($m.f)"
    if (-not (Test-Path $mp)) { Write-Host "SKIP $($m.n) - model file missing"; continue }
    if ($m.mm -and -not (Test-Path (Join-Path $root ".tools\$($m.mm)"))) {
        Write-Host "SKIP $($m.n) - projector missing"; continue
    }

    Write-Host "`n=== $($m.n) ==="
    Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2

    # Paths contain a space ("Decision-models TEST"), and Start-Process joins
    # ArgumentList with spaces without quoting, so quote each path by hand.
    $argList = @('-m', "`"$mp`"", '-ngl', '99', '-c', $m.ctx, '--port', $Port, '--host', '127.0.0.1')
    if ($m.mm) {
        $mmp = Join-Path $root ".tools\$($m.mm)"
        # A single 560x400 image becomes ~2200 tokens on these projectors, which
        # overflows the default 512-token physical batch, so raise it.
        $argList += @('--mmproj', "`"$mmp`"", '-b', '4096', '-ub', '4096')
    }

    $log = Join-Path $root ".tools\srv-$($m.n).log"
    $err = Join-Path $root ".tools\srv-$($m.n).err"
    $proc = Start-Process -FilePath $server -ArgumentList $argList -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError $err

    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 3
        try {
            $h = Invoke-WebRequest "http://127.0.0.1:$Port/health" -TimeoutSec 3 -SkipHttpErrorCheck
            if ($h.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        if ($proc.HasExited) { break }
    }
    if (-not $ready) {
        Write-Host "  LOAD FAILED - see $err"
        if (Test-Path $err) { Get-Content $err -Tail 5 | ForEach-Object { "    $_" } }
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
        $results += [pscustomobject]@{ model = $m.n; text = $null; vision = $null; status = 'load-failed' }
        continue
    }

    $vram = (nvidia-smi --query-gpu=memory.used --format=csv,noheader)
    Write-Host "  ready, VRAM used: $vram"

    $textOut = "runs/local-$($m.n)-text.json"
    $visOut = "runs/local-$($m.n)-vision.json"
    $ep = "http://127.0.0.1:$Port/v1/systemone"

    & $vpy -m src.local_bench --model $m.n --endpoint $ep --out $textOut 2>&1 | Select-Object -Last 2
    & $vpy -m src.local_vision --model $m.n --endpoint $ep --out $visOut 2>&1 | Select-Object -Last 2

    Stop-Process -Id $proc.Id -Force
    Start-Sleep -Seconds 2

    $t = if (Test-Path (Join-Path $root $textOut)) { Get-Content (Join-Path $root $textOut) -Raw | ConvertFrom-Json } else { $null }
    $v = if (Test-Path (Join-Path $root $visOut)) { Get-Content (Join-Path $root $visOut) -Raw | ConvertFrom-Json } else { $null }
    $results += [pscustomobject]@{
        model  = $m.n
        text   = if ($t) { [math]::Round($t.accuracy, 3) } else { $null }
        vision = if ($v -and $v.accuracy) { [math]::Round($v.accuracy, 3) } else { $null }
        status = 'ok'
    }
}

Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "`n=== summary ==="
$results | Format-Table -AutoSize
$results | ConvertTo-Json -Depth 4 | Set-Content -Path 'runs/local-sweep.json' -Encoding utf8
Write-Host "saved: runs/local-sweep.json"
