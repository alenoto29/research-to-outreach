#!/usr/bin/env python3
"""04_qa_gate.py — gate deterministico finale. exit != 0 = batch bloccato.

Controlli (solo righe scritte dall'engine = match per email/persona in scored.json):
  1. Colonne A-K (1..11): header riga 2 colonne A..J non spostate (semantica preservata).
  2. Ogni riga engine ha Example Article (D) non vuoto.
  3. Ogni riga engine ha target_score >= target_floor (da plan).
  4. Email tier B/C -> colonna R deve contenere confirmed=false.
  5. Anti-hallucination: l'email scritta (K) deve esistere tra le evidenze raccolte
     (email_candidates) del candidato in scored.json.

Usage: python3 04_qa_gate.py --topic-dir example-topic
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]
PR_ROOT = SKILL.parents[1]

EXPECTED_AJ = [
    "Batch Date", "Status", "Tracker follow-up", "Example Article",
    "Newspaper Name", "Domain Newspaper", "DR", "Name", "Surname", "Note",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-dir", required=True)
    args = ap.parse_args()
    topic_root = PR_ROOT / args.topic_dir
    plan_files = list((topic_root / "PLAN").glob("*_plan.json"))
    plan = json.loads(plan_files[0].read_text(encoding="utf-8")) if plan_files else {}
    csv_subdir = plan.get("csv_input_subdir", "INPUT")
    csv_path = next((topic_root / csv_subdir).glob("*.csv"))
    scored = json.loads((topic_root / ".tmp" / "scored.json").read_text(encoding="utf-8"))
    floor = plan.get("thresholds", {}).get("target_floor", 40)
    conf_col = plan.get("confidence_col_index", 17)

    # mappa email_lower -> (score, set evidenze emails)
    by_email, by_ns = {}, {}
    for c in scored:
        ev = {e.get("email", "").strip().lower() for e in c.get("email_candidates", [])}
        rec = {"score": c.get("target_score", 0), "ev": ev}
        for e in ev:
            by_email[e] = rec
        by_ns[f"{c.get('name','').lower()}|{c.get('surname','').lower()}"] = rec

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    errors = []

    # check 1: header A..J
    hdr = rows[1] if len(rows) > 1 else []
    for i, exp in enumerate(EXPECTED_AJ):
        got = hdr[i].strip() if i < len(hdr) else ""
        if got != exp:
            errors.append(f"header col {i+1}: atteso '{exp}', trovato '{got}' (colonne A-K spostate?)")

    # check righe engine
    engine_rows = 0
    for n, r in enumerate(rows[2:], start=3):
        r = r + [""] * (conf_col + 1 - len(r))
        email = r[10].strip().lower()
        ns = f"{r[7].strip().lower()}|{r[8].strip().lower()}"
        rec = by_email.get(email) or by_ns.get(ns)
        if not rec:
            continue  # riga non dell'engine (collega) -> skip
        engine_rows += 1
        tag = f"riga {n} ({r[7]} {r[8]})"
        if not r[3].strip():
            errors.append(f"{tag}: Example Article (D) vuoto")
        if rec["score"] < floor:
            errors.append(f"{tag}: target_score {rec['score']} < floor {floor}")
        rcell = r[conf_col].lower()
        # tier dal label in confidence col
        if "a-confirmed" not in rcell:  # tier B o C
            if "confirmed=false" not in rcell:
                errors.append(f"{tag}: tier B/C senza confirmed=false in col R ('{r[17]}')")
        if email and rec["ev"] and email not in rec["ev"]:
            errors.append(f"{tag}: email '{r[10]}' NON nelle evidenze (hallucination)")

    if errors:
        print(f"QA FAIL ({len(errors)} errori, {engine_rows} righe engine):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"QA PASS  {engine_rows} righe engine validate.")


if __name__ == "__main__":
    main()
