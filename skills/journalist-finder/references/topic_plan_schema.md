# Topic plan schema

The discovery plan is a JSON object reviewed by a human before candidate collection. Minimum fields:

- `topic`: short research subject.
- `angle`: the supported claim or question being explored, not an asserted result.
- `topic_core`: essential query terms.
- `topic_expansion`: optional related terms.
- `seed_domains`: optional site hosts selected for research.
- `email_pattern_hints`: optional, sourced pattern notes. These are not addresses and never prove an address exists.
- `market`: a declared audience region.
- `run_date`: explicit ISO date.

The plan must not contain personal contact data, API keys or unsupported factual claims.
