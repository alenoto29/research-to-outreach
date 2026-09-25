#!/usr/bin/env python3
"""01_scoring.py — target_score deterministico (0-100).

Input : .tmp/candidates.json (evidenze raccolte dall'agent in FASE 2)
        PLAN/<topic>_plan.json (pesi + thresholds + run_date)
Output: .tmp/scored.json (candidates + target_score + score_breakdown), ordinato desc.

Determinismo: nessun LLM, nessuna rete, nessuna data di sistema. La data "oggi" arriva
dal plan (run_date) per riproducibilita. Stesso input -> stesso score.

Pesi default (override da plan.scoring_weights):
  on_topic_articles 35 | headline_match 25 | recency 20 | author_page 10 | topic_focus 10
"""
import argparse
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]

DEFAULT_WEIGHTS = {
    "on_topic_articles": 35,
    "headline_match": 25,
    "recency": 20,
    "author_page": 10,
    "topic_focus": 10,
}


def _parse_date(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def score_candidate(c: dict, weights: dict, run_date: date, core_terms: list) -> dict:
    arts = c.get("articles", [])
    on_topic = [a for a in arts if a.get("on_topic")]
    n_ot = len(on_topic)
    n_head = sum(1 for a in on_topic if a.get("in_headline"))

    # on_topic_articles: cap 5
    s_ot = (min(n_ot, 5) / 5) * weights["on_topic_articles"]
    # headline_match: cap 3
    s_head = (min(n_head, 3) / 3) * weights["headline_match"]
    # recency: piu recente articolo on-topic
    dates = [d for d in (_parse_date(a.get("date")) for a in on_topic) if d]
    if dates:
        days = (run_date - max(dates)).days
        if days <= 90:
            r = 1.0
        elif days <= 365:
            r = 0.5
        else:
            r = 0.0
    else:
        r = 0.0
    s_rec = r * weights["recency"]
    # author_page
    s_ap = weights["author_page"] if c.get("author_page") else 0
    # topic_focus: core term nel beat (=full) o nei topics (=meta')
    beat = (c.get("beat") or "").lower()
    topics = " ".join(c.get("topics", [])).lower()
    if any(t.lower() in beat for t in core_terms):
        s_focus = weights["topic_focus"]
    elif any(t.lower() in topics for t in core_terms):
        s_focus = weights["topic_focus"] * 0.5
    else:
        s_focus = 0
    breakdown = {
        "on_topic_articles": round(s_ot, 1),
        "headline_match": round(s_head, 1),
        "recency": round(s_rec, 1),
        "author_page": round(s_ap, 1),
        "topic_focus": round(s_focus, 1),
        "n_on_topic": n_ot,
        "n_headline": n_head,
    }
    total = round(sum(v for k, v in breakdown.items() if k not in ("n_on_topic", "n_headline")))
    out = dict(c)
    out["target_score"] = total
    out["score_breakdown"] = breakdown
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-dir", required=True, help="directory with the approved plan and candidates")
    args = ap.parse_args()
    topic_root = SKILL.parents[1] / args.topic_dir
    plan_files = list((topic_root / "PLAN").glob("*_plan.json"))
    if not plan_files:
        raise SystemExit(f"plan mancante in {topic_root/'PLAN'}")
    plan = json.loads(plan_files[0].read_text(encoding="utf-8"))
    weights = {**DEFAULT_WEIGHTS, **plan.get("scoring_weights", {})}
    run_date = _parse_date(plan.get("run_date")) or date.fromisoformat("2026-05-29")
    core_terms = plan.get("topic_core", [])

    cand_path = topic_root / ".tmp" / "candidates.json"
    cands = json.loads(cand_path.read_text(encoding="utf-8"))
    scored = [score_candidate(c, weights, run_date, core_terms) for c in cands]
    scored.sort(key=lambda x: (-x["target_score"], -(x.get("dr") or 0)))

    out_path = topic_root / ".tmp" / "scored.json"
    out_path.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK  {len(scored)} candidati scored -> {out_path}")
    for c in scored[:10]:
        print(f"  {c['target_score']:3d}  {c.get('name','')} {c.get('surname','')} ({c.get('domain','')})")


if __name__ == "__main__":
    main()
