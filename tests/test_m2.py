import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine

import bot
from app import db, service
from app.formatting import format_verdict
from app.schemas import Link, Verdict


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()


def make_verdict(**kw) -> Verdict:
    base = dict(
        verdict="scam", scheme="fake_bonus", reasons=["Link saxtadır <b>"], actions=["Klikləməyin", "Bloklayın"],
        confidence=0.97, explanation_az="Bu fırıldaqdır.", text_redacted="bonus [PHONE] bonus-azercell.top",
        links=[Link(url="bonus-azercell.top/x", domain="bonus-azercell.top", status="lookalike", flags=["f"])],
        provider="gemini", model="m",
    )
    return Verdict(**(base | kw))


def test_format_per_verdict_and_html_escaping():
    scam = format_verdict(make_verdict())
    assert scam.startswith("🔴") and "Saxta bonus" in scam and "bonus-azercell.top" in scam
    assert "&lt;b&gt;" in scam  # LLM text can't inject HTML into Telegram
    assert format_verdict(make_verdict(verdict="suspicious")).startswith("🟡")
    safe = format_verdict(make_verdict(verdict="safe", scheme="none", links=[]))
    assert safe.startswith("🟢") and "Üsul" not in safe
    assert "⚠️" in format_verdict(make_verdict(degraded=True))


def test_save_and_read_report():
    rid = db.save_report(make_verdict(), source="telegram", had_image=True)
    [row] = db.recent_reports()
    assert row["id"] == rid and row["verdict"] == "scam" and row["had_image"] is True
    assert row["domains"] == ["bonus-azercell.top"] and row["provider"] == "gemini"
    assert "url" not in row["links"][0]  # full URLs are not stored


def test_service_check_stores_report(monkeypatch):
    monkeypatch.setattr(service, "analyze", lambda text, image, **kw: make_verdict())
    v, rid = service.check("salam", None, source="telegram")
    assert rid is not None and db.recent_reports()[0]["source"] == "telegram"


def test_service_survives_db_failure(monkeypatch):
    monkeypatch.setattr(service, "analyze", lambda text, image, **kw: make_verdict())
    monkeypatch.setattr(db, "save_report", lambda *a, **k: 1 / 0)
    v, rid = service.check("salam")
    assert v.verdict == "scam" and rid is None


def fake_update(text=None, photo=None, caption=None):
    waiting = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(
        text=text, caption=caption, photo=photo or [], document=None,
        reply_text=AsyncMock(return_value=waiting), chat=SimpleNamespace(send_action=AsyncMock()),
    )
    return SimpleNamespace(message=message), message, waiting


def test_bot_text_flow(monkeypatch):
    monkeypatch.setattr(bot, "check", lambda text, image, source: (make_verdict(), 1))
    update, message, waiting = fake_update(text="salam, bonusunuz hazirdir")
    asyncio.run(bot.on_text(update, None))
    sent = waiting.edit_text.call_args.args[0]
    assert sent.startswith("🔴") and waiting.edit_text.call_args.kwargs["parse_mode"] == "HTML"


def test_bot_photo_flow(monkeypatch):
    seen = {}

    def fake_check(text, image, source):
        seen.update(text=text, image=image, source=source)
        return make_verdict(), 1

    monkeypatch.setattr(bot, "check", fake_check)
    file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"\x89PNGxx")))
    photo = SimpleNamespace(get_file=AsyncMock(return_value=file))
    update, _, waiting = fake_update(photo=[photo], caption="bu nədir?")
    asyncio.run(bot.on_photo(update, None))
    assert seen == {"text": "bu nədir?", "image": b"\x89PNGxx", "source": "telegram"}


def test_bot_error_gives_friendly_message(monkeypatch):
    monkeypatch.setattr(bot, "check", lambda *a: 1 / 0)
    update, _, waiting = fake_update(text="x")
    asyncio.run(bot.on_text(update, None))
    assert "xəta" in waiting.edit_text.call_args.args[0]
