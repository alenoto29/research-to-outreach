# Research to outreach

This project is a **toolkit for turning research into a report and then into outreach ideas**. People choose the question, check the sources and approve the story and pitches. Python does the calculations and checks structured files. An LLM can help research and write, but **it must not invent numbers, evidence or contacts**. Nothing here sends emails automatically.

It is **not** one command that turns any topic or CSV into a trustworthy report and a list of journalists.

## Start with your topic and angle

Open this repository in a coding LLM that can read files and run Python. Give it this prompt:

> Read `RUNBOOK.md`. My topic is **[topic]** and my angle is **[angle]**. Work from source research through a checked report to a shortlist and unsent, personalized pitch drafts. Show me which claims and contacts have been verified; stop if essential data are missing. Use my Serper key for web searches, not your own credentials.

Set **your own** `SERPER_API_KEY` in that environment before starting. The key is for Serper web search only; the LLM you opened the repo in supplies the writing/analysis. No Anthropic or OpenAI API key is needed by the scripts. Do not paste keys into the prompt or commit them. The workflow still needs source checks, enough data for any numerical analysis and human approval of the report and outreach drafts. See [`RUNBOOK.md`](RUNBOOK.md) for the steps and expected files.

## Start with the worked example

You need Python 3.10+. Open [`examples/setpoint-sweep/README.md`](examples/setpoint-sweep/README.md): it walks through a small, invented cooling-cost calculation, a report draft, a fictional candidate and an unsent pitch. The figures show how the arithmetic works; they are **not** real savings. The example's report and chart are already included, so you can read them without installing anything.

To check the arithmetic yourself from the repository folder:

```sh
python3 -m unittest discover -s report-writer/tests -v
```

The `sweep_t_in` test checks 22, 18 and 14 kWh for the example inputs. To see the calculator's JSON output, run:

```sh
printf '%s\n' '{"analysis_id":"setpoint_sweep","method":"sweep_t_in","data":{"K_cond":100,"K_inf":0,"T_ext":35,"T_in_list":[24,26,28],"seer":4,"hours_day":8,"season_days":10,"tariff_eur_kwh":0.25},"unit":"kWh and EUR","inputs":["examples/setpoint-sweep/inputs.json"]}' | python3 report-writer/tools/compute.py
```

The example's calculation is deliberately narrow: it is not a general model of a building or an electricity bill.

## Use it for your own research

You can give an LLM this repository and ask: “Help me adapt this workflow to **my question and my data**. Identify the sources to check, the inputs and units needed, which calculations already exist, and what new code or review is required. Do not make up numbers or journalist contacts. Keep human approval before the report and pitches.” Share the *shape* of private data first, not the data itself.

Then work through these stages:

1. **Research:** choose one clear question; inspect and record sources for each factual claim. `papers-references/` has a source checklist and an optional paper finder. Online search is opt-in.
2. **Calculate:** choose a method in `report-writer/tools/compute.py`, supply real, documented inputs and check the assumptions and units. Unsupported methods are flagged as **not calculated**, not guessed. An LLM can help write a brief, but Python must produce the numbers.
3. **Write and review:** draft the report from checked results, check every claim and chart, and get human approval. `report-writer/WORKFLOW.md` describes the stages; the repo does not run them all for you.
4. **Find relevant people:** supply researched candidate records with evidence of what they cover. `skills/report-outreach/` and `skills/journalist-finder/` can rank candidates and check a shortlist. A score is a sorting rule, **not** a probability that someone will respond. Review each choice and pitch; no automatic contact is made.

For a new topic, the calculator may need a **new method**, not just a different input file. A random CSV of articles or journalists is not enough: you must map its fields, verify its sources and decide what the data actually supports. The worked example shows the *shape* of the process, not a ready-to-run pipeline for every subject.

## Checks and optional tools

The offline tests use invented data and do not call any external service:

```sh
python3 -m unittest discover -s papers-references/tests -v
python3 -m unittest discover -s report-writer/tests -v
python3 skills/journalist-finder/tests/run_tests.py
python3 skills/report-outreach/tests/run_tests.py
```

Passing tests confirms specific calculations and file/ranking rules, **not** that your sources, assumptions, report or contacts are correct. Report DOCX and chart generation need optional packages (`pip install -r requirements-optional.txt`). Network searches, paid email lookup and database updates require separate, explicit setup; the example uses none of them. Keep private research and contact data out of Git.

The code was extracted and adapted from Alessandro Noto's internal workflow with AI assistance. See [`PROVENANCE.md`](PROVENANCE.md): **license selection and public-release review are still pending**. This repository is not yet cleared for public release.
