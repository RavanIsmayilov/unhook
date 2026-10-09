import json

import pytest

import eval as ev
from app.schemas import Verdict


def row(id, label, variant, text="x"):
    return {"id": id, "label": label, "variant": variant, "text": text, "source": "t"}


def res(id, label, variant, verdict, degraded=False):
    return {**row(id, label, variant), "verdict": verdict, "confidence": 0.9, "reasons": ["r"], "scheme": "",
            "degraded": degraded, "provider": "gemini", "model": "m", "link_flags": []}


def test_baseline_keywords_and_translit_weakness():
    assert ev.baseline_predict("Bonus qazandınız, kartınızı təsdiqləyin") == "scam"
    assert ev.baseline_predict("bax: azercell-bonus.top/x") == "scam"
    assert ev.baseline_predict("Salam, sabah görüşək") == "safe"
    assert ev.baseline_predict("musteri, hesabiniz dayandirilib, zeng edin") == "safe"  # translit evades it


def test_load_dataset_validates(tmp_path):
    good = tmp_path / "g.csv"
    good.write_text("id,text,label,variant,source\nS1-az,salam,scam,az,t\n", encoding="utf-8")
    assert ev.load_dataset(good)[0]["id"] == "S1-az"
    bad = tmp_path / "b.csv"
    bad.write_text("id,text,label,variant,source\nS1-az,salam,maybe,az,t\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ev.load_dataset(bad)


def test_shipped_dataset_is_valid():
    rows = ev.load_dataset(ev.settings.DATA_DIR / "labeled.csv")
    assert len(rows) >= 5 and {r["variant"] for r in rows} <= set(ev.VARIANTS)


def test_metrics():
    results = [
        res("S1-az", "scam", "az", "scam"), res("S1-translit", "scam", "translit", "suspicious"),
        res("S2-az", "scam", "az", "safe"), res("S2-az_ru", "scam", "az_ru", "scam"),
        res("B1-az", "safe", "az", "safe"), res("B2-az", "safe", "az", "suspicious"),
        res("B3-az", "safe", "az", "scam"), res("B4-az", "safe", "az", "safe"),
        res("S9-az", "scam", "az", "safe", degraded=True),  # excluded
    ]
    m = ev.compute_metrics(results)
    assert (m["n_scam"], m["n_safe"], m["n_degraded"]) == (4, 4, 1)
    assert m["recall_flagged"] == 0.75 and m["recall_strict"] == 0.5
    assert m["fpr_flagged"] == 0.5 and m["fpr_strict"] == 0.25
    assert m["recall_flagged_by_variant"]["translit"] == 1.0
    # groups with 2+ writings: S1 (scam vs suspicious: differs), S2 (safe vs scam: differs)
    assert m["consistency_groups"] == 2 and m["consistency_verdict"] == 0.0
    assert m["consistency_flagged"] == 0.5  # S1 both flagged, S2 not


def test_consistency_all_same():
    ok = [res("S1-az", "scam", "az", "scam"), res("S1-translit", "scam", "translit", "scam"),
          res("S1-az_ru", "scam", "az_ru", "scam")]
    assert ev.consistency(ok) == (1.0, 1.0, 1)
    assert ev.consistency([res("S1-az", "scam", "az", "scam")]) == (None, None, 0)  # single writing: nothing to compare


def test_failure_types():
    assert ev.failure_type(res("a", "scam", "az", "safe")) == "MISSED scam"
    assert "weak" in ev.failure_type(res("a", "scam", "az", "suspicious"))
    assert "FALSE ALARM" in ev.failure_type(res("a", "safe", "az", "scam"))
    assert ev.failure_type(res("a", "safe", "az", "safe")) is None
    assert "degraded" in ev.failure_type(res("a", "scam", "az", "safe", degraded=True))


def test_full_run_writes_reports(monkeypatch, tmp_path):
    def fake_analyze(text, provider=None, fallback=True):
        verdict = "scam" if "bonus" in text else "safe"
        return Verdict(verdict=verdict, scheme="fake_bonus" if verdict == "scam" else "none", reasons=["səbəb"],
                       actions=["a"], confidence=0.9, provider=provider, model="fake-model")

    monkeypatch.setattr(ev, "analyze", fake_analyze)
    rows = [row("S1-az", "scam", "az", "bonus var"), row("S1-translit", "scam", "translit", "yoxdur"),
            row("B1-az", "safe", "az", "salam")]
    out = ev.evaluate(rows, ["gemini"], delay=0, out_dir=tmp_path)
    assert out["metrics"]["gemini"]["recall_flagged"] == 0.5
    data = json.loads((tmp_path / "eval_results.json").read_text(encoding="utf-8"))
    assert set(data["metrics"]) == {"baseline", "gemini"}
    assert "MISSED scam" in (tmp_path / "failures.md").read_text(encoding="utf-8")
    md = (tmp_path / "eval_results.md").read_text(encoding="utf-8")
    assert "gemini (fake-model)" in md and "Small dataset" in md


def test_provider_is_skipped_after_repeated_failures(monkeypatch):
    calls = []

    def always_degraded(text, provider=None, fallback=True):
        calls.append(text)
        return Verdict(verdict="suspicious", scheme="other", reasons=[], actions=[], confidence=0.3, degraded=True)

    monkeypatch.setattr(ev, "analyze", always_degraded)
    rows = [row(f"S{i}-az", "scam", "az") for i in range(8)]
    results = ev.run_provider("gemini", rows, delay=0)
    assert len(calls) == ev.MAX_CONSECUTIVE_FAILURES and len(results) == 8 and all(r["degraded"] for r in results)
