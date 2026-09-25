# Outreach plan schema

An approved plan is JSON with at least:

```json
{
  "topic": "example research topic",
  "angle": "one-sentence, source-backed framing",
  "report_type": "TOP",
  "run_date": "2030-01-01",
  "topic_core": ["term one", "term two"],
  "topic_expansion": ["related phrase"],
  "headline_hooks": ["result key: example_metric"],
  "email_pattern_hints": {},
  "publisher_email_domain": {},
  "weights_version": "v1"
}
```

`report_type` must be `TOP` or `MID` when the optional domain-rating gate runs. Dates are explicit; no system date is substituted. Hooks must map to a reviewed report source or result key. Do not put contacts or credentials in the plan.
