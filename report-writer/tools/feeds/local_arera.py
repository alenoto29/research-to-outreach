"""Reference adapter: retail price series from a caller-supplied snapshot directory.
Each PLACET csv = one offer per row with price columns (p_fix_f, p_fix_v, p_vol, alpha).
This adapter aggregates one column across snapshot dates → a real retail price series.

Demonstrates the feed contract end-to-end on verifiable local data. PLACET (csv) is
supported; MLIBERO is XML → flagged until an XML adapter is added (pilot-driven).
"""
from __future__ import annotations

import csv
import re
import statistics as st
from pathlib import Path

try:
    from .base import series_result, flag_result
except ImportError:  # running as a standalone script (tools/feeds on sys.path)
    from base import series_result, flag_result

FEED = "ARERA-local"
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch(arera_root, commodity="G", market="PLACET", column="p_fix_v", agg="median"):
    """Series of agg(column) across snapshot dates. commodity E|G, market PLACET only.
    Fail-soft: returns flag_result on any structural problem, never a fake number."""
    root = Path(arera_root)
    if not root.is_dir():
        return flag_result(FEED, "snapshot directory is missing")
    if market != "PLACET":
        return flag_result(FEED, f"market {market} è XML, parser non implementato (MVP solo PLACET csv)")

    aggfn = {"median": st.median, "mean": st.mean}.get(agg)
    if aggfn is None:
        return flag_result(FEED, f"agg non supportato: {agg}")

    points = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and _DATE.match(p.name)):
        compact = d.name.replace("-", "")
        f = d / f"PO_Offerte_{commodity}_{market}_{compact}.csv"
        if not f.exists():
            continue
        vals = []
        with f.open(encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                raw = (row.get(column) or "").strip()
                if raw:
                    try:
                        vals.append(float(raw))
                    except ValueError:
                        pass
        if vals:
            points.append([d.name, aggfn(vals)])

    if not points:
        return flag_result(FEED, f"nessun valore per {commodity}/{market}/{column}")
    return series_result(
        FEED,
        label=f"{commodity}/{market} {column} ({agg})",
        unit="€ (componente prezzo ARERA)",
        points=points,
        source=f"ARERA snapshot directory — {column}, {agg} per date",
    )
