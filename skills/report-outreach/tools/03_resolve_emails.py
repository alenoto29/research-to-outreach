#!/usr/bin/env python3
"""03_resolve_emails.py — optional email resolution; paid service is disabled by default.

Input : .tmp/selected.json + PLAN (email_pattern_hints)
Output: .tmp/resolved.json   (selected con email finali + rimpiazzi a cascata + usage)

Catena per i candidati senza email (solo discovery; dashboard ce l'ha già):
  1. raggruppa per dominio -> 1 domain-search per dominio:
     hit diretto sulla persona -> email Hunter; altrimenti pattern del dominio
  2. email-finder SOLO per chi non è risolto dal domain-search
  3. email-verifier su ogni email composta/low-confidence
Tier: A-confirmed (scraped da evidenze) | A-hunter (Hunter verificata valid) |
      B-pattern (composta, confirmed=false) | C-redazione. MAI inventare.
Budget gate: search_budget_per_run (default 20). Cache .tmp/hunter_cache.json:
re-run idempotenti e gratis. invalid -> no_email -> rimpiazzo a cascata dagli
alternates della stessa sorgente (ordine = classifica, deterministico).
Exit 3 = budget esaurito con candidati irrisolti.
"""
import argparse
import json
import os
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lib_common import (load_config, load_plan, normalize_domain,
                        normalize_name, update_run_log)

HUNTER_BASE = "https://api.hunter.io/v2"


# ---------- client con cache + budget ----------

class HunterClient:
    def __init__(self, api_key: str, cache_path: Path, search_budget: int, verify_budget: int):
        self.key = api_key
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        self.search_budget = search_budget
        self.verify_budget = verify_budget
        self.searches_used = 0
        self.verifications_used = 0

    def _call(self, endpoint: str, params: dict, kind: str) -> dict:
        ck = f"{endpoint}|{json.dumps(params, sort_keys=True)}"
        if ck in self.cache:
            return self.cache[ck]
        if kind == "search" and self.searches_used >= self.search_budget:
            raise BudgetExhausted("search")
        if kind == "verify" and self.verifications_used >= self.verify_budget:
            raise BudgetExhausted("verify")
        q = dict(params); q["api_key"] = self.key
        url = f"{HUNTER_BASE}/{endpoint}?{urllib.parse.urlencode(q)}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data", {})
        except urllib.error.HTTPError as e:
            data = {"_error": e.code}
        if kind == "search":
            self.searches_used += 1
        else:
            self.verifications_used += 1
        if api_error_exhausts_budget(data):
            raise BudgetExhausted(kind)
        # Errori transitori/quota non sono risultati: metterli in cache renderebbe
        # permanente un 429/5xx e impedirebbe retry successivi anche a quota resettata.
        if not is_transient_api_error(data):
            self.cache[ck] = data
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(1.1)  # rate-limit Hunter free
        return data

    def domain_search(self, domain: str) -> dict:
        return self._call("domain-search", {"domain": domain}, "search")

    def email_finder(self, domain: str, first: str, last: str) -> dict:
        return self._call("email-finder", {"domain": domain, "first_name": first, "last_name": last}, "search")

    def email_verifier(self, email: str) -> dict:
        return self._call("email-verifier", {"email": email}, "verify")


class BudgetExhausted(Exception):
    pass


# ---------- funzioni pure (testabili senza rete) ----------

def is_transient_api_error(data: dict) -> bool:
    code = data.get("_error") if isinstance(data, dict) else None
    return code == 429 or (isinstance(code, int) and code >= 500)


def api_error_exhausts_budget(data: dict) -> bool:
    return isinstance(data, dict) and data.get("_error") == 429

def ascii_lower(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch) and (ch.isalnum() or ch in ".-"))


