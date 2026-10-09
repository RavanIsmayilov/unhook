import json

import pytest

from app import analyzer, llm
from app.linkcheck import check_links, check_url, extract_urls
from app.redact import find_phones, mask_phone, redact


# ---------------------------------------------------------------- redaction

def test_redact_card_and_phone():
    out = redact("Kart 4169 7388 1234 5678, zeng et +994 50 123 45 67 ya da 055-555-55-55")
    assert "4169" not in out and "[CARD]" in out
    assert "123 45 67" not in out and out.count("[PHONE]") == 2


def test_redact_otp_codes():
    assert redact("Kod: 4821. Heç kimə verməyin") == "Kod: [OTP]. Heç kimə verməyin"
    assert redact("4821 kodu ilə təsdiqləyin") == "[OTP] kodu ilə təsdiqləyin"
    assert "5521" not in redact("Ваш пароль 5521 никому не говорите")
    assert "123456" not in redact("OTP is 123456")


def test_redact_keeps_normal_numbers_and_domains():
    assert redact("Bonus 500 AZN qazandınız") == "Bonus 500 AZN qazandınız"
    assert "bonus-azercell.top/claim" in redact("keç bonus-azercell.top/claim")


def test_find_phones_ignores_cards():
    text = "kart 4169738812345678 nömrə 0501234567"
    assert find_phones(text) == ["0501234567"]
    assert mask_phone("0501234567") == "0501***67"


# ---------------------------------------------------------------- link checker

def test_extract_urls_bare_and_explicit():
    urls = extract_urls("Keç: bonus-azercell.top/claim və https://kapitalbank.az/login. sağ ol")
    assert "bonus-azercell.top/claim" in urls and "https://kapitalbank.az/login" in urls


def test_official_ok():
    assert check_url("https://www.azercell.com/az/bonus").status == "official"
    assert check_url("https://my.kapitalbank.az").status == "official"
    assert check_url("https://asan.gov.az/x").status == "official"


def test_lookalikes():
    assert check_url("azercel1.com").status == "lookalike"
    assert check_url("https://azercell-bonus.top").status == "lookalike"
    assert check_url("https://kapitalbank.az.verify-login.xyz").status == "lookalike"
    assert check_url("https://nar-hediyye.click").status == "lookalike"
    assert check_url("https://kapitalbank.az@evil.com").status != "official"


def test_shortener_and_unknown():
    assert check_url("https://bit.ly/3xYz").status == "shortener"
    assert check_url("https://wikipedia.org/wiki/Baku").status == "unknown"
    assert check_links("heç bir link yoxdur") == []


# ---------------------------------------------------------------- llm layer

@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr("app.settings.CACHE_PATH", tmp_path / "cache.sqlite")
    monkeypatch.setattr("app.llm.time.sleep", lambda s: None)


VERDICT_JSON = json.dumps({
    "verdict": "scam", "scheme": "fake_bonus", "reasons": ["a", "b"], "actions": ["x", "y"],
    "confidence": 0.9, "explanation_az": "Bu fırıldaqdır.",
})


def test_fallback_to_groq_when_gemini_fails(monkeypatch):
    def gemini_down(*a, **k):
        raise llm.LLMUnavailable("quota")

    monkeypatch.setitem(llm._PROVIDERS, "gemini", gemini_down)
    monkeypatch.setitem(llm._PROVIDERS, "groq", lambda *a, **k: "{}")
    r = llm.generate("gemini", "sys", "hi", schema={"type": "object"})
    assert r.provider == "groq"
    with pytest.raises(llm.LLMUnavailable):  # images can't fall back
        llm.generate("gemini", "sys", "hi", image=b"\x89PNG....")
    with pytest.raises(llm.LLMUnavailable):  # fallback can be switched off
        llm.generate("gemini", "sys", "hi", fallback=False)


def test_cache_prevents_second_call(monkeypatch):
    calls = []

    def fake(*a, **k):
        calls.append(1)
        return "{}"

    monkeypatch.setitem(llm._PROVIDERS, "gemini", fake)
    assert not llm.generate("gemini", "s", "same").cached
    assert llm.generate("gemini", "s", "same").cached
    llm.generate("gemini", "s", "different")
    assert len(calls) == 2


