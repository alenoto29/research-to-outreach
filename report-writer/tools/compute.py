"""Deterministic compute for report analyses — stdlib only (statistics, math).

IRON RULE: numbers come from THIS code, never from LLM reasoning. Every function
takes numeric series in and returns a number out, with provenance. Methods not
implemented here (GARCH, structural break, synthetic control) are flagged
[DA CALCOLARE], never faked.

Result contract (consumed by docx_writer / charts):
  computed:  {"analysis_id","method","metric","value","unit","inputs","computed":True[,"note"]}
  infeasible:{"analysis_id","method","computed":False,"flag":"[DA CALCOLARE: <reason>]"}
"""
from __future__ import annotations

import math
import json
import statistics as st
import sys
from statistics import NormalDist

# methods we CAN compute deterministically with stdlib (Easy/Med tier)
FEASIBLE = {
    "descriptive", "pct_change", "event_study_car", "correlation",
    "pass_through", "lead_lag", "cross_country",
    "thermal_cooling", "sweep_t_in", "old_vs_new",
}
# methods that need libs/assumptions we don't ship in MVP -> flag, never fake
HARD = {"garch", "structural_break", "synthetic_control"}


def _flag(analysis_id, method, reason):
    return {"analysis_id": analysis_id, "method": method, "computed": False,
            "flag": f"[DA CALCOLARE: {reason}]"}


def _ok(analysis_id, method, metric, value, unit, inputs, note=None):
    r = {"analysis_id": analysis_id, "method": method, "metric": metric,
         "value": value, "unit": unit, "inputs": list(inputs), "computed": True}
    if note:
        r["note"] = note
    return r


# --- AC thermal primitives (template stile "Foglio Riscaldamento" adattato al fresco) ---

def thermal_cooling(K_cond, K_inf, delta_T, seer, hours_day, season_days, tariff):
    """Fabbisogno raffrescamento stile sheet Riscaldamento: K_tot * dT -> W -> kWh termici/giorno
    -> kWh stagionali (el) via SEER -> € stagione. SPECIFICA: NON usa duty cycle (modello
    sheet Riscaldamento: ore di accensione piene, no frazione di duty)."""
    K_tot = float(K_cond) + float(K_inf)
    dT = float(delta_T)
    power_w = K_tot * dT
    thermal_kwh_day = power_w * float(hours_day) / 1000.0
    thermal_kwh_season = thermal_kwh_day * float(season_days)
    el_kwh_season = thermal_kwh_season / float(seer)
    season_eur = el_kwh_season * float(tariff)
    return {
        "K_tot": round(K_tot, 2),
        "delta_T": dT,
        "power_w": round(power_w, 1),
        "thermal_kwh_day": round(thermal_kwh_day, 2),
        "thermal_kwh_season": round(thermal_kwh_season, 1),
        "el_kwh_season": round(el_kwh_season, 1),
        "season_eur": round(season_eur, 2),
    }


def sweep_t_in(K_cond, K_inf, T_ext, T_in_list, seer, hours_day, season_days, tariff):
    """Sweep T_interna 24..28°C, fissa T_esterna. Output: tabella {T_in: {kwh, eur}}."""
    rows = []
    for T_in in T_in_list:
        # Cooling load increases with outdoor temperature above the indoor setpoint.
        dT = T_ext - T_in
        if dT <= 0:
            rows.append({"T_in": T_in, "delta_T": 0,
                         "el_kwh_season": 0.0, "season_eur": 0.0})
        else:
            r = thermal_cooling(K_cond, K_inf, dT, seer, hours_day, season_days, tariff)
            rows.append({"T_in": T_in, "delta_T": dT,
                         "el_kwh_season": r["el_kwh_season"],
                         "season_eur": r["season_eur"]})
    return rows


