import csv

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
import challenge_misses
from app import db, service
from app.schemas import Link, Verdict


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


def fake_analyze(verdict_for):
    def analyze(text, image):
        return Verdict(verdict=verdict_for(text), scheme="fake_bonus", reasons=["səbəb"], actions=["a"], confidence=0.9,
                       text_redacted=text, provider="groq", model="m",
                       links=[Link(url="bonus-azercell.top", domain="bonus-azercell.top", status="lookalike",
                                   flags=["brand_in_domain:Azercell"])])
    return analyze


def test_challenge_scoreboard(client, monkeypatch):
    monkeypatch.setattr(service, "analyze", fake_analyze(lambda t: "safe" if "sneaky" in t else "scam" if "obvious" in t else "suspicious"))
    for text in ("obvious scam", "sneaky one", "sneaky two", "something odd"):
        r = client.post("/challenge", json={"text": text})
        assert r.status_code == 200 and r.json()["report_id"]
    stats = client.get("/challenge/stats").json()
    assert (stats["attempts"], stats["fooled"], stats["unsure"], stats["caught"]) == (4, 2, 1, 1)
    assert stats["fooled_rate"] == 0.5
    assert [x["text"] for x in stats["fooled_examples"]] == ["sneaky two", "sneaky one"]  # newest first


def test_challenge_messages_never_pollute_real_data(client, monkeypatch):
    monkeypatch.setattr(service, "analyze", fake_analyze(lambda t: "scam"))
    client.post("/challenge", json={"text": "made up bonus-azercell.top scam"})
    assert client.get("/stats").json()["total_reports"] == 0
    assert client.get("/reports/recent").json() == []
    assert client.get("/campaigns").json() == [] and client.get("/blocklist").json() == []
    assert db.recent_reports(10) == [] and len(db.recent_reports(10, only_source="challenge")) == 1


def test_challenge_never_alerts_partners(client, monkeypatch):
    monkeypatch.setattr(service, "analyze", fake_analyze(lambda t: "scam"))
    alerts = []
    monkeypatch.setattr(service.webhooks, "notify_in_background", lambda *a: alerts.append(a))
    client.post("/challenge", json={"text": "made up scam"})
    assert alerts == []
    client.post("/check", json={"text": "a real check"})
    assert len(alerts) == 1  # the normal path still notifies


def test_challenge_validation_and_degraded_attempts_do_not_count(client, monkeypatch):
    assert client.post("/challenge", json={"text": ""}).status_code == 422
    assert client.post("/challenge", json={"text": "   "}).status_code == 422
    assert client.post("/challenge", json={"text": "x" * 1001}).status_code == 422
    monkeypatch.setattr(service, "analyze", lambda text, image: Verdict(
        verdict="suspicious", scheme="other", reasons=[], actions=[], confidence=0.3, degraded=True, text_redacted=text))
    assert client.post("/challenge", json={"text": "no AI available"}).status_code == 200
    assert client.get("/challenge/stats").json()["attempts"] == 0


def test_fooling_messages_become_test_cases(client, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(service, "analyze", fake_analyze(lambda t: "safe" if "sneaky" in t else "scam"))
    client.post("/challenge", json={"text": "sneaky bonus"})
    client.post("/challenge", json={"text": "obvious bonus"})
    target = tmp_path / "attack_misses.csv"
    monkeypatch.setattr(challenge_misses, "PATH", target)
    challenge_misses.main()
    challenge_misses.main()  # running twice adds nothing new
    rows = list(csv.DictReader(open(target, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["text"] == "sneaky bonus" and rows[0]["label"] == "scam"
    assert "unverified" in rows[0]["source"] and list(rows[0]) == challenge_misses.COLUMNS
