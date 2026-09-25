#!/usr/bin/env python3
"""01_unified_scoring.py — scoring unificato deterministico 0-100 (D3/D4).

Input : .tmp/candidates.json   (evidenze Sonnet per ENTRAMBE le sorgenti, D2)
        PLAN/*plan.json        (run_date, pesi override)
        config/weights.json
Output: .tmp/scored.json       (dedup + score + breakdown, ordinato desc)

Determinismo: no LLM, no rete, no system date (run_date dal plan).
Stesso input -> output byte-identical.

Blocchi (default v1): topic_correlation 45 | authority 20 | recency 15 | history 20.
History: dashboard da response_status/contact_count/last_contacted; discovery = neutro 10.
Cooldown (< cooldown_default_days da last_contacted) = ESCLUSIONE hard, non penalità.
DR mai nello score: solo tie-breaker (regola ferrea "target over DR").
"""
import argparse
import json
from pathlib import Path

from lib_common import load_config, load_plan, normalize_domain, normalize_name, parse_date, update_run_log


# ---------- blocchi score (funzioni pure) ----------

def score_topic_correlation(c: dict, cfg: dict, w: float) -> tuple:
    tc = cfg["topic_correlation"]
    arts = [a for a in c.get("articles", []) if a.get("on_topic")]
    n_ot = len(arts)
    n_head = sum(1 for a in arts if a.get("in_headline"))
    s = w * (tc["on_topic_share"] * min(n_ot, tc["on_topic_cap"]) / tc["on_topic_cap"]
             + tc["headline_share"] * min(n_head, tc["headline_cap"]) / tc["headline_cap"])
    return round(s, 1), {"n_on_topic": n_ot, "n_headline": n_head}


def score_authority(c: dict, cfg: dict, w: float) -> tuple:
    au = cfg["authority"]
    pts = 0
    if c.get("author_page"):
        pts += au["author_page_points"]
    title = (c.get("job_title") or "").lower()
    if any(t in title for t in au["senior_titles"]):
        pts += au["seniority_senior_points"]
    elif any(t in title for t in au["staff_titles"]):
        pts += au["seniority_staff_points"]
    elif any(t in title for t in au["freelance_titles"]):
        pts += au["seniority_freelance_points"]
    vol = c.get("articles_count_6m")
    if vol is not None:
        if vol >= 10:
            pts += au["volume_high_points"]
        elif vol >= 5:
            pts += au["volume_mid_points"]
        elif vol >= 1:
            pts += au["volume_low_points"]
    else:
        yrs = c.get("years_exp") or 0
        if yrs >= 10:
            pts += au["volume_mid_points"]
        elif yrs >= 3:
            pts += au["volume_low_points"]
    max_pts = au["author_page_points"] + au["seniority_senior_points"] + au["volume_high_points"]
    return round(min(pts, max_pts) / max_pts * w, 1), {"authority_raw": pts}


def score_recency(c: dict, cfg: dict, w: float, run_date) -> tuple:
    rc = cfg["recency"]
    dates = [d for d in (parse_date(a.get("date")) for a in c.get("articles", []) if a.get("on_topic")) if d]
    if not dates:
        return 0.0, {"last_on_topic": None}
    last = max(dates)
    days = (run_date - last).days
    r = 1.0 if days <= rc["full_days"] else (0.5 if days <= rc["half_days"] else 0.0)
    return round(r * w, 1), {"last_on_topic": last.isoformat()}


def is_positive_response(status, cfg: dict) -> bool:
    s = (status or "").strip().lower()
    return any(p in s for p in cfg["history"]["positive_response_statuses"]) if s else False


def score_history(c: dict, cfg: dict, w: float, run_date) -> tuple:
    h = cfg["history"]
    if c.get("source") != "dashboard":
        return float(h["neutral_discovery"]), {"history_kind": "neutral_discovery"}

    count = c.get("contact_count") or 0
    positive = is_positive_response(c.get("response_status"), cfg)
    last = parse_date(c.get("last_contacted"))

    if positive:
        rel = h["relationship_max"]
    elif count == 0:
        rel = h["relationship_never_contacted"]
    elif count >= h["unresponsive_contact_threshold"]:
        rel = 0
    else:
        rel = h["relationship_contacted_no_reply"]

    if count == 0 or last is None:
        fat = h["fatigue_never_contacted"] if count == 0 else h["fatigue_recent_points"]
    else:
        days = (run_date - last).days
        fat = h["fatigue_rested_points"] if days > h["fatigue_rested_days"] else h["fatigue_recent_points"]

    total = min(rel + fat, w)
    kind = "responder" if positive else ("never_contacted" if count == 0 else "contacted_no_reply")
    return float(total), {"history_kind": kind, "relationship": rel, "fatigue": fat,
                          "contact_count": count}


