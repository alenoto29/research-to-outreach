"""validate_briefs.py — pre-flight sui brief di writer/grapher/compose.

Verifica che ogni {placeholder} nei brief risolva in numbers.json["report_keys"].
Gate hard: exit 1 su chiave orfana, brief mancante, o report_keys assente.
Scan euristico: avvisa su numeri analitici letterali (€/kWh/%) senza placeholder.

Uso:
  python3 tools/validate_briefs.py \\
    --briefs <TOPIC>/brief_write.md <TOPIC>/brief_graph.md <TOPIC>/brief_layout.md \\
    --numbers <TOPIC>/numbers.json

Exit 0 = tutti i placeholder risolvono, headline_number presente.
Exit 1 = chiave orfana, brief mancante, report_keys assente, headline_number mancante.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Patterns
_PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
# Heuristic: €/kWh/W/% preceded by a number = likely analytical value
_ANALYTIC_NUM_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(?:€|kWh|kWh/anno|kWh/giorno|W\b|%|EUR|MWh|Smc)\b",
    re.IGNORECASE,
)


def fail(msg: str) -> None:
    print(f"STOP — {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"WARN — {msg}", file=sys.stderr)


def ok(msg: str) -> None:
    print(f"OK   — {msg}")


def load_report_keys(numbers_path: Path) -> dict:
    if not numbers_path.exists():
        fail(f"numbers.json non trovato: {numbers_path}")
    data = json.loads(numbers_path.read_text(encoding="utf-8"))
    if "report_keys" not in data:
        fail(
            f"'report_keys' assente in {numbers_path}. "
            "Eseguire analyzer per popolare report_keys (vedi references/numbers_contract.md)."
        )
    rk = data["report_keys"]
    if not isinstance(rk, dict):
        fail(f"'report_keys' deve essere un dizionario, trovato: {type(rk).__name__}")
    return rk


def extract_placeholders(text: str) -> list[str]:
    return _PLACEHOLDER_RE.findall(text)


def scan_heuristic_numbers(text: str, brief_path: Path) -> list[str]:
    """Warn on likely analytical numbers written as literals."""
    warnings = []
    for m in _ANALYTIC_NUM_RE.finditer(text):
        line_num = text[: m.start()].count("\n") + 1
        warnings.append(
            f"{brief_path.name}:{line_num} — numero letterale '{m.group()}' "
            "potrebbe richiedere un {{placeholder}} (vedi numbers_contract.md)"
        )
    return warnings


def validate_brief(brief_path: Path, report_keys: dict) -> tuple[list[str], list[str], list[str]]:
    """Returns (resolved, orphans, heuristic_warnings)."""
    if not brief_path.exists():
        fail(f"brief non trovato: {brief_path}")
    text = brief_path.read_text(encoding="utf-8")
    placeholders = extract_placeholders(text)
    resolved, orphans = [], []
    for key in placeholders:
        if key in report_keys:
            resolved.append(key)
        else:
            orphans.append(key)
    hints = scan_heuristic_numbers(text, brief_path)
    return resolved, orphans, hints


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate writer briefs against numbers.json report_keys")
    parser.add_argument("--briefs", nargs="+", required=True, help="Path(s) ai brief (brief_write.md, brief_graph.md, ...)")
    parser.add_argument("--numbers", required=True, help="Path a numbers.json con campo report_keys")
    args = parser.parse_args()

    numbers_path = Path(args.numbers)
    report_keys = load_report_keys(numbers_path)

    # Check headline_number
    if "headline_number" not in report_keys:
        fail("'headline_number' mancante in report_keys — obbligatorio (vedi numbers_contract.md §Chiave obbligatoria)")
    ok(f"headline_number = {report_keys['headline_number']}")

    all_orphans: list[str] = []
    all_hints: list[str] = []

    for brief_str in args.briefs:
        brief_path = Path(brief_str)
        resolved, orphans, hints = validate_brief(brief_path, report_keys)

        if resolved:
            ok(f"{brief_path.name}: {len(resolved)} placeholder risolti ({', '.join(resolved[:5])}{'...' if len(resolved) > 5 else ''})")
        else:
            ok(f"{brief_path.name}: nessun placeholder trovato")

        for key in orphans:
            print(f"FAIL — {brief_path.name}: placeholder '{{{key}}}' non trovato in report_keys", file=sys.stderr)

        all_orphans.extend(orphans)
        all_hints.extend(hints)

    # Heuristic warnings (non-blocking)
    for hint in all_hints:
        warn(hint)

    if all_orphans:
        unique = sorted(set(all_orphans))
        print(
            f"\nSTOP — {len(unique)} chiave/i orfana/e: {unique}\n"
            f"Aggiungere a report_keys in {numbers_path} oppure correggere il placeholder nel brief.",
            file=sys.stderr,
        )
        sys.exit(1)

    total_placeholders = sum(
        len(extract_placeholders(Path(b).read_text(encoding="utf-8")))
        for b in args.briefs
        if Path(b).exists()
    )
    print(f"\nPASS — {total_placeholders} placeholder su {len(args.briefs)} brief, tutti risolti.")
    sys.exit(0)


if __name__ == "__main__":
    main()
