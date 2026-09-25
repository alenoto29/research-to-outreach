# Brief output contract — consultant deliverable

The consultant bot's output. Given a **topic** (and optionally an **angle**), it
produces this brief: 2 distinct angles + 10 feasible analyses, each grounded in a
harvested paper + an open data feed, each scored for top-tier pickup potential.
Alessandro picks 1 angle + 3-4 analyses → then we build the report.

Fill every field. Never invent a number — suggest the *analysis*, not its result.

---

```markdown
# Consultant brief — <TOPIC>
date: <YYYY-MM-DD>   |   papers harvested: <N>   |   data: papers digest at <path>

## Topic framing
<2-3 lines: what the topic is, why it's timely for a top-tier IT outlet, the hook.>

## Angle A — <name>
- **Thesis:** <the one-sentence claim the report would prove>
- **Headline number (target):** <the quotable stat we'd aim to produce — described, not faked>
- **Paper basis:** <1-3 harvested papers that supply the method/credibility> [#refs]
- **Journalist hook:** <why a top-tier editor bites — the wallet/national angle>
- **Why authority:** <what makes this defensible & exclusive>

## Angle B — <name>
<same fields — must be genuinely DIFFERENT framing, not a variant of A>

## 10 unique analyses
Each = open data feed x paper-grade method = a number nobody else has.

| # | Analysis | Method | Data feed(s) | Output metric | Diff. | Pickup | Feasible |
|---|----------|--------|--------------|---------------|-------|--------|----------|
| 1 | <name> | <method from toolkit> | <feed from data_sources> | <the € or % it yields> | E/M/H | H/M/L | yes/no |
| ... | | | | | | | |
| 10| | | | | | | |

Legend: Diff = difficulty (Easy/Med/Hard), Pickup = top-tier appeal (High/Med/Low),
Feasible = data actually available in energy_data_sources.md (drop if no).

## Recommended combo
- **Angle:** <A or B> + analyses <ids> — <one line why this maximizes pickup x effort>

## Papers harvested (top of digest)
<ranked table from fetch_papers.py .md, top ~8, for traceability>
```

---

## QA gates (before handing the brief over)

1. **2 angles are distinct** — different thesis, not rewordings.
2. **10 analyses, each feasible** — every one names a real feed from
   `energy_data_sources.md`; infeasible ones dropped and replaced.
3. **Every analysis maps to a method** in `methods_toolkit.md`.
4. **At least 3 analyses rated Pickup=High** — or the topic is too niche; flag it.
5. **Paper basis is real** — cite from the harvested digest, never invent a title.
6. **No fabricated results** — outputs are described as *targets*, never asserted.
7. **Headline numbers are wallet/national** where possible (top-tier rule).

## Notes

- If `--angle` was given, still produce 2 angles but bias both toward it, and weight
  analyses that serve it.
- Keep the brief skimmable: a busy person picks from the table in 60 seconds.
- The brief is input to the (future) stage-3 report writer — keep it machine-friendly
  (the analyses table is the contract).
