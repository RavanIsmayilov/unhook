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
    def analyze(text, image, **kw):
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
    monkeypatch.setattr(service, "analyze", lambda text, image, **kw: Verdict(
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


# ---------------------------------------------------------------- usage / cost

def test_usage_summary_and_cost():
    from app import usage
    entries = [
        {"model": "openai/gpt-oss-120b", "tokens_in": 1000, "tokens_out": 400, "latency_ms": 1000, "cached": False},
        {"model": "openai/gpt-oss-120b", "tokens_in": 2000, "tokens_out": 600, "latency_ms": 3000, "cached": False},
        {"model": "openai/gpt-oss-120b", "tokens_in": None, "tokens_out": None, "latency_ms": None, "cached": True},  # skipped
    ]
    s = usage.summarize(entries)
    assert s["calls"] == 2 and s["tokens_in_avg"] == 1500 and s["tokens_out_avg"] == 500
    assert s["latency_ms_p50"] in (1000, 3000) and s["latency_ms_p95"] == 3000
    assert s["calls_with_rate_limit_wait"] == 0 and s["model_ms_p95"] == 3000
    expected = ((1000 * 0.15 + 400 * 0.60) + (2000 * 0.15 + 600 * 0.60)) / 2 / 1_000_000
    assert abs(s["cost_per_check_usd"] - expected) < 1e-12
    assert usage.cost_of({"model": "unknown/model", "tokens_in": 5, "tokens_out": 5}) is None  # no price: no invented cost
    assert usage.summarize([{"cached": True}]) == {"calls": 0}


def test_old_database_gets_the_usage_column(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # a reports table as the first version created it: no usage column
        conn.execute(text("CREATE TABLE reports (id INTEGER PRIMARY KEY, created_at DATETIME, source VARCHAR(20), had_image BOOLEAN, "
                          "text_redacted TEXT, verdict VARCHAR(12), scheme VARCHAR(30), confidence FLOAT, reasons JSON, actions JSON, "
                          "explanation_az TEXT, links JSON, domains JSON, provider VARCHAR(20), model VARCHAR(60), degraded BOOLEAN)"))
        conn.execute(text("INSERT INTO reports (id, created_at, source, had_image, text_redacted, verdict, scheme, confidence, reasons, "
                          "actions, explanation_az, links, domains, provider, model, degraded) VALUES (1, '2026-10-08 10:00:00', 'telegram', 0, "
                          "'x', 'scam', 'fake_bonus', 0.9, '[]', '[]', '', '[]', '[]', 'groq', 'm', 0)"))
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()
    assert "usage" in {c["name"] for c in inspect(engine).get_columns("reports")}
    [row] = db.recent_reports(10)
    assert row["id"] == 1 and row["usage"] is None


def test_rate_limit_waits_are_reported_apart_from_model_time():
    from app import usage
    entries = [
        {"model": "m", "tokens_in": 10, "tokens_out": 5, "latency_ms": 1200, "waited_ms": 0, "cached": False},
        {"model": "m", "tokens_in": 10, "tokens_out": 5, "latency_ms": 9400, "waited_ms": 8000, "cached": False},
    ]
    s = usage.summarize(entries)
    assert s["calls_with_rate_limit_wait"] == 1 and s["model_ms_p95"] == 1400 and s["latency_ms_p95"] == 9400


def test_backoff_time_is_measured(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.random, "uniform", lambda a, b: 0)

    class Quota(Exception):
        code = 429

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise Quota("rate limit")
        return "ok"

    llm._waited.seconds = 0.0
    assert llm._with_backoff(flaky) == "ok"
    assert llm._waited.seconds == 2.0 + 4.0  # two retries: 2s, then 4s


def test_call_reports_the_wait_inside_its_latency(monkeypatch):
    from app import llm
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.random, "uniform", lambda a, b: 0)

    class Quota(Exception):
        code = 429

    def adapter(system, prompt, image, schema, temperature, max_tokens, model=None):
        state = adapter.__dict__.setdefault("n", [0])
        def attempt():
            state[0] += 1
            if state[0] < 2:
                raise Quota("rate limit")
            return "{}"
        return llm._with_backoff(attempt), {"in": 7, "out": 3}

    monkeypatch.setitem(llm._PROVIDERS, "groq", adapter)
    r = llm._call_cached("groq", "s", "p", None, None, 0.0, 10, use_cache=False)
    assert (r.tokens_in, r.tokens_out, r.waited_ms) == (7, 3, 2000)
