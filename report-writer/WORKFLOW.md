# Report workflow and review gates

The report module combines deterministic calculations with separate human/AI-assisted authoring stages. The stages are related but not an unattended pipeline.

## Stages

1. **Frame** — a human clarifies the research question, audience, scope and assumptions. Output: `intent.md`.
2. **Research** — collect and inspect sources; draft a consultant brief with candidate analyses. Human selects which analyses to pursue.
3. **Scan** — implement or select deterministic calculations, produce a structured result file and a shallow set of candidate findings. Human selects findings.
4. **Focus interview** — ask one focused question at a time to clarify each selected finding's meaning, caveats and intended audience. Output: a human-approved focus note.
5. **Deepen** — calculate only approved findings, write a provenance-bearing number file and a summary. An independent reviewer checks the assumptions and output before the structure stage.
6. **Structure** — create writing, chart and layout briefs. All computed values must reference keys in the result file; literal result numbers are not hand-entered into briefs.
7. **Validate briefs** — run `tools/validate_briefs.py`. Missing or orphaned keys stop the workflow.
8. **Draft in parallel** — a writing assistant drafts prose and a charting assistant authors/render charts from approved result keys. They do not recalculate or infer missing results.
9. **Reconcile** — `tools/docx_writer.py` and the reconciliation log verify that reported/chart values map to approved result keys. Missing charts or unmatched values block the draft.
10. **Human review** — review sources, claims, assumptions, accessibility and visual clarity. Feedback is recorded before final assembly. A language edit cannot change data, links or claims.

## Runtime rules

- Deterministic Python owns numeric calculations. Writing assistance may explain, summarize or frame only those results; it must not invent numbers.
- Unsupported methods return an explicit uncomputed flag.
- A numeric check proves arithmetic against its inputs, not that the model assumptions are valid.
- Sources must be inspected and cited for the exact factual claim they support.
- Human approval is required at question selection, finding selection, independent analysis review and final draft review.
- Use only generic, original report styling. This distribution contains no employer template, brand assets, company boilerplate or historic report.

## Output contracts

- Analysis result: `report_keys` map each output name to a value, unit, source/input references and calculation method.
- Brief: placeholders must be a subset of `report_keys`; checked by `tools/validate_briefs.py`.
- Writer/chart logs: each placeholder resolution maps back to a result key.
- Final report: no uncomputed placeholder, missing required chart, orphan value or unresolved reviewer feedback.

This workflow preserves stages and review gates but does not ship a model agent, global skill, company data source, CMS connector or automatic publication step.
