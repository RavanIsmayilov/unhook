"""Add REAL messages to data/labeled.csv, with personal data removed first.

1. Put one message per line in data/real_messages.txt, starting with its label:
       scam | Hörmətli müştəri, kartınız bloklanıb. Təcili keçin: kapital-bank-yoxla.top/giris
       safe | Kapital Bank: 4821 kodu heç kimə verməyin. Ödəniş 25.00 AZN təsdiqləndi.
   Lines starting with # are ignored. A message must fit on one line.
2. python add_real.py
3. python eval.py --providers groq

Cards, phone numbers, IBANs, emails and one-time codes are replaced ([CARD], [PHONE], [OTP]...) BEFORE anything is
written, because labeled.csv is committed to Git. Check the new rows before you push. Domains are kept.
"""
import csv
import re
import sys

from app import settings
from app.redact import redact

SOURCE = "real message (collected by the team, personal data removed)"
INPUT = settings.DATA_DIR / "real_messages.txt"
OUTPUT = settings.DATA_DIR / "labeled.csv"
COLUMNS = ["id", "text", "label", "variant", "source"]


def detect_variant(text: str) -> str:
    if re.search(r"[а-яА-ЯёЁ]", text):
        return "az_ru"
    return "az" if re.search(r"[əıöüşçğƏİÖÜŞÇĞ]", text) else "translit"


def parse(lines: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    rows, problems = [], []
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        label, sep, text = line.partition("|")
        label, text = label.strip().lower(), text.strip()
        if not sep or label not in ("scam", "safe") or not text:
            problems.append(f"line {n}: expected 'scam | message' or 'safe | message'")
            continue
        rows.append((label, text))
    return rows, problems


def main() -> None:
    if not INPUT.exists():
        sys.exit(f"Create {INPUT} first (see the instructions at the top of add_real.py).")
    rows, problems = parse(INPUT.read_text(encoding="utf-8").splitlines())
    with open(OUTPUT, encoding="utf-8", newline="") as f:
        existing = list(csv.DictReader(f))
    known = {r["text"] for r in existing}
    next_id = 1 + max([int(m.group(1)) for r in existing if (m := re.match(r"R(\d+)-", r["id"]))] or [0])

    added = 0
    with open(OUTPUT, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        for label, text in rows:
            clean = redact(text)
            if clean in known:
                continue
            known.add(clean)
            w.writerow({"id": f"R{next_id:03d}-{detect_variant(clean)}", "text": clean, "label": label,
                        "variant": detect_variant(clean), "source": SOURCE})
            next_id += 1
            added += 1
    for p in problems:
        print("skipped", p)
    print(f"{added} messages added to {OUTPUT.name} ({len(rows) - added} duplicates skipped)")


if __name__ == "__main__":
    main()
