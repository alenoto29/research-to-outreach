# Methods supported by the calculator

`report-writer/tools/compute.py` implements a limited set of deterministic methods. Review assumptions and input shape before using a result.

| Method | Required input shape | Important limit |
|---|---|---|
| Descriptive statistics | `series` of numeric observations | Does not establish representativeness or causality |
| Percentage change | Ordered values in `series` | A change between endpoints is not attribution |
| Event-study CAR | `series`, `event_index`, `window` | Normal-approximation inference is not a full causal design |
| Pearson correlation | Paired `x`, `y` arrays | Association only; sensitive to outliers and common trends |
| Pass-through | Paired wholesale/retail series | Linear specification and timing must be justified |
| Lead/lag | Paired ordered `x`, `y` series | Search window must be pre-specified; correlation is not causation |
| Cross-country comparison | `it`, `other` series | Requires comparable definitions, periods and units |
| Cooling-envelope sensitivity | Explicit conductance, temperature, duration, SEER and tariff | Narrow simplified model, not a building or bill simulation |
| Older/newer efficiency comparison | Thermal load, two SEER values and tariff | Holds thermal load constant by assumption |

Methods requiring additional modeling (for example GARCH, structural breaks or synthetic control) are not computed by this package and return an explicit uncomputed flag. Never replace that flag with a plausible-looking number.