def is_blacklisted(c: dict, cfg: dict) -> bool:
    """Giornali blacklistati (config) -> fuori dal pool, mai scorati. Match su dominio canonico."""
    bl = {normalize_domain(d) for d in cfg.get("blacklist_domains", [])}
    return normalize_domain(c.get("domain")) in bl


def cooldown_excluded(c: dict, cfg: dict, run_date) -> bool:
    if c.get("source") != "dashboard":
        return False
    last = parse_date(c.get("last_contacted"))
    if last is None:
        return False
    days = cfg["cooldown_responder_days"] if is_positive_response(c.get("response_status"), cfg) \
        else cfg["cooldown_default_days"]
    return (run_date - last).days < days


def score_candidate(c: dict, cfg: dict, weights: dict, run_date) -> dict:
    s_topic, m1 = score_topic_correlation(c, cfg, weights["topic_correlation"])
    s_auth, m2 = score_authority(c, cfg, weights["authority"])
    s_rec, m3 = score_recency(c, cfg, weights["recency"], run_date)
    s_hist, m4 = score_history(c, cfg, weights["history"], run_date)
    breakdown = {"topic_correlation": s_topic, "authority": s_auth,
                 "recency": s_rec, "history": s_hist}
    breakdown.update(m1); breakdown.update(m2); breakdown.update(m3); breakdown.update(m4)
    out = dict(c)
    out["score"] = round(s_topic + s_auth + s_rec + s_hist)
    out["score_breakdown"] = breakdown
    return out


def dedup_candidates(candidates: list) -> tuple:
    """Stessa persona in entrambe le sorgenti -> vince la versione dashboard (ha la storia).

    Match su ENTRAMBE le chiavi (email O nome+dominio): la stessa persona puo avere
    email diverse tra le sorgenti, o due righe DB con email diverse."""
    people, key_to_idx, merged = [], {}, []
    for c in candidates:
        keys = [("name", normalize_name(c.get("first_name"), c.get("last_name")),
                 (c.get("domain") or "").lower())]
        email = (c.get("email") or "").strip().lower()
        if email and "@" in email:
            keys.append(("email", email))
        idx = next((key_to_idx[k] for k in keys if k in key_to_idx), None)
        if idx is not None:
            prev = people[idx]
            if prev["source"] != "dashboard" and c["source"] == "dashboard":
                # la dashboard sostituisce ma eredita le evidenze articoli del discovery
                if not c.get("articles") and prev.get("articles"):
                    c = dict(c); c["articles"] = prev["articles"]
                people[idx] = c
            merged.append({"key": list(map(str, keys[0])), "kept": people[idx]["source"]})
        else:
            idx = len(people)
            people.append(c)
        for k in keys:
            key_to_idx.setdefault(k, idx)
    return people, merged


def sort_key(c: dict):
    dr = c.get("dr")
    return (-c["score"], -(dr if isinstance(dr, (int, float)) else -1),
            (c.get("last_name") or "").lower(), (c.get("first_name") or "").lower())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    cfg = load_config()
    plan = load_plan(args.run_dir)
    run_date = parse_date(plan.get("run_date"))
    if run_date is None:
        raise SystemExit("plan.run_date mancante o invalido (no system date: determinismo)")
    weights = {**cfg["weights"], **plan.get("scoring_weights", {})}

    tmp = Path(args.run_dir) / ".tmp"
    candidates = json.loads((tmp / "candidates.json").read_text(encoding="utf-8"))
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates", [])

    deduped, merges = dedup_candidates(candidates)
    blacklisted = [c for c in deduped if is_blacklisted(c, cfg)]
    rest = [c for c in deduped if not is_blacklisted(c, cfg)]
    excluded = [c for c in rest if cooldown_excluded(c, cfg, run_date)]
    pool = [c for c in rest if not cooldown_excluded(c, cfg, run_date)]
    scored = sorted((score_candidate(c, cfg, weights, run_date) for c in pool), key=sort_key)

    out = {"weights_version": cfg["weights_version"], "weights": weights,
           "run_date": run_date.isoformat(), "scored": scored}
    (tmp / "scored.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    update_run_log(args.run_dir, "scoring", {
        "weights_version": cfg["weights_version"],
        "pool": len(scored),
        "dedup_merges": merges,
        "excluded_cooldown": [
            {"name": f"{c.get('first_name')} {c.get('last_name')}", "email": c.get("email"),
             "last_contacted": c.get("last_contacted"), "reason": "cooldown"}
            for c in excluded
        ],
        "excluded_blacklist": [
            {"name": f"{c.get('first_name')} {c.get('last_name')}", "domain": c.get("domain"),
             "reason": "blacklist"}
            for c in blacklisted
        ],
    })
    print(f"OK scored={len(scored)} cooldown_excluded={len(excluded)} "
          f"blacklist_excluded={len(blacklisted)} dedup={len(merges)}")


if __name__ == "__main__":
    main()
