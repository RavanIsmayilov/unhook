import asyncio
import csv
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot
import add_real
from app.schemas import Link, Verdict


def verdict(v="scam", degraded=False):
    return Verdict(verdict=v, scheme="fake_bonus", reasons=["r"], actions=["Linkə klikləməyin", "ikinci"], confidence=0.95,
                   explanation_az="Bu fırıldaqdır.", degraded=degraded,
                   links=[Link(url="bonus-x.top", domain="bonus-x.top", status="lookalike")])


def group_update(text=None, caption=None, reply_to=None):
    message = SimpleNamespace(text=text, caption=caption, reply_text=AsyncMock(), reply_to_message=reply_to,
                              chat=SimpleNamespace(send_action=AsyncMock()))
    message.reply_text.return_value = SimpleNamespace(edit_text=AsyncMock())
    return SimpleNamespace(message=message), message


# ---------------------------------------------------------------- group guard

def test_group_message_with_scam_link_gets_a_short_warning(monkeypatch):
    calls = []
    monkeypatch.setattr(bot, "check", lambda text, image, source: calls.append(text) or (verdict("scam"), 1))
    update, message = group_update(text="Bonus qazandınız! bonus-x.top/qazan")
    asyncio.run(bot.on_group_text(update, None))
    assert calls and message.reply_text.await_count == 1
    sent = message.reply_text.call_args.args[0]
    assert sent.startswith("🔴") and "bonus-x.top" in sent and "Linkə klikləməyin" in sent and "ikinci" not in sent


def test_group_stays_silent_for_safe_degraded_and_linkless_messages(monkeypatch):
    calls = []

    def fake(text, image, source):
        calls.append(text)
        return fake.result, 1

    monkeypatch.setattr(bot, "check", fake)
    fake.result = verdict("safe")
    update, message = group_update(text="Baxın: azercell.com/az")
    asyncio.run(bot.on_group_text(update, None))
    fake.result = verdict("suspicious", degraded=True)
    asyncio.run(bot.on_group_text(update, None))
    assert len(calls) == 2 and message.reply_text.await_count == 0

    calls.clear()
    update, message = group_update(text="Salam, necəsən? Sabah görüşək")   # no link: not even analyzed (saves quota)
    asyncio.run(bot.on_group_text(update, None))
    assert calls == [] and message.reply_text.await_count == 0


def test_group_errors_never_reach_the_group(monkeypatch):
    monkeypatch.setattr(bot, "check", lambda *a: 1 / 0)
    update, message = group_update(text="bax bit.ly/abc")
    asyncio.run(bot.on_group_text(update, None))
    assert message.reply_text.await_count == 0


# ---------------------------------------------------------------- /yoxla

def test_yoxla_checks_the_message_it_replies_to(monkeypatch):
    seen = {}
    monkeypatch.setattr(bot, "check", lambda text, image, source: seen.update(text=text, image=image) or (verdict("scam"), 1))
    target = SimpleNamespace(text="Kartınız bloklandı: bit.ly/x", caption=None, photo=[])
    update, message = group_update(reply_to=target)
    asyncio.run(bot.yoxla(update, None))
    assert seen["text"] == "Kartınız bloklandı: bit.ly/x" and seen["image"] is None
    waiting = message.reply_text.return_value
    assert waiting.edit_text.call_args.args[0].startswith("🔴")


def test_yoxla_without_a_reply_explains_how(monkeypatch):
    update, message = group_update(reply_to=None)
    asyncio.run(bot.yoxla(update, None))
    assert "cavab verib" in message.reply_text.call_args.args[0]
    empty = SimpleNamespace(text=None, caption=None, photo=[])
    update, message = group_update(reply_to=empty)
    asyncio.run(bot.yoxla(update, None))
    assert "cavab verib" in message.reply_text.call_args.args[0]


# ---------------------------------------------------------------- add_real

def test_parse_and_variant_detection():
    rows, problems = add_real.parse(["# comment", "", "scam | Kartınız bloklandı", "SAFE|salam", "maybe | x", "scam |", "no separator"])
    assert rows == [("scam", "Kartınız bloklandı"), ("safe", "salam")] and len(problems) == 3
    assert add_real.detect_variant("Kartınız bloklandı") == "az"
    assert add_real.detect_variant("kartiniz bloklandi") == "translit"
    assert add_real.detect_variant("vasha karta zablokirovana, срочно") == "az_ru"


def test_add_real_removes_personal_data_and_skips_duplicates(tmp_path, monkeypatch, capsys):
    labeled = tmp_path / "labeled.csv"
    labeled.write_text("id,text,label,variant,source\nS001-az,x,scam,az,s\nR007-az,old,safe,az,s\n", encoding="utf-8")
    source = tmp_path / "real.txt"
    source.write_text("scam | Zəng edin 0501234567, kart 4169 7388 1234 5678, kod 4821: promo-x.top\n"
                      "safe | Salam ana\nscam | Zəng edin 0501234567, kart 4169 7388 1234 5678, kod 4821: promo-x.top\n", encoding="utf-8")
    monkeypatch.setattr(add_real, "INPUT", source)
    monkeypatch.setattr(add_real, "OUTPUT", labeled)
    add_real.main()
    rows = list(csv.DictReader(open(labeled, encoding="utf-8")))
    new = rows[2:]
    assert [r["id"] for r in new] == ["R008-az", "R009-translit"] and len(rows) == 4
    text = new[0]["text"]
    assert "0501234567" not in text and "4169" not in text and "4821" not in text and "promo-x.top" in text
    assert "[PHONE]" in text and "[CARD]" in text and "[OTP]" in text
    assert "1 duplicates skipped" in capsys.readouterr().out
