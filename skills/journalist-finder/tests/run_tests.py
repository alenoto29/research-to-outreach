#!/usr/bin/env python3
"""run_tests.py — test deterministici dei tool PR engine. Zero rete, zero LLM.

    python3 run_tests.py    # exit 0 = tutti pass
"""
import csv
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


emailmod = load("emailmod", TOOLS / "02_email_patterns.py")
scoremod = load("scoremod", TOOLS / "01_scoring.py")

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


# --- 02_email_patterns ---
print("02_email_patterns")
res = emailmod.generate("Alex", "Example", "example.test", {"example.test": "finitial+surname"})
check("hint first applied", res and res[0]["email"] == "aexample@example.test")
check("all tier B confirmed false", all(r["tier"] == "B" and r["confirmed"] is False for r in res))
check("all RFC valid", all(emailmod.valid(r["email"]) for r in res))
check("accents normalized", emailmod.generate("José", "Muñoz", "example.test")[0]["email"].startswith("jose.munoz@"))
check("no domain -> empty", emailmod.generate("A", "B", "") == [])
check("no surname -> empty", emailmod.generate("A", "", "example.test") == [])
check("invalid domain (no dot) -> empty", emailmod.generate("A", "B", "localhost") == [])

# --- 01_scoring ---
print("01_scoring")
from datetime import date
W = scoremod.DEFAULT_WEIGHTS
cand_hot = {
    "name": "Alex", "surname": "Example", "domain": "news.example.test", "dr": 90,
    "author_page": "https://news.example.test/author/alex-example",
    "beat": "energia e nucleare",
    "topics": ["nucleare", "energia"],
    "articles": [
        {"url": "u1", "date": "2026-05-01", "on_topic": True, "in_headline": True},
        {"url": "u2", "date": "2026-04-01", "on_topic": True, "in_headline": True},
        {"url": "u3", "date": "2026-03-01", "on_topic": True, "in_headline": False},
        {"url": "u4", "date": "2026-02-01", "on_topic": True, "in_headline": True},
        {"url": "u5", "date": "2026-01-01", "on_topic": True, "in_headline": False},
    ],
}
s = scoremod.score_candidate(cand_hot, W, date(2026, 5, 29), ["nucleare"])
# 5 ontopic->35, 3+ headline->25, recency<90d->20, author_page->10, focus in beat->10 = 100
check("hot candidate = 100", s["target_score"] == 100)

cand_weak = {
    "name": "Lina", "surname": "Bianchi", "domain": "example.test", "dr": 50,
    "author_page": "",
    "beat": "cronaca",
    "topics": ["politica"],
    "articles": [
        {"url": "z1", "date": "2024-01-01", "on_topic": True, "in_headline": False},
    ],
}
sw = scoremod.score_candidate(cand_weak, W, date(2026, 5, 29), ["nucleare"])
# 1 ontopic->7, 0 headline->0, recency>365->0, no author_page->0, no focus->0 = 7
check("weak candidate = 7", sw["target_score"] == 7)
check("determinism: same input same score",
      scoremod.score_candidate(cand_hot, W, date(2026, 5, 29), ["nucleare"])["target_score"] == 100)

# --- 03 write + 04 qa end-to-end ---
print("03_write_csv + 04_qa_gate (e2e)")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    # finta struttura PR
    (root / "data").mkdir()
    (root / "data" / "dr_lookup.json").write_text(json.dumps({"news.example.test": 90}))
    tdir = root / "example-topic"
    (tdir / "INPUT").mkdir(parents=True)
    (tdir / "PLAN").mkdir()
    (tdir / ".tmp").mkdir()
    (tdir / "PLAN" / "nucleare_plan.json").write_text(json.dumps({
        "run_date": "2026-05-29", "topic_core": ["nucleare"],
        "thresholds": {"target_floor": 40}}))
    # CSV locked minima: 2 righe header
    with (tdir / "INPUT" / "DB.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["REMEMBER", "Newspaper info"] + [""] * 15)
        w.writerow(["Batch Date", "Status", "Tracker follow-up", "Example Article",
                    "Newspaper Name", "Domain Newspaper", "DR", "Name", "Surname",
                    "Note", "Email", "General topic they write about", "LinkedIn",
                    "Did we already used", "Do we have it", "Can we send", "Mobile"])
    scored = [{
        "name": "Mario", "surname": "Rossi", "publisher": "Corriere della Sera",
        "domain": "news.example.test", "linkedin": "", "mobile": "",
        "why_in_target": "5 articoli nucleare, beat energia",
        "target_score": 100,
        "articles": [{"url": "https://news.example.test/article-1", "date": "2030-05-01",
                      "on_topic": True, "in_headline": True}],
        "topics": ["nucleare"],
        "email_candidates": [{"email": "a.example@news.example.test", "tier": "B",
                              "source": "pattern", "confirmed": False}],
    }]
    (tdir / ".tmp" / "scored.json").write_text(json.dumps(scored))

    writemod = load("writemod", TOOLS / "03_write_csv.py")
    qamod = load("qamod", TOOLS / "04_qa_gate.py")
    # patch PR_ROOT dei moduli alla root temporanea
    writemod.PR_ROOT = root
    qamod.PR_ROOT = root
    sys.argv = ["x", "--topic-dir", "example-topic"]
    writemod.main()
    out = list(csv.reader((tdir / "INPUT" / "DB.csv").open()))
    check("riga aggiunta", len(out) == 3)
    check("col R header", out[1][17] == "Email confidence")
    check("email in K (col 11)", out[2][10] == "a.example@news.example.test")
    check("DR in G da lookup", out[2][6] == "90")
    check("R confirmed=false per tier B", "confirmed=false" in out[2][17].lower())
    check("colonne A-J intatte", out[1][:10] == ["Batch Date", "Status", "Tracker follow-up",
          "Example Article", "Newspaper Name", "Domain Newspaper", "DR", "Name", "Surname", "Note"])
    # idempotenza: re-run non duplica
    writemod.main()
    out2 = list(csv.reader((tdir / "INPUT" / "DB.csv").open()))
    check("idempotente (no dup)", len(out2) == 3)
    # qa gate pass
    try:
        qamod.main()
        check("qa gate PASS", True)
    except SystemExit as e:
        check("qa gate PASS", e.code in (0, None))

print(f"\n{PASS} pass, {FAIL} fail")
sys.exit(1 if FAIL else 0)
