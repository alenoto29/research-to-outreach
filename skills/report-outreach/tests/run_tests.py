#!/usr/bin/env python3
"""run_tests.py — test deterministici report-outreach. Zero rete, zero LLM.

Uso: python3 tests/run_tests.py
"""
import importlib.util
import json
import sys
from unittest.mock import patch
from datetime import date
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
sys.path.insert(0, str(SKILL / "tools"))


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, SKILL / "tools" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

scoring = _load("scoring", "01_unified_scoring.py")
select_mod = _load("select_mix", "02_select_mix.py")
emails = _load("resolve_emails", "03_resolve_emails.py")
dr_mod = _load("resolve_dr", "04_resolve_dr.py")
csv_mod = _load("write_csv", "05_write_csv.py")
common = _load("common", "lib_common.py")

CFG = json.loads((SKILL / "config" / "weights.json").read_text(encoding="utf-8"))
W = CFG["weights"]
RUN_DATE = date(2026, 6, 15)

PASS, FAIL = 0, []


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
    else:
        FAIL.append(f"{name} {detail}")


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b"{}"


check("no default dashboard endpoint", common.DEFAULT_API_BASE is None)
try:
    common.api_get(None, "/api/journalists", "sentinel")
    check("dashboard base must be explicit", False)
except ValueError:
    check("dashboard base must be explicit", True)

with patch("urllib.request.urlopen", return_value=_FakeResponse()) as mocked:
    common.api_get("https://example.invalid", "/api/test", "sentinel", {"q": "demo"})
    request = mocked.call_args.args[0]
    check("API token is a bearer header, not URL data",
          request.get_header("Authorization") == "Bearer sentinel"
          and "sentinel" not in request.full_url)


def cand(**kw):
    base = {"source": "discovery", "first_name": "Mario", "last_name": "Rossi",
            "domain": "news.example.test", "articles": [], "email": "", "journalist_id": None}
    base.update(kw)
    return base


def art(days_ago=30, on_topic=True, in_headline=False):
    from datetime import timedelta
    return {"url": "https://x", "date": (RUN_DATE - timedelta(days=days_ago)).isoformat(),
            "title": "t", "on_topic": on_topic, "in_headline": in_headline}


# ---------- scoring ----------

# cooldown: escluso hard
c = cand(source="dashboard", last_contacted="2026-06-05", contact_count=1)
check("cooldown_excluded", scoring.cooldown_excluded(c, CFG, RUN_DATE))
c = cand(source="dashboard", last_contacted="2026-04-01", contact_count=1)
check("cooldown_ok_fuori_finestra", not scoring.cooldown_excluded(c, CFG, RUN_DATE))
check("cooldown_mai_su_discovery", not scoring.cooldown_excluded(
    cand(last_contacted="2026-06-14"), CFG, RUN_DATE))

# history: responder al massimo (rel 12 + fatigue)
s, meta = scoring.score_history(
    cand(source="dashboard", response_status="replied", contact_count=2,
         last_contacted="2026-01-01"), CFG, W["history"], RUN_DATE)
check("history_responder_max", s == 20, f"got {s}")
check("history_responder_rel12", meta["relationship"] == 12)

# history: >=3 contatti senza risposta -> relationship 0
s, meta = scoring.score_history(
    cand(source="dashboard", response_status=None, contact_count=3,
         last_contacted="2026-01-01"), CFG, W["history"], RUN_DATE)
check("history_unresponsive_rel0", meta["relationship"] == 0, f"got {meta}")

# history: discovery neutro 10
s, meta = scoring.score_history(cand(), CFG, W["history"], RUN_DATE)
check("history_discovery_neutro", s == 10, f"got {s}")

# history: dashboard mai contattato == neutro discovery (scala comparabile)
s2, _ = scoring.score_history(
    cand(source="dashboard", contact_count=0), CFG, W["history"], RUN_DATE)
check("history_mai_contattato_eq_neutro", s2 == s, f"{s2} != {s}")

# topic correlation: 5 on-topic + 3 headline = max
c = cand(articles=[art(in_headline=True)] * 3 + [art()] * 2)
s, meta = scoring.score_topic_correlation(c, CFG, W["topic_correlation"])
check("topic_max", s == W["topic_correlation"], f"got {s}")
check("topic_zero_senza_articoli", scoring.score_topic_correlation(cand(), CFG, 45)[0] == 0)

