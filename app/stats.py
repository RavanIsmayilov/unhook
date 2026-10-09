"""Numbers for the dashboard's overview page."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.clustering import brands_of, campaign_domains
from app.schemas import SCHEME_AZ


def compute_stats(reports: list[dict], campaigns: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    day_ago = (now - timedelta(hours=24)).isoformat()
    ok = [r for r in reports if not r["degraded"]]
    threats = [r for r in ok if r["verdict"] in ("scam", "suspicious")]

    daily = []
    for offset in range(6, -1, -1):  # last 7 days, oldest first, zero-filled
        day = (now - timedelta(days=offset)).date().isoformat()
        of_day = [r for r in reports if r["created_at"][:10] == day]
        daily.append({"date": day, "total": len(of_day), "scam": sum(r["verdict"] == "scam" for r in of_day)})

    return {
        "total_reports": len(reports),
        "reports_last_24h": sum(r["created_at"] >= day_ago for r in reports),
        "by_verdict": {v: sum(r["verdict"] == v for r in reports) for v in ("scam", "suspicious", "safe")},
        "degraded_reports": len(reports) - len(ok),
        "by_scheme": [{"scheme": s, "scheme_az": SCHEME_AZ.get(s, s), "count": c}
                      for s, c in Counter(r["scheme"] for r in threats if r["scheme"] != "none").most_common()],
        "top_brands": [{"brand": b, "count": c} for b, c in Counter(b for r in threats for b in brands_of(r)).most_common(10)],
        "top_domains": [{"domain": d, "count": c}
                        for d, c in Counter(d for r in threats for d in set(campaign_domains(r))).most_common(10)],
        "by_source": dict(Counter(r["source"] for r in reports)),
        "campaigns_total": len(campaigns),
        "campaigns_active_24h": sum(c["last_seen"] >= day_ago for c in campaigns),
        "daily": daily,
    }
