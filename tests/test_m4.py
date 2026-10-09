import csv
import json

import pytest

import attacker as at
from app import llm
from app.schemas import Verdict

SEED = {"id": "S001-az", "text": "Azercell bonus qazandınız: azercell-bonus.top", "label": "scam", "variant": "az"}


def fake_generation(monkeypatch, items):
    monkeypatch.setattr(llm, "generate", lambda *a, **k: llm.LLMResult(json.dumps({"variants": items}), "groq", "atk-model"))


def test_generate_variants_parses_dedupes_and_assigns_ids(monkeypatch):
    fake_generation(monkeypatch, [
        {"technique": "translit", "text": "Azercell bonus qazandiniz"},
        {"technique": "az_ru", "text": "Azercell бонус"},
        {"technique": "az_ru", "text": "azercell бонус"},            # duplicate (case-insensitive)
        {"technique": "unknown", "text": "Başqa mətn"},              # unknown technique -> assigned one
        {"technique": "typos", "text": SEED["text"]},                # identical to the seed
        {"technique": "typos", "text": "  "},                        # empty
    ])
    v = at.generate_variants(SEED, 6, "groq", "atk-model")
    assert [x["id"] for x in v] == ["AS001-01", "AS001-02", "AS001-03"]
    assert [x["variant"] for x in v] == ["translit", "az_ru", "az"]
    assert v[2]["technique"] in at.TECHNIQUES and v[0]["attacker_model"] == "atk-model" and v[0]["label"] == "scam"


def test_generation_prompt_names_every_technique_and_model_override(monkeypatch):
    seen = {}

    def fake(provider, system, prompt, **k):
        seen.update(prompt=prompt, model=k["model"], cache=k["use_cache"])
        return llm.LLMResult(json.dumps({"variants": [{"technique": "typos", "text": "x"}]}), "groq", k["model"])

    monkeypatch.setattr(llm, "generate", fake)
    at.generate_variants(SEED, 8, "groq", "qwen/x")
    assert all(t in seen["prompt"] for t in at.TECHNIQUES) and seen["model"] == "qwen/x" and seen["cache"] is False


def result(id, technique, verdict, degraded=False):
    return {"id": id, "seed_id": "S001-az", "technique": technique, "text": f"text {id}", "label": "scam",
            "variant": "az", "attacker_model": "m", "verdict": verdict, "confidence": 0.8, "degraded": degraded,
            "analyzer_model": "a", "reasons": []}


def test_rates_and_pick_fewshot():
    rs = [result("1", "typos", "scam"), result("2", "typos", "safe"), result("3", "no_link", "safe"),
          result("4", "no_link", "safe"), result("5", "translit", "suspicious"), result("6", "az_ru", "safe", degraded=True)]
    r = at.rates(rs)
    assert r["n"] == 5 and r["degraded"] == 1 and r["missed"] == 3
    assert r["detected_flagged"] == 0.4 and r["detected_strict"] == 0.2
    assert len(at.pick_fewshot(rs, 10)) == 1  # 3 misses -> at most half (1) become examples, 2 stay held out
    four = rs + [result("7", "az_ru", "safe")]
    assert [p["technique"] for p in at.pick_fewshot(four, 2)] == ["typos", "no_link"]  # diverse first
    assert at.pick_fewshot([result("1", "typos", "safe")], 5) == []  # one miss: nothing can be held out
    assert at.pick_fewshot([result("1", "typos", "scam")], 5) == []


def test_save_misses_appends_without_duplicates(tmp_path):
    path = tmp_path / "attack_misses.csv"
    rs = [result("1", "typos", "safe"), result("2", "typos", "scam"), result("3", "no_link", "safe")]
    assert at.save_misses(rs, path, "groq") == 2
    assert at.save_misses(rs, path, "groq") == 0  # same texts again
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert [r["id"] for r in rows] == ["1", "3"] and rows[0]["label"] == "scam" and "attacker agent" in rows[0]["source"]
    assert list(rows[0]) == at.MISSES_COLUMNS


def test_full_run_before_after_uses_held_out_only(monkeypatch, tmp_path):
    items = [{"technique": t, "text": f"variant {t} {i}"} for i, t in enumerate(list(at.TECHNIQUES) * 1)]
    fake_generation(monkeypatch, items)
    calls = []

    def fake_analyze(text, provider=None, fallback=True, extra_examples=None):
        calls.append((text, bool(extra_examples)))
        # without examples the analyzer misses "no_link" and "typos"; with examples it catches them
        missed = ("no_link" in text or "typos" in text) and not extra_examples
        if text.startswith("safe"):
            verdict = "scam" if extra_examples else "safe"  # examples make it paranoid: false positives must be reported
        else:
            verdict = "safe" if missed else "scam"
        return Verdict(verdict=verdict, scheme="other", reasons=["r"], actions=["a"], confidence=0.9, provider="groq", model="m")

    monkeypatch.setattr(at, "analyze", fake_analyze)
    seeds = [SEED]
    safe = [{"id": "B1-az", "text": "safe one", "technique": "safe", "label": "safe", "variant": "az", "seed_id": "",
             "attacker_model": ""}]
    report = at.run(seeds, len(at.TECHNIQUES), 5, "groq", "atk", "groq", 0, safe, tmp_path, tmp_path / "misses.csv")

    data = json.loads((tmp_path / "attack_results.json").read_text(encoding="utf-8"))
    assert len(data["fewshot_ids"]) == 1  # 2 misses -> 1 example, 1 miss stays held out
    # held-out = 8 variants - 1 example = 7; the example itself is never re-graded
    assert data["heldout_before"]["n"] == 7 and data["heldout_after"]["n"] == 7
    assert data["heldout_after"]["detected_flagged"] == 1.0 and data["heldout_before"]["detected_flagged"] < 1.0
    assert data["false_positives_before"]["fpr_flagged"] == 0.0 and data["false_positives_after"]["fpr_flagged"] == 1.0
    assert "held-out" in report and "False positives" in report and (tmp_path / "misses.csv").exists()


def test_run_with_no_misses(monkeypatch, tmp_path):
    fake_generation(monkeypatch, [{"technique": "typos", "text": "a variant"}])
    monkeypatch.setattr(at, "analyze", lambda *a, **k: Verdict(verdict="scam", scheme="other", reasons=[], actions=[],
                                                                  confidence=0.9, model="m"))
    report = at.run([SEED], 1, 5, "groq", "", "groq", 0, None, tmp_path, tmp_path / "m.csv")
    assert "nothing to add" in report


def test_run_fails_clearly_when_nothing_generated(monkeypatch, tmp_path):
    def down(*a, **k):
        raise llm.LLMUnavailable("no key")

    monkeypatch.setattr(llm, "generate", down)
    with pytest.raises(SystemExit):
        at.run([SEED], 3, 5, "groq", "", "groq", 0, None, tmp_path, tmp_path / "m.csv")


def test_load_seeds_uses_az_scam_rows():
    seeds = at.load_seeds(at.settings.DATA_DIR / "labeled.csv", 3)
    assert len(seeds) == 3 and all(s["label"] == "scam" and s["variant"] == "az" for s in seeds)