# recency: <=90gg pieno, <=365 metà
check("recency_full", scoring.score_recency(cand(articles=[art(30)]), CFG, 15, RUN_DATE)[0] == 15)
check("recency_half", scoring.score_recency(cand(articles=[art(200)]), CFG, 15, RUN_DATE)[0] == 7.5)
check("recency_zero", scoring.score_recency(cand(articles=[art(400)]), CFG, 15, RUN_DATE)[0] == 0)

# authority: DR non c'entra
c1 = scoring.score_authority(cand(author_page="x", job_title="caporedattore",
                                  articles_count_6m=12, dr=90), CFG, 20)
c2 = scoring.score_authority(cand(author_page="x", job_title="caporedattore",
                                  articles_count_6m=12, dr=5), CFG, 20)
check("authority_ignora_dr", c1[0] == c2[0] == 20, f"{c1[0]} vs {c2[0]}")

# determinismo: stesso input -> stesso output
a = scoring.score_candidate(cand(source="dashboard", contact_count=0,
                                 articles=[art(10, in_headline=True)]), CFG, W, RUN_DATE)
b = scoring.score_candidate(cand(source="dashboard", contact_count=0,
                                 articles=[art(10, in_headline=True)]), CFG, W, RUN_DATE)
check("determinismo_scoring", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))

# dedup: vince dashboard, eredita articoli discovery
dup_disc = cand(email="mario.rossi@example.test", articles=[art(5)])
dup_dash = cand(source="dashboard", email="mario.rossi@example.test", journalist_id=7)
merged, log = scoring.dedup_candidates([dup_disc, dup_dash])
check("dedup_1_riga", len(merged) == 1)
check("dedup_vince_dashboard", merged[0]["source"] == "dashboard")
check("dedup_eredita_articoli", len(merged[0]["articles"]) == 1)

# dedup: same person with distinct addresses matches by normalized name and domain
dup_a = cand(source="dashboard", email="taylor@example.test", journalist_id=7)
dup_b = cand(source="dashboard", email="taylor.alt@example.test", journalist_id=12)
merged, log = scoring.dedup_candidates([dup_a, dup_b])
check("dedup_email_diverse_stesso_nome", len(merged) == 1, f"{len(merged)} righe")

# tie-break: score uguale -> DR desc, poi cognome
rows = [dict(cand(last_name="Bianchi", dr=40), score=80, score_breakdown={}),
        dict(cand(last_name="Verdi", dr=70), score=80, score_breakdown={}),
        dict(cand(last_name="Asti", dr=None), score=80, score_breakdown={})]
ordered = sorted(rows, key=scoring.sort_key)
check("tiebreak_dr_poi_cognome",
      [r["last_name"] for r in ordered] == ["Verdi", "Bianchi", "Asti"], str([r["last_name"] for r in ordered]))

# ---------- selection ----------

def srow(i, source, score):
    return dict(cand(first_name=f"N{i}", last_name=f"C{i:02d}", source=source,
                     domain=f"s{i}.it"), score=score)

# quota: 20 dashboard forti + discovery tutti a -4 dal marginale -> swap fino a max share
pool = [srow(i, "dashboard", 90 - i) for i in range(20)] + \
       [srow(100 + i, "discovery", 67) for i in range(20)]
pool.sort(key=lambda c: -c["score"])
res = select_mod.select(pool, CFG["selection"])
counts = res["log"]["counts"]
check("quota_swap_riequilibra", counts["dashboard"] <= 15, str(counts))
check("quota_swaps_loggati", len(res["log"]["swaps"]) > 0)

# gap che cresce oltre soglia -> swap parziali, poi lo score vince
pool_g = [srow(i, "dashboard", 90 - i) for i in range(20)] + \
         [srow(100 + i, "discovery", 63 - i) for i in range(20)]
pool_g.sort(key=lambda c: -c["score"])
res_g = select_mod.select(pool_g, CFG["selection"])
check("gap_ferma_swap", res_g["log"]["counts"]["dashboard"] > 15, str(res_g["log"]["counts"]))

