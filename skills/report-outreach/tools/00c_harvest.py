#!/usr/bin/env python3
"""00c_harvest.py — harvester deterministico OUT-OF-CONTEXT (D3/D6).

Input  : .tmp/urls.json            (lista URL + meta minimo, dal subagent discovery)
         .tmp/dashboard_shortlist.json (record DB da arricchire, output di 00)
Output : .tmp/raw_candidates.json  (schema discovery_brief, consumato dal judge `complete`)
         .tmp/harvest_log.json      (URL droppati + motivo, conteggi cache)

L'HTML delle pagine NON entra MAI nel contesto del modello: crawl4ai scarica e
estrae qui, in Python. Il modello legge solo il JSON compatto, una volta.

Regola ferrea: URL non parsabile → drop + log. MAI inventare byline/data/titolo.

Uso: python3 tools/00c_harvest.py --run-dir runs/<slug> [--no-cache]
crawl4ai/playwright opzionali a import-time: le funzioni di estrazione sono pure
(testabili offline); solo il fetch tocca la rete.
"""
import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_common import normalize_domain, normalize_name, run_paths  # noqa: E402

# Cache disco dei CAMPI ESTRATTI (non l'HTML): piccola, condivisa tra report
# (cross-report), zero token modello. Re-run di un URL già visto = nessun download.
CACHE_DIR = Path(__file__).resolve().parents[1] / ".crawl_cache"