def old_vs_new(thermal_kwh, seer_old, seer_new, tariff):
    """Stesso fabbisogno termico, SEER vecchio vs SEER nuovo. € risparmiati stagione."""
    kwh_old = float(thermal_kwh) / float(seer_old)
    kwh_new = float(thermal_kwh) / float(seer_new)
    eur_old = kwh_old * float(tariff)
    eur_new = kwh_new * float(tariff)
    saved_eur = eur_old - eur_new
    pct = (kwh_old - kwh_new) / kwh_old * 100.0
    return {
        "thermal_kwh": float(thermal_kwh),
        "kwh_old": round(kwh_old, 1), "eur_old": round(eur_old, 2),
        "kwh_new": round(kwh_new, 1), "eur_new": round(eur_new, 2),
        "saved_eur": round(saved_eur, 2), "pct_saved": round(pct, 1),
    }


# --- envelope physics for cooling (modello "Foglio Riscaldamento" + apporti solari) ---
# Simplified envelope model for cooling: the load has TWO terms — the envelope
# (K_tot x ΔT, depends on the temperature difference)
# e gli APPORTI GRATUITI estivi (sole + interni, NON dipendono dal ΔT). Questo secondo
# termine d'inverno è trascurabile (il foglio riscaldamento lo ignora) ma d'estate è il
# carico dominante: per questo va aggiunto. 0,34 Wh/(m³·K) = capacità termica volumica
# dell'aria (ρ·c), costante standard di fisica tecnica (UNI/ISO 13789).

_RHO_C_AIR = 0.34  # Wh/(m³·K)


def envelope_conductance(u_avg, a_disp, ach, volume):
    """Conduttanze dell'involucro (W/K).
    K_cond = U medio x superficie disperdente ; K_inf = 0,34 x ricambi/h x volume.
    Identica fisica del foglio riscaldamento (lì K_cond/K_inf sono dati a mano; qui li
    deriviamo da U e ricambi d'aria, così ogni input è ispezionabile)."""
    k_cond = float(u_avg) * float(a_disp)
    k_inf = _RHO_C_AIR * float(ach) * float(volume)
    return {"k_cond": round(k_cond, 1), "k_inf": round(k_inf, 1),
            "k_tot": round(k_cond + k_inf, 1)}


def solar_internal_gains(a_window, irradiance_w_m2, shgc_eff, a_floor, q_internal_w_m2):
    """Apporti gratuiti estivi che entrano in casa durante le ore di AC acceso (W).
    Q_solare = sup. vetrata x irraggiamento estivo medio nelle ore di funzionamento
               x fattore solare effettivo (vetro x schermatura/tende).
    Q_interni = densità apporti interni (persone+elettrodomestici+luci) x superficie.
    NON dipendono dal ΔT: per questo il costo marginale di un grado resta puro involucro."""
    q_solar = float(a_window) * float(irradiance_w_m2) * float(shgc_eff)
    q_internal = float(q_internal_w_m2) * float(a_floor)
    return {"q_solar": round(q_solar, 1), "q_internal": round(q_internal, 1),
            "q_gain": round(q_solar + q_internal, 1)}


def cooling_load(k_tot, delta_t, q_gain, seer, hours_day, season_days, tariff):
    """Carico di raffrescamento (W) = K_tot x ΔT (involucro) + Q_apporti (sole+interni).
    ΔT = T_esterna (ore di funzionamento) − T_interna (setpoint). -> kWh termici/giorno
    -> stagione -> kWh elettrici via SEER -> €/stagione."""
    dt = max(0.0, float(delta_t))
    power_envelope = float(k_tot) * dt
    power_w = power_envelope + float(q_gain)
    thermal_kwh_day = power_w * float(hours_day) / 1000.0
    thermal_kwh_season = thermal_kwh_day * float(season_days)
    el_kwh_season = thermal_kwh_season / float(seer)
    return {
        "delta_T": dt,
        "power_envelope_w": round(power_envelope, 1),
        "power_gain_w": round(float(q_gain), 1),
        "power_w": round(power_w, 1),
        "thermal_kwh_season": round(thermal_kwh_season, 1),
        "el_kwh_season": round(el_kwh_season, 1),
        "season_eur": round(el_kwh_season * float(tariff), 2),
    }


