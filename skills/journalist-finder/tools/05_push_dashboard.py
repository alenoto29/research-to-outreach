#!/usr/bin/env python3
"""05_push_dashboard.py — optional, explicitly configured API writeback.

After a completed human QA gate, this optional adapter submits candidates to an
operator-selected compatible API. It is not part of offline processing or tests.

Input : <TOPIC>/INPUT/*.csv
Auth  : explicit --api-base + ACCESS_TOKEN bearer token
Uso   :
    python3 tools/05_push_dashboard.py --topic-dir example-topic --dry-run
    ACCESS_TOKEN=<operator-token> python3 tools/05_push_dashboard.py --topic-dir example-topic \
        --api-base <authorized-instance>
"""
import argparse
import csv
import json
import os
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]
PR_ROOT = SKILL.parents[1]

# indici colonna CSV (vedi 03_write_csv.py)
C_ARTICLE, C_PUB, C_DOM, C_NAME, C_SURNAME, C_NOTE, C_EMAIL, C_TOPICS, C_LINKEDIN = 3, 4, 5, 7, 8, 9, 10, 11, 12


def candidates_from_csv(csv_path: Path, market: str) -> list[dict]:
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    out = []
    for r in rows[2:]:  # righe dati dalla 3 in poi (riga 1-2 = header)
        if len(r) <= C_EMAIL:
            continue
        email = (r[C_EMAIL] or "").strip()
        if not email or "@" not in email:
            continue  # nessuna email -> escluso (mai inventare)
        topics = [t.strip() for t in (r[C_TOPICS] if len(r) > C_TOPICS else "").split(",") if t.strip()]
        out.append({
            "email": email,
            "first_name": (r[C_NAME] or "").strip(),
            "last_name": (r[C_SURNAME] or "").strip(),
            "market": market,
            "publisher": (r[C_PUB] or "").strip(),
            "author_page": (r[C_ARTICLE] or "").strip(),
            "linkedin": (r[C_LINKEDIN] if len(r) > C_LINKEDIN else "").strip(),
            "notes": (r[C_NOTE] or "").strip(),
            "topics": topics,
            "main_topic": topics[0] if topics else "",
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-dir", required=True)
    ap.add_argument("--api-base", help="Authorized API base URL; no service is assumed")
    ap.add_argument("--market", default="IT")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    topic_root = PR_ROOT / args.topic_dir
    csv_files = list((topic_root / "INPUT").glob("*.csv"))
    if not csv_files:
        raise SystemExit(f"CSV mancante in {topic_root / 'INPUT'}")
    candidates = candidates_from_csv(csv_files[0], args.market)
    print(f"  {len(candidates)} candidati con email da {csv_files[0].name}")

    if args.dry_run:
        print(json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2))
        print("DRY-RUN: nessuna POST.")
        return

    if not args.api_base:
        raise SystemExit("--api-base must name an explicitly authorized instance")

    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise SystemExit("ACCESS_TOKEN env mancante (necessario per la POST). Usa --dry-run per testare.")

    body = json.dumps({"candidates": candidates}).encode("utf-8")
    url = f"{args.api_base.rstrip('/')}/api/journalists/enrich"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print(f"OK  created={result.get('created')} skipped={result.get('skipped')} errors={len(result.get('errors', []))}")
    if result.get("errors"):
        print(json.dumps(result["errors"][:10], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
