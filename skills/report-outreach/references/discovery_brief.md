# discovery_brief — evidenze simmetriche per entrambe le sorgenti (D2)

La discovery (Sonnet, segue `../journalist-finder/SKILL.md` per metodo di ricerca,
WebSearch/WebFetch) produce UN SOLO `.tmp/candidates.json` che copre:

1. **Shortlist dashboard** (`.tmp/dashboard_shortlist.json`, output di `00_fetch_dashboard.py`):
   per OGNI nome in shortlist, raccogliere le stesse evidenze articoli dei discovery.
   I campi DB (tag, storia outreach) sono GIÀ nel record: NON toccarli, solo aggiungere
   `articles` (+ `author_page`/`job_title` se mancanti e trovati).
2. **Discovery nuovi**: target 25-30 candidati (buffer 2×, D8) via seed_publishers del
   plan + discovery aperta. Per loro vale tutto journalist-finder: evidenze + email
   scraped se pubblicata (tier A) + `email_candidates`.

## Formato entry (unificato)

```json
{
  "source": "dashboard | discovery",
  "journalist_id": 123,
  "first_name": "…", "last_name": "…",
  "publisher": "…", "domain": "…", "dr": null,
  "job_title": "…", "author_page": "https://…", "beat": "…",
  "articles": [
    {"url": "…", "date": "2026-05-12", "title": "…", "on_topic": true, "in_headline": true}
  ],
  "email": "", "email_tier": "", "email_confirmed": false,
  "email_candidates": [],
  "contact_count": 0, "last_contacted": null, "response_status": null,
  "articles_count_6m": null, "years_exp": null
}
```

Le entry dashboard si copiano dalla shortlist e si arricchiscono con `articles`.
Le entry discovery nascono da zero (`journalist_id: null`, campi storia null).

## Regole ferree (ereditate + nuove)

1. `on_topic`/`in_headline` valutati contro `topic_core` + `headline_hooks` del plan.
2. MAI inventare email, articoli o date. Evidenza senza URL = non esiste.
3. 1 entry per persona (freelancer: publisher = testata dell'articolo on-topic top).
4. La discovery NON scora, NON seleziona, NON chiama Hunter: produce SOLO candidates.json.
   Scoring e tutto il resto = tool Python deterministici lanciati dopo.
5. Stesse evidenze per tutti: un candidato dashboard senza articoli on-topic trovati
   resta nel file con `articles: []` (prenderà score topic 0 — corretto, non un bug).
6. **Blocked domains** declared in the caller's config are excluded before scoring and remain excluded in QA.
