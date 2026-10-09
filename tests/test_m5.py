import base64
import random
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
import seed_demo
from app import db
from app.clustering import brands_of, build_campaigns, campaign_domains, normalize
from app.linkcheck import check_links
from app.schemas import Verdict
from app.stats import compute_stats

NOW = datetime(2026, 10, 8, 12, 0, 0)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()


def report(id, text, verdict="scam", scheme="fake_bonus", hours_ago=1, degraded=False, conf=0.9):
    links = [{"domain": l.domain, "status": l.status, "flags": l.flags} for l in check_links(text)]
    return {"id": id, "created_at": (NOW - timedelta(hours=hours_ago)).isoformat(), "source": "telegram",
            "text_redacted": text, "verdict": verdict, "scheme": scheme, "confidence": conf, "links": links,
            "domains": [l["domain"] for l in links], "degraded": degraded}


def test_normalize_folds_letters_and_drops_placeholders():
    assert normalize("Qazandınız [PHONE] ŞƏKİL") == "qazandiniz sekil"


def test_translit_variants_form_one_campaign_and_unrelated_stays_apart():
    reports = [
        report(1, "Hörmətli müştəri, Azercell tərəfindən 50 AZN bonus qazandınız! Linkə keçin: azercell-bonus.top/qazan", hours_ago=5),
        report(2, "Hormetli musteri, Azercell terefinden 50 AZN bonus qazandiniz! Linke kecin: azercell-bonus.top/qazan", hours_ago=3),
        report(3, "Hormetli musteri, Azercell terefinden 50 AZN bonus qazandiniz!! Linke kecin: azercell-bonus.top/qazan2", hours_ago=1),
        report(4, "AzerPost: Baglamaniz gomrukde saxlanilib. Catdirilma ucun 3.50 AZN odeyin: azerpost-delivery.top/pay",
               scheme="delivery_scam", hours_ago=2),
        report(5, "AzerPost: Bağlamanız gömrükdə saxlanılıb. Çatdırılma üçün 3.50 AZN ödəyin: azerpost-delivery.top/pay",
               scheme="delivery_scam", hours_ago=1),
        report(6, "Salam, sabah görüşək", verdict="safe", scheme="none"),
        report(7, "tək mesaj: bir nəfər göndərib fərqli mətn kriptovalyuta", scheme="investment_scam"),
    ]
    camps = build_campaigns(reports, now=NOW)
    assert [c["count"] for c in camps] == [3, 2]  # safe and lone reports are not campaigns
    bonus = camps[0]
    assert bonus["scheme"] == "fake_bonus" and bonus["brands"] == ["Azercell"] and "azercell-bonus.top" in bonus["domains"]
    assert bonus["name"].startswith("Saxta bonus") and "Azercell" in bonus["name"]
    assert bonus["first_seen"] < bonus["last_seen"] and bonus["report_ids"] == [1, 2, 3]
    assert bonus["reports_last_24h"] == 3 and bonus["verdicts"] == {"scam": 3}
    assert camps[1]["id"] == "C4" and camps[1]["brands"] == ["AzerPost"]


def test_same_domain_merges_dissimilar_texts():
    reports = [report(1, "Bonus qazandınız, keçin: promo-xyz-az.top/a", hours_ago=2),
               report(2, "Vergi borcunuz var, ödəyin: promo-xyz-az.top/b", scheme="other", hours_ago=1)]
    camps = build_campaigns(reports, now=NOW)
    assert len(camps) == 1 and camps[0]["count"] == 2


def test_shorteners_and_official_domains_do_not_merge():
    reports = [report(1, "Bonus qazandınız bit.ly/aaa", hours_ago=2), report(2, "Vergi borcu: bit.ly/bbb ödəyin", hours_ago=1),
               report(3, "Kapital Bank: hesabınızda yeni əməliyyat var, ətraflı kapitalbank.az", hours_ago=1),
               report(4, "Pulsuz internet paketi kampaniyası başladı, qoşulmaq üçün kapitalbank.az/promo ziyarət edin", hours_ago=1)]
    assert campaign_domains(reports[0]) == [] and campaign_domains(reports[2]) == []
    assert build_campaigns(reports, now=NOW) == []


def test_degraded_and_too_few_reports():
    assert build_campaigns([], now=NOW) == [] and build_campaigns([report(1, "x")], now=NOW) == []
    degraded = [report(1, "bonus azercell-bonus.top", degraded=True), report(2, "bonus azercell-bonus.top", degraded=True)]
    assert build_campaigns(degraded, now=NOW) == []


def test_brands_from_flags():
    assert brands_of(report(1, "bax: azercel1.com")) == ["Azercell"]
    assert brands_of(report(2, "bax: kapitalbank-secure.xyz")) == ["Kapital Bank"]
    assert brands_of(report(3, "salam")) == []


def test_stats():
    reports = [report(1, "bonus azercell-bonus.top", hours_ago=1), report(2, "bonus azercell-bonus.top/x", hours_ago=30),
               report(3, "salam", verdict="safe", scheme="none", hours_ago=2),
               report(4, "bilinmir", verdict="suspicious", scheme="other", degraded=True)]
    s = compute_stats(reports, build_campaigns(reports, now=NOW), now=NOW)
    assert s["total_reports"] == 4 and s["reports_last_24h"] == 3 and s["degraded_reports"] == 1
    assert s["by_verdict"] == {"scam": 2, "suspicious": 1, "safe": 1}
    assert s["by_scheme"][0]["scheme"] == "fake_bonus" and s["top_brands"][0] == {"brand": "Azercell", "count": 2}
    assert len(s["daily"]) == 7 and s["daily"][-1]["date"] == "2026-10-08" and s["daily"][-1]["total"] == 3  # counts every report of the day, degraded included
    assert s["campaigns_total"] == 1 and s["campaigns_active_24h"] == 1


