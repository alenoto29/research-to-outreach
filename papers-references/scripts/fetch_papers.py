#!/usr/bin/env python3
"""
fetch_papers.py — harvest relevant scientific papers for an energy report topic.

Queries free academic APIs (OpenAlex, Semantic Scholar, arXiv), normalizes them to
one schema, dedups, ranks by relevance x recency x citations, and writes:
  <out>.json   normalized papers (machine input for the consultant brief)
  <out>.md     human digest (ranked table + abstracts)

Zero third-party deps: urllib + json + xml.etree only. Runs on stock python3.

Usage:
  python3 fetch_papers.py "geopolitical risk energy prices Italy" --allow-network --since 2020 --limit 30
  python3 fetch_papers.py "<topic query>" --allow-network --since 2019 --limit 40 --out .tmp/papers

Notes:
  - OpenAlex: --mailto optionally identifies the operator. No key needed.
  - Semantic Scholar: anonymous ~1 req/s. tldr field = auto one-line summary, gold.
  - arXiv: Atom XML; energy-econ coverage is THIN, kept as a quant-method sidecar.
  - RePEc working papers are largely indexed inside OpenAlex already.
  - One failing API never kills the run; sources are queried independently.
"""

import argparse
import datetime
import json
import math
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "research-to-outreach/0.1 (optional academic metadata fetcher)"
TIMEOUT = 30

# macOS python.org builds ship without a CA bundle wired in -> SSL verify fails.
# Use certifi's bundle when available; fall back to the system default context.
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL_CTX = ssl.create_default_context()


def _get(url, headers=None, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - resilience over precision here
            if attempt == retries:
                sys.stderr.write(f"  ! request failed: {e}\n")
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def _norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


# ---------------------------------------------------------------- OpenAlex ----
def _openalex_abstract(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def fetch_openalex(query, since, limit, mailto):
    base = "https://api.openalex.org/works"
    params = {
        "search": query,
        "filter": f"from_publication_date:{since}-01-01",
        "sort": "relevance_score:desc",
        "per-page": min(limit, 50),
    }
    if mailto:
        params["mailto"] = mailto
    url = base + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    if not raw:
        return [], "request_failed"
    try:
        works = json.loads(raw).get("results", [])
    except (ValueError, AttributeError):
        return [], "invalid_response"
    out = []
    for i, w in enumerate(works):
        loc = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "title": w.get("display_name") or "",
            "authors": [a["author"]["display_name"]
                        for a in (w.get("authorships") or [])
                        if a.get("author")][:6],
            "year": w.get("publication_year"),
            "venue": loc.get("display_name") or "",
            "abstract": _openalex_abstract(w.get("abstract_inverted_index")),
            "tldr": "",
            "citations": w.get("cited_by_count") or 0,
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "url": w.get("id") or "",
            "source": "openalex",
            "_rank": i,
        })
    return out, None


# -------------------------------------------------------- Semantic Scholar ----
def fetch_s2(query, since, limit):
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "title,abstract,year,citationCount,tldr,venue,authors,externalIds,url"
    params = {
        "query": query,
        "limit": min(limit, 50),
        "fields": fields,
        "publicationDateOrYear": f"{since}:",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    raw = _get(url)
    if not raw:
        return [], "request_failed"
    try:
        records = json.loads(raw).get("data", []) or []
    except (ValueError, AttributeError):
        return [], "invalid_response"
    out = []
    for i, p in enumerate(records):
        ext = p.get("externalIds") or {}
        tldr = (p.get("tldr") or {}).get("text") or ""
        out.append({
            "title": p.get("title") or "",
            "authors": [a.get("name", "") for a in (p.get("authors") or [])][:6],
            "year": p.get("year"),
            "venue": p.get("venue") or "",
            "abstract": p.get("abstract") or "",
            "tldr": tldr,
            "citations": p.get("citationCount") or 0,
            "doi": ext.get("DOI", ""),
            "url": p.get("url") or "",
            "source": "s2",
            "_rank": i,
        })
    return out, None


# -------------------------------------------------------------------- arXiv ----
def fetch_arxiv(query, limit):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 30),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    raw = _get(url)
    if not raw:
        return [], "request_failed"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return [], "invalid_response"
    out = []
    for i, e in enumerate(root.findall("a:entry", ns)):
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
        published = e.findtext("a:published", default="", namespaces=ns) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [a.findtext("a:name", default="", namespaces=ns)
                   for a in e.findall("a:author", ns)][:6]
        link = e.findtext("a:id", default="", namespaces=ns) or ""
        out.append({
            "title": title,
            "authors": authors,
            "year": year,
            "venue": "arXiv",
            "abstract": summary,
            "tldr": "",
            "citations": 0,
            "doi": "",
            "url": link,
            "source": "arxiv",
            "_rank": i,
        })
    return out, None