def test_invalid_output_is_not_cached_and_falls_back(monkeypatch):
    monkeypatch.setitem(llm._PROVIDERS, "gemini", lambda *a, **k: '{"verdict": "sca')  # truncated
    monkeypatch.setitem(llm._PROVIDERS, "groq", lambda *a, **k: '{"ok": 1}')
    r = llm.generate("gemini", "s", "p", validate=json.loads)
    assert r.provider == "groq"
    key = llm._cache_key("gemini", "s", "p", None, None, 0.0)
    assert llm._cache_get(key) is None


def test_backoff_retries_429_then_succeeds():
    class Quota(Exception):
        code = 429

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise Quota("RESOURCE_EXHAUSTED")
        return "ok"

    assert llm._with_backoff(flaky) == "ok" and len(attempts) == 3
    with pytest.raises(ValueError):  # non-retryable errors are raised immediately
        llm._with_backoff(lambda: (_ for _ in ()).throw(ValueError("bad")))


def test_daily_quota_is_not_retried():
    daily = Exception("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    long_hint = Exception("429 RESOURCE_EXHAUSTED 'retryDelay': '20368s'")
    minute = Exception("429 rate limit, retryDelay: '12s'")
    assert not llm._is_retryable(daily) and not llm._is_retryable(long_hint)
    assert llm._is_retryable(minute)


def test_missing_keys_raise_unavailable(monkeypatch):
    monkeypatch.setattr("app.settings.GEMINI_API_KEY", "")
    monkeypatch.setattr("app.settings.GROQ_API_KEY", "")
    with pytest.raises(llm.LLMUnavailable):
        llm.generate("gemini", "s", "p")


# ---------------------------------------------------------------- analyzer

def test_analyze_redacts_before_llm_and_records_provider(monkeypatch):
    seen = {}

    def fake_generate(provider, system, prompt, **k):
        seen["prompt"] = prompt
        return llm.LLMResult(VERDICT_JSON, "gemini", "gemini-test")

    monkeypatch.setattr(llm, "generate", fake_generate)
    v = analyzer.analyze("Bonus: azercel1.com/x zeng et 0501234567, kart 4169738812345678, kod 4821")
    assert "0501234567" not in seen["prompt"] and "4169" not in seen["prompt"] and "4821" not in seen["prompt"]
    assert "azercel1.com" in seen["prompt"] and "lookalike" in seen["prompt"]
    assert v.verdict == "scam" and v.provider == "gemini" and v.model == "gemini-test"
    assert v.scheme_az == "Saxta bonus / uduş"
    assert "0501234567" not in v.text_redacted and v.phones == ["0501***67"]


def test_low_confidence_scam_becomes_suspicious(monkeypatch):
    low = json.loads(VERDICT_JSON) | {"confidence": 0.4}
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult(json.dumps(low), "groq", "m"))
    assert analyzer.analyze("salam, bonusunuz hazirdir").verdict == "suspicious"


def test_safe_with_lookalike_link_is_upgraded(monkeypatch):
    safe = json.loads(VERDICT_JSON) | {"verdict": "safe", "scheme": "none"}
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult(json.dumps(safe), "groq", "m"))
    assert analyzer.analyze("bax: azercel1.com").verdict == "suspicious"


def test_degraded_when_no_api(monkeypatch):
    def down(*a, **k):
        raise llm.LLMUnavailable("no keys")

    monkeypatch.setattr(llm, "generate", down)
    v = analyzer.analyze("bonus-azercell.top")
    assert v.degraded and v.verdict == "suspicious" and v.links[0].status == "lookalike"


def test_garbage_llm_output_is_degraded_not_crash(monkeypatch):
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult("not json", "groq", "m"))
    assert analyzer.analyze("salam").degraded


def test_image_only_uses_transcript(monkeypatch):
    monkeypatch.setattr(analyzer, "transcribe_image", lambda b: "Bonus bit.ly/abc")
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult(VERDICT_JSON, "groq", "m"))
    v = analyzer.analyze(None, b"\x89PNG....")
    assert v.links and v.links[0].status == "shortener" and "bit.ly" in v.text_redacted
