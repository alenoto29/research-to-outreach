#!/usr/bin/env python3
"""lib_common.py — utilities condivise dai tool report-outreach.

Nessuna chiamata LLM. Le funzioni qui dentro sono pure (no rete, no system date)
salvo gli helper API esplicitamente marcati (usati solo dai tool di rete).
"""
import json
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]
DEFAULT_API_BASE = None


# ---------- config / run dir ----------

def load_config(path: Path = None) -> dict:
    p = path or (SKILL / "config" / "weights.json")
    return json.loads(p.read_text(encoding="utf-8"))


def run_paths(run_dir: str) -> dict:
    root = Path(run_dir).resolve()
    return {
        "root": root,
        "plan_dir": root / "PLAN",
        "tmp": root / ".tmp",
        "output": root / "OUTPUT",
    }


def load_plan(run_dir: str) -> dict:
    plans = sorted((Path(run_dir) / "PLAN").glob("*plan.json"))
    if not plans:
        raise SystemExit(f"plan mancante in {run_dir}/PLAN/ (gate 1 non superato?)")
    return json.loads(plans[0].read_text(encoding="utf-8"))


def parse_date(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except (ValueError, TypeError):
        return None


# ---------- normalizzazione / dedup ----------

def normalize_name(first: str, last: str) -> str:
    full = f"{(first or '').strip()} {(last or '').strip()}".lower()
    full = unicodedata.normalize("NFKD", full)
    full = "".join(ch for ch in full if not unicodedata.combining(ch))
    return " ".join(full.split())


def dedup_key(c: dict):
    email = (c.get("email") or "").strip().lower()
    if email and "@" in email:
        return ("email", email)
    return ("name", normalize_name(c.get("first_name"), c.get("last_name")), (c.get("domain") or "").lower())


def normalize_domain(d: str) -> str:
    """Dominio canonico per match (blacklist, cap per giornale): lowercase, no 'www.'."""
    d = (d or "").strip().lower()
    return d[4:] if d.startswith("www.") else d


# ---------- DR (Ahrefs free, condiviso da 01b e 04) ----------

AHREFS_FREE = "https://api.ahrefs.com/v3/public/domain-rating-free"


def fetch_dr_free(domain: str):
    """Endpoint pubblico Ahrefs GRATUITO (no API key). None su qualsiasi errore. MAI inventare."""
    url = f"{AHREFS_FREE}?{urllib.parse.urlencode({'target': domain, 'output': 'json'})}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        dr = data.get("domain_rating", {}).get("domain_rating")
        return round(dr) if dr is not None else None
    except Exception:
        return None


def resolve_dr(domain: str, lookup: dict, fetcher) -> tuple:
    """-> (dr|None, from_api: bool). Funzione pura se fetcher è iniettato."""
    domain = (domain or "").lower().strip()
    if not domain:
        return None, False
    if domain in lookup:
        return lookup[domain], False
    dr = fetcher(domain)
    if dr is not None:
        lookup[domain] = dr
        return dr, True
    return None, False


# ---------- run log ----------

def update_run_log(run_dir: str, section: str, payload) -> dict:
    p = Path(run_dir) / "OUTPUT" / "run_log.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    log = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    log[section] = payload
    p.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return log


def read_run_log(run_dir: str) -> dict:
    p = Path(run_dir) / "OUTPUT" / "run_log.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ---------- dashboard API (solo tool di rete) ----------

def api_get(api_base: str, path: str, token: str, params: dict = None) -> dict:
    if not api_base:
        raise ValueError("API base must be provided explicitly")
    query = urllib.parse.urlencode(params or {})
    url = f"{api_base.rstrip('/')}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_send(api_base: str, path: str, token: str, body: dict, method: str = "POST") -> dict:
    if not api_base:
        raise ValueError("API base must be provided explicitly")
    url = f"{api_base.rstrip('/')}{path}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), method=method,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))
