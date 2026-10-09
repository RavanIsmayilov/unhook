"""Fill the database with DEMO reports so the dashboard has campaigns to show. No LLM calls, no API keys needed.

    python seed_demo.py            # (re)create demo reports, spread over the last 7 days
    python seed_demo.py --clear    # remove them again

Demo reports come from our synthetic data/labeled.csv, are stored with source="demo", and are never mixed up with real
ones: re-running only replaces rows whose source is "demo".
"""
import argparse
import csv
import random
from datetime import datetime, timedelta, timezone

from app import db, settings
from app.linkcheck import check_links
from app.redact import redact
from app.schemas import Verdict

SCHEME_BY_GROUP = {
    "S001": "fake_bonus", "S002": "bank_impersonation", "S003": "bank_impersonation", "S004": "fake_job",
    "S005": "delivery_scam", "S006": "investment_scam", "S007": "other", "S008": "fake_bonus", "S009": "other",
}


def seed(rng: random.Random, now: datetime) -> int:
    with open(settings.DATA_DIR / "labeled.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    created = 0
    for r in rows:
        scam = r["label"] == "scam"
        copies = rng.randint(1, 3) if scam else 1  # a campaign is reported by several people
        for _ in range(copies):
            when = now - timedelta(hours=rng.uniform(0, 7 * 24) ** 0.9)  # more recent than old
            verdict = Verdict(
                verdict="scam" if scam else "safe",
                scheme=SCHEME_BY_GROUP.get(r["id"].rsplit("-", 1)[0], "other") if scam else "none",
                reasons=["Demo məlumatı"], actions=[], confidence=round(rng.uniform(0.85, 0.99), 2),
                links=check_links(r["text"]), text_redacted=redact(r["text"]), provider="demo", model="demo",
            )
            db.save_report(verdict, source="demo", created_at=when)
            created += 1
    return created


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clear", action="store_true", help="only remove demo reports")
    args = ap.parse_args()
    db.init_db()
    removed = db.delete_reports("demo")
    if args.clear:
        print(f"Removed {removed} demo reports.")
        return
    n = seed(random.Random(7), datetime.now(timezone.utc).replace(tzinfo=None))
    print(f"Replaced {removed} old demo reports with {n} new ones (source='demo').")


if __name__ == "__main__":
    main()
