#!/usr/bin/env python3
"""07_push_dashboard.py — writeback contatti discovery nel DB dashboard.

Dopo QA PASS: le righe source=discovery del CSV confluiscono nel DB via
POST /api/journalists/enrich (dedup email O nome+cognome, SKIP se presente,
idempotente). enrichment_source=report-outreach. Al run successivo questi
contatti sono candidati dashboard con storia (loop D9).

Uso:
    ACCESS_TOKEN=<tok> python3 tools/07_push_dashboard.py --run-dir runs/<report> [--dry-run]
"""
import argparse
import csv
import json
import os
from pathlib import Path

from lib_common import api_send, load_plan, update_run_log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--api-base", required=True, help="Authorized API base URL; no service is assumed")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plan = load_plan(args.run_dir)
    run = Path(args.run_dir)
    csvs = sorted((run / "OUTPUT").glob("*.csv"))
    if not csvs:
        raise SystemExit("CSV mancante in OUTPUT/ (lanciare 05_write_csv prima)")
    resolved = json.loads((run / ".tmp" / "resolved.json").read_text(encoding="utf-8"))["rows"]
    by_email = {(c.get("email") or "").lower(): c for c in resolved}

    candidates = []
    with csvs[0].open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("source") != "discovery" or not r.get("email"):
                continue
            c = by_email.get(r["email"].lower(), {})
            candidates.append({
                "email": r["email"],
                "first_name": c.get("first_name") or r["name"].split(" ")[0],
                "last_name": c.get("last_name") or " ".join(r["name"].split(" ")[1:]),
                "market": plan.get("market", "IT"),
                "publisher": c.get("publisher") or "",
                "publisher_domain": r.get("domain") or "",
                "author_page": c.get("author_page") or "",
                "linkedin": c.get("linkedin") or "",
                "notes": r.get("why_picked") or "",
                "topics": plan.get("topic_core", [])[:3],
                "main_topic": plan.get("topic", ""),
            })

    print(f"  {len(candidates)} contatti discovery da pushare")
    if args.dry_run:
        print(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2))
        print("DRY-RUN: nessuna POST.")
        return

    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise SystemExit("ACCESS_TOKEN env mancante. Usa --dry-run per testare.")
    result = api_send(args.api_base, "/api/journalists/enrich", token, {
        "candidates": candidates, "enrichment_source": "report-outreach"})
    update_run_log(args.run_dir, "push_dashboard", {
        "created": result.get("created"), "skipped": result.get("skipped"),
        "errors": result.get("errors", [])[:10]})
    print(f"OK created={result.get('created')} skipped={result.get('skipped')} "
          f"errors={len(result.get('errors', []))}")


if __name__ == "__main__":
    main()
