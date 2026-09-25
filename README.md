# Research to outreach

A small, human-guided workflow for turning a research question into a sourced analysis, an editorial report and a short, evidence-based outreach shortlist. The Python tools calculate and validate structured data; they do not replace research judgment, write or send emails autonomously, or validate factual claims by themselves.

## Quick start (offline)

Requirements: Python 3.10+ and the standard library for the calculator and outreach-ranking tests.

```bash
python3 -m unittest discover -s papers-references/tests -v
python3 -m unittest discover -s report-writer/tests -v
python3 skills/journalist-finder/tests/run_tests.py
python3 skills/report-outreach/tests/run_tests.py
```

The final command is a JSON-lines calculator. Example:

```bash
printf '%s\n' '{"analysis_id":"setpoint_sweep","method":"sweep_t_in","data":{"K_cond":100,"K_inf":0,"T_ext":35,"T_in_list":[24,26,28],"seer":4,"hours_day":8,"season_days":10,"tariff_eur_kwh":0.25},"unit":"kWh and EUR","inputs":["synthetic-example.json"]}' | python3 report-writer/tools/compute.py
```

Expected calculated seasonal electricity: 22.0, 18.0 and 14.0 kWh; cost: €5.50, €4.50 and €3.50. These are arithmetic checks over explicitly invented inputs, not measured savings or a performance benchmark.

## End-to-end case

[`examples/setpoint-sweep/`](examples/setpoint-sweep/) contains the complete offline worked example: source/method notes, synthetic model inputs, result JSON, a short report and generated chart, invented candidate records and a pitch draft. The example keeps observed/public-source facts separate from assumptions. No journalist, publication, email address or contact detail in the case is real.

The conceptual sequence is:

1. **Research** — use the source checklist and record title, publisher, URL, access date and the precise claim each source supports. Optional paper discovery uses public OpenAlex/Semantic Scholar endpoints and requires `--allow-network`; each API result records `results`, `empty`, `error` or `skipped` separately.
2. **Frame** — a person selects the question and angle. The research-consultant instructions are a decision aid, not an automated source-quality guarantee.
3. **Calculate** — provide validated numeric inputs to the deterministic functions in `report-writer/tools/compute.py`. Assumptions and units travel with the result. Unimplemented methods return a `DA CALCOLARE` flag.
4. **Write and visualize** — a person or explicitly chosen writing assistant drafts from computed values. `validate_briefs.py` checks placeholder-to-key references; it does not establish that a claim is true. Charts and report assembly are optional tools with additional Python dependencies.
5. **Review** — a human checks source fit, units, assumptions, prose, chart presence and every reported number before finalizing.
6. **Outreach** — provide a file of candidate records. Discovery and editorial rationale require human judgment. Deterministic tools deduplicate, apply configured eligibility/cooldown/tier rules and report reasons. The QA gate checks structure and policy rules, not whether an editorial reason is factually persuasive.
7. **Contact** — sending, paid email lookup, online DR lookups and any API/database writeback are separate, opt-in integrations. The offline example does none of them.

## Repository map

- `papers-references/` — research source discovery, source/method references and output contract.
- `report-writer/` — deterministic analysis functions, report validation, chart/report helpers and the staged human review workflow.
- `skills/journalist-finder/` — topic-plan contract and deterministic scoring, email-pattern formatting, CSV writing and QA.
- `skills/report-outreach/` — unified candidate scoring, selection, optional integrations and tests.
- `examples/` — synthetic worked case; no historic topic runs or contact records.

These are related modules, not one fully automated program. Steps involving editorial choices, source verification and approval remain human gates.

## Optional dependencies and network use

The arithmetic functions and deterministic ranking tests use Python's standard library. Report DOCX output needs `python-docx`; chart rendering needs `matplotlib` (`pip install -r requirements-optional.txt`). Paper fetching, public DR queries and scraping require explicit network flags. Paid email enrichment requires `--allow-paid-hunter` plus the operator's `HUNTER_API_KEY` and an approved budget. No external service is used by the offline quickstart.

Dashboard fetch, writeback and sent-mark tools require the operator to supply an API base and token explicitly. Do not point them at a service without authorization. Email send is never performed by these scripts.

## Quality and limitations

- Tests exercise deterministic behavior on synthetic fixtures; passing tests do not measure relevance, fact accuracy, journalistic response, or campaign outcomes.
- An `email_tier` describes the method/evidence in the input, not deliverability. Never invent an address. Unknowns remain unknown.
- Scores are configured ranking heuristics, not probabilities or calibrated predictions.
- The cooling model is a narrow envelope-load calculation, not a building simulation or universal energy model. Assumptions (including ignored gains/duty cycle in this sweep) must be stated.
- Source-data rights and API terms remain the user's responsibility. No historical reports, research caches, private contacts, company data, logo, branded template or third-party paper text are included.
- The code is an extraction and adaptation of internal tools. The repository license is intentionally pending review; it is not cleared for publication yet. See [`PROVENANCE.md`](PROVENANCE.md).

## Provenance and AI assistance

The tools were extracted and adapted from Alessandro Noto's internal PR research/report and outreach workflow. AI assistance was used for repository preparation and code adaptation. Original human review gates are retained; no claim is made that the examples demonstrate production performance. Third-party references are attributed where used; exact license clearance and repository license selection remain release gates.
