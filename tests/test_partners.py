import hashlib
import hmac
import json
import random
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
import partners
import seed_demo
from app import db, webhooks
from app.schemas import Link, Verdict

NOW = datetime(2026, 10, 8, 12, 0, 0)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr("app.settings.CACHE_PATH", tmp_path / "cache.sqlite")
    db.init_db()


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


def H(key):
    return {"X-API-Key": key}


# ---------------------------------------------------------------- keys

def test_key_is_shown_once_and_only_its_hash_is_stored():
    partner, key = db.create_partner("Azercell", brand="Azercell")
    assert key.startswith("unhook_") and len(key) > 30
    from sqlalchemy import text
    with db.engine.connect() as c:
        stored = c.execute(text("select key_hash, key_prefix from partners")).one()
    assert stored[0] == hashlib.sha256(key.encode()).hexdigest() and key not in stored
    assert db.get_partner_by_key(key)["name"] == "Azercell" and db.get_partner_by_key("nope") is None
    with pytest.raises(ValueError):
        db.create_partner("Azercell")
    _, new_key = db.create_partner("Azercell", brand="Azercell", replace=True)
    assert db.get_partner_by_key(key) is None and db.get_partner_by_key(new_key)


def test_revoked_key_stops_working(client):
    _, key = db.create_partner("Kapital Bank", brand="Kapital Bank")
    assert client.get("/partner/me", headers=H(key)).json() == {"name": "Kapital Bank", "brand": "Kapital Bank", "webhook": False}
    assert db.revoke_partner("Kapital Bank") and not db.revoke_partner("ghost")
    assert client.get("/partner/me", headers=H(key)).status_code == 401


def test_endpoints_need_a_valid_key(client):
    for path in ("/partner/me", "/partner/summary", "/partner/campaigns", "/partner/blocklist"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=H("wrong")).status_code == 401
    assert client.post("/partner/check", json={"text": "x"}).status_code == 401


# ---------------------------------------------------------------- brand scoping

def test_partner_sees_only_its_own_brand(client):
    seed_demo.seed(random.Random(7), NOW)
    _, az = db.create_partner("Azercell", brand="Azercell")
    _, kb = db.create_partner("Kapital Bank", brand="Kapital Bank")
    _, everyone = db.create_partner("Regulator")

    camps = client.get("/partner/campaigns", headers=H(az)).json()
    assert camps and all("Azercell" in c["brands"] for c in camps)
    assert all("Kapital Bank" not in c["brands"] for c in camps)

    domains = {r["domain"] for r in client.get("/partner/blocklist", headers=H(az)).json()}
    assert domains == {"azercell-bonus.top"}
    assert "kapitalbank-secure.xyz" in {r["domain"] for r in client.get("/partner/blocklist", headers=H(kb)).json()}

    all_domains = {r["domain"] for r in client.get("/partner/blocklist", headers=H(everyone)).json()}
    assert {"azercell-bonus.top", "kapitalbank-secure.xyz", "nar-udus.click"} <= all_domains

    summary = client.get("/partner/summary", headers=H(az)).json()
    assert summary["partner"]["brand"] == "Azercell" and summary["campaigns"] >= 1 and summary["blocklist_domains"] == 1
    assert summary["reports_total"] < client.get("/partner/summary", headers=H(everyone)).json()["reports_total"]

    csv_text = client.get("/partner/blocklist", headers=H(az), params={"format": "csv"}).text
    assert "azercell-bonus.top" in csv_text and "kapitalbank" not in csv_text


# ---------------------------------------------------------------- checking