# score vince: gap enorme -> niente swap, deviazione loggata
pool2 = [srow(i, "dashboard", 90 - i) for i in range(25)] + \
        [srow(100 + i, "discovery", 20 - i) for i in range(10)]
pool2.sort(key=lambda c: -c["score"])
res2 = select_mod.select(pool2, CFG["selection"])
check("score_batte_quota", res2["log"]["counts"]["dashboard"] > 15, str(res2["log"]["counts"]))
check("deviazione_loggata", res2["log"]["quota_deviation"] is True)

# thin pool
res3 = select_mod.select([srow(i, "discovery", 50) for i in range(10)], CFG["selection"])
check("thin_pool_warning", res3["log"]["thin_pool"] is True)

# alternates ordinati e separati per sorgente
check("alternates_per_sorgente",
      all(c["source"] == "dashboard" for c in res["alternates"]["dashboard"]) and
      all(c["source"] == "discovery" for c in res["alternates"]["discovery"]))

# ---------- email: tier mapping + pattern + cascata ----------

check("tier_scraped_A", emails.map_tier("scraped", None, None, CFG) == ("A-confirmed", True, True))
check("tier_finder_valid_forte", emails.map_tier("hunter-finder", "valid", 95, CFG) == ("A-hunter", True, True))
check("tier_finder_debole_B", emails.map_tier("hunter-finder", "accept_all", 60, CFG) == ("B-hunter", False, True))
check("tier_pattern_sempre_B", emails.map_tier("pattern", "valid", None, CFG) == ("B-pattern", False, True))
check("tier_invalid_fuori", emails.map_tier("pattern", "invalid", None, CFG)[2] is False)

check("pattern_compose", emails.compose_from_pattern("{first}.{last}", "María", "Rossi Bianchi", "example.test")
      == "maria.rossibianchi@example.test")
check("pattern_iniziale", emails.compose_from_pattern("{f}{last}", "Mario", "Rossi", "example.test") == "mrossi@example.test")
check("pattern_ignoto_none", emails.compose_from_pattern("{boh}", "M", "R", "example.test") is None)

# supported hint vocabulary can be composed into a test address
check("pattern_jf_finitial_surname",
      emails.compose_from_pattern("finitial+surname", "Alex", "Example", "example.test") == "aexample@example.test")
check("pattern_jf_first_last",
      emails.compose_from_pattern("first.last", "Mario", "Rossi", "example.test") == "mario.rossi@example.test")
check("pattern_jf_surname",
      emails.compose_from_pattern("surname", "Mario", "Rossi", "example.test") == "rossi@example.test")
check("pattern_jf_finitial_dot",
      emails.compose_from_pattern("finitial.surname", "Mario", "Rossi", "example.test") == "m.rossi@example.test")
check("hunter_429_non_cacheabile", emails.is_transient_api_error({"_error": 429}))
check("hunter_5xx_non_cacheabile", emails.is_transient_api_error({"_error": 503}))
check("hunter_4xx_stabile_cacheabile", not emails.is_transient_api_error({"_error": 404}))
check("hunter_429_esaurisce_budget", emails.api_error_exhausts_budget({"_error": 429}))
check("hunter_503_non_segnala_quota", not emails.api_error_exhausts_budget({"_error": 503}))

ds = {"emails": [{"value": "m.rossi@example.test", "first_name": "Mario", "last_name": "Rossi"}]}
check("domain_search_match", emails.match_person_in_domain_search(ds, "mario", "ROSSI")["value"] == "m.rossi@example.test")
check("domain_search_no_match", emails.match_person_in_domain_search(ds, "Luca", "Verdi") is None)

# cascata: no_email rimpiazzato dal prossimo della stessa sorgente, in ordine
sel = [srow(1, "discovery", 80), srow(2, "dashboard", 75)]
alts = {"discovery": [srow(3, "discovery", 70), srow(4, "discovery", 65)], "dashboard": []}
resolved_ok = {"N2", "N3", "N4"}
out = emails.cascade_replace(sel, alts, lambda c: c["first_name"] in resolved_ok)
check("cascata_rimpiazza", out[0]["first_name"] == "N3", out[0]["first_name"])
check("cascata_marca_replaced", "replaced" in out[0])
check("cascata_lascia_risolti", out[1]["first_name"] == "N2" and "replaced" not in out[1])

