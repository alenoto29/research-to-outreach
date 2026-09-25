# Result-key contract

`report_keys` is the flat source of calculated numeric values used by writing and charting stages. `validate_briefs.py` checks that every placeholder used in a brief exists in this object. This validates references, not truth or model assumptions.

```json
{
  "topic": "example-topic",
  "report_keys": {
    "headline_number": 0,
    "example_metric": 0
  }
}
```

Key names use lowercase words separated by underscores, with entity, scenario and metric where useful. Include a unit with every value in the surrounding result record or key metadata. `headline_number` is required when a brief expects a headline metric.

## Brief usage

```markdown
<!-- Correct: computed values resolve by key. -->
The model output was {example_metric} [unit].

<!-- Incorrect: do not hard-code a calculated result. -->
The model output was 42 [unit].
```

Published facts still require a direct citation. A placeholder match does not prove an external fact or validate the calculation.
