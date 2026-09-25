# Worked example: a deliberately narrow cooling sweep

This example demonstrates the arithmetic-to-report-to-pitch contract. The building inputs and the fictional outlet/candidate are invented. The stated sources are for method context only; they do not validate the invented parameter values or the output as a real-world estimate.

## Research notes

- European Commission, Commission Delegated Regulation (EU) No 626/2011, official text: <https://eur-lex.europa.eu/eli/reg_del/2011/626/oj> — regulatory context for air-conditioner energy labelling terminology; this example does not extract numeric inputs from the regulation.
- Accessed: 2026-09-25. Verify current content and reuse terms before relying on it for a real report.

## Reproduce the calculation

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
p = Path("report-writer/tools/compute.py")
s = importlib.util.spec_from_file_location("compute", p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
for row in m.sweep_t_in(100, 0, 35, [24, 26, 28], 4, 8, 10, 0.25):
    print(row)
PY
```

Independent arithmetic, for setpoint `T_in`: `100 W/K × (35 − T_in) K × 8 h/day × 10 days ÷ 1000 ÷ 4`. This gives 22, 18 and 14 kWh; at €0.25/kWh, €5.50, €4.50 and €3.50. Raising the indoor setpoint reduces this simplified envelope load. It does not model total household consumption or a bill.

## Short report draft

**A higher cooling setpoint lowers the envelope load in a deliberately simplified example.** With a constant 35°C outdoor temperature, hypothetical 100 W/K conductance, eight operating hours a day for ten days, and fixed SEER 4, the model gives 22 kWh at 24°C, 18 kWh at 26°C and 14 kWh at 28°C. The pattern follows directly from the assumed temperature difference; it is not measured household data. Solar and internal gains, infiltration, thermal mass, equipment cycling, changing weather and user behavior are excluded. The calculation should be treated as a transparent sensitivity illustration, not a savings forecast.

## Fictional outreach record and pitch

All candidate fields below are invented for this test fixture and are not contact data.

| candidate | outlet | coverage evidence | email | tier | decision |
|---|---|---|---|---|---|
| Alex Example | Example Climate Desk | Fictional profile says they cover household cooling | none supplied | none | Hold: no address; do not infer one |

**Draft pitch (not sent):**

> Subject: A small, reproducible cooling-setpoint sensitivity example
>
> Hello Alex, I put together a clearly labeled toy calculation showing how a cooling setpoint changes one simplified envelope-load term. It excludes weather variability, solar/internal gains and equipment cycling, so it is not a household-savings estimate. Would a short methods note on transparent assumptions be useful for your climate coverage?

The pitch is grounded only in this case's calculation and fictional coverage record. A human must verify that a real recipient covers the subject and approve any contact. No address is fabricated and no send/writeback is performed.
