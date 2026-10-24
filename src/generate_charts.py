"""
Generate high-resolution dark-mode visual benchmark charts for GitHub README.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ASSETS = Path("assets")
ASSETS.mkdir(exist_ok=True)

# GitHub Dark Theme Palette
BG_COLOR = "#0d1117"
CARD_BG = "#161b22"
GRID_COLOR = "#30363d"
TEXT_COLOR = "#e6edf3"
SUB_COLOR = "#8b949e"
CLOUD_COLOR = "#58a6ff"       # Vibrant Blue
LOCAL_GOOD = "#3fb950"        # Green
LOCAL_MID = "#d29922"         # Amber
LOCAL_BAD = "#f85149"         # Coral Red

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial", "Helvetica"],
    "text.color": TEXT_COLOR,
    "axes.labelcolor": TEXT_COLOR,
    "xtick.color": SUB_COLOR,
    "ytick.color": TEXT_COLOR,
    "figure.facecolor": BG_COLOR,
    "axes.facecolor": CARD_BG,
    "axes.edgecolor": GRID_COLOR,
    "grid.color": GRID_COLOR,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
})


def generate_text_chart():
    # 15 models, accuracy desc
    models = [
        ("mammoth-1", 97.2, "Cloud", "884ms", CLOUD_COLOR),
        ("jev-1.14", 93.5, "Cloud", "575ms", CLOUD_COLOR),
        ("mercury-decide", 90.7, "Cloud", "1438ms", CLOUD_COLOR),
        ("elephant-1", 88.8, "Cloud", "950ms", CLOUD_COLOR),
        ("vllm-d3-flash", 86.9, "Local 8GB", "58ms", LOCAL_GOOD),
        ("pplx-flash", 85.0, "Cloud", "510ms", CLOUD_COLOR),
        ("vllm-d3-mini", 83.2, "Local 8GB", "52ms", LOCAL_GOOD),
        ("Clef-Flash", 81.3, "Local 8GB", "45ms", LOCAL_GOOD),
        ("Kev-9B", 79.4, "Local 8GB", "76ms", LOCAL_MID),
        ("Kev-4B", 76.6, "Local 8GB", "49ms", LOCAL_MID),
        ("vllm-d3-nano", 72.0, "Local 8GB", "38ms", LOCAL_MID),
        ("vllm-d3-lite", 65.4, "Local 8GB", "47ms", LOCAL_MID),
        ("vllm-d3-edge", 53.3, "Local 8GB", "31ms", LOCAL_BAD),
        ("Laya", 51.4, "Local 8GB", "32ms", LOCAL_BAD),
        ("Julia-1", 36.4, "Local 8GB", "31ms", LOCAL_BAD),
    ]

    names = [f"{m[0]} [{m[2]}]" for m in models][::-1]
    accs = [m[1] for m in models][::-1]
    colors = [m[4] for m in models][::-1]
    lats = [m[3] for m in models][::-1]

    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)
    bars = ax.barh(names, accs, color=colors, height=0.68, edgecolor=GRID_COLOR, linewidth=0.8)

    ax.set_xlim(0, 108)
    ax.set_xlabel("Accuracy (%) on 107 Decision Tasks", fontsize=12, fontweight="bold", labelpad=10)
    ax.set_title("Decision Models Benchmark — Text Accuracy (Cloud vs. Local RTX 2060 SUPER 8GB)",
                 fontsize=14, fontweight="bold", pad=16, color=TEXT_COLOR)

    ax.grid(axis="x", linestyle="--", alpha=0.5)
    ax.axvline(80.0, color="#d29922", linestyle=":", linewidth=1.5, alpha=0.8, label="80% Usability Threshold")

    for i, bar in enumerate(bars):
        w = bar.get_width()
        lat = lats[i]
        ax.text(w + 1.2, bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}% ({lat})", va="center", ha="left",
                fontsize=10, fontweight="bold", color=TEXT_COLOR)

    # Custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=CLOUD_COLOR, label="Cloud API (OpenRouter)"),
        Patch(facecolor=LOCAL_GOOD, label="Local RTX 2060 SUPER (High Tier >80%)"),
        Patch(facecolor=LOCAL_MID, label="Local RTX 2060 SUPER (Mid Tier 65–80%)"),
        Patch(facecolor=LOCAL_BAD, label="Local RTX 2060 SUPER (Failing <60%)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", framealpha=0.9,
              facecolor=CARD_BG, edgecolor=GRID_COLOR, fontsize=9.5)

    plt.tight_layout()
    out_path = ASSETS / "benchmark_text_accuracy.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


def generate_vision_chart():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.2), dpi=300, gridspec_kw={"width_ratios": [1.1, 0.9]})

    # 1. Vision Models Ranking
    vis_models = [
        ("span-02", 94.7, "Cloud", CLOUD_COLOR),
        ("pplx-decider", 94.7, "Cloud", CLOUD_COLOR),
        ("clef", 89.5, "Cloud", CLOUD_COLOR),
        ("vllm-d3-flash", 89.5, "Local 8GB", LOCAL_GOOD),
        ("Clef-Flash", 89.5, "Local 8GB", LOCAL_GOOD),
        ("jev-1.14", 85.0, "Cloud", CLOUD_COLOR),
        ("liquid/d1", 84.2, "Cloud", CLOUD_COLOR),
        ("vllm-d3-mini", 84.2, "Local 8GB", LOCAL_GOOD),
        ("clef-flash", 78.9, "Cloud", CLOUD_COLOR),
        ("vllm-d3-nano", 78.9, "Local 8GB", LOCAL_MID),
        ("vllm-d3-lite", 73.7, "Local 8GB", LOCAL_MID),
        ("vllm-d3-edge", 57.9, "Local 8GB", LOCAL_BAD),
    ]

    names = [f"{m[0]} [{m[2]}]" for m in vis_models][::-1]
    accs = [m[1] for m in vis_models][::-1]
    colors = [m[3] for m in vis_models][::-1]

    bars = ax1.barh(names, accs, color=colors, height=0.65, edgecolor=GRID_COLOR, linewidth=0.8)
    ax1.set_xlim(0, 108)
    ax1.set_xlabel("Accuracy (%) on 20 Ladder Tasks", fontsize=11, fontweight="bold", labelpad=8)
    ax1.set_title("Vision Models Ranking (20 Tasks)", fontsize=13, fontweight="bold", pad=12)
    ax1.grid(axis="x", linestyle="--", alpha=0.5)

    for bar in bars:
        w = bar.get_width()
        ax1.text(w + 1.2, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%",
                 va="center", ha="left", fontsize=9.5, fontweight="bold", color=TEXT_COLOR)

    # 2. Ladder Levels: Cloud vs Local Grouped Bar Chart
    levels = ["L1: Objects", "L2: Text/Stamp", "L3: Logic/Receipt", "L4: Tables/Grid", "L5: Code/OCR"]
    cloud_lvl = [95.8, 91.7, 87.5, 83.3, 79.2]
    local_lvl = [91.7, 83.3, 79.2, 75.0, 66.7]

    x = np.arange(len(levels))
    width = 0.35

    b_cloud = ax2.bar(x - width/2, cloud_lvl, width, label="Cloud (6 models avg)", color=CLOUD_COLOR, edgecolor=GRID_COLOR)
    b_local = ax2.bar(x + width/2, local_lvl, width, label="Local RTX 2060S (6 models avg)", color=LOCAL_GOOD, edgecolor=GRID_COLOR)

    ax2.set_ylabel("Accuracy (%)", fontsize=11, fontweight="bold")
    ax2.set_title("Complexity Ladder: Cloud vs. Local (8GB)", fontsize=13, fontweight="bold", pad=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(levels, rotation=22, ha="right", fontsize=9.5)
    ax2.set_ylim(0, 110)
    ax2.grid(axis="y", linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", facecolor=CARD_BG, edgecolor=GRID_COLOR, fontsize=9)

    for bar in b_cloud:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}%", ha="center", fontsize=8.5, color=TEXT_COLOR)
    for bar in b_local:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.5, f"{h:.1f}%", ha="center", fontsize=8.5, color=LOCAL_GOOD)

    plt.suptitle("Decision Models Benchmark — Vision & Multimodal Ladder Evaluation",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR, y=0.98)
    plt.tight_layout()
    out_path = ASSETS / "benchmark_vision_ladder.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


def generate_pareto_chart():
    # Latency vs Accuracy Scatter
    points = [
        # (name, acc, lat, type, color)
        ("mammoth-1", 97.2, 884, "Cloud", CLOUD_COLOR),
        ("jev-1.14", 93.5, 575, "Cloud", CLOUD_COLOR),
        ("mercury-decide", 90.7, 1438, "Cloud", CLOUD_COLOR),
        ("elephant-1", 88.8, 950, "Cloud", CLOUD_COLOR),
        ("pplx-flash", 85.0, 510, "Cloud", CLOUD_COLOR),
        ("vllm-d3-flash", 86.9, 58, "Local", LOCAL_GOOD),
        ("vllm-d3-mini", 83.2, 52, "Local", LOCAL_GOOD),
        ("Clef-Flash", 81.3, 45, "Local", LOCAL_GOOD),
        ("Kev-9B", 79.4, 76, "Local", LOCAL_MID),
        ("Kev-4B", 76.6, 49, "Local", LOCAL_MID),
        ("vllm-d3-nano", 72.0, 38, "Local", LOCAL_MID),
        ("vllm-d3-lite", 65.4, 47, "Local", LOCAL_MID),
        ("vllm-d3-edge", 53.3, 31, "Local", LOCAL_BAD),
        ("Laya", 51.4, 32, "Local", LOCAL_BAD),
        ("Julia-1", 36.4, 31, "Local", LOCAL_BAD),
    ]

    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=300)

    for name, acc, lat, env, col in points:
        size = 140 if env == "Local" and acc > 80 else 100
        marker = "o" if env == "Cloud" else "s"
        ax.scatter(lat, acc, color=col, s=size, edgecolors="#ffffff", linewidth=1.2, alpha=0.9, zorder=5)

        # Label offsets
        dx, dy = 15, 0.8
        if name == "vllm-d3-flash":
            dx, dy = 8, 1.4
        elif name == "Clef-Flash":
            dx, dy = 6, -2.0
        elif name == "vllm-d3-mini":
            dx, dy = -90, -1.8
        elif name == "pplx-flash":
            dx, dy = -85, 1.5
        elif name == "mammoth-1":
            dx, dy = -90, 1.2
        elif name == "Julia-1":
            dx, dy = 8, -0.5
        elif name == "Laya":
            dx, dy = 8, -1.8
        elif name == "vllm-d3-edge":
            dx, dy = -85, 1.2

        ax.annotate(f"{name}\n({acc}%, {lat}ms)", (lat, acc),
                    xytext=(lat + dx, acc + dy),
                    fontsize=8.5, color=TEXT_COLOR,
                    arrowprops=dict(arrowstyle="-", color=SUB_COLOR, lw=0.6, alpha=0.6))

    ax.set_xscale("log")
    ax.set_xlabel("Latency p50 in ms (Log Scale, lower is faster)", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_ylabel("Accuracy (%) on 107 Tasks (higher is better)", fontsize=11, fontweight="bold", labelpad=8)
    ax.set_title("Pareto Efficiency: Latency vs. Accuracy (Sweet Spot: Top-Left)",
                 fontsize=13, fontweight="bold", pad=14)

    # Highlight Sweet Spot Box
    ax.axvspan(30, 100, ymin=0.68, ymax=0.95, color=LOCAL_GOOD, alpha=0.08, zorder=1)
    ax.text(35, 91, "[*] Sweet Spot:\nHigh Acc (>80%) &\nSub-60ms Local Latency",
            fontsize=9.5, fontweight="bold", color=LOCAL_GOOD,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=CARD_BG, edgecolor=LOCAL_GOOD, alpha=0.85))

    ax.grid(True, which="both", linestyle="--", alpha=0.4)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=CLOUD_COLOR, markersize=9, label="Cloud API"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=LOCAL_GOOD, markersize=9, label="Local 8GB (>80% Acc)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=LOCAL_MID, markersize=9, label="Local 8GB (65–80%)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=LOCAL_BAD, markersize=9, label="Local 8GB (<60% Acc)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", facecolor=CARD_BG, edgecolor=GRID_COLOR, fontsize=9)

    plt.tight_layout()
    out_path = ASSETS / "benchmark_pareto_latency.png"
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Generated {out_path}")


if __name__ == "__main__":
    generate_text_chart()
    generate_vision_chart()
    generate_pareto_chart()
