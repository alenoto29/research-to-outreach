# Provenance and release license review

Status: **public release approved for this extracted package**. Alessandro confirmed the MIT license and publication to `alenoto29/research-to-outreach` on 2026-09-28. The license covers the original/adapted code and documentation in this repository, not third-party services or content retrieved at runtime.

## Source and adaptation

- Source repository: `pursuance-hub`, baseline commit `c652513518363d1d11fce1953bbf7bc43f149cfe`.
- Source modules: research consultant and paper fetcher; deterministic report calculations/validation; journalist scoring/email-tier logic; report candidate selection and QA.
- The source owner authorized publication of code in the portfolio plan and selected MIT for this package. This does not grant rights over fetched data, third-party content, trademarks or external services.
- The initial standalone commit contains the extracted modules and synthetic example; later commits add the user-facing instructions and Serper search. Historical claims and benchmark numbers are not carried over as package results.

## Third-party material and dependencies

- No historic topics, collected paper abstracts/full text, journalist/contact data, company database exports, historic report files/charts, spreadsheet models, caches, prompts from prior runs, credentials or company deployment configuration are included.
- `fetch_papers.py` calls OpenAlex, Semantic Scholar and arXiv only with `--allow-network`. `search_web.py` uses the operator's `SERPER_API_KEY` on explicit invocation. API terms and source-content licenses apply; no fetched content is distributed here.
- Optional email enrichment and dashboard tools are present but not part of the Serper-only path or offline example. Any actual use requires separate terms, cost and authorization checks.
- Core calculations and ranking use the Python standard library. Optional tested versions: `python-docx 1.2.0` (MIT) and `matplotlib 3.10.9` (Matplotlib license agreement; distribution bundles separate third-party font/colormap notices). They are installed from upstream and not vendored.
- The chart under `examples/setpoint-sweep/` was generated from invented model inputs. It contains no real-world dataset or third-party art.
- Employer-specific report boilerplate, brand assets, examples and historical material were removed; the report-writing contract is generic.

## Findings and release review

- Resolved: offline calculations/tests, explicit network and paid-service gates, no default dashboard host, generic report style and invented end-to-end case.
- MIT was explicitly confirmed by the owner. No dependency code is vendored; optional Python packages are installed separately and retain their own licenses. Search and outreach integrations require the operator's own credentials or explicit network flags; the shipped example and tests are offline.
- The released Git history is the new, standalone repository (not the private source history). The tracked tree and its three preparatory commits were checked for credentials, company data, imported assets and private paths. The only bundled chart and outreach example use invented values/contacts. Public-release approval applies to this reviewed package; any later addition of data or third-party material needs its own review.

The tools do not validate factual claims automatically, and no new real-topic run or live Serper query has been verified. The repository's MIT license is in [`LICENSE`](LICENSE).
