"""Feed adapter registry. Add per-feed adapters here as the pilot requires them.

Each adapter exposes `fetch(...) -> series_result | flag_result` (see base.py).
Topic-agnostic spine only — concrete adapters are added pilot-driven so we never
build speculative fetchers for feeds no chosen analysis actually needs.
"""
from . import base  # noqa: F401
from . import local_arera

# name -> fetch callable. Extend pilot-driven (gme, istat, eurostat, entsoe, gpr...).
REGISTRY = {
    "ARERA-local": local_arera.fetch,
}


def get(name):
    """Return the fetch callable for a feed, or None if not yet implemented."""
    return REGISTRY.get(name)


def available():
    return sorted(REGISTRY)
