"""Turn the messages that fooled the detector in the website challenge into test cases.

    python challenge_misses.py            # append them to data/attack_misses.csv (skips ones already there)

They were typed by people who claim they are scams, but nobody verified that: review them before using them as labels.
"""
import csv
from pathlib import Path

from app import db, settings

PATH = settings.DATA_DIR / "attack_misses.csv"
COLUMNS = ["id", "text", "label", "variant", "source", "technique", "seed_id", "verdict", "confidence", "analyzer"]


def main() -> None:
    db.init_db()
    fooled = [r for r in db.recent_reports(1000, only_source="challenge") if r["verdict"] == "safe" and not r["degraded"]]
    existing = set()
    if PATH.exists():
        with open(PATH, encoding="utf-8", newline="") as f:
            existing = {r["text"] for r in csv.DictReader(f)}
    new = [r for r in reversed(fooled) if r["text_redacted"] not in existing]
    write_header = not PATH.exists() or PATH.stat().st_size == 0
    with open(PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            w.writeheader()
        for r in new:
            w.writerow({"id": f"H{r['id']:04d}", "text": r["text_redacted"], "label": "scam", "variant": "az",
                        "source": "human challenge (unverified)", "technique": "human", "seed_id": "",
                        "verdict": r["verdict"], "confidence": round(r["confidence"], 2), "analyzer": f"{r['provider']}/{r['model']}"})
    print(f"{len(new)} new messages added to {PATH} ({len(fooled)} fooled the detector in total)")


if __name__ == "__main__":
    main()