def compose_from_pattern(pattern: str, first: str, last: str, domain: str):
    """Pattern Hunter tipo '{first}.{last}' / '{f}{last}' -> email. None se pattern ignoto.

    Supporta anche il vocabolario hint dei plan journalist-finder
    ('first.last', 'finitial+surname', 'finitial.surname', 'surname'):
    tradotto in token Hunter prima della compose ('+' = concatenazione)."""
    if not pattern:
        return None
    f, l = ascii_lower(first).replace(".", ""), ascii_lower(last).replace(".", "")
    if not f or not l:
        return None
    if "{" not in pattern:
        pattern = (pattern.replace("finitial", "\x01").replace("linitial", "\x02")
                   .replace("first", "\x03").replace("surname", "\x04")
                   .replace("last", "\x04").replace("+", "")
                   .replace("\x01", "{f}").replace("\x02", "{l}")
                   .replace("\x03", "{first}").replace("\x04", "{last}"))
    local = (pattern.replace("{first}", f).replace("{last}", l)
             .replace("{f}", f[0]).replace("{l}", l[0]))
    if "{" in local or not local or not all(ch.isalnum() or ch in "._-" for ch in local):
        return None
    return f"{local}@{domain}"


def match_person_in_domain_search(ds: dict, first: str, last: str):
    """Cerca la persona tra le email ritornate dal domain-search."""
    target = normalize_name(first, last)
    for e in ds.get("emails", []):
        if normalize_name(e.get("first_name"), e.get("last_name")) == target and e.get("value"):
            return e
    return None


def map_tier(method: str, verifier_status: str, hunter_confidence, cfg: dict):
    """-> (tier_label, confirmed, keep). MAI inventare: invalid = fuori."""
    if method == "scraped":
        return "A-confirmed", True, True
    if verifier_status == "invalid":
        return None, False, False
    strong = verifier_status == "valid" and (hunter_confidence or 0) >= cfg["hunter"]["finder_min_score"]
    if method in ("hunter-direct", "hunter-finder"):
        if strong:
            return "A-hunter", True, True
        return "B-hunter", False, True
    if method == "pattern":
        return "B-pattern", False, True  # anche se valid: composta, non pubblicata
    if method == "redazione":
        return "C-redazione", False, True
    return None, False, False


def cascade_replace(selected: list, alternates: dict, is_resolved,
                    max_journal: int = None, domain_of=None) -> list:
    """no_email -> rimpiazzo col prossimo alternate della stessa sorgente (deterministico).

    Cap per giornale: un alternate non entra se il suo dominio ha già max_journal
    righe tenute (la quota di 02 vale anche dopo i rimpiazzi a cascata)."""
    pool = {k: list(v) for k, v in alternates.items()}
    kept = {}

    def ok(c):
        if not is_resolved(c):
            return False
        if max_journal is None or domain_of is None:
            return True
        return kept.get(domain_of(c), 0) < max_journal

    out = []
    for c in selected:
        cur, replaced_from = c, None
        while not ok(cur):
            nxt = pool.get(cur["source"]) and pool[cur["source"]].pop(0) or None
            if nxt is None:
                break
            replaced_from = replaced_from or cur
            cur = nxt
        if not ok(cur):
            # nessun rimpiazzo valido (esauriti o tutti sopra il cap): torna
            # all'originale, che verrà scartato a valle come no_email
            cur, replaced_from = c, None
        elif replaced_from is not None:
            cur = dict(cur)
            cur["replaced"] = f"{replaced_from.get('first_name')} {replaced_from.get('last_name')} (no_email)"
        if ok(cur) and domain_of is not None:
            kept[domain_of(cur)] = kept.get(domain_of(cur), 0) + 1
        out.append(cur)
    return out


# ---------- risoluzione di un candidato (usa client) ----------

