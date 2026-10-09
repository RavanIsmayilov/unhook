import csv
import io
import random
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
import seed_demo
from app import db, llm, settings
from app.blocklist import blocklist_csv, build_blocklist
from app.schemas import Verdict

NOW = datetime(2026, 10, 8, 12, 0, 0)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr("app.settings.CACHE_PATH", tmp_path / "cache.sqlite")
    monkeypatch.setattr("app.llm.time.sleep", lambda s: None)
    db.init_db()


@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


# ---------------------------------------------------------------- blocklist

def test_blocklist_from_demo_data(client):
    seed_demo.seed(random.Random(7), NOW)
    rows = client.get("/blocklist").json()
    domains = {r["domain"] for r in rows}
    assert {"kapitalbank-secure.xyz", "nar-udus.click", "azerpost-delivery.top"} <= domains
    assert "azercell.com" not in domains and "bit.ly" not in domains and "t.me" not in domains
    top = rows[0]
    assert top["reports"] >= rows[-1]["reports"] and top["brands"] and top["status"] in ("lookalike", "suspicious", "unknown")
    only_nar = client.get("/blocklist", params={"brand": "nar"}).json()
    assert only_nar and all("Nar" in r["brands"] for r in only_nar)
    assert client.get("/blocklist", params={"min_reports": 999}).json() == []


def test_blocklist_csv(client):
    seed_demo.seed(random.Random(7), NOW)
    r = client.get("/blocklist", params={"format": "csv"})
    assert r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    parsed = list(csv.DictReader(io.StringIO(r.text)))
    assert parsed and list(parsed[0]) == ["domain", "reports", "first_seen", "last_seen", "brands", "status"]


def test_blocklist_ignores_safe_and_degraded():
    link = [{"domain": "evil-bonus.top", "status": "suspicious", "flags": []}]
    base = {"links": link, "created_at": "2026-10-08T10:00:00", "degraded": False}
    reports = [{**base, "verdict": "safe"}, {**base, "verdict": "scam", "degraded": True}, {**base, "verdict": "scam"}]
    rows = build_blocklist(reports)
    assert len(rows) == 1 and rows[0]["reports"] == 1
    assert "evil-bonus.top,1" in blocklist_csv(rows)


# ---------------------------------------------------------------- feedback

def make_report() -> int:
    v = Verdict(verdict="scam", scheme="fake_bonus", reasons=["r"], actions=["a"], confidence=0.9, text_redacted="bonus [PHONE]")
    return db.save_report(v, source="api")


def test_feedback_flow(client):
    rid = make_report()
    assert client.post("/feedback", json={"report_id": rid, "agrees": True}).json()["ok"]
    r = client.post("/feedback", json={"report_id": rid, "agrees": False, "suggested": "safe", "note": "zəng et 0501234567"})
    assert r.status_code == 200
    stats = client.get("/stats").json()
    assert stats["feedback"] == {"total": 2, "agree": 1, "disagree": 1}
    [wrong] = client.get("/feedback/recent").json()
    assert wrong["report_id"] == rid and wrong["model_verdict"] == "scam" and wrong["suggested"] == "safe"
    assert "0501234567" not in wrong["note"] and "[PHONE]" in wrong["note"]  # notes are redacted too


def test_feedback_validation(client):
    rid = make_report()
    assert client.post("/feedback", json={"report_id": rid, "agrees": False}).status_code == 422  # must say what it is
    assert client.post("/feedback", json={"report_id": 9999, "agrees": True}).status_code == 404
    assert client.post("/feedback", json={"report_id": rid, "agrees": False, "suggested": "maybe"}).status_code == 422
    assert client.get("/stats").json()["feedback"]["total"] == 0


# ---------------------------------------------------------------- model fallback chain

def test_chain_walks_other_models_before_giving_up(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_MODEL", "big")
    monkeypatch.setattr(settings, "GROQ_FALLBACK_MODELS", ["big", "small", "other"])
    seen = []

    def groq(system, prompt, image, schema, temperature, max_tokens, model=None):
        seen.append(model)
        if model != "other":
            raise llm.LLMUnavailable("rate limited")
        return "{}"

    monkeypatch.setitem(llm._PROVIDERS, "groq", groq)
    r = llm.generate("groq", "s", "p")
    assert seen == ["big", "small", "other"] and (r.provider, r.model) == ("groq", "other")


def test_chain_for_gemini_images_stays_on_gemini(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_FALLBACK_MODELS", ["lite"])
    tried = []

    def gemini(system, prompt, image, schema, temperature, max_tokens, model=None):
        tried.append(model)
        if model != "lite":
            raise llm.LLMUnavailable("quota")
        return "text from image"

    def groq(*a, **k):
        raise AssertionError("groq has no vision and must not be tried for images")

    monkeypatch.setitem(llm._PROVIDERS, "gemini", gemini)
    monkeypatch.setitem(llm._PROVIDERS, "groq", groq)
    r = llm.generate("gemini", "s", "p", image=b"\x89PNG..")
    assert r.model == "lite" and tried[-1] == "lite"


def test_chain_off_when_fallback_false(monkeypatch):
    calls = []

    def groq(system, prompt, image, schema, temperature, max_tokens, model=None):
        calls.append(model)
        raise llm.LLMUnavailable("limit")

    monkeypatch.setitem(llm._PROVIDERS, "groq", groq)
    with pytest.raises(llm.LLMUnavailable):
        llm.generate("groq", "s", "p", fallback=False)
    assert len(calls) == 1