def marginal_degree_cost(k_tot, seer, hours_day, season_days, tariff):
    """Costo marginale di UN grado di ΔT, sostenuto su tutta la stagione (estate più calda
    di 1°C O termostato 1°C più basso: stesso effetto). Puro involucro: +1°C alza il carico
    di K_tot (W); gli apporti restano invariati. Indipendente dalla zona climatica.
    kWh el/°C = K_tot x 1 x ore x giorni / 1000 / SEER ; € = x tariffa."""
    thermal_kwh_per_deg = float(k_tot) * float(hours_day) * float(season_days) / 1000.0
    el_kwh_per_deg = thermal_kwh_per_deg / float(seer)
    return {"thermal_kwh_per_deg": round(thermal_kwh_per_deg, 2),
            "el_kwh_per_deg": round(el_kwh_per_deg, 2),
            "eur_per_deg": round(el_kwh_per_deg * float(tariff), 2)}


# --- primitives (pure math on lists of floats) ---

def descriptive(series):
    s = [float(x) for x in series]
    return {"mean": st.mean(s), "median": st.median(s),
            "stdev": st.stdev(s) if len(s) > 1 else 0.0,
            "min": min(s), "max": max(s), "n": len(s)}


def pct_change(series):
    """First -> last percentage change."""
    s = [float(x) for x in series]
    if s[0] == 0:
        raise ValueError("baseline is zero, % change undefined")
    return (s[-1] - s[0]) / abs(s[0]) * 100.0


def event_study_car(series, event_index, window):
    """Descriptive cumulative abnormal change: mean(post) vs mean(pre) over a
    +/- window around event_index, with a normal-approx t-stat & two-sided p.
    Returns CAR% + t + p. p is a NORMAL approximation (valid large-n) — labelled."""
    s = [float(x) for x in series]
    pre = s[max(0, event_index - window):event_index]
    post = s[event_index:event_index + window]
    if len(pre) < 2 or len(post) < 2:
        raise ValueError("window too small for pre/post means")
    car = (st.mean(post) - st.mean(pre)) / abs(st.mean(pre)) * 100.0
    # two-sample t (unequal var, Welch) on levels
    m1, m2 = st.mean(pre), st.mean(post)
    v1, v2 = st.variance(pre), st.variance(post)
    n1, n2 = len(pre), len(post)
    se = math.sqrt(v1 / n1 + v2 / n2)
    t = (m2 - m1) / se if se else float("inf")
    p = 2 * (1 - NormalDist().cdf(abs(t)))  # normal approx
    return {"car_pct": car, "t_stat": t, "p_value_normal_approx": p}


def correlation(x, y):
    a = [float(v) for v in x]
    b = [float(v) for v in y]
    return st.correlation(a, b)  # Pearson


def pass_through(wholesale, retail):
    """OLS slope retail~wholesale = pass-through coefficient (+ intercept)."""
    w = [float(v) for v in wholesale]
    r = [float(v) for v in retail]
    res = st.linear_regression(w, r)
    return {"pass_through_coef": res.slope, "intercept": res.intercept}


def lead_lag(x, y, max_lag):
    """Lag k (in steps) that maximizes |corr(x[t], y[t+k])|. Positive k => x leads y."""
    a = [float(v) for v in x]
    b = [float(v) for v in y]
    best = {"lag": 0, "corr": 0.0}
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            xa, yb = a[:len(a) - k], b[k:]
        else:
            xa, yb = a[-k:], b[:len(b) + k]
        if len(xa) > 2 and len(set(xa)) > 1 and len(set(yb)) > 1:
            c = st.correlation(xa, yb)
            if abs(c) > abs(best["corr"]):
                best = {"lag": k, "corr": c}
    return best


def cross_country(it_series, other_series):
    """Mean ratio + % gap of Italy vs another country on a common unit."""
    it_m = st.mean([float(v) for v in it_series])
    ot_m = st.mean([float(v) for v in other_series])
    return {"it_mean": it_m, "other_mean": ot_m,
            "ratio": it_m / ot_m if ot_m else float("inf"),
            "gap_pct": (it_m - ot_m) / abs(ot_m) * 100.0 if ot_m else float("inf")}


# --- dispatcher: map a brief method string -> a FEASIBLE key, else flag ---

