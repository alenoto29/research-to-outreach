#!/usr/bin/env python3
"""02_email_patterns.py — generatore tier B (pattern dedotto) + validatore formato.

REGOLA CRITICA (Gotcha, da lezione outreach-planner): MAI restituire un pattern come
se fosse verificato. Tier B = sempre confirmed=false. Se manca il dominio o un segnale
di formato noto -> nessun pattern (meglio zero che inventato).

Tier:
  A = email pubblicata/scraped  -> confirmed=true   (NON gestita qui, viene dallo scraping)
  B = pattern dedotto           -> confirmed=false   (questa funzione)
  C = redazione generica        -> confirmed=false   (passata esplicitamente)

Uso libreria:
  from importlib import import_module
  patterns = generate("Alex", "Example", "example.test", hints={"example.test": "finitial+surname"})

Uso CLI (test):
  python3 02_email_patterns.py "Alex" "Example" example.test
"""
import argparse
import re
import sys
import unicodedata

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

# pattern noti generici (fallback se nessun hint per dominio)
GENERIC_PATTERNS = [
    "{first}.{last}",
    "{f}{last}",
    "{first}{last}",
    "{last}.{first}",
    "{f}.{last}",
]

# alias hint -> template
HINT_MAP = {
    "first.last": "{first}.{last}",
    "finitial+surname": "{f}{last}",
    "firstlast": "{first}{last}",
    "last.first": "{last}.{first}",
    "finitial.surname": "{f}.{last}",
    "surname": "{last}",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z]", "", s).lower()
    return s


def valid(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def generate(first: str, last: str, domain: str, hints: dict | None = None) -> list[dict]:
    """Ritorna lista di candidati tier B. Vuota se input insufficiente."""
    f, l = _norm(first), _norm(last)
    dom = (domain or "").strip().lower().lstrip("@")
    if not f or not l or not dom or "." not in dom:
        return []
    hints = hints or {}
    templates: list[str] = []
    hint = hints.get(dom)
    if hint:
        tmpl = HINT_MAP.get(hint, hint if "{" in hint else None)
        if tmpl:
            templates.append(tmpl)
    # sempre includi i generici dopo l'hint (dedup mantiene ordine)
    templates += GENERIC_PATTERNS
    seen, out = set(), []
    for t in templates:
        local = t.format(first=f, last=l, f=f[0])
        email = f"{local}@{dom}"
        if email in seen or not valid(email):
            continue
        seen.add(email)
        out.append({
            "email": email,
            "tier": "B",
            "source": "pattern",
            "confirmed": False,
            "template": t,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("first")
    ap.add_argument("last")
    ap.add_argument("domain")
    ap.add_argument("--hint", default=None)
    args = ap.parse_args()
    hints = {args.domain.lower(): args.hint} if args.hint else {}
    res = generate(args.first, args.last, args.domain, hints)
    if not res:
        print("(nessun pattern: input insufficiente)", file=sys.stderr)
        sys.exit(1)
    for r in res:
        print(f"{r['email']:40s} tier={r['tier']} confirmed={r['confirmed']} ({r['template']})")


if __name__ == "__main__":
    main()