# cascata: alternates finiti -> resta il no_email (gestito a valle)
out2 = emails.cascade_replace([srow(9, "dashboard", 50)], {"dashboard": [], "discovery": []},
                              lambda c: False)
check("cascata_pool_vuoto", out2[0]["first_name"] == "N9")

# ---------- DR chain (fetcher mockato) ----------

lookup = {"cached.example.test": 55}
dr, from_api = dr_mod.resolve_dr("cached.example.test", lookup, lambda d: 99)
check("dr_lookup_first", (dr, from_api) == (55, False))
dr, from_api = dr_mod.resolve_dr("new.example.test", lookup, lambda d: 42)
check("dr_api_fallback", (dr, from_api) == (42, True))
check("dr_writeback_lookup", lookup["new.example.test"] == 42)
dr, from_api = dr_mod.resolve_dr("missing.example.test", lookup, lambda d: None)
check("dr_miss_vuoto", dr is None)

# ---------- why_picked determinismo ----------

row = dict(cand(author_page="x", job_title="redattore", dr=70),
           score=77, score_breakdown={"topic_correlation": 40.0, "authority": 12.0,
                                      "recency": 15.0, "history": 10.0, "n_on_topic": 4,
                                      "n_headline": 2, "last_on_topic": "2026-06-01",
                                      "history_kind": "neutral_discovery"})
w1 = csv_mod.build_why_picked(row, W)
w2 = csv_mod.build_why_picked(dict(row), W)
check("why_picked_deterministico", w1 == w2)
check("why_picked_cita_breakdown", "4 articoli on-topic" in w1 and "40.0/45" in w1, w1)
check("why_picked_dr_tiebreaker", "DR 70" in w1)

row_resp = dict(row, score_breakdown=dict(row["score_breakdown"], history_kind="responder"))
check("why_picked_responder", "già risposto" in csv_mod.build_why_picked(row_resp, W))

# QA: forma email invalida (pattern non risolto) -> FAIL
qa_mod = _load("qa_gate", "06_qa_gate.py")
bad_row = {"name": "X Y", "domain": "example.test", "email": "finitial+surname@example.test",
           "email_tier": "B-pattern", "confirmed": "false", "source": "discovery",
           "why_picked": "x"}
fails = qa_mod.check_csv([bad_row], [], [], CFG, date(2026, 6, 12))
check("qa_email_pattern_non_risolto",
      any("forma email invalida" in f for f in fails), str(fails))
ok_row = dict(bad_row, email="lastella.first@example.test")  # substring 'last'/'first' legittime
fails_ok = qa_mod.check_csv([ok_row], [], [], CFG, date(2026, 6, 12))
check("qa_email_substring_legittima",
      not any("forma email invalida" in f for f in fails_ok), str(fails_ok))

# ---------- normalize_domain + blacklist (01) ----------

check("normalize_domain_www", select_mod.normalize_domain("WWW.Blocked.Example.Test") == "blocked.example.test")
check("is_blacklisted_true", scoring.is_blacklisted(cand(domain="never-contact.example.test"), CFG))
check("is_blacklisted_www", scoring.is_blacklisted(cand(domain="www.blocked.example.test"), CFG))
check("is_blacklisted_false", not scoring.is_blacklisted(cand(domain="news.example.test"), CFG))

# ---------- DR gate (01b) ----------

drg = _load("dr_gate", "01b_dr_gate.py")
check("gate_none_keep", drg.passes_dr_gate(None, "TOP", CFG) and drg.passes_dr_gate(None, "MID", CFG))
check("gate_top_50_in", drg.passes_dr_gate(50, "TOP", CFG))
check("gate_top_49_out", not drg.passes_dr_gate(49, "TOP", CFG))
check("gate_top_81_in", drg.passes_dr_gate(81, "TOP", CFG))
check("gate_mid_80_in", drg.passes_dr_gate(80, "MID", CFG))
check("gate_mid_81_out", not drg.passes_dr_gate(81, "MID", CFG))
check("gate_mid_40_in", drg.passes_dr_gate(40, "MID", CFG))
check("gate_overlap_both",
      drg.passes_dr_gate(65, "TOP", CFG) and drg.passes_dr_gate(65, "MID", CFG))

