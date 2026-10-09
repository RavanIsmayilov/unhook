"""The one function the Telegram bot (and later the API) call: analyze + store the redacted report.

Try it without Telegram:
    python -m app.service "salam, bonusunuz hazirdir: bonus-azercell.top/qazan"
    python -m app.service --image path/to/screenshot.png
"""
import sys

from app import db, webhooks
from app.analyzer import analyze
from app.formatting import format_verdict
from app.schemas import Verdict


def check(text: str | None, image_bytes: bytes | None = None, source: str = "api", lang: str = "az") -> tuple[Verdict, int | None]:
    """Analyze, then store the redacted report. A storage failure never blocks the answer."""
    verdict = analyze(text, image_bytes, check_domain_age=True, lang=lang)
    try:
        report_id = db.save_report(verdict, source=source, had_image=image_bytes is not None)
    except Exception as e:
        print(f"[service] could not save report: {type(e).__name__}: {e}", file=sys.stderr)
        report_id = None
    if source != "challenge":  # made-up scams must not alert partners
        webhooks.notify_in_background(verdict, report_id)
    return verdict, report_id


if __name__ == "__main__":
    args = sys.argv[1:]
    image = None
    if "--image" in args:
        i = args.index("--image")
        with open(args[i + 1], "rb") as f:
            image = f.read()
        args = args[:i] + args[i + 2:]
    db.init_db()
    v, rid = check(" ".join(args), image, source="cli")
    print(format_verdict(v).replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
          .replace("<code>", "").replace("</code>", ""))
    print(f"\n[saved as report #{rid}]")