def classify_method(method_text):
    """Loose map from the brief's free-text 'Method' column to a compute key."""
    m = (method_text or "").lower()
    if m in FEASIBLE or m in HARD:
        return m
    if "garch" in m:
        return "garch"
    if "bai" in m or "structural break" in m or "chow" in m:
        return "structural_break"
    if "synthetic" in m or "counterfactual" in m:
        return "synthetic_control"
    if "event study" in m or "abnormal" in m or "car" in m:
        return "event_study_car"
    if "pass-through" in m or "pass through" in m or "ecm" in m:
        return "pass_through"
    if "cross-country" in m or "normaliz" in m:
        return "cross_country"
    if "lead-lag" in m or "lead lag" in m or "cross-correl" in m:
        return "lead_lag"
    if "correlation" in m or "regression" in m or "index" in m or "composite" in m:
        return "correlation"
    if "descriptive" in m:
        return "descriptive"
    return None


# --- bottom-up end-use primitives (cooling pilot, 2026-06-01) -------------
# Pure deterministic arithmetic for appliance bottom-up reports. Inputs are
# either SOURCED anchors (cited in the driver) or TRANSPARENT scenario
# assumptions (labelled in the driver) — never LLM-asserted results.
# kWh_el = thermal energy delivered / SEER ; thermal = P_cool[kW] x EFLH[h].

def cooling_kwh(p_cool_kw, eflh_h, seer):
    """Seasonal electricity [kWh] of a cooling unit.
    thermal_kWh = P_cool x equivalent-full-load-hours ; electric = thermal / SEER."""
    if seer <= 0:
        raise ValueError("SEER must be > 0")
    thermal = float(p_cool_kw) * float(eflh_h)
    return {"thermal_kwh": thermal, "kwh_el": thermal / float(seer)}


def to_eur(kwh, tariff_eur_kwh):
    """Electricity cost [€] = kWh x tariff."""
    return float(kwh) * float(tariff_eur_kwh)


def share_pct(part_eur, base_eur):
    """part / (part + base) as % — AC € as a share of the summer electricity bill."""
    denom = float(part_eur) + float(base_eur)
    if denom == 0:
        raise ValueError("zero summer bill")
    return float(part_eur) / denom * 100.0


def degree_day_cost(season_kwh, season_cdd, tariff_eur_kwh):
    """Marginal cost of weather: € per extra cooling degree-day, and per +1°C
    sustained over the cooling season (delta_CDD = season_days x 1°C ≈ a season's
    worth of days). Returns €/CDD; caller multiplies by a CDD delta or season days."""
    if season_cdd <= 0:
        raise ValueError("season CDD must be > 0")
    kwh_per_cdd = float(season_kwh) / float(season_cdd)
    return {"kwh_per_cdd": kwh_per_cdd,
            "eur_per_cdd": kwh_per_cdd * float(tariff_eur_kwh)}


def efficiency_savings(thermal_kwh, seer_old, seer_new, tariff_eur_kwh):
    """Old vs new unit on the SAME thermal demand: kWh + € + % saved."""
    if seer_old <= 0 or seer_new <= 0:
        raise ValueError("SEER must be > 0")
    kwh_old = float(thermal_kwh) / float(seer_old)
    kwh_new = float(thermal_kwh) / float(seer_new)
    return {"kwh_old": kwh_old, "kwh_new": kwh_new,
            "kwh_saved": kwh_old - kwh_new,
            "eur_saved": (kwh_old - kwh_new) * float(tariff_eur_kwh),
            "pct_saved": (kwh_old - kwh_new) / kwh_old * 100.0}


def national_estimate(households, diffusion_frac, avg_kwh_per_unit, tariff_eur_kwh):
    """Bottom-up national scale: households x diffusion x avg seasonal kWh.
    Returns AC households, TWh, and € (transparent estimate — avg_kwh is an assumption)."""
    ac_hh = float(households) * float(diffusion_frac)
    kwh = ac_hh * float(avg_kwh_per_unit)
    return {"ac_households": ac_hh, "twh": kwh / 1e9,
            "eur_total": kwh * float(tariff_eur_kwh)}


