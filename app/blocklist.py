"""A domain blocklist for banks and telecoms, built from reports that were judged scam/suspicious."""
import csv
import io
from collections import Counter

from app.clustering import brands_of, campaign_domains

CSV_COLUMNS = ["domain", "reports", "first_seen", "last_seen", "brands", "status"]


def build_blocklist(reports: list[dict], brand: str | None = None, min_reports: int = 1) -> list[dict]:
    """One row per suspicious domain (official domains, shorteners and generic sites are never listed)."""
    found: dict[str, dict] = {}
    for r in reports:
        if r["verdict"] not in ("scam", "suspicious") or r["degraded"]:
            continue
        statuses = {l["domain"]: l["status"] for l in r.get("links", [])}
        for domain in set(campaign_domains(r)):
            entry = found.setdefault(domain, {"domain": domain, "reports": 0, "first_seen": r["created_at"],
                                              "last_seen": r["created_at"], "brands": Counter(), "statuses": Counter()})
            entry["reports"] += 1
            entry["first_seen"] = min(entry["first_seen"], r["created_at"])
            entry["last_seen"] = max(entry["last_seen"], r["created_at"])
            entry["brands"].update(brands_of(r))
            entry["statuses"][statuses.get(domain, "unknown")] += 1

    rows = [{"domain": e["domain"], "reports": e["reports"], "first_seen": e["first_seen"], "last_seen": e["last_seen"],
             "brands": [b for b, _ in e["brands"].most_common()], "status": e["statuses"].most_common(1)[0][0]}
            for e in found.values() if e["reports"] >= min_reports]
    if brand:
        rows = [r for r in rows if brand.lower() in (b.lower() for b in r["brands"])]
    return sorted(rows, key=lambda r: (r["reports"], r["last_seen"]), reverse=True)


def blocklist_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow({**r, "brands": ";".join(r["brands"])})
    return out.getvalue()
