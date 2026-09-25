"""Validate a Consultant brief + resolve Alessandro's pick (stage 3 pre-flight).

Reads papers-references/<TOPIC>/brief.md, checks the Output Contract sections are
present (else STOP), parses the 10-analysis table, and resolves the pick:
  --angle A|B + --analyses 1,4,5,6   (explicit), else the brief's Recommended combo.

Output: pick.json — the machine-friendly input to the report-deep-draft skill.
STOP (exit 1) on any malformed/missing required section. No silent defaults.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = ["Topic framing", "Angle A", "Angle B", "Recommended combo"]
ANGLE_FIELDS = {
    "thesis": "Thesis", "headline": "Headline number", "paper_basis": "Paper basis",
    "hook": "Journalist hook", "authority": "Why authority",
}


def fail(msg):
    print(f"STOP — brief non valido: {msg}", file=sys.stderr)
    sys.exit(1)


def _section(text, header):
    """Return body of '## <header...>' up to the next '## ' (or EOF), or None."""
    m = re.search(rf"^##\s+{re.escape(header)}[^\n]*\n(.*?)(?=^##\s|\Z)",
                  text, re.S | re.M)
    return m.group(1).strip() if m else None


def _angle_name(text, letter):
    m = re.search(rf"^##\s+Angle {letter}\s*[—\-]\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def _field(block, label):
    m = re.search(rf"-\s*\*\*{re.escape(label)}[^:]*:\*\*\s*(.+?)(?=\n-\s*\*\*|\Z)",
                  block, re.S)
    return re.sub(r"\s+", " ", m.group(1).strip()) if m else ""


def parse_angle(text, letter):
    block = _section(text, f"Angle {letter}")
    if not block:
        fail(f"manca la sezione 'Angle {letter}'")
    angle = {"letter": letter, "name": _angle_name(text, letter)}
    for key, label in ANGLE_FIELDS.items():
        angle[key] = _field(block, label)
    if not angle["thesis"]:
        fail(f"Angle {letter} senza Thesis")
    return angle


def parse_analyses(text):
    """Find the pipe table whose header has Analysis+Method+Feasible; parse rows."""
    rows = []
    header_idx = None
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        low = ln.lower()
        if low.count("|") >= 6 and "analysis" in low and "method" in low and "feasible" in low:
            header_idx = i
            break
    if header_idx is None:
        fail("tabella 10 analisi non trovata (header con Analysis/Method/Feasible)")
    for ln in lines[header_idx + 2:]:  # skip header + separator row
        if not ln.strip().startswith("|"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 8 or not re.match(r"^\d+$", cells[0]):
            continue
        rows.append({
            "id": int(cells[0]), "analysis": cells[1], "method": cells[2],
            "feeds": cells[3], "output_metric": cells[4],
            "diff": cells[5], "pickup": cells[6], "feasible": cells[7].lower(),
        })
    if not rows:
        fail("tabella analisi presente ma 0 righe parse-abili")
    return rows


def parse_recommended(text):
    """From 'Recommended combo' return (angle_letter, [ids])."""
    block = _section(text, "Recommended combo") or ""
    al = re.search(r"\bAngle\s*\*{0,2}\s*([AB])\b", block) or re.search(r"\*\*Angle:\*\*\s*([AB])", block)
    letter = al.group(1) if al else None
    # capture from 'analys...' up to the first dash/newline, then pull digits
    # (avoids trailing parenthetical refs like '(#5) ... (#1 ...)' after the em-dash)
    ids_m = re.search(r"analys\w*(.*?)(?:[—–]|\n|$)", block, re.I | re.S)
    ids = [int(x) for x in re.findall(r"\d+", ids_m.group(1))] if ids_m else []
    return letter, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="path to brief.md")
    ap.add_argument("--angle", choices=["A", "B"], help="override pick angle")
    ap.add_argument("--analyses", help="comma ids, e.g. 1,4,5,6")
    ap.add_argument("--out", help="pick.json output path (default: <brief dir>/pick.json)")
    args = ap.parse_args()

    p = Path(args.brief)
    if not p.exists():
        fail(f"file inesistente: {p}")
    text = p.read_text(encoding="utf-8")

    for sec in REQUIRED:
        if _section(text, sec) is None:
            fail(f"manca la sezione richiesta '## {sec}'")

    framing = _section(text, "Topic framing")
    angles = {"A": parse_angle(text, "A"), "B": parse_angle(text, "B")}
    analyses = parse_analyses(text)

    rec_letter, rec_ids = parse_recommended(text)
    letter = args.angle or rec_letter
    if letter not in ("A", "B"):
        fail("nessun angolo: passa --angle o aggiungi 'Angle A/B' alla Recommended combo")
    ids = ([int(x) for x in re.findall(r"\d+", args.analyses)] if args.analyses else rec_ids)
    if not ids:
        fail("nessuna analisi scelta: passa --analyses o specificale nella Recommended combo")

    by_id = {a["id"]: a for a in analyses}
    missing = [i for i in ids if i not in by_id]
    if missing:
        fail(f"analisi non in tabella: {missing}")
    if not (3 <= len(ids) <= 4):
        print(f"WARN: pick di {len(ids)} analisi (atteso 3-4)", file=sys.stderr)

    topic_m = re.search(r"^#\s+Consultant brief\s*[—\-]\s*(.+)$", text, re.M)
    pick = {
        "topic": topic_m.group(1).strip() if topic_m else p.parent.name,
        "brief_path": str(p),
        "framing": framing,
        "angle": angles[letter],
        "analyses": [by_id[i] for i in ids],
    }
    out = Path(args.out) if args.out else p.parent / "pick.json"
    out.write_text(json.dumps(pick, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK — pick risolto: angolo {letter}, analisi {ids} → {out}")
    infeasible = [a["id"] for a in pick["analyses"] if a["feasible"].startswith("no")]
    if infeasible:
        print(f"WARN: analisi marcate feasible=no nel brief: {infeasible} "
              f"(saranno flaggate [DA CALCOLARE] dallo stage 3)", file=sys.stderr)


if __name__ == "__main__":
    main()
