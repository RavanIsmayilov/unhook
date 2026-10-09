"""Tell partners (banks, telecoms) when a scam report mentions their brand.

Each event is a JSON POST signed with HMAC-SHA256 of the raw body, using the partner's webhook secret:
    X-Unhook-Signature: sha256=<hex>      X-Unhook-Event: report.flagged
"""
import hashlib
import hmac
import json
import sys
import threading
from datetime import datetime, timezone

import httpx

from app import db
from app.clustering import brands_of, campaign_domains
from app.schemas import SCHEME_AZ, Verdict

TIMEOUT_SECONDS = 5


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def build_event(verdict: Verdict, report_id: int | None) -> dict:
    links = [{"domain": l.domain, "status": l.status, "flags": l.flags} for l in verdict.links]
    report = {"links": links}
    return {
        "event": "report.flagged",
        "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report": {
            "id": report_id, "verdict": verdict.verdict, "scheme": verdict.scheme,
            "scheme_az": SCHEME_AZ.get(verdict.scheme, verdict.scheme), "confidence": verdict.confidence,
            "text_redacted": verdict.text_redacted, "domains": campaign_domains(report), "brands": brands_of(report),
        },
    }


def send(partner: dict, event: dict) -> bool:
    body = json.dumps(event, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json", "X-Unhook-Event": event["event"],
               "X-Unhook-Signature": sign(body, partner["webhook_secret"])}
    try:
        return httpx.post(partner["webhook_url"], content=body, headers=headers, timeout=TIMEOUT_SECONDS).is_success
    except httpx.HTTPError as e:
        print(f"[webhook] {partner['name']}: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def notify(verdict: Verdict, report_id: int | None) -> int:
    """Send the event to every partner whose brand is mentioned (or who watches all brands). Returns how many were tried."""
    if verdict.verdict == "safe" or verdict.degraded:
        return 0
    event = build_event(verdict, report_id)
    brands = {b.lower() for b in event["report"]["brands"]}
    sent = 0
    for partner in db.webhook_partners():
        if partner["brand"] is None and not brands:
            continue  # "all brands" partners only want reports that impersonate someone
        if partner["brand"] is None or partner["brand"].lower() in brands:
            send(partner, event)
            sent += 1
    return sent


def notify_in_background(verdict: Verdict, report_id: int | None) -> None:
    """Never slow down or break the answer to the user."""
    def run():
        try:
            notify(verdict, report_id)
        except Exception as e:
            print(f"[webhook] failed: {type(e).__name__}: {e}", file=sys.stderr)

    threading.Thread(target=run, daemon=True).start()
