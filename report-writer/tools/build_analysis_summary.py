"""build_analysis_summary.py — genera analysis_summary.md da numbers.json.

Tool deterministico (no LLM). Produce il digest per gate 1 (giudice off-page):
  - headline_number + top insight fattuali (pattern da report_keys)
  - 1 riga per ogni top-level key della struttura computazionale
  - [DA CALCOLARE] espliciti

Uso:
  python3 tools/build_analysis_summary.py --numbers <TOPIC>/numbers.json [--out <TOPIC>/analysis_summary.md]

Exit 0 sempre (è un generatore, non un gate).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def fmt(v) -> str:
    """Format a numeric value for display."""
    if v is None:
        return "N/A"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return str(v)
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def extract_insights(report_keys: dict) -> list[str]:
    """Derive factual pattern insights from report_keys (no LLM)."""
    insights = []
    rk = report_keys

    # Insight 1: savings A+++ vs G per dwelling (any dwelling)
    for did in ["villa", "apt", "mono"]:
        pct_key = f"{did}_appp_vs_g_savings_pct"
        eur_key = f"{did}_appp_vs_g_savings_eur"
        if pct_key in rk and eur_key in rk:
            dname = {"villa": "Villa", "apt": "Appartamento", "mono": "Monolocale"}.get(did, did)
            insights.append(
                f"{dname} A+++ risparmia **{fmt(rk[pct_key])}%** rispetto a classe G "
                f"({fmt(rk[eur_key])} €/stagione)"
            )

    # Insight 2: payback (fastest)
    paybacks = {k: v for k, v in rk.items() if "payback" in k and v is not None}
    if paybacks:
        fastest_k = min(paybacks, key=lambda k: paybacks[k])
        did = fastest_k.split("_")[0]
        dname = {"villa": "Villa", "apt": "Appartamento", "mono": "Monolocale"}.get(did, did)
        insights.append(
            f"Payback upgrade più rapido: **{dname}** con {fmt(paybacks[fastest_k])} anni"
        )

    # Insight 3: range min/max cost
    season_eurs = {k: v for k, v in rk.items() if k.endswith("_season_eur") and v is not None}
    if len(season_eurs) >= 2:
        min_k = min(season_eurs, key=lambda k: season_eurs[k])
        max_k = max(season_eurs, key=lambda k: season_eurs[k])
        ratio = round(season_eurs[max_k] / season_eurs[min_k], 1)
        insights.append(
            f"Range costo stagionale: da **{fmt(season_eurs[min_k])} €** ({min_k}) "
            f"a **{fmt(season_eurs[max_k])} €** ({max_k}) — rapporto {ratio}×"
        )

    # Insight 4: paradox / outlier (a5_ratio if present)
    if "a5_ratio_max_vs_min" in rk:
        insights.append(
            f"Paradosso dimensionale: la combo più costosa consuma "
            f"**{fmt(rk['a5_ratio_max_vs_min'])}× di più** della meno costosa"
        )

    return insights


def build_summary(numbers_path: Path) -> str:
    data = json.loads(numbers_path.read_text(encoding="utf-8"))
    topic = data.get("topic", numbers_path.parent.name)
    rk = data.get("report_keys", {})

    lines = [
        f"# Analysis Summary — {topic}",
        "",
        "> Generato deterministicamente da `build_analysis_summary.py`. Non modificare a mano.",
        "",
    ]

    # Headline number
    hl = rk.get("headline_number")
    if hl is not None:
        lines += [f"## Headline number", "", f"**{fmt(hl)}** (`headline_number`)", ""]
    else:
        lines += ["## Headline number", "", "⚠️ `headline_number` assente in report_keys", ""]

    # Insight fattuali
    insights = extract_insights(rk)
    if insights:
        lines += ["## Insight fattuali (da report_keys)", ""]
        for ins in insights:
            lines.append(f"- {ins}")
        lines.append("")

    # Per-key table (report_keys flat)
    if rk:
        lines += ["## report_keys (tutti i valori)", "", "| Chiave | Valore |", "|---|---|"]
        for k, v in sorted(rk.items()):
            lines.append(f"| `{k}` | {fmt(v)} |")
        lines.append("")

    # Struttura computazionale (top-level keys, non report_keys)
    structural = {
        k: v for k, v in data.items()
        if k not in ("report_keys", "topic", "model") and not k.startswith("_")
    }
    if structural:
        lines += ["## Struttura computazionale", ""]
        for k, v in structural.items():
            if isinstance(v, list):
                lines.append(f"- **{k}**: lista di {len(v)} elementi")
            elif isinstance(v, dict):
                lines.append(f"- **{k}**: dict con {len(v)} chiavi ({', '.join(list(v.keys())[:4])}{'...' if len(v) > 4 else ''})")
            else:
                lines.append(f"- **{k}**: {fmt(v)}")
        lines.append("")

    # DA CALCOLARE (se presenti come stringhe con marker)
    da_calc = []
    def _scan(obj, path=""):
        if isinstance(obj, str) and "[DA CALCOLARE" in obj:
            da_calc.append(f"`{path}`: {obj}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _scan(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _scan(item, f"{path}[{i}]")
    _scan(data)

    if da_calc:
        lines += ["## ⚠️ [DA CALCOLARE]", ""]
        for item in da_calc:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate analysis_summary.md from numbers.json")
    parser.add_argument("--numbers", required=True, help="Path a numbers.json")
    parser.add_argument("--out", help="Output path (default: <TOPIC>/analysis_summary.md)")
    args = parser.parse_args()

    numbers_path = Path(args.numbers)
    if not numbers_path.exists():
        print(f"STOP — numbers.json non trovato: {numbers_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out) if args.out else numbers_path.parent / "analysis_summary.md"

    summary = build_summary(numbers_path)
    out_path.write_text(summary, encoding="utf-8")
    print(f"OK — analysis_summary.md scritto: {out_path} ({len(summary.splitlines())} righe)")


if __name__ == "__main__":
    main()