# ------------------------------------------------------------- merge + rank ----
def dedup(papers):
    seen = {}
    for p in papers:
        key = p["doi"].lower() if p.get("doi") else _norm_title(p["title"])
        if not key:
            continue
        if key not in seen:
            seen[key] = p
        else:  # keep the richer record (prefer one with tldr/abstract/citations)
            cur = seen[key]
            score = lambda x: (bool(x["tldr"]), bool(x["abstract"]), x["citations"])
            if score(p) > score(cur):
                p["source"] = f"{cur['source']}+{p['source']}"
                seen[key] = p
    return list(seen.values())


def rank(papers, since, now_year):
    span = max(1, now_year - since)
    max_cit = max((p["citations"] for p in papers), default=0) or 1
    for p in papers:
        rel = 1.0 / (1.0 + p.get("_rank", 0))               # in-source relevance
        rec = ((p["year"] or since) - since) / span         # newer = higher
        rec = min(max(rec, 0.0), 1.0)
        cit = math.log1p(p["citations"]) / math.log1p(max_cit)
        p["score"] = round(0.50 * rel + 0.30 * rec + 0.20 * cit, 4)
    papers.sort(key=lambda x: x["score"], reverse=True)
    return papers


def source_status(records, error=None):
    if error:
        return {"status": "error", "error": error, "count": 0}
    return {"status": "results" if records else "empty", "count": len(records)}


# ----------------------------------------------------------------- outputs ----
def write_md(papers, query, path, source_statuses):
    lines = [
        f"# Papers digest — `{query}`",
        "",
        f"{len(papers)} papers, ranked by relevance x recency x citations.",
        "",
        "## Source retrieval status",
        "",
    ]
    for source, status in source_statuses.items():
        detail = f" — {status['error']}" if status.get("error") else ""
        lines.append(f"- `{source}`: **{status['status']}** ({status['count']} records){detail}")
    lines += [
        "",
        "| # | Title | Year | Cit. | Venue | Source | Score |",
        "|---|-------|------|------|-------|--------|-------|",
    ]
    for i, p in enumerate(papers, 1):
        t = p["title"].replace("|", "/")[:90]
        v = (p["venue"] or "").replace("|", "/")[:28]
        lines.append(f"| {i} | {t} | {p['year'] or '-'} | {p['citations']} | "
                     f"{v} | {p['source']} | {p['score']} |")
    lines += ["", "---", "", "## Abstracts / TLDRs", ""]
    for i, p in enumerate(papers, 1):
        lines.append(f"### {i}. {p['title']}")
        meta = f"{', '.join(p['authors'][:3])}"
        if p["year"]:
            meta += f" ({p['year']})"
        if p["venue"]:
            meta += f" — *{p['venue']}*"
        lines.append(meta)
        if p["doi"]:
            lines.append(f"DOI: {p['doi']}")
        if p["url"]:
            lines.append(f"<{p['url']}>")
        body = p["tldr"] or p["abstract"]
        if body:
            lines.append("")
            lines.append(("**TLDR:** " if p["tldr"] else "") + body[:1200])
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", help="topic query, e.g. 'geopolitical risk energy prices'")
    ap.add_argument("--since", type=int, default=2019, help="min publication year")
    ap.add_argument("--limit", type=int, default=30, help="max results per source")
    ap.add_argument("--out", default=".tmp/papers", help="output path stem (no ext)")
    ap.add_argument("--mailto", default="", help="email for OpenAlex polite pool")
    ap.add_argument("--no-arxiv", action="store_true", help="skip arXiv (thin for energy-econ)")
    ap.add_argument("--allow-network", action="store_true",
                    help="explicitly permit requests to OpenAlex, Semantic Scholar and arXiv")
    args = ap.parse_args()
    if not args.allow_network:
        ap.error("paper discovery uses public network services; pass --allow-network to proceed")

    now_year = datetime.datetime.now().year
    papers = []
    print(f"OpenAlex ...", file=sys.stderr)
    openalex, openalex_error = fetch_openalex(args.query, args.since, args.limit, args.mailto)
    papers += openalex
    print(f"Semantic Scholar ...", file=sys.stderr)
    semantic_scholar, semantic_error = fetch_s2(args.query, args.since, args.limit)
    papers += semantic_scholar
    source_statuses = {
        "openalex": source_status(openalex, openalex_error),
        "semantic_scholar": source_status(semantic_scholar, semantic_error),
    }
    if not args.no_arxiv:
        print(f"arXiv ...", file=sys.stderr)
        arxiv, arxiv_error = fetch_arxiv(args.query, args.limit)
        papers += arxiv
        source_statuses["arxiv"] = source_status(arxiv, arxiv_error)
    else:
        source_statuses["arxiv"] = {"status": "skipped", "count": 0}

    papers = dedup(papers)
    papers = rank(papers, args.since, now_year)
    for p in papers:
        p.pop("_rank", None)

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out + ".json", "w") as f:
        json.dump({"query": args.query, "since": args.since,
                   "count": len(papers), "source_status": source_statuses,
                   "papers": papers}, f, ensure_ascii=False, indent=2)
    write_md(papers, args.query, args.out + ".md", source_statuses)
    print(f"\n{len(papers)} papers -> {args.out}.json + {args.out}.md", file=sys.stderr)


if __name__ == "__main__":
    main()
