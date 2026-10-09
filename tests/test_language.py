import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import api
from app import analyzer, db, llm, service
from app.schemas import Link, Verdict


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "engine", create_engine(f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False}))
    monkeypatch.setattr("app.settings.CACHE_PATH", tmp_path / "cache.sqlite")
    db.init_db()


ANSWER = json.dumps({"verdict": "safe", "scheme": "none", "reasons": ["a", "b"], "actions": ["x", "y"],
                     "confidence": 0.9, "explanation_az": "e"})


SYSTEMS = []


def run(monkeypatch, lang, text="salam azercel1.com/x"):
    prompts = []
    SYSTEMS.clear()
    monkeypatch.setattr(llm, "generate", lambda p, system, prompt, **k: (SYSTEMS.append(system), prompts.append(prompt),
                                                                           llm.LLMResult(ANSWER, "groq", "m"))[2])
    return analyzer.analyze(text, lang=lang), prompts[0]


def test_language_instruction_only_for_non_azerbaijani(monkeypatch):
    _, az = run(monkeypatch, "az")
    _, en = run(monkeypatch, "en")
    _, ru = run(monkeypatch, "ru")
    assert "Answer language" not in az  # Azerbaijani prompts stay byte-identical, so cached answers stay valid
    assert "in English" in en and "in Russian" in ru and "NOT in Azerbaijani" in en


def test_system_prompt_is_unchanged_for_azerbaijani_and_swaps_only_the_output_rule():
    az, en, ru = (analyzer.system_prompt(l) for l in ("az", "en", "ru"))
    assert az == analyzer.SYSTEM_PROMPT and analyzer.AZ_OUTPUT_RULE in az
    assert "must be in Azerbaijani, Latin script" not in en and "written in English" in en
    assert "written in Russian" in ru and "Do NOT write these fields in Azerbaijani" in ru
    assert en.replace("written in English", "X").split("ALL user-facing")[0] == az.split("ALL user-facing")[0]  # rest identical


def test_the_model_receives_the_language_specific_system_prompt(monkeypatch):
    run(monkeypatch, "en")
    assert "written in English" in SYSTEMS[0]
    run(monkeypatch, "az")
    assert "Azerbaijani, Latin script" in SYSTEMS[0]


@pytest.mark.parametrize("lang,word", [("az", "oxşayır"), ("en", "imitates"), ("ru", "похожа")])
def test_guardrail_message_follows_the_language(monkeypatch, lang, word):
    verdict, _ = run(monkeypatch, lang)  # the model said "safe" but the link is a lookalike
    assert verdict.verdict == "suspicious" and any(word in r for r in verdict.reasons)


@pytest.mark.parametrize("lang,word", [("az", "Ehtiyatlı"), ("en", "Be careful"), ("ru", "Будьте осторожны")])
def test_no_model_answer_message_follows_the_language(monkeypatch, lang, word):
    def down(*a, **k):
        raise llm.LLMUnavailable("no keys")

    monkeypatch.setattr(llm, "generate", down)
    v = analyzer.analyze("bax: bonus-azercell.top", lang=lang)
    assert v.degraded and word in v.explanation_az


def test_busy_message_is_translated(monkeypatch):
    def busy(*a, **k):
        raise llm.LLMBusy("queue")

    monkeypatch.setattr(llm, "generate", busy)
    assert "try again" in analyzer.analyze("salam", lang="en").reasons[0]
    assert "Повторите" in analyzer.analyze("salam", lang="ru").reasons[0]


def test_api_passes_the_language_through(monkeypatch):
    seen = []

    def fake_analyze(text, image, **kw):
        seen.append(kw.get("lang"))
        return Verdict(verdict="scam", scheme="fake_bonus", reasons=["r"], actions=["a"], confidence=0.9, text_redacted=text)

    monkeypatch.setattr(service, "analyze", fake_analyze)
    with TestClient(api.app) as client:
        assert client.post("/check", json={"text": "x"}).status_code == 200
        assert client.post("/check", json={"text": "x", "lang": "en"}).status_code == 200
        assert client.post("/check", json={"text": "x", "lang": "ru"}).status_code == 200
        assert client.post("/challenge", json={"text": "x", "lang": "ru"}).status_code == 200
        assert client.post("/check", json={"text": "x", "lang": "de"}).status_code == 422  # unknown language is rejected
    assert seen == ["az", "en", "ru", "ru"]
