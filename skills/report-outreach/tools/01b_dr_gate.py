#!/usr/bin/env python3
"""01b_dr_gate.py — risolve il DR dell'intero pool e applica il gate per tipo report.

Input : .tmp/scored.json   (pool scorato, ordinato)
        PLAN/*plan.json     (report_type: TOP | MID)
        PR/data/dr_lookup.json (cache condivisa) + Ahrefs free (no API key)
Output: .tmp/scored.json   (DR scritto su ogni candidato + pool filtrato dal gate)

Gate per tipo report (inclusivo, deterministico):
  TOP -> tiene DR >= top_min (default 50)
  MID -> tiene DR <= mid_max (default 80)
  DR tra top_min e mid_max -> passa in ENTRAMBI i tipi.
DR sconosciuto (Ahrefs miss + non in cache) -> tenuto, esente dal gate, loggato.
DR risolto sull'INTERO pool qui (Ahrefs gratuito, throttle): 04 diventa quasi
solo cache. DR resta SOLO tie-breaker nello score (regola "target over DR").
Determinismo: stesso pool -> stesso DR (cache committata), stesso esito gate.
"""
import argparse
import json
import time
from pathlib import Path

from lib_common import (fetch_dr_free, load_config, load_plan,
                        normalize_domain, resolve_dr, update_run_log)


def passes_dr_gate(dr, report_type: str, cfg: dict) -> bool:
    """DR None -> True (esente, tenuto). Altrimenti gate inclusivo per tipo."""
    if dr is None:
        return True
    g = cfg["dr_gate"]
    if report_type == "TOP":
        return dr >= g["top_min"]
    if report_type == "MID":
        return dr <= g["mid_max"]
    raise SystemExit(f"report_type invalido: {report_type!r} (atteso TOP | MID)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--allow-network", action="store_true",
                    help="explicitly permit public domain-rating lookups")
    args = ap.parse_args()

    cfg = load_config()
    plan = load_plan(args.run_dir)
    report_type = (plan.get("report_type") or "").strip().upper()
    if report_type not in ("TOP", "MID"):
        raise SystemExit("plan.report_type mancante o invalido (atteso TOP | MID)")

    throttle = cfg["dr"]["throttle_seconds"]
    tmp = Path(args.run_dir) / ".tmp"
    data = json.loads((tmp / "scored.json").read_text(encoding="utf-8"))
    lookup_path = tmp / "dr_lookup.json"
    lookup = json.loads(lookup_path.read_text(encoding="utf-8")) if lookup_path.exists() else {}

    # risolvi una sola volta per dominio (dedup), poi propaga su ogni candidato
    last_call = 0.0

    def throttled(domain):
        nonlocal last_call
        if not args.allow_network:
            return None
        w = throttle - (time.monotonic() - last_call)
        if w > 0:
            time.sleep(w)
        last_call = time.monotonic()
        return fetch_dr_free(domain)

    # DR già presente su un candidato (raro: lo schema nasce dr=null) ha priorità sul
    # fetch, per non clobberare un dato reale con un miss di rete (MAI inventare/perdere).
    existing = {}
    for c in data["scored"]:
        dom = normalize_domain(c.get("domain"))
        if dom and dom not in existing and isinstance(c.get("dr"), (int, float)):
            existing[dom] = c["dr"]

    domain_dr, api_hits = {}, []
    for c in data["scored"]:
        dom = normalize_domain(c.get("domain"))
        if not dom or dom in domain_dr:
            continue
        if dom in lookup:
            domain_dr[dom] = lookup[dom]
        elif dom in existing:
            domain_dr[dom] = existing[dom]
        else:
            dr, from_api = resolve_dr(dom, lookup, throttled)
            domain_dr[dom] = dr
            if from_api:
                api_hits.append({"domain": dom, "dr": dr})

    for c in data["scored"]:
        c["dr"] = domain_dr.get(normalize_domain(c.get("domain")))

    if api_hits:
        lookup_path.write_text(
            json.dumps(dict(sorted(lookup.items())), ensure_ascii=False, indent=2), encoding="utf-8")

    kept = [c for c in data["scored"] if passes_dr_gate(c.get("dr"), report_type, cfg)]
    excluded = [c for c in data["scored"] if not passes_dr_gate(c.get("dr"), report_type, cfg)]
    dr_unknown = [c for c in kept if c.get("dr") is None]

    data["scored"] = kept
    data["report_type"] = report_type
    (tmp / "scored.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    update_run_log(args.run_dir, "dr_gate", {
        "report_type": report_type,
        "gate": cfg["dr_gate"],
        "api_hits": api_hits,
        "excluded_dr_gate": [
            {"name": f"{c.get('first_name')} {c.get('last_name')}", "domain": c.get("domain"),
             "dr": c.get("dr"), "reason": f"dr fuori range {report_type}"}
            for c in excluded
        ],
        "dr_unknown": [
            {"name": f"{c.get('first_name')} {c.get('last_name')}", "domain": c.get("domain")}
            for c in dr_unknown
        ],
    })
    print(f"OK report_type={report_type} kept={len(kept)} gate_excluded={len(excluded)} "
          f"dr_unknown={len(dr_unknown)} api_hits={len(api_hits)}")


if __name__ == "__main__":
    main()
