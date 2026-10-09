"""Manage partner API keys (banks, telecoms).

    python partners.py create "Azercell" --brand Azercell [--webhook https://...]
    python partners.py demo                  # two demo partners: Azercell and Kapital Bank (keys are re-created)
    python partners.py list
    python partners.py revoke "Azercell"
    python partners.py test-webhook "Azercell"   # sends a sample event to its webhook

The API key is printed once and never stored (only a hash). Keep it somewhere safe.
"""
import argparse
import sys

from app import db, webhooks
from app.schemas import Link, Verdict


def show(partner: dict, key: str) -> None:
    print(f"\nPartner : {partner['name']}  (brand: {partner['brand'] or 'all brands'})")
    print(f"API key : {key}")
    if partner["webhook_url"]:
        print(f"Webhook : {partner['webhook_url']}\nSecret  : {partner['webhook_secret']}  (signs each event)")
    print("Send it as the header  X-API-Key: <key>   or paste it on the /partner page.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("name")
    c.add_argument("--brand", help="brand this partner may see (omit for all brands)")
    c.add_argument("--webhook", help="URL that receives report.flagged events")
    sub.add_parser("demo")
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("name")
    t = sub.add_parser("test-webhook")
    t.add_argument("name")
    args = ap.parse_args()
    db.init_db()

    if args.cmd == "create":
        try:
            show(*db.create_partner(args.name, args.brand, args.webhook))
        except ValueError as e:
            sys.exit(str(e))
    elif args.cmd == "demo":
        for name, brand in (("Demo: Azercell", "Azercell"), ("Demo: Kapital Bank", "Kapital Bank")):
            show(*db.create_partner(name, brand, replace=True))
    elif args.cmd == "list":
        for p in db.list_partners():
            print(f"{'active ' if p['active'] else 'REVOKED'} {p['name']:<24} brand={p['brand'] or '*':<14} key={p['key_prefix']}…"
                  f"  webhook={p['webhook_url'] or '-'}")
    elif args.cmd == "revoke":
        print("revoked" if db.revoke_partner(args.name) else "no such partner")
    elif args.cmd == "test-webhook":
        found = [p for p in db.webhook_partners() if p["name"] == args.name]
        if not found:
            sys.exit("that partner has no webhook (create it with --webhook)")
        sample = Verdict(verdict="scam", scheme="fake_bonus", reasons=[], actions=[], confidence=0.97,
                         text_redacted="TEST: salam, bonusunuz hazirdir: bonus-example.top/qazan",
                         links=[Link(url="bonus-example.top", domain="bonus-example.top", status="lookalike",
                                     flags=[f"brand_in_domain:{found[0]['brand'] or 'Azercell'}"])])
        print("delivered" if webhooks.send(found[0], webhooks.build_event(sample, None)) else "FAILED (see message above)")


if __name__ == "__main__":
    main()
