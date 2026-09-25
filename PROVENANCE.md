# Provenance and release license review

Status: **not cleared for public release**. No license has been selected or added.

## Source and adaptation

- Source repository: `pursuance-hub`, baseline commit `c652513518363d1d11fce1953bbf7bc43f149cfe`.
- Source modules: research consultant and paper fetcher; deterministic report calculations/validation; journalist scoring/email-tier logic; report candidate selection and QA.
- The source owner authorized publication of code in the portfolio plan; that authorization does not settle third-party licenses, data rights, trade marks or a license grant to downstream users.
- Public package changes made during extraction must be identified in the eventual first commit/review. Historical claims and benchmark numbers are not carried over as package results.

## Third-party material and dependencies

- No historic topics, collected paper abstracts/full text, journalist/contact data, company database exports, report files, spreadsheet models, charts, caches, prompts from prior runs, credentials or company deployment configuration are included.
- `fetch_papers.py` calls OpenAlex and Semantic Scholar when explicitly run with network access. Their API terms and source-content licenses apply; the program does not redistribute fetched content in this repository.
- Optional email enrichment and dashboard integrations are not part of the offline example. Any later inclusion requires a separate terms/cost/authorization review.
- Core calculations and ranking use the Python standard library. Optional tested versions: `python-docx 1.2.0` (MIT) and `matplotlib 3.10.9` (Matplotlib license agreement; distribution bundles separate third-party font/colormap notices). They are installed from upstream and not vendored.
- `fetch_papers.py` calls OpenAlex, Semantic Scholar and arXiv only with `--allow-network`; outputs distinguish `error` from `empty`. API terms and underlying source-content rights apply. No fetched records or paper text are distributed.
- Employer-specific report boilerplate, brand assets, examples and historical material were removed; the report-writing contract is generic.

## Findings and release gate

- Resolved: offline calculations/tests, explicit network and paid-service gates, no default dashboard host, generic report style and invented end-to-end case.
- Pending: final license selection and coordinator approval of source authorization, optional dependencies, API terms and exact commit.

Coordinator must review the exact final tree, dependency/source attribution inventory, license compatibility, tests, generated artifacts and commit history, then approve publication. This file is an audit record, not a license grant.