def test_partner_check_and_batch(client, monkeypatch):
    def fake_check(text, image, source):
        return Verdict(verdict="scam" if "bonus" in text else "safe", scheme="fake_bonus", reasons=["r"], actions=["a"],
                       confidence=0.9, provider="groq", model="m"), 7

    monkeypatch.setattr(api, "check", fake_check)
    _, key = db.create_partner("Nar", brand="Nar")
    assert client.post("/partner/check", headers=H(key), json={"text": "bonus var"}).json()["verdict"] == "scam"

    r = client.post("/partner/check/batch", headers=H(key), json={"messages": ["bonus var", "salam", "   "]})
    assert r.status_code == 200
    out = r.json()
    assert [o["index"] for o in out] == [0, 1, 2]
    assert out[0]["verdict"] == "scam" and out[1]["verdict"] == "safe" and out[2]["error"] == "empty message"
    assert client.post("/partner/check/batch", headers=H(key), json={"messages": ["x"] * 11}).status_code == 422
    assert client.post("/partner/check/batch", headers=H(key), json={"messages": []}).status_code == 422


# ---------------------------------------------------------------- webhooks

def flagged(brand="Azercell", verdict="scam", degraded=False):
    flag = f"brand_in_domain:{brand}" if brand else "suspicious_word:bonus"
    return Verdict(verdict=verdict, scheme="fake_bonus", reasons=[], actions=[], confidence=0.9, degraded=degraded,
                   text_redacted="bonus [PHONE] bonus-x.top", links=[Link(url="bonus-x.top", domain="bonus-x.top",
                                                                          status="lookalike", flags=[flag])])


def test_webhook_is_signed_and_scoped_to_brand(monkeypatch):
    sent = []
    monkeypatch.setattr(webhooks.httpx, "post", lambda url, content, headers, timeout: sent.append((url, content, headers)) or
                        type("R", (), {"is_success": True})())
    partner, _ = db.create_partner("Azercell", brand="Azercell", webhook_url="https://hooks.example/az")
    db.create_partner("Kapital Bank", brand="Kapital Bank", webhook_url="https://hooks.example/kb")
    db.create_partner("No webhook", brand="Azercell")

    assert webhooks.notify(flagged("Azercell"), 5) == 1
    [(url, body, headers)] = sent
    assert url == "https://hooks.example/az" and headers["X-Unhook-Event"] == "report.flagged"
    expected = "sha256=" + hmac.new(partner["webhook_secret"].encode(), body, hashlib.sha256).hexdigest()
    assert headers["X-Unhook-Signature"] == expected
    event = json.loads(body)
    assert event["report"]["id"] == 5 and event["report"]["brands"] == ["Azercell"] and event["report"]["domains"] == ["bonus-x.top"]
    assert "[PHONE]" in event["report"]["text_redacted"]


def test_webhook_skips_safe_degraded_and_other_brands(monkeypatch):
    sent = []
    monkeypatch.setattr(webhooks.httpx, "post", lambda *a, **k: sent.append(1) or type("R", (), {"is_success": True})())
    db.create_partner("Azercell", brand="Azercell", webhook_url="https://hooks.example/az")
    db.create_partner("Watcher", webhook_url="https://hooks.example/all")  # all brands
    assert webhooks.notify(flagged("Azercell", verdict="safe"), 1) == 0
    assert webhooks.notify(flagged("Azercell", degraded=True), 1) == 0
    assert webhooks.notify(flagged("Kapital Bank"), 1) == 1          # only the watcher
    assert webhooks.notify(flagged(None), 1) == 0                     # no brand impersonated: nobody asked for this
    assert len(sent) == 1


def test_webhook_failure_never_raises(monkeypatch):
    def boom(*a, **k):
        raise webhooks.httpx.ConnectError("down")

    monkeypatch.setattr(webhooks.httpx, "post", boom)
    db.create_partner("Azercell", brand="Azercell", webhook_url="https://hooks.example/az")
    assert webhooks.notify(flagged("Azercell"), 1) == 1


def test_cli_create_and_list(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["partners.py", "create", "Bakcell", "--brand", "Bakcell"])
    partners.main()
    assert "API key : unhook_" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["partners.py", "list"])
    partners.main()
    assert "Bakcell" in capsys.readouterr().out