def resolve_one(c: dict, client: HunterClient, hints: dict, cfg: dict, domain_map: dict = None) -> dict:
    c = dict(c)
    if c.get("email") and c.get("source") == "dashboard":
        return c  # email già nel DB, zero costo
    if c.get("email") and c.get("email_tier", "").startswith("A"):
        c["email_method"] = "scraped"
        return c

    domain, first, last = (c.get("domain") or "").lower(), c.get("first_name"), c.get("last_name")
    if not domain:
        c["no_email"] = True
        return c
    # A plan may map a publication's site host to an independently verified email host.
    domain = (domain_map or {}).get(domain, domain)

    ds = client.domain_search(domain)
    hit = match_person_in_domain_search(ds, first, last)
    method, email, verification = None, None, None
    if hit:
        method, email = "hunter-direct", hit["value"]
        verification = (hit.get("verification") or {}).get("status")
        confidence = hit.get("confidence")
    else:
        # hint del plan (conoscenza editoriale verificata) vince sul pattern generico Hunter
        pattern = hints.get(domain) or ds.get("pattern")
        email = compose_from_pattern(pattern, first, last, domain)
        if email:
            method, confidence = "pattern", None
        else:
            fr = client.email_finder(domain, first, last)
            if fr.get("email"):
                method, email, confidence = "hunter-finder", fr["email"], fr.get("score")
                verification = (fr.get("verification") or {}).get("status")

    if not email:
        c["no_email"] = True
        return c

    if verification is None:
        verification = (client.email_verifier(email) or {}).get("status")

    tier, confirmed, keep = map_tier(method, verification, confidence if method != "pattern" else None, cfg)
    if not keep:
        c["no_email"] = True
        c["rejected_email"] = {"email": email, "method": method, "verifier": verification}
        return c
    c.update({"email": email, "email_tier": tier, "email_confirmed": confirmed,
              "email_method": method, "email_verifier_status": verification})
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--allow-paid-hunter", action="store_true",
                    help="explicitly permit paid email lookup/verification calls")
    args = ap.parse_args()

    cfg = load_config()
    plan = load_plan(args.run_dir)
    hints = plan.get("email_pattern_hints", {})
    domain_map = {k.lower(): v.lower() for k, v in (plan.get("publisher_email_domain") or {}).items()}
    tmp = Path(args.run_dir) / ".tmp"
    sel = json.loads((tmp / "selected.json").read_text(encoding="utf-8"))

    client = None
    if args.allow_paid_hunter:
        key = os.environ.get("HUNTER_API_KEY")
        if not key:
            raise SystemExit("HUNTER_API_KEY env mancante")
        client = HunterClient(key, tmp / "hunter_cache.json",
                              cfg["hunter"]["search_budget_per_run"],
                              cfg["hunter"]["verification_budget_per_run"])

    budget_hit, resolved_map = False, {}

    def resolve_cached(c):
        k = id(c)
        if k not in resolved_map:
            # Offline mode keeps only addresses already present in the input;
            # it never guesses an address or performs verification implicitly.
            if client is None and not (c.get("email") and (
                    c.get("source") == "dashboard" or c.get("email_tier", "").startswith("A"))):
                resolved_map[k] = dict(c, no_email=True, resolution_disabled=True)
            else:
                try:
                    resolved_map[k] = resolve_one(c, client, hints, cfg, domain_map)
                except BudgetExhausted:
                    resolved_map[k] = dict(c, no_email=True, budget_exhausted=True)
        return resolved_map[k]

    try:
        final = cascade_replace(sel["selected"], sel["alternates"],
                                lambda c: not resolve_cached(c).get("no_email"),
                                max_journal=cfg["selection"].get("max_per_journal"),
                                domain_of=lambda c: normalize_domain(c.get("domain")))
    except BudgetExhausted:
        budget_hit = True
        final = sel["selected"]
    final = [resolve_cached(c) for c in final]
    budget_hit = budget_hit or any(c.get("budget_exhausted") for c in final)

    unresolved = [f"{c.get('first_name')} {c.get('last_name')}" for c in final if c.get("no_email")]
    replacements = [{"in": f"{c.get('first_name')} {c.get('last_name')}", "for": c["replaced"]}
                    for c in final if c.get("replaced")]

    out = {"weights_version": sel["weights_version"], "run_date": sel["run_date"],
           "rows": [c for c in final if not c.get("no_email")],
           "unresolved": unresolved}
    (tmp / "resolved.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    update_run_log(args.run_dir, "emails", {
        "hunter_enabled": client is not None,
        "hunter_searches_used": client.searches_used if client else 0,
        "hunter_verifications_used": client.verifications_used if client else 0,
        "search_budget": cfg["hunter"]["search_budget_per_run"],
        "replacements": replacements,
        "unresolved": unresolved,
        "budget_exhausted": budget_hit,
    })
    print(f"OK rows={len(out['rows'])} searches={client.searches_used} "
          f"verify={client.verifications_used} unresolved={len(unresolved)}")
    if budget_hit and unresolved:
        print(f"BUDGET ESAURITO — irrisolti: {', '.join(unresolved)}")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
