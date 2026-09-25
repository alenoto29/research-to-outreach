"""Neutral matplotlib charts for reports.

Renders PNG from a chart spec built ONLY on numbers already computed by compute.py
(stage 3). charts.py never invents data — it visualizes what it is given. Optional
CSV/JSON sidecar for later Flourish/web reuse.

Chart spec:
  {"type": "line"|"bar"|"scatter", "title": str, "xlabel": str, "ylabel": str,
   "series": [{"label": str, "x": [...], "y": [...]}], "source": str}

Requires matplotlib (requirements.txt). Uses the Agg backend (headless PNG).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


def render_chart(spec, out_path, sidecar=False):
    """Render `spec` to PNG at out_path using a neutral style. Returns the PNG Path.
    If sidecar=True, also writes <stem>.csv + <stem>.json next to it."""
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.2,
    })
    ctype = spec.get("type", "line")
    series = spec["series"]
    fig, ax = plt.subplots(figsize=(8, 4.5))

    if ctype == "line":
        for s in series:
            ax.plot(s["x"], s["y"], label=s.get("label"), linewidth=2.2, marker="")
    elif ctype == "bar":
        # grouped bars by series; categories = first series x
        cats = [str(v) for v in series[0]["x"]]
        n, width = len(series), 0.8 / max(1, len(series))
        for i, s in enumerate(series):
            offs = [j + (i - (n - 1) / 2) * width for j in range(len(cats))]
            ax.bar(offs, s["y"], width=width, label=s.get("label"))
        ax.set_xticks(range(len(cats)))
        ax.set_xticklabels(cats, rotation=0)
    elif ctype == "scatter":
        for s in series:
            ax.scatter(s["x"], s["y"], label=s.get("label"), s=28, alpha=0.8)
    else:
        plt.close(fig)
        raise ValueError(f"tipo grafico non supportato: {ctype}")

    if spec.get("title"):
        ax.set_title(spec["title"], loc="left", pad=12)
    if spec.get("xlabel"):
        ax.set_xlabel(spec["xlabel"])
    if spec.get("ylabel"):
        ax.set_ylabel(spec["ylabel"])
    if len(series) > 1 or series[0].get("label"):
        ax.legend(loc="best")
    if spec.get("source"):
        fig.text(0.99, 0.01, f"Fonte: {spec['source']}", ha="right", va="bottom",
                  fontsize=8, color="#344054", alpha=0.7)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    if sidecar:
        _write_sidecar(spec, out_path)
    return out_path


def _write_sidecar(spec, png_path):
    """Emit chart data as CSV + JSON for Flourish/web reuse."""
    stem = png_path.with_suffix("")
    stem.with_suffix(".json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    # long-format CSV: series,label,x,y
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "x", "y"])
        for s in spec["series"]:
            for x, y in zip(s["x"], s["y"]):
                w.writerow([s.get("label", ""), x, y])