def tou_shift(ac_kwh, price_f1_eur_kwh, price_f23_eur_kwh):
    """Cost difference of running cooling in F1 (day) vs F23 (eve/night), on the
    energy component. spread>0 => F1 cheaper (running by day saves). Returns the
    €/season difference for the given AC kWh + whether F1 is the cheaper band."""
    spread = float(price_f23_eur_kwh) - float(price_f1_eur_kwh)  # >0: F1 cheaper
    return {"spread_eur_kwh": spread, "eur_diff_season": float(ac_kwh) * spread,
            "f1_cheaper": spread > 0}


def weighted_mean(pairs):
    """Hours-weighted mean of [(value, weight), ...] — e.g. F23 = mean(F2,F3 by hours)."""
    num = sum(float(v) * float(w) for v, w in pairs)
    den = sum(float(w) for _, w in pairs)
    if den == 0:
        raise ValueError("zero total weight")
    return num / den


def growth_multiplier(*factors):
    """Compound several relative factors (e.g. diffusion ratio x CDD ratio) into a
    single multiplier and a % growth. Pure product — provenance of each factor is
    the caller's (real series ratios)."""
    m = 1.0
    for f in factors:
        m *= float(f)
    return {"multiplier": m, "pct_growth": (m - 1.0) * 100.0}


def run(analysis_id, method_text, data, unit="", inputs=()):
    """Dispatch one analysis. `data` carries the series the chosen method needs.
    Hard / unknown / missing-data methods -> [DA CALCOLARE] flag, never a fake number."""
    key = classify_method(method_text)
    if key is None:
        return _flag(analysis_id, method_text, f"metodo non riconosciuto: '{method_text}'")
    if key in HARD:
        return _flag(analysis_id, method_text, f"metodo {key} non implementato nell'MVP")
    try:
        if key == "descriptive":
            val, metric = descriptive(data["series"]), "descrittive (mean/median/stdev)"
        elif key == "pct_change":
            val, metric = pct_change(data["series"]), "variazione %"
        elif key == "event_study_car":
            val = event_study_car(data["series"], data["event_index"], data["window"])
            metric = "CAR % + t-stat (p normal-approx)"
        elif key == "correlation":
            val, metric = correlation(data["x"], data["y"]), "correlazione (Pearson)"
        elif key == "pass_through":
            val = pass_through(data["wholesale"], data["retail"])
            metric = "coefficiente di pass-through (OLS)"
        elif key == "lead_lag":
            val = lead_lag(data["x"], data["y"], data.get("max_lag", 10))
            metric = "lead-lag (giorni)"
        elif key == "cross_country":
            val = cross_country(data["it"], data["other"])
            metric = "gap cross-country (%/ratio)"
        elif key == "thermal_cooling":
            val = thermal_cooling(
                data["K_cond"], data["K_inf"], data["delta_T"],
                data["seer"], data["hours_day"], data["season_days"],
                data["tariff_eur_kwh"],
            )
            metric = "fabbisogno termico -> kWh el -> €/stag"
        elif key == "sweep_t_in":
            val = sweep_t_in(
                data["K_cond"], data["K_inf"], data["T_ext"],
                data["T_in_list"], data["seer"], data["hours_day"],
                data["season_days"], data["tariff_eur_kwh"],
            )
            metric = "sweep T_interna -> kWh/€"
        elif key == "old_vs_new":
            val = old_vs_new(
                data["thermal_kwh"], data["seer_old"], data["seer_new"],
                data["tariff_eur_kwh"],
            )
            metric = "vecchio vs A+++ (kWh+€)"
        else:  # pragma: no cover
            return _flag(analysis_id, method_text, f"dispatch mancante per {key}")
    except (KeyError, ValueError, ZeroDivisionError, st.StatisticsError) as e:
        return _flag(analysis_id, method_text, f"dati insufficienti/non validi: {e}")
    return _ok(analysis_id, method_text, metric, val, unit, inputs,
               note="p_value normal-approx" if key == "event_study_car" else None)


def main():
    """Read one JSON request per line and emit one deterministic JSON result per line."""
    for line_number, line in enumerate(sys.stdin, start=1):
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            result = run(
                request["analysis_id"], request["method"], request["data"],
                request.get("unit", ""), request.get("inputs", ()),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"Invalid request on line {line_number}: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
