#!/usr/bin/env python3
"""02_select_mix.py — selezione ~25 con quota 50/50 soft (D4 grill Q1/D4 design).

Input : .tmp/scored.json
Output: .tmp/selected.json  (selected + alternates per sorgente per la cascata email)

Quota soft: si parte dal top-N per score; se una sorgente supera max_source_share,
swap della riga marginale con la migliore esclusa dell'altra sorgente SOLO se
gap <= swap_gap_threshold. Gap maggiore -> lo score vince, deviazione loggata.
Tie-break deterministico: score desc, DR desc (assente = ultimo), cognome, nome.
"""
import argparse
import json
import math
from pathlib import Path

from lib_common import load_config, normalize_domain, update_run_log


def select(scored: list, sel_cfg: dict) -> dict:
    target = min(sel_cfg["target_size"], len(scored))
    max_journal = sel_cfg.get("max_per_journal")

    # fill iniziale: top per score rispettando il cap per giornale (max N dallo stesso dominio)
    selected, rest, dcount, cap_skips = [], [], {}, []
    for c in scored:
        dom = normalize_domain(c.get("domain"))
        if len(selected) < target and (max_journal is None or dcount.get(dom, 0) < max_journal):
            selected.append(c)
            dcount[dom] = dcount.get(dom, 0) + 1
        else:
            if len(selected) < target and max_journal is not None and dcount.get(dom, 0) >= max_journal:
                cap_skips.append(_label(c))
            rest.append(c)
    n = len(selected)
    swaps = []

    max_count = math.ceil(sel_cfg["max_source_share"] * n)
    while n > 0:
        counts = {"dashboard": 0, "discovery": 0}
        for c in selected:
            counts[c["source"]] = counts.get(c["source"], 0) + 1
        over = [s for s, k in counts.items() if k > max_count]
        if not over:
            break
        src = over[0]
        other = "discovery" if src == "dashboard" else "dashboard"
        marginal = next((c for c in reversed(selected) if c["source"] == src), None)
        if marginal is None:
            break
        m_dom = normalize_domain(marginal.get("domain"))
        # candidato dell'altra sorgente che NON sfora il cap dopo lo swap (lo swap
        # libera il dominio del marginal)
        candidate = next(
            (c for c in rest if c["source"] == other and (
                max_journal is None
                or dcount.get(normalize_domain(c.get("domain")), 0)
                - (1 if normalize_domain(c.get("domain")) == m_dom else 0) < max_journal)),
            None)
        if candidate is None:
            break
        gap = marginal["score"] - candidate["score"]
        if gap > sel_cfg["swap_gap_threshold"]:
            break  # lo score vince, quota sbilanciata (loggata sotto)
        selected[next(i for i, c in enumerate(selected) if c is marginal)] = candidate
        rest = [c for c in rest if c is not candidate] + [marginal]
        dcount[m_dom] = dcount.get(m_dom, 0) - 1
        c_dom = normalize_domain(candidate.get("domain"))
        dcount[c_dom] = dcount.get(c_dom, 0) + 1
        swaps.append({"out": _label(marginal), "in": _label(candidate), "gap": round(gap, 1)})

    # riordina dopo gli swap (stesso ordine deterministico dello scored)
    order = {id(c): i for i, c in enumerate(scored)}
    selected.sort(key=lambda c: order[id(c)])
    counts = {"dashboard": 0, "discovery": 0}
    for c in selected:
        counts[c["source"]] = counts.get(c["source"], 0) + 1

    selected_ids = {id(c) for c in selected}
    alternates = {
        "dashboard": [c for c in scored if id(c) not in selected_ids and c["source"] == "dashboard"],
        "discovery": [c for c in scored if id(c) not in selected_ids and c["source"] == "discovery"],
    }
    thin_pool = len(scored) < sel_cfg["thin_pool_factor"] * sel_cfg["target_size"]
    deviation = abs(counts.get("dashboard", 0) - counts.get("discovery", 0)) > max(1, round(0.2 * n))
    return {"selected": selected, "alternates": alternates,
            "log": {"counts": counts, "swaps": swaps, "journal_cap_skips": cap_skips,
                    "quota_deviation": deviation, "thin_pool": thin_pool}}


def _label(c: dict) -> str:
    return f"{c.get('first_name')} {c.get('last_name')} ({c['source']}, {c['score']})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    cfg = load_config()
    tmp = Path(args.run_dir) / ".tmp"
    data = json.loads((tmp / "scored.json").read_text(encoding="utf-8"))
    result = select(data["scored"], cfg["selection"])
    result["weights_version"] = data["weights_version"]
    result["run_date"] = data["run_date"]

    (tmp / "selected.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    update_run_log(args.run_dir, "selection", result["log"])
    log = result["log"]
    print(f"OK selected={len(result['selected'])} mix={log['counts']} "
          f"swaps={len(log['swaps'])} thin_pool={log['thin_pool']}")


if __name__ == "__main__":
    main()
