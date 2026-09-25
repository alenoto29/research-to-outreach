---
name: research-consultant
description: Turn a research question into a source-backed analysis brief with explicit methods, inputs and human review gates.
---

# Research consultant workflow

## Intent

Produce a concise brief that helps a human decide whether a proposed analysis is feasible and worth pursuing. The brief proposes a question and method; it must not report an uncomputed result.

## Runtime rules

- Cite sources that were actually inspected. Record the title, publisher, URL, access date and the specific fact or method supported.
- Distinguish source facts, proposed calculations, assumptions and unknowns.
- A paper can support a method; it does not supply the result of applying that method to a different dataset.
- If data or a method is unavailable, mark the analysis uncomputed and stop that claim from entering a final report.
- Search and retrieval are optional network steps. `scripts/fetch_papers.py` requires `--allow-network` and is never run by the offline quickstart.
- A human chooses the angle, reviews sources, approves the calculation plan and signs off on report claims.

## Input

A topic/question, audience, scope and optional time/place constraints. Missing scope is a clarification gate, not a reason to invent an answer.

## Output contract

Create a brief with: question; candidate angles; each proposed analysis with method, data source, output metric, assumptions and feasibility; source list; unresolved questions; human approval status. Use `references/brief_template.md` as the machine-readable structure.

## QA gates

1. All source claims have an inspected citation.
2. Every proposed number is labeled as a target until deterministic calculation is run.
3. Each method maps to an implemented function or is explicitly marked for separate implementation.
4. A human approves the question, assumptions and final interpretation.
