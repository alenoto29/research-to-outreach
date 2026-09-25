# Paper APIs — free, no-key, energy-econ fit

All free, no API key required. `scripts/fetch_papers.py` wraps the first three.
Backbone = **OpenAlex + Semantic Scholar**. arXiv = optional sidecar. Crossref =
metadata glue.

| API | Free | Key | Energy-econ | Best for |
|-----|------|-----|-------------|----------|
| OpenAlex | yes | no | **strong** | broad corpus, indexes RePEc working papers |
| Semantic Scholar | yes | optional | **strong** | TLDR auto-summaries + citation graph |
| arXiv | yes | no | thin | quant-method preprints (GARCH, ML forecasting) |
| Crossref | yes | no | metadata | DOI resolution, citation counts, dates |

> Energy-economics literature lives in journals (Energy Economics, Energy Policy,
> The Energy Journal, Energy Research & Social Science) and RePEc working papers —
> **NOT arXiv**. Lead with OpenAlex + S2.

---

## OpenAlex — `api.openalex.org`

Broadest free index (~250M works). Indexes RePEc, so working papers come for free.

```
GET https://api.openalex.org/works
  ?search=geopolitical risk energy prices
  &filter=from_publication_date:2020-01-01
  &sort=relevance_score:desc
  &per-page=25
  &mailto=<operator-contact>              # optional polite-pool contact
```

Useful fields: `display_name`, `publication_year`, `cited_by_count`, `doi`,
`primary_location.source.display_name` (venue), `authorships[].author.display_name`,
`abstract_inverted_index` (reconstruct — `fetch_papers.py` does it).

Extra filters worth knowing:
- `concepts.id:` / `topics.id:` — narrow to a field (energy economics)
- `is_oa:true` — only open-access (full text reachable)
- `cited_by_count:>50` — high-impact only

No key. Polite pool just wants `mailto`. Rate ~10 req/s with mailto.

---

## Semantic Scholar — `api.semanticscholar.org`

Best **TLDR** (one-line auto-summary) — fastest way to triage 40 papers.

```
GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query=energy price volatility geopolitical
  &limit=25
  &fields=title,abstract,year,citationCount,tldr,venue,authors,externalIds,url
  &publicationDateOrYear=2020:
```

Anonymous ~1 req/s (the script tolerates 429 with backoff). Free API key (from
semanticscholar.org/product/api) lifts the limit — drop it in a header
`x-api-key:` only if you start batching many topics.

`externalIds.DOI` = dedup key across sources. `tldr.text` = the gold field.

---

## arXiv — `export.arxiv.org` (sidecar only)

Atom XML, not JSON. Thin for energy economics; use for **quant methods**
(volatility models, ML price forecasting, time-series econometrics).

```
GET http://export.arxiv.org/api/query
  ?search_query=all:energy price forecasting GARCH
  &max_results=20
  &sortBy=relevance
```

Relevant categories: `econ.GN` (general economics), `q-fin.ST` (statistical
finance), `stat.AP` (applied stats). `fetch_papers.py --no-arxiv` skips it.

---

## Crossref — `api.crossref.org` (glue, not search)

Resolve a DOI → clean metadata, citation count, exact publication date, license.

```
GET https://api.crossref.org/works?query=...&filter=from-pub-date:2020-01-01&mailto=...
GET https://api.crossref.org/works/<DOI>        # resolve one
```

Use when you have a DOI and need authoritative venue/date for a citation in the
report. Not a primary discovery tool here.

---

## RePEc / IDEAS — covered via OpenAlex

RePEc (`ideas.repec.org`) = the econ working-paper frontier (NBER, CESifo, Banca
d'Italia Temi di Discussione). No clean JSON API. **OpenAlex already indexes most
RePEc records**, so query OpenAlex and filter for working papers rather than
scraping IDEAS. For Italian central-bank papers specifically, also worth a manual
look at `bancaditalia.it/pubblicazioni/temi-discussione`.

---

## Gotchas

- arXiv returns **Atom XML**, everything else JSON. Script handles both.
- OpenAlex abstracts are an **inverted index** — must be reconstructed to read.
- S2 anonymous rate is ~1 req/s — don't loop topics without sleeps or a key.
- DOIs come with/without the `https://doi.org/` prefix — normalize before dedup.
- Optionally pass your own contact address for the OpenAlex polite pool; never embed a personal address in a shared config or example.
- Coverage gaps are real: a 2026 working paper may not be indexed yet — cross-check
  the author's page / SSRN if a key source seems missing.
