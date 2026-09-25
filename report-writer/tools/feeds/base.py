"""Feed adapter framework — the contract every open-data adapter follows.

An adapter turns an open feed (ARERA/GME/ISTAT/Eurostat/GPR...) into a Series the
compute layer can use. Per-feed adapters are added pilot-driven (the chosen analyses
decide which feeds are needed); this module is the topic-agnostic spine.

Contract:
  series_result(...)  -> {"feed","label","unit","points":[[x,y]],"source","retrieved"}
  flag_result(feed,reason) -> {"feed","computed":False,"flag":"[DA CALCOLARE: ...]"}

Adapters MUST be fail-soft: a network/parse failure returns a flag_result, never a
crash and never a fabricated number. Raw inputs are cached under <TOPIC>/.tmp/feeds/
for traceability + recompute.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path


def series_result(feed, label, unit, points, source):
    """A successful series. points = list of [x, value] (x = date str or category)."""
    return {
        "feed": feed, "label": label, "unit": unit,
        "points": [[x, float(y)] for x, y in points],
        "source": source,
        "retrieved": _dt.date.today().isoformat(),
        "computed": True,
    }


def flag_result(feed, reason):
    """A fail-soft flag — the analysis using this feed becomes [DA CALCOLARE]."""
    return {"feed": feed, "computed": False,
            "flag": f"[DA CALCOLARE: feed {feed} non disponibile — {reason}]"}


def cache_raw(topic_dir, feed, filename, content, mode="w"):
    """Save raw feed bytes/text under <TOPIC>/.tmp/feeds/<feed>/ for traceability."""
    d = Path(topic_dir) / ".tmp" / "feeds" / feed
    d.mkdir(parents=True, exist_ok=True)
    path = d / filename
    if "b" in mode:
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def values(series_result_dict):
    """Convenience: extract the y-values from a series_result for compute.py."""
    return [p[1] for p in series_result_dict["points"]]
