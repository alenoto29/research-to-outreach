#!/usr/bin/env python3
"""Build a local domain-rating lookup from caller-supplied JSON records."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def build(src: Path, market: str) -> dict:
    data = json.loads(src.read_text(encoding="utf-8"))
    journalists = data.get("journalists", [])
    domain_rating = defaultdict(int)
    for row in journalists:
        if row.get("market") != market:
            continue
        domain = (row.get("domain") or "").strip().lower()
        value = row.get("dr")
        if domain and isinstance(value, (int, float)) and value > 0:
            domain_rating[domain] = max(domain_rating[domain], int(value))
    return dict(sorted(domain_rating.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, type=Path,
                        help="operator-provided JSON with a journalists array")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--market", required=True)
    args = parser.parse_args()
    src = args.src.expanduser()
    output = args.output.expanduser()
    if not src.exists():
        raise SystemExit(f"input file not found: {src}")
    lookup = build(src, args.market)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(lookup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(lookup)} domains to {output}")


if __name__ == "__main__":
    main()