# ---------------------------------------------------------------- API

@pytest.fixture
def client():
    with TestClient(api.app) as c:
        yield c


def test_demo_seed_makes_campaigns_through_the_api(client):
    seed_demo.seed(random.Random(7), NOW)
    camps = client.get("/campaigns").json()
    assert len(camps) >= 8  # 9 scam message groups (some may hold a single report only if copies == 1 per writing)
    assert all(c["count"] >= 2 and c["name"] and c["domains"] is not None for c in camps)
    azercell = client.get("/campaigns", params={"brand": "azercell"}).json()
    assert azercell and all("Azercell" in c["brands"] for c in azercell)
    stats = client.get("/stats").json()
    assert stats["total_reports"] > 40 and stats["by_source"] == {"demo": stats["total_reports"]}
    recent = client.get("/reports/recent", params={"limit": 5}).json()
    assert len(recent) == 5 and "scheme_az" in recent[0] and "brands" in recent[0]
    assert db.delete_reports("demo") == stats["total_reports"] and client.get("/stats").json()["total_reports"] == 0


def test_check_endpoint(client, monkeypatch):
    seen = {}

    def fake_check(text, image, source):
        seen.update(text=text, image=image, source=source)
        return Verdict(verdict="scam", scheme="fake_bonus", reasons=["r"], actions=["a"], confidence=0.9,
                       explanation_az="e", provider="groq", model="m"), 42

    monkeypatch.setattr(api, "check", fake_check)
    r = client.post("/check", json={"text": "salam, bonusunuz hazirdir"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "scam" and body["report_id"] == 42 and body["scheme_az"] == "Saxta bonus / uduş"
    assert seen == {"text": "salam, bonusunuz hazirdir", "image": None, "source": "api"}

    png = base64.b64encode(b"\x89PNGdata").decode()
    assert client.post("/check", json={"image_base64": f"data:image/png;base64,{png}"}).status_code == 200
    assert seen["image"] == b"\x89PNGdata"


def test_check_endpoint_validation(client):
    assert client.post("/check", json={}).status_code == 422
    assert client.post("/check", json={"text": "   "}).status_code == 422
    assert client.post("/check", json={"image_base64": "%%%not base64%%%"}).status_code == 400
    assert client.post("/check", json={"text": "x" * 4001}).status_code == 422
    big = base64.b64encode(b"0" * (api.MAX_IMAGE_BYTES + 1)).decode()
    assert client.post("/check", json={"image_base64": big}).status_code == 413


def test_cors_and_health(client):
    def allowed(origin):
        r = client.options("/stats", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        return r.headers.get("access-control-allow-origin")

    assert allowed("http://localhost:3000") == "http://localhost:3000"
    assert allowed("https://unhook-demo.vercel.app") == "https://unhook-demo.vercel.app"
    assert allowed("https://evil.example.com") is None
    assert client.get("/stats", headers={"Origin": "http://localhost:3000"}).headers["access-control-allow-origin"]
    assert client.get("/health").json() == {"status": "ok"}


def test_results_endpoint_empty_and_with_files(client, monkeypatch, tmp_path):
    import json
    from app import results

    monkeypatch.setattr(results.settings, "RESULTS_DIR", tmp_path)
    assert client.get("/results").json() == {"eval": None, "attack": None, "performance": None}

    eval_data = {"generated": "2026-10-08T12:00:00", "n_rows": 2, "systems": {"baseline": "baseline", "groq": "groq (m)"},
                 "metrics": {"baseline": {"recall_flagged": 1.0}, "groq": {"recall_flagged": 1.0}},
                 "predictions": {"baseline": [{"id": "B1-az", "label": "safe", "variant": "az", "verdict": "scam", "text": "t",
                                               "reasons": [], "degraded": False}],
                                 "groq": [{"id": "B1-az", "label": "safe", "variant": "az", "verdict": "safe", "text": "t",
                                           "reasons": [], "degraded": False}]}}
    (tmp_path / "eval_results.json").write_text(json.dumps(eval_data), encoding="utf-8")
    attack = {"config": {"attacker_model": "q"}, "fewshot_ids": ["A1-01"], "heldout_before": {"n": 1}, "heldout_after": None,
              "false_positives_before": None, "false_positives_after": None,
              "before": [{"id": "A1-01", "technique": "typos", "text": "x", "verdict": "safe", "confidence": 0.7, "degraded": False},
                         {"id": "A1-02", "technique": "typos", "text": "y", "verdict": "scam", "confidence": 0.9, "degraded": False}]}
    (tmp_path / "attack_results.json").write_text(json.dumps(attack), encoding="utf-8")

    body = client.get("/results").json()
    assert [s["key"] for s in body["eval"]["systems"]] == ["baseline", "groq"]
    assert body["eval"]["failures"]["baseline"]["total"] == 1 and body["eval"]["failures"]["groq"]["total"] == 0
    assert body["attack"]["overall"]["missed"] == 1 and body["attack"]["by_technique"][0]["technique"] == "typos"
    assert body["attack"]["fewshot"][0]["id"] == "A1-01" and body["attack"]["misses"][0]["id"] == "A1-01"
