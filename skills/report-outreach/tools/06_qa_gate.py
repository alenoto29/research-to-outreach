#!/usr/bin/env python3
"""06_qa_gate.py — gate deterministico sul CSV finale. Exit != 0 = consegna bloccata.

FAIL (exit 1):
  - duplicati email o persona (nome+dominio)
  - row count fuori [min_rows, max_rows]
  - tier C oltre il cap
  - confirmed incoerente col tier (true solo A-*)
  - email pattern/hunter senza verifier status nei dati di risoluzione
  - riga dashboard che viola il cooldown (run_date dal plan)
  - why_picked vuoto
WARN (exit 0, loggato): quota deviation, unrecorded_sends dal fetch.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from lib_common import (load_config, load_plan, normalize_domain, normalize_name, parse_date,
                        read_run_log, update_run_log)


def _csv_dr(v):
    s = str(v).strip()
    if s in ("", "None"):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def check_csv(rows: list, resolved_rows: list, shortlist: list, cfg: dict, run_date,
              report_type: str = None) -> list:
    fails = []
    sel = cfg["selection"]

    if not (sel["min_rows"] <= len(rows) <= sel["max_rows"]):
        fails.append(f"row count {len(rows)} fuori [{sel['min_rows']},{sel['max_rows']}]")

    # blacklist: nessun giornale blacklistato puo arrivare al CSV (backstop su 01)
    bl = {normalize_domain(d) for d in cfg.get("blacklist_domains", [])}
    for r in rows:
        if normalize_domain(r.get("domain")) in bl:
            fails.append(f"{r.get('domain')}: giornale in blacklist")

    # cap per giornale: max N righe dallo stesso dominio (backstop su 02/03)
    max_journal = sel.get("max_per_journal")
    if max_journal is not None:
        for dom, k in Counter(normalize_domain(r.get("domain")) for r in rows if r.get("domain")).items():
            if k > max_journal:
                fails.append(f"{dom}: {k} righe dallo stesso giornale > cap {max_journal}")

    # gate DR per tipo report (backstop su 01b): DR noto fuori range -> FAIL. DR vuoto esente.
    if report_type in ("TOP", "MID"):
        g = cfg["dr_gate"]
        for r in rows:
            dr = _csv_dr(r.get("dr"))
            if dr is None:
                continue
            if report_type == "TOP" and dr < g["top_min"]:
                fails.append(f"{r.get('domain')}: DR {dr} < {g['top_min']} (gate TOP)")
            if report_type == "MID" and dr > g["mid_max"]:
                fails.append(f"{r.get('domain')}: DR {dr} > {g['mid_max']} (gate MID)")

    emails = [r["email"].lower() for r in rows if r.get("email")]
    if len(emails) != len(set(emails)):
        dupes = sorted({e for e in emails if emails.count(e) > 1})
        fails.append(f"email duplicate: {dupes}")

    persons = [f"{r['name'].lower().strip()}|{r.get('domain', '').lower()}" for r in rows]
    if len(persons) != len(set(persons)):
        fails.append("persone duplicate (nome+dominio)")

    n_c = sum(1 for r in rows if (r.get("email_tier") or "").startswith("C"))
    if n_c > cfg["tiers"]["tier_c_cap"]:
        fails.append(f"tier C = {n_c} > cap {cfg['tiers']['tier_c_cap']}")

    # forma email: local-part valida e nessun token pattern non sostituito
    bad_tokens = ("finitial", "surname", "{", "}")
    for r in rows:
        em = (r.get("email") or "").lower()
        if not em:
            continue
        local = em.split("@")[0]
        if "@" not in em or not all(ch.isalnum() or ch in "._%+-" for ch in local) \
           or any(t in local for t in bad_tokens) \
           or re.fullmatch(r"first[._-]?last", local):
            fails.append(f"{em}: forma email invalida (pattern non risolto?)")

    for r in rows:
        tier = r.get("email_tier") or ""
        confirmed = (r.get("confirmed") or "").lower() == "true"
        if confirmed and not (tier.startswith("A") or tier == "db"):
            fails.append(f"{r['email']}: confirmed=true con tier {tier}")
        if tier.startswith("A") and not confirmed:
            fails.append(f"{r['email']}: tier {tier} ma confirmed=false")
        if not (r.get("why_picked") or "").strip():
            fails.append(f"{r.get('email')}: why_picked vuoto")

    # verifier obbligatorio su pattern/hunter (dai dati di risoluzione)
    by_email = {(c.get("email") or "").lower(): c for c in resolved_rows}
    for r in rows:
        c = by_email.get((r.get("email") or "").lower(), {})
        method = c.get("email_method")
        if method in ("pattern", "hunter-finder", "hunter-direct") and not c.get("email_verifier_status"):
            fails.append(f"{r['email']}: email {method} senza verifier status")

    # cooldown sulle righe dashboard
    by_email_sl = {(c.get("email") or "").lower(): c for c in shortlist}
    cd = cfg["cooldown_default_days"]
    for r in rows:
        if r.get("source") != "dashboard":
            continue
        c = by_email_sl.get((r.get("email") or "").lower(), {})
        last = parse_date(c.get("last_contacted"))
        if last and (run_date - last).days < cd:
            fails.append(f"{r['email']}: viola cooldown ({(run_date - last).days}gg < {cd})")

    return fails


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    cfg = load_config()
    plan = load_plan(args.run_dir)
    run_date = parse_date(plan.get("run_date"))
    run = Path(args.run_dir)
    csvs = sorted((run / "OUTPUT").glob("*.csv"))
    if not csvs:
        raise SystemExit("CSV mancante in OUTPUT/")
    with csvs[0].open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    resolved = json.loads((run / ".tmp" / "resolved.json").read_text(encoding="utf-8"))["rows"]
    sl_path = run / ".tmp" / "dashboard_shortlist.json"
    shortlist = json.loads(sl_path.read_text(encoding="utf-8"))["shortlist"] if sl_path.exists() else []

    report_type = (plan.get("report_type") or "").strip().upper() or None
    fails = check_csv(rows, resolved, shortlist, cfg, run_date, report_type)
    log = read_run_log(args.run_dir)
    warns = []
    if log.get("selection", {}).get("quota_deviation"):
        warns.append("quota 50/50 sbilanciata (vedi selection.counts)")
    if log.get("fetch_dashboard", {}).get("unrecorded_sends"):
        warns.append("unrecorded_sends dal run precedente")

    update_run_log(args.run_dir, "qa", {"fails": fails, "warns": warns,
                                        "result": "FAIL" if fails else "PASS"})
    for w in warns:
        print(f"WARN {w}")
    if fails:
        for f_ in fails:
            print(f"FAIL {f_}")
        sys.exit(1)
    print(f"QA PASS ({len(rows)} righe)")


if __name__ == "__main__":
    main()
