#!/usr/bin/env python3
"""00_fetch_dashboard.py — shortlist candidati dashboard per il report.

Scarica i giornalisti dal DB dashboard (GET /api/journalists), pre-filtra per match
con topic_core+topic_expansion del plan (campi DB usati SOLO come pre-filtro, D2:
le evidenze articoli le raccoglie Sonnet dopo, per tutti) e scrive la shortlist.

Check loop chiuso (D9): se esiste un run precedente con CSV in OUTPUT e run_log senza
sent_marked, verifica su dati freschi che last_contacted sia stato aggiornato;
altrimenti warning `unrecorded_sends` nel run log.

Uso:
    ACCESS_TOKEN=<tok> python3 tools/00_fetch_dashboard.py --run-dir runs/<report> \
        --api-base <authorized-instance> [--runs-root runs/]
"""
import argparse
import json
import os
from pathlib import Path

from lib_common import api_get, load_config, load_plan, parse_date, update_run_log


def tag_match_score(j: dict, terms: list) -> int:
    """Conta i term hit nei campi tag del DB. Pre-filtro, non score finale."""
    hay = " ".join([
        str(j.get("expertise_tags") or ""),
        str(j.get("main_topic") or ""),
        str(j.get("notes") or ""),
        str(j.get("job_title") or ""),
    ]).lower()
    return sum(1 for t in terms if t.lower() in hay)


def build_shortlist(journalists: list, plan: dict, cfg: dict) -> tuple:
    terms = list(plan.get("topic_core", [])) + list(plan.get("topic_expansion", []))
    scored = []
    for j in journalists:
        if j.get("deleted_at"):
            continue
        hits = tag_match_score(j, terms)
        if hits > 0:
            scored.append((hits, j))
    scored.sort(key=lambda x: (-x[0], (x[1].get("last_name") or "").lower()))
    cap = cfg["shortlist"]["dashboard_max"]
    shortlist = [j for _, j in scored[:cap]]
    thin = len(shortlist) < cfg["shortlist"]["dashboard_min"]
    return shortlist, thin


def to_candidate(j: dict) -> dict:
    return {
        "source": "dashboard",
        "journalist_id": j.get("id"),
        "first_name": j.get("first_name") or "",
        "last_name": j.get("last_name") or "",
        "publisher": j.get("publisher_name") or "",
        "domain": (j.get("publisher_domain") or "").lower(),
        "dr": j.get("dr"),
        "job_title": j.get("job_title") or "",
        "author_page": j.get("author_page") or "",
        "email": j.get("email") or "",
        "email_tier": "db",
        "email_confirmed": True,
        "linkedin": j.get("linkedin") or "",
        "contact_count": j.get("contact_count") or 0,
        "last_contacted": j.get("last_contacted"),
        "response_status": j.get("response_status"),
        "articles_count_6m": j.get("articles_count_6m"),
        "years_exp": j.get("years_exp"),
        "expertise_tags": j.get("expertise_tags"),
        "articles": [],
    }


def check_unrecorded_sends(runs_root: Path, current_run: Path, journalists_by_email: dict) -> list:
    """Run precedenti con CSV consegnato ma mai marcato sent → email senza last_contacted aggiornato."""
    import csv as csvmod
    warnings = []
    if not runs_root.is_dir():
        return warnings
    for run in sorted(runs_root.iterdir()):
        if not run.is_dir() or run.resolve() == current_run.resolve():
            continue
        log_p = run / "OUTPUT" / "run_log.json"
        log = json.loads(log_p.read_text(encoding="utf-8")) if log_p.exists() else {}
        if log.get("sent_marked"):
            continue
        for csv_p in (run / "OUTPUT").glob("*.csv"):
            with csv_p.open(encoding="utf-8") as f:
                for row in csvmod.DictReader(f):
                    email = (row.get("email") or "").strip().lower()
                    j = journalists_by_email.get(email)
                    if j is not None and not j.get("last_contacted"):
                        warnings.append({"run": run.name, "email": email})
    return warnings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--api-base", required=True, help="Authorized API base URL; no service is assumed")
    ap.add_argument("--runs-root", default=None, help="default: parent del run-dir")
    args = ap.parse_args()

    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise SystemExit("ACCESS_TOKEN env mancante")

    cfg = load_config()
    plan = load_plan(args.run_dir)
    market = plan.get("market", "IT")

    journalists, offset, limit = [], 0, 1000
    while True:
        batch = api_get(args.api_base, "/api/journalists", token,
                        {"market": market, "limit": limit, "offset": offset})
        items = batch if isinstance(batch, list) else batch.get("items", batch.get("journalists", []))
        journalists.extend(items)
        if len(items) < limit:
            break
        offset += limit

    shortlist, thin = build_shortlist(journalists, plan, cfg)
    candidates = [to_candidate(j) for j in shortlist]

    run = Path(args.run_dir)
    tmp = run / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    out = {"market": market, "total_in_db": len(journalists), "shortlist": candidates}
    (tmp / "dashboard_shortlist.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    by_email = {(j.get("email") or "").lower(): j for j in journalists}
    runs_root = Path(args.runs_root) if args.runs_root else run.parent
    unrecorded = check_unrecorded_sends(runs_root, run, by_email)

    update_run_log(args.run_dir, "fetch_dashboard", {
        "total_in_db": len(journalists),
        "shortlist_size": len(candidates),
        "thin_shortlist": thin,
        "unrecorded_sends": unrecorded,
    })
    print(f"OK shortlist={len(candidates)} (db={len(journalists)}) thin={thin}")
    if unrecorded:
        print(f"WARNING unrecorded_sends: {len(unrecorded)} righe — run precedenti mai marcati sent (08_mark_sent.py)")


if __name__ == "__main__":
    main()
