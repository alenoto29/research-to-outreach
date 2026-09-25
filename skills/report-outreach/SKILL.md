# Outreach workflow

Produce a human-reviewable shortlist and draft pitches for a completed research report. This is a candidate-ranking and QA workflow, not a mailer.

## Required inputs

- A reviewed report and its approved topic/angle.
- An input candidate JSON file. It may contain invented candidates for tests or records the operator is authorized to use.
- A plan declaring target audience, inclusion/exclusion rules, dates and any configured score weights.

## Human gates

1. A human approves the plan before discovery/analysis begins.
2. A human verifies the evidence and rationale attached to candidates.
3. A human reviews the final shortlist and every pitch.
4. Any real-world contact, paid enrichment, network lookup, database writeback or send happens outside the offline path and requires explicit configuration and authorization.

## Runtime rules

- Never invent email addresses or evidence. Keep unresolved addresses out of contact-ready exports.
- Ranking scores are configured heuristics, not probabilities or calibrated predictions. Domain authority may be a tie-breaker only when the plan explicitly says so.
- Cooldown, blacklist, tier and per-domain caps are deterministic filters; document their source in the plan/config.
- QA validates record shape, duplicates, configured constraints and required rationale fields. It cannot prove that the rationale is factually accurate.
- Dashboard base, tokens, public-domain fetches and paid-provider credentials must be supplied explicitly. There is no default endpoint; no service is contacted by the offline example.

## Outputs

Machine-readable intermediate files, a deterministic candidate CSV and a run log with exclusions, replacements, unresolved addresses and QA result. Draft pitches remain unsent text for human editing.