# ---------- max per journal (02) ----------

pool_j = [dict(cand(first_name=f"D{i}", last_name=f"C{i:02d}", source="dashboard", domain="duplicate.example.test"),
               score=95 - i) for i in range(3)] + \
         [dict(cand(first_name=f"X{i}", last_name=f"C{50 + i:02d}", source="discovery", domain=f"d{i}.it"),
               score=80 - i) for i in range(22)]
pool_j.sort(key=lambda c: -c["score"])
res_j = select_mod.select(pool_j, CFG["selection"])
dup_count = sum(1 for c in res_j["selected"] if c["domain"] == "duplicate.example.test")
check("journal_cap_max2", dup_count <= 2, f"got {dup_count}")
check("journal_cap_skip_loggato", len(res_j["log"]["journal_cap_skips"]) >= 1)

# ---------- cascata rispetta il cap per giornale (03) ----------

selA = [dict(cand(first_name="A", domain="full.example.test", source="discovery")),
        dict(cand(first_name="B", domain="full.example.test", source="discovery")),
        dict(cand(first_name="C", domain="other.example.test", source="discovery"))]
altsA = {"discovery": [dict(cand(first_name="ALT", domain="full.example.test", source="discovery"))],
         "dashboard": []}
resolved_setA = {"A", "B", "ALT"}  # C non risolto, unico alt è full.it (già al cap)
outA = emails.cascade_replace(selA, altsA, lambda c: c["first_name"] in resolved_setA,
                              max_journal=2, domain_of=lambda c: c["domain"])
check("cascata_cap_blocca_terzo", outA[2]["first_name"] == "C", outA[2]["first_name"])
check("cascata_cap_full_resta_2",
      sum(1 for c in outA if c["domain"] == "full.example.test") == 2,
      str([c["first_name"] for c in outA]))

# ---------- QA backstop: blacklist / cap / dr gate (06) ----------

bl_row = {"name": "X Y", "domain": "blocked.example.test", "email": "x@blocked.example.test", "email_tier": "B-pattern",
          "confirmed": "false", "source": "discovery", "why_picked": "x", "dr": "60"}
check("qa_blacklist_fail",
      any("blacklist" in f for f in qa_mod.check_csv([bl_row], [], [], CFG, date(2026, 6, 12))))

jr = [{"name": f"P{i}", "domain": "same.example.test", "email": f"p{i}@example.test", "email_tier": "B-pattern",
       "confirmed": "false", "source": "discovery", "why_picked": "x", "dr": "60"} for i in range(3)]
check("qa_journal_cap_fail",
      any("stesso giornale" in f for f in qa_mod.check_csv(jr, [], [], CFG, date(2026, 6, 12))))

top_row = {"name": "X Y", "domain": "low.example.test", "email": "x@low.example.test", "email_tier": "B-pattern",
           "confirmed": "false", "source": "discovery", "why_picked": "x", "dr": "40"}
check("qa_dr_gate_top_fail",
      any("gate TOP" in f for f in qa_mod.check_csv([top_row], [], [], CFG, date(2026, 6, 12), "TOP")))
check("qa_dr_gate_mid_fail",
      any("gate MID" in f for f in qa_mod.check_csv([dict(top_row, dr="90")], [], [], CFG, date(2026, 6, 12), "MID")))
check("qa_dr_gate_unknown_esente",
      not any("gate" in f for f in qa_mod.check_csv([dict(top_row, dr="")], [], [], CFG, date(2026, 6, 12), "TOP")))
check("qa_dr_gate_range_ok",
      not any("gate" in f for f in qa_mod.check_csv([dict(top_row, dr="65")], [], [], CFG, date(2026, 6, 12), "TOP")))

# ---------- esito ----------

total = PASS + len(FAIL)
print(f"\n{PASS}/{total} PASS")
if FAIL:
    for f in FAIL:
        print(f"  FAIL {f}")
    sys.exit(1)
