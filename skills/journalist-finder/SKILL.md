# Candidate discovery workflow

Use this workflow to turn an approved topic plan and sourced candidate records into a ranked, reviewable list. Discovery itself may require human research or explicitly enabled public web access; Python tools handle scoring, formatting and deterministic checks.

## Rules

- The human-approved plan fixes the topic scope, seed terms, exclusions and thresholds before candidates are scored.
- Each candidate needs a source URL and evidence of relevant coverage. Missing evidence means exclude or request review, not infer.
- Email tiers describe the evidence/source method; they are not deliverability guarantees. Never infer a person's address.
- Keep input column/output contracts and identifier references stable. Record a reason for every manual removal or inclusion.
- Push/writeback is an optional separate step, requires an explicit authorized API base and token, and is never part of the local quickstart.

## Output

A CSV shortlist with source evidence, confidence tier, score and reason, plus a QA result. Human approval is required before contact or writeback.
