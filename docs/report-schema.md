# Контракт данных веб-отчёта

Один файл `reports/index.html` содержит весь отчёт: разметку, стили, JS и
данные. Данные лежат в `<script id="payload" type="application/json">` и
собираются из `raw.jsonl` двух прогонов. Никаких сетевых запросов страница не
делает.

## `reports/data.json`

```jsonc
{
  "meta": {
    "built_at": "2026-10-24T00:30:00",        // момент сборки
    "sources": { "text": "run-...", "vision": "vision-..." },
    "source_sha256": { "text_raw": "...", "vision_raw": "..." },
    "counts": { "observations": 655, "models": 11, "tasks": 127 }
  },

  "models": [
    { "slug": "baseten/mammoth-1:free", "test": "text", "tier": "free",
      "price_in": 0.0, "price_out": 0.0, "ctx": 16384 }
  ],

  "observations": [
    { "id": "text|baseten/mammoth-1:free|CH-001|q",
      "test": "text",            // text | vision
      "model": "baseten/mammoth-1:free",
      "task": "CH-001",
      "cat": "choice_fact",      // семейство текста или vision_*
      "level": 0,                // 1..5 для зрения, 0 для текста
      "lang": "ru",
      "diff": "easy",            // easy|medium|hard|L1..L5
      "ok": 1,                   // 1 верно, 0 неверно, null если пропуск
      "p": 0.9994,               // вероятность, отданная золотому ответу
      "b": 0.0012,               // Brier этого ответа (null для box)
      "conf": 0.82,              // уверенность выбранного ответа
      "lat": 594,                // мс
      "cost": 0.0                // $ за вызов
    }
  ],

  "catalog": [ { "slug": "...", "modalities": ["text","image"], "price_in": 0.0, "ctx": 16384 } ],

  "verify": [ { "check": "1. unit tests", "ok": true, "detail": "..." } ],

  "claims": [ {
      "id": "C-01",
      "quote": "дословная или близкая к тексту цитата",
      "topic": "биллинг",
      "status": "подтверждено",   // подтверждено|опровергнуто|частично|непроверяемо|несопоставимо
      "evidence": "чем именно проверено",
      "comparability": "exact|family|none"
  } ]
}
```

## Инварианты

1. Каждое `observation` выводится ровно из одной строки `raw.jsonl`
   (`test|model|task|qid` уникален).
2. Пересчёт `ok` по `observations` даёт ту же точность, что `summary.json`,
   с расхождением не более `1e-9`.
3. `p`, `b`, `conf` — либо числа, либо `null`; `NaN` и `Infinity` запрещены
   (иначе `JSON.parse` в браузере молча ломается).
4. `claims[].status` — только из перечисления выше; `evidence` не пустой.
5. `meta.source_sha256` позволяет доказать, из каких файлов собран отчёт.
