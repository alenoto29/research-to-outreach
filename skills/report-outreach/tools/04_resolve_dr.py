#!/usr/bin/env python3
"""04_resolve_dr.py — DR per i domini finali (D6).

Chain: PR/data/dr_lookup.json (cache) -> miss -> endpoint pubblico Ahrefs GRATUITO
(no API key, verificato live 2026-06-12):
  GET https://api.ahrefs.com/v3/public/domain-rating-free?target=<dominio>&output=json
Risultato scritto nel lookup (auto-crescente, committato). Throttle 1 req/s.
Failure totale -> DR vuoto, riga valida. MAI inventare. DR = solo tie-breaker.

Input : .tmp/resolved.json  ->  Output: .tmp/resolved.json (aggiornato in place)
"""
import argparse
import json
import time
from pathlib import Path

from lib_common import fetch_dr_free, load_config, resolve_dr, update_run_log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--allow-network", action="store_true",
                    help="explicitly permit public domain-rating lookups")
    args = ap.parse_args()

    cfg = load_config()
    throttle = cfg["dr"]["throttle_seconds"]
    tmp = Path(args.run_dir) / ".tmp"
    data = json.loads((tmp / "resolved.json").read_text(encoding="utf-8"))
    lookup_path = tmp / "dr_lookup.json"
    lookup = json.loads(lookup_path.read_text(encoding="utf-8")) if lookup_path.exists() else {}

    api_hits, misses = [], []
    last_call = 0.0
    for row in data["rows"]:
        if row.get("dr") is not None:
            continue

        def throttled(domain):
            nonlocal last_call
            if not args.allow_network:
                return None
            w = throttle - (time.monotonic() - last_call)
            if w > 0:
                time.sleep(w)
            last_call = time.monotonic()
            return fetch_dr_free(domain)

        dr, from_api = resolve_dr(row.get("domain"), lookup, throttled)
        row["dr"] = dr
        if from_api:
            api_hits.append({"domain": row["domain"], "dr": dr})
        elif dr is None:
            misses.append(row.get("domain"))

    if api_hits:
        lookup_path.write_text(
            json.dumps(dict(sorted(lookup.items())), ensure_ascii=False, indent=2), encoding="utf-8")

    (tmp / "resolved.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    update_run_log(args.run_dir, "dr", {"api_hits": api_hits, "misses": misses})
    print(f"OK api_hits={len(api_hits)} misses={len(misses)} lookup_size={len(lookup)}")


if __name__ == "__main__":
    main()
