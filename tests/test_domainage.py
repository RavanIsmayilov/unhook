from datetime import date

import pytest

from app import analyzer, domainage, llm, settings
from app.linkcheck import check_links
from app.schemas import Link


class FakeResponse:
    def __init__(self, status=200, events=None):
        self.status_code = status
        self._events = events if events is not None else [{"eventAction": "registration", "eventDate": "2026-10-06T08:00:00Z"}]

    def json(self):
        return {"events": self._events}


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_PATH", tmp_path / "cache.sqlite")


def fake_rdap(monkeypatch, response=None, calls=None, error=None):
    def get(url, timeout, follow_redirects):
        if calls is not None:
            calls.append(url)
        if error:
            raise error
        return response or FakeResponse()

    monkeypatch.setattr(domainage.httpx, "get", get)


def test_age_is_read_from_rdap_and_cached(monkeypatch):
    calls = []
    fake_rdap(monkeypatch, calls=calls)
    assert domainage.age_days("bonus-x.top", today=date(2026, 10, 9)) == 3
    assert domainage.age_days("bonus-x.top", today=date(2026, 10, 10)) == 4  # same lookup, the age keeps growing
    assert len(calls) == 1  # second answer came from the cache


def test_unknown_domain_is_remembered_for_a_while_but_network_errors_are_not(monkeypatch):
    calls = []
    fake_rdap(monkeypatch, FakeResponse(404), calls)
    assert domainage.age_days("nothing.top") is None and domainage.age_days("nothing.top") is None
    assert len(calls) == 1
    calls.clear()
    fake_rdap(monkeypatch, calls=calls, error=domainage.httpx.ConnectTimeout("slow"))
    assert domainage.age_days("flaky.top") is None and domainage.age_days("flaky.top") is None
    assert len(calls) == 2  # a timeout says nothing about the domain, so we try again next time


def test_temporary_errors_are_not_remembered_as_not_found(monkeypatch):
    calls = []
    fake_rdap(monkeypatch, FakeResponse(429), calls)
    assert domainage.age_days("busy.top") is None and domainage.age_days("busy.top") is None
    assert len(calls) == 2  # 429 is not "unknown domain": ask again next time


def test_annotate_flags_new_domains_and_skips_the_rest(monkeypatch):
    calls = []
    fake_rdap(monkeypatch, calls=calls)
    monkeypatch.setattr(domainage, "age_days", lambda d, today=None: {"fresh-bonus.top": 3, "old-site.top": 2000}.get(d))
    links = check_links("bax fresh-bonus.top/a və old-site.top/b və azercell.com/az və bit.ly/x və kapital-yoxla.az/g və t.me/kanal")
    domainage.annotate(links)
    by = {l.domain: l for l in links}
    assert by["fresh-bonus.top"].age_days == 3 and "new_domain:3d" in by["fresh-bonus.top"].flags
    assert by["old-site.top"].age_days == 2000 and not any(f.startswith("new_domain") for f in by["old-site.top"].flags)
    for skipped in ("azercell.com", "bit.ly", "kapital-yoxla.az", "t.me"):
        assert by[skipped].age_days is None


def test_a_slow_lookup_never_blocks_the_check(monkeypatch):
    import time
    monkeypatch.setattr(settings, "DOMAIN_AGE_TIMEOUT", 0.2)
    monkeypatch.setattr(domainage, "age_days", lambda d, today=None: time.sleep(3) or 1)
    links = [Link(url="x.top", domain="x.top", status="unknown")]
    started = time.monotonic()
    domainage.annotate(links)
    assert time.monotonic() - started < 1.5 and links[0].age_days is None


def verdict_json(verdict):
    import json
    return json.dumps({"verdict": verdict, "scheme": "none" if verdict == "safe" else "fake_bonus", "reasons": ["a", "b"],
                       "actions": ["x", "y"], "confidence": 0.9, "explanation_az": "e"})


def test_analyzer_uses_age_only_when_asked_and_only_tells_the_model_then(monkeypatch):
    prompts = []

    def fake_generate(provider, system, prompt, **k):
        prompts.append(prompt)
        return llm.LLMResult(verdict_json("safe"), "groq", "m")

    monkeypatch.setattr(llm, "generate", fake_generate)
    monkeypatch.setattr(domainage, "age_days", lambda d, today=None: 2)
    text = "salam, maraqlı sayt: brand-new-site.top/a"

    plain = analyzer.analyze(text)                                   # eval and attacker path
    assert "age_days" not in prompts[0] and plain.links[0].age_days is None and plain.verdict == "safe"

    live = analyzer.analyze(text, check_domain_age=True)             # bot and website path
    assert '"age_days": 2' in prompts[1] and "registered in the last 30 days" in prompts[1]
    assert live.links[0].age_days == 2
    assert live.verdict == "suspicious"                              # "safe" is not allowed next to a 2-day-old domain


def test_age_is_shown_in_telegram_text():
    from app.formatting import format_verdict
    from app.schemas import Verdict
    v = Verdict(verdict="scam", scheme="fake_bonus", reasons=["r"], actions=["a"], confidence=0.9,
                links=[Link(url="x.top", domain="x.top", status="suspicious", age_days=3)])
    assert "3 gün əvvəl yaradılıb" in format_verdict(v)
    v.links[0].age_days = 0
    assert "bu gün yaradılıb" in format_verdict(v)
    v.links[0].age_days = 4000
    assert "yaradılıb" not in format_verdict(v)
