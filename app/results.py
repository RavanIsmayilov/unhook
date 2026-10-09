"""Shape results/eval_results.json and results/attack_results.json for the /results page (judges' view)."""
import json
from datetime import datetime
from pathlib import Path

from app import settings

MAX_FAILURES_PER_SYSTEM = 20
MAX_MISSES = 30


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return None


def load_eval(results_dir: Path) -> dict | None:
    import eval as evaluation  # top-level eval.py

    path = results_dir / "eval_results.json"
    data = _read(path)
    if not data:
        return None
    systems, failures = [], {}
    for key, label in data["systems"].items():
        systems.append({"key": key, "label": label, "kind": "baseline" if key == "baseline" else "llm",
                        "metrics": data["metrics"][key]})
        bad = []
        for r in data["predictions"].get(key, []):
            kind = evaluation.failure_type(r)
            if kind:
                bad.append({"id": r["id"], "label": r["label"], "variant": r["variant"], "verdict": r["verdict"],
                            "type": kind, "text": r["text"], "reasons": r["reasons"]})
        failures[key] = {"total": len(bad), "items": bad[:MAX_FAILURES_PER_SYSTEM]}
    return {"generated": data["generated"], "n_rows": data["n_rows"], "systems": systems, "failures": failures}


def load_attack(results_dir: Path) -> dict | None:
    import attacker

    path = results_dir / "attack_results.json"
    data = _read(path)
    if not data:
        return None
    before = data["before"]
    misses = [r for r in before if not r["degraded"] and r["verdict"] == "safe"]
    fewshot_ids = set(data.get("fewshot_ids", []))
    return {
        "generated": _mtime(path),
        "config": data["config"],
        "overall": attacker.rates(before),
        "by_technique": [{"technique": t, **r} for t, r in attacker.by_technique(before).items()],
        "heldout_before": data.get("heldout_before"),
        "heldout_after": data.get("heldout_after"),
        "false_positives_before": data.get("false_positives_before"),
        "false_positives_after": data.get("false_positives_after"),
        "fewshot": [{"id": r["id"], "technique": r["technique"], "text": r["text"]} for r in before if r["id"] in fewshot_ids],
        "misses": [{"id": r["id"], "technique": r["technique"], "text": r["text"], "confidence": r["confidence"]}
                   for r in misses[:MAX_MISSES]],
    }


def load_results(results_dir: Path | None = None) -> dict:
    results_dir = results_dir or settings.RESULTS_DIR
    return {"eval": load_eval(results_dir), "attack": load_attack(results_dir)}
