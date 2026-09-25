#!/usr/bin/env python3
"""08_mark_sent.py — chiude il loop (D9): registra gli invii reali nel DB dashboard.

Dopo conferma umana "lista inviata": per ogni riga del CSV
  1. trova il giornalista per email (GET /api/journalists?search=)
  2. crea/recupera la campagna "report-outreach <report_name>"
  3. se il giornalista è GIÀ nella campagna -> SKIP (idempotenza)
  4. altrimenti: aggiungi alla campagna + PATCH contact_count+1, last_contacted=<sent-date>
Senza questo passo cooldown e fatigue sono ciechi al run successivo.

Uso:
    ACCESS_TOKEN=<tok> python3 tools/08_mark_sent.py --run-dir runs/<report> \
        --sent-date 2026-06-15 [--dry-run]
"""
import argparse
import csv
import os
from pathlib import Path

from lib_common import api_get, api_send, load_plan, parse_date, update_run_log


def find_journalist(api_base: str, token: str, email: str):
    res = api_get(api_base, "/api/journalists", token, {"search": email, "limit": 10})
    items = res if isinstance(res, list) else res.get("items", res.get("journalists", []))
    for j in items:
        if (j.get("email") or "").lower() == email.lower():
            return j
    return None


def get_or_create_campaign(api_base: str, token: str, name: str, market: str) -> dict:
    res = api_get(api_base, "/api/campaigns", token, {"market": market})
    items = res if isinstance(res, list) else res.get("items", res.get("campaigns", []))
    for c in items:
        if c.get("name") == name:
            return c
    return api_send(api_base, "/api/campaigns", token, {"name": name, "market": market})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--sent-date", required=True, help="YYYY-MM-DD (esplicita, no system date)")
    ap.add_argument("--api-base", required=True, help="Authorized API base URL; no service is assumed")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if parse_date(args.sent_date) is None:
        raise SystemExit("--sent-date invalida (YYYY-MM-DD)")

    plan = load_plan(args.run_dir)
    market = plan.get("market", "IT")
    campaign_name = f"report-outreach {plan.get('report_name') or plan.get('topic')}"
    csvs = sorted((Path(args.run_dir) / "OUTPUT").glob("*.csv"))
    if not csvs:
        raise SystemExit("CSV mancante in OUTPUT/")
    with csvs[0].open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("email")]

    if args.dry_run:
        print(f"DRY-RUN: marcherei sent {len(rows)} righe, campagna '{campaign_name}', "
              f"data {args.sent_date}")
        return

    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise SystemExit("ACCESS_TOKEN env mancante")

    campaign = get_or_create_campaign(args.api_base, token, campaign_name, market)
    cid = campaign["id"]
    detail = api_get(args.api_base, f"/api/campaigns/{cid}", token)
    already = {(j.get("email") or "").lower() for j in detail.get("journalists", [])}

    updated, skipped, missing = [], [], []
    for r in rows:
        email = r["email"].lower()
        if email in already:
            skipped.append(email)
            continue
        j = find_journalist(args.api_base, token, email)
        if j is None:
            missing.append(email)
            continue
        api_send(args.api_base, f"/api/campaigns/{cid}/journalists", token,
                 {"journalist_ids": [j["id"]]})
        api_send(args.api_base, f"/api/journalists/{j['id']}", token, {
            "contact_count": (j.get("contact_count") or 0) + 1,
            "last_contacted": args.sent_date,
        }, method="PATCH")
        updated.append(email)

    update_run_log(args.run_dir, "sent_marked", {
        "sent_date": args.sent_date, "campaign": campaign_name,
        "updated": len(updated), "skipped_already_in_campaign": len(skipped),
        "missing_from_db": missing,
    })
    print(f"OK updated={len(updated)} skipped={len(skipped)} missing={len(missing)}")
    if missing:
        print(f"NOTA: {len(missing)} email non nel DB (push 07 non eseguito?): {missing[:5]}")


if __name__ == "__main__":
    main()