def _cache_path(url: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")


# ---------- estrazione pura (no rete, testabile) ----------

def _clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def domain_of(url: str) -> str:
    return normalize_domain(urlparse(url or "").netloc)


def split_name(byline: str):
    """byline grezza -> (first, last). Vuoto se non plausibile. MAI inventare."""
    b = _clean(byline)
    b = re.sub(r"(?i)^(di|by|a cura di|redazione)\s+", "", b)
    b = re.split(r"\s*[|,/·–-]\s*", b)[0]  # primo autore se lista
    b = _clean(b)
    if not b or len(b) > 60 or any(ch.isdigit() for ch in b):
        return "", ""
    parts = b.split()
    if not (2 <= len(parts) <= 4):
        return "", ""  # "Redazione", frasi: non è un nome persona
    return parts[0], " ".join(parts[1:])


def extract_fields(html: str, url: str) -> dict:
    """HTML -> {title, author, date, domain}. bs4 + JSON-LD + meta. Campi mancanti = ''."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "lxml")
    title = author = pub_date = ""

    # JSON-LD (NewsArticle): la fonte più affidabile quando presente
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if not isinstance(obj, dict):
                continue
            graph = obj.get("@graph", [obj])
            for node in (graph if isinstance(graph, list) else [graph]):
                if not isinstance(node, dict):
                    continue
                title = title or _clean(node.get("headline"))
                pub_date = pub_date or _clean(node.get("datePublished") or node.get("dateCreated"))
                a = node.get("author")
                if isinstance(a, list):
                    a = a[0] if a else None
                if isinstance(a, dict):
                    author = author or _clean(a.get("name"))
                elif isinstance(a, str):
                    author = author or _clean(a)

    def meta(attr, key):
        t = soup.find("meta", attrs={attr: key})
        return _clean(t.get("content")) if t and t.get("content") else ""

    title = title or meta("property", "og:title") or _clean(soup.title.string if soup.title else "")
    author = author or meta("name", "author") or meta("property", "article:author")
    if author and author.startswith("http"):  # article:author a volte è un URL profilo
        author = ""
    rel = soup.find(attrs={"rel": "author"})
    author = author or (_clean(rel.get_text()) if rel else "")
    pub_date = (pub_date or meta("property", "article:published_time")
                or meta("name", "date") or meta("itemprop", "datePublished"))

    return {
        "title": title,
        "author": author,
        "date": (pub_date or "")[:10],
        "domain": domain_of(url),
    }


# ---------- assemblaggio raw_candidates (no rete, testabile) ----------

def _blank_entry(source, domain):
    return {
        "source": source, "journalist_id": None,
        "first_name": "", "last_name": "", "publisher": "", "domain": domain, "dr": None,
        "job_title": "", "author_page": "", "beat": "",
        "articles": [],
        "email": "", "email_tier": "", "email_confirmed": False, "email_candidates": [],
        "contact_count": 0, "last_contacted": None, "response_status": None,
        "articles_count_6m": None, "years_exp": None,
    }


def build_candidates(url_records, extracted, shortlist):
    """Raggruppa gli articoli estratti in entry-persona (schema discovery_brief).

    - url_records : [{url, source, journalist_id, publisher_hint, ...}]  da urls.json
    - extracted   : {url: {title, author, date, domain}}  (solo URL parsati ok)
    - shortlist   : record DB dashboard (campi storia/tag) -> entry arricchite

    dashboard: chiave = journalist_id (porta i campi DB invariati).
    discovery: chiave = nome-normalizzato + dominio (byline dell'articolo).
    URL senza dati estratti o senza identità persona -> droppato dal chiamante.
    """
    sl_by_id = {str(r.get("journalist_id")): r for r in shortlist if r.get("journalist_id") is not None}
    by_key = {}
    dropped = []

    def get_dashboard(rec):
        jid = str(rec.get("journalist_id"))
        key = ("db", jid)
        if key not in by_key:
            db = dict(sl_by_id.get(jid, {}))
            e = _blank_entry("dashboard", db.get("domain", ""))
            # eredita i campi DB invariati (D2: NON toccarli, solo aggiungere articles)
            for k in ("journalist_id", "first_name", "last_name", "publisher", "domain",
                      "job_title", "author_page", "beat", "email", "email_tier",
                      "email_confirmed", "contact_count", "last_contacted",
                      "response_status", "articles_count_6m", "years_exp"):
                if db.get(k) not in (None, ""):
                    e[k] = db[k]
            e["domain"] = normalize_domain(e.get("domain", ""))
            by_key[key] = e
        return by_key[key]

    def get_discovery(first, last, domain, pub_hint):
        key = ("dc", normalize_name(first, last), domain)
        if key not in by_key:
            e = _blank_entry("discovery", domain)
            e["first_name"], e["last_name"] = first, last
            e["publisher"] = pub_hint or domain
            by_key[key] = e
        return by_key[key]

    for rec in url_records:
        url = rec.get("url", "")
        ex = extracted.get(url)
        if not ex:
            dropped.append({"url": url, "reason": "fetch/parse failed"})
            continue
        article = {
            "url": url, "date": ex["date"], "title": ex["title"],
            "on_topic": False, "in_headline": False,  # placeholder: il judge `complete` finalizza
        }
        if str(rec.get("source")) == "dashboard" and rec.get("journalist_id") is not None:
            get_dashboard(rec)["articles"].append(article)
        else:
            first, last = split_name(ex["author"] or rec.get("name_hint", ""))
            if not (first and last):
                dropped.append({"url": url, "reason": "no parsable byline", "title": ex["title"]})
                continue
            get_discovery(first, last, ex["domain"], rec.get("publisher_hint", "")) \
                ["articles"].append(article)

    return list(by_key.values()), dropped


# ---------- fetch (rete, crawl4ai) ----------

async def _fetch_all(urls):
    """url -> html via crawl4ai. {} per i falliti (drop loggato a valle)."""
    from crawl4ai import AsyncWebCrawler, CacheMode
    out = {}
    async with AsyncWebCrawler(verbose=False) as crawler:
        for url in urls:
            try:
                res = await crawler.arun(url=url, cache_mode=CacheMode.BYPASS)
                if res and res.success and (res.html or res.cleaned_html):
                    out[url] = res.html or res.cleaned_html
            except Exception:
                pass
    return out


def harvest_extracted(urls, use_cache: bool, cache_dir: Path = CACHE_DIR):
    """url -> campi estratti, servendo dalla cache disco quando disponibile.

    Re-run di URL già in cache = zero download, zero token modello (D6).
    -> (extracted: {url: fields}, n_cache_hits, n_fetched)
    """
    if use_cache:
        cached = {u: json.loads(_cache_path(u, cache_dir).read_text(encoding="utf-8"))
                  for u in urls if _cache_path(u, cache_dir).exists()}
    else:
        cached = {}
    to_fetch = [u for u in urls if u not in cached]

    html_by_url = asyncio.run(_fetch_all(to_fetch)) if to_fetch else {}
    fresh = {u: extract_fields(h, u) for u, h in html_by_url.items()}
    if use_cache and fresh:
        cache_dir.mkdir(parents=True, exist_ok=True)
        for u, fields in fresh.items():
            _cache_path(u, cache_dir).write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")

    extracted = {**cached, **fresh}
    return extracted, len(cached), len(fresh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--no-cache", action="store_true", help="bypassa la cache disco crawl4ai")
    ap.add_argument("--allow-network", action="store_true",
                    help="explicitly permit fetching candidate article pages")
    args = ap.parse_args()
    if not args.allow_network:
        ap.error("article fetching requires network access; pass --allow-network to proceed")

    p = run_paths(args.run_dir)
    urls_path = p["tmp"] / "urls.json"
    if not urls_path.exists():
        raise SystemExit(f"manca {urls_path} (il subagent discovery non ha scritto urls.json?)")
    url_records = json.loads(urls_path.read_text(encoding="utf-8")).get("urls", [])
    sl_path = p["tmp"] / "dashboard_shortlist.json"
    shortlist = json.loads(sl_path.read_text(encoding="utf-8")) if sl_path.exists() else []
    if isinstance(shortlist, dict):
        shortlist = shortlist.get("candidates") or shortlist.get("shortlist") or []

    urls = [r.get("url", "") for r in url_records if r.get("url")]
    extracted, n_cache, n_fetch = harvest_extracted(
        urls, use_cache=not args.no_cache, cache_dir=p["tmp"] / "crawl_cache")

    candidates, dropped = build_candidates(url_records, extracted, shortlist)

    p["tmp"].mkdir(parents=True, exist_ok=True)
    (p["tmp"] / "raw_candidates.json").write_text(
        json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2), encoding="utf-8")
    (p["tmp"] / "harvest_log.json").write_text(json.dumps({
        "urls_in": len(urls), "cache_hits": n_cache, "fetched": n_fetch,
        "candidates": len(candidates), "dropped": dropped,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    n_db = sum(1 for c in candidates if c["source"] == "dashboard")
    n_dc = len(candidates) - n_db
    arts = sum(len(c["articles"]) for c in candidates)
    print(f"HARVEST OK urls={len(urls)} cache_hits={n_cache} fetched={n_fetch} "
          f"dashboard={n_db} discovery={n_dc} articles={arts} dropped={len(dropped)}")


if __name__ == "__main__":
    main()
