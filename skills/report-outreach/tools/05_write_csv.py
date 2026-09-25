#!/usr/bin/env python3
"""05_write_csv.py — CSV finale + why_picked da template deterministico (D12).

Input : .tmp/resolved.json
Output: OUTPUT/outreach_<report_slug>.csv
Colonne: name, domain, dr, email, email_tier, confirmed, source, score,
         weights_version, why_picked
why_picked = template + breakdown reale dello score. MAI prosa LLM:
stesso input -> stessa motivazione, verificabile contro il breakdown.
"""
import argparse
import csv
import json
import re
from pathlib import Path

from lib_common import load_config, load_plan, update_run_log


def build_why_picked(c: dict, weights: dict) -> str:
    b = c.get("score_breakdown", {})
    parts = []

    n_ot, n_head = b.get("n_on_topic", 0), b.get("n_headline", 0)
    topic_bit = f"{n_ot} articoli on-topic"
    if n_head:
        topic_bit += f" ({n_head} in headline)"
    parts.append(f"{topic_bit} [{b.get('topic_correlation', 0)}/{weights['topic_correlation']}]")

    auth_bits = []
    if c.get("author_page"):
        auth_bits.append("author page")
    if c.get("job_title"):
        auth_bits.append(c["job_title"])
    parts.append(f"autorevolezza: {', '.join(auth_bits) or 'segnali deboli'} "
                 f"[{b.get('authority', 0)}/{weights['authority']}]")

    if b.get("last_on_topic"):
        parts.append(f"ultimo articolo on-topic {b['last_on_topic']} "
                     f"[{b.get('recency', 0)}/{weights['recency']}]")
    else:
        parts.append(f"nessun articolo on-topic datato [0/{weights['recency']}]")

    kind = b.get("history_kind")
    if kind == "responder":
        hist = "ha già risposto a un nostro outreach"
    elif kind == "never_contacted":
        hist = "nel DB, mai contattato"
    elif kind == "contacted_no_reply":
        hist = f"contattato {b.get('contact_count', '?')}x senza risposta"
    else:
        hist = "contatto nuovo (storia neutra)"
    parts.append(f"{hist} [{b.get('history', 0)}/{weights['history']}]")

    if c.get("dr") is not None:
        parts.append(f"DR {c['dr']} (tie-breaker)")
    if c.get("replaced"):
        parts.append(f"subentrato a {c['replaced']}")
    return "; ".join(parts)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "report").lower()).strip("-")


def write_csv(rows: list, weights: dict, weights_version: str, out_path: Path) -> None:
    cols = ["name", "domain", "dr", "email", "email_tier", "confirmed",
            "source", "score", "weights_version", "why_picked"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for c in rows:
            w.writerow({
                "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "domain": c.get("domain") or "",
                "dr": c.get("dr") if c.get("dr") is not None else "",
                "email": c.get("email") or "",
                "email_tier": c.get("email_tier") or "",
                "confirmed": str(bool(c.get("email_confirmed"))).lower(),
                "source": c.get("source") or "",
                "score": c.get("score"),
                "weights_version": weights_version,
                "why_picked": build_why_picked(c, weights),
            })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    cfg = load_config()
    plan = load_plan(args.run_dir)
    tmp = Path(args.run_dir) / ".tmp"
    data = json.loads((tmp / "resolved.json").read_text(encoding="utf-8"))
    scored = json.loads((tmp / "scored.json").read_text(encoding="utf-8"))
    weights = scored["weights"]

    out_path = Path(args.run_dir) / "OUTPUT" / f"outreach_{slugify(plan.get('report_name') or plan.get('topic'))}.csv"
    write_csv(data["rows"], weights, data["weights_version"], out_path)

    update_run_log(args.run_dir, "csv", {
        "path": str(out_path),
        "rows": len(data["rows"]),
        "weights_version": data["weights_version"],
        "topic": plan.get("topic"), "angle": plan.get("angle"),
    })
    print(f"OK {out_path} rows={len(data['rows'])}")


if __name__ == "__main__":
    main()
