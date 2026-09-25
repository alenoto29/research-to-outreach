#!/usr/bin/env python3
"""03_write_csv.py — scrive i candidati nella CSV locked del topic.

Vincoli (decisione grill 2026-05-29):
- Colonne A-K (1..11) INVARIATE per posizione e semantica (AppScript: "DO NOT MOVE UP TO K").
- Confidence email in NUOVA colonna R (18), mai inline nella cella email (K).
- Idempotente: match per email (lower) o (name,surname). Righe pre-esistenti NON sovrascritte.
- DR (G) da dr_lookup.json; dominio assente -> G vuota (fill manuale Ahrefs).

Input : .tmp/scored.json (gia filtrato a monte: target>=floor, 1/publisher, cap)
        data/dr_lookup.json
Output: aggiorna in-place la CSV locked in <TOPIC>/INPUT/*.csv (append righe nuove + header R)
"""
import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]
PR_ROOT = SKILL.parents[1]

# header canonico riga 2 (colonne A..Q = 1..17). R = 18 aggiunta.
HEADER_ROW2_AK = [
    "Batch Date", "Status", "Tracker follow-up", "Example Article",
    "Newspaper Name", "Domain Newspaper", "DR", "Name", "Surname", "Note",
]  # A..J (K = "Email..." testo lungo, lasciato com'e nel file originale)
COL_R_HEADER = "Email confidence"


def best_email(cands: list) -> dict | None:
    order = {"A": 0, "B": 1, "C": 2}
    valid = [e for e in cands if e.get("email")]
    if not valid:
        return None
    return sorted(valid, key=lambda e: order.get(e.get("tier", "C"), 3))[0]


def best_article(arts: list) -> str:
    on = [a for a in arts if a.get("on_topic")]
    if not on:
        return ""
    head = [a for a in on if a.get("in_headline")]
    pool = head or on
    pool = sorted(pool, key=lambda a: a.get("date", ""), reverse=True)
    return pool[0].get("url", "")


def conf_label(e: dict) -> str:
    tier = e.get("tier", "C")
    lab = {"A": "A-confirmed", "B": "B-pattern", "C": "C-redazione"}.get(tier, "C-redazione")
    return f"{lab} | confirmed={'true' if e.get('confirmed') else 'false'}"


def row_key(name, surname, email):
    if email:
        return ("email", email.strip().lower())
    return ("ns", f"{(name or '').strip().lower()}|{(surname or '').strip().lower()}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-dir", required=True)
    args = ap.parse_args()
    topic_root = PR_ROOT / args.topic_dir
    plan_files = list((topic_root / "PLAN").glob("*_plan.json"))
    plan = json.loads(plan_files[0].read_text(encoding="utf-8")) if plan_files else {}
    # support per-topic CSV subdir (default INPUT/, override via plan.csv_input_subdir)
    csv_subdir = plan.get("csv_input_subdir", "INPUT")
    csv_files = list((topic_root / csv_subdir).glob("*.csv"))
    if not csv_files:
        raise SystemExit(f"CSV mancante in {topic_root / csv_subdir}")
    csv_path = csv_files[0]
    dr_lookup = json.loads((PR_ROOT / "data" / "dr_lookup.json").read_text(encoding="utf-8"))
    scored = json.loads((topic_root / ".tmp" / "scored.json").read_text(encoding="utf-8"))
    run_date = plan.get("run_date", "2026-05-29")
    batch = f"{run_date[8:10]}/{run_date[5:7]}"  # DD/MM
    # confidence column index: default 17 (col R), override if that col is already used
    conf_col = plan.get("confidence_col_index", 17)

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise SystemExit("CSV malformato: meno di 2 righe header")
    width = max(len(r) for r in rows)
    width = max(width, conf_col + 1)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # header confidence col (riga 2, indice 1)
    if not rows[1][conf_col].strip():
        rows[1][conf_col] = COL_R_HEADER

    # indice righe esistenti (dalla riga 3 in poi)
    existing = set()
    for r in rows[2:]:
        existing.add(row_key(r[7], r[8], r[10]))

    added = 0
    for c in scored:
        be = best_email(c.get("email_candidates", []))
        if not be:
            continue  # nessuna email -> escluso (mai inventare)
        name, surname = c.get("name", ""), c.get("surname", "")
        key = row_key(name, surname, be["email"])
        if key in existing or row_key(name, surname, "") in existing:
            continue  # gia presente -> non duplicare
        dom = (c.get("domain") or "").lower()
        new = [""] * width
        new[0] = batch                                   # A Batch Date
        new[1] = "To Contact"                            # B Status
        new[2] = ""                                       # C Tracker
        new[3] = best_article(c.get("articles", []))      # D Example Article
        new[4] = c.get("publisher", "")                  # E Newspaper Name
        new[5] = dom                                      # F Domain
        new[6] = str(dr_lookup.get(dom, ""))             # G DR
        new[7] = name                                     # H Name
        new[8] = surname                                  # I Surname
        new[9] = c.get("why_in_target", "")              # J Note
        new[10] = be["email"]                            # K Email
        new[11] = ", ".join(c.get("topics", []))         # L General topic
        new[12] = c.get("linkedin", "")                  # M LinkedIn
        new[13] = ""                                       # N Already used
        new[14] = "New Contact"                          # O On our DB
        new[15] = ""                                       # P Can send now
        new[16] = c.get("mobile", "")                    # Q Mobile
        new[conf_col] = conf_label(be)                   # confidence col (R default, S for topics with R occupied)
        rows.append(new)
        existing.add(key)
        added += 1

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"OK  +{added} righe nuove -> {csv_path.name}  (tot data rows: {len(rows)-2})")


if __name__ == "__main__":
    main()
