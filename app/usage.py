"""Token usage, latency and (estimated) cost of model calls."""
import statistics
from functools import lru_cache

import yaml

from app.settings import ROOT

PRICING_PATH = ROOT / "config" / "pricing.yaml"


@lru_cache(maxsize=1)
def load_prices() -> dict:
    try:
        return yaml.safe_load(PRICING_PATH.read_text(encoding="utf-8")).get("models", {})
    except OSError:
        return {}


def cost_of(entry: dict) -> float | None:
    """USD for one model call, or None when we have no price or no token counts for it."""
    price = load_prices().get(entry.get("model"))
    if not price or entry.get("tokens_in") is None or entry.get("tokens_out") is None:
        return None
    return (entry["tokens_in"] * price["input"] + entry["tokens_out"] * price["output"]) / 1_000_000


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def summarize(entries: list[dict]) -> dict:
    """entries: usage entries of FRESH calls (cached ones carry no tokens and are skipped)."""
    fresh = [e for e in entries if not e.get("cached") and e.get("tokens_in") is not None]
    if not fresh:
        return {"calls": 0}
    latencies = [e["latency_ms"] for e in fresh if e.get("latency_ms") is not None]
    # the model's own time = total minus the sleeping we did after rate-limit errors
    model_times = [e["latency_ms"] - (e.get("waited_ms") or 0) for e in fresh if e.get("latency_ms") is not None]
    costs = [c for c in map(cost_of, fresh) if c is not None]
    return {
        "calls": len(fresh),
        "tokens_in_avg": round(statistics.mean(e["tokens_in"] for e in fresh)),
        "tokens_out_avg": round(statistics.mean(e["tokens_out"] for e in fresh)),
        "latency_ms_mean": round(statistics.mean(latencies)) if latencies else None,
        "latency_ms_p50": round(_percentile(latencies, 0.5)) if latencies else None,
        "latency_ms_p95": round(_percentile(latencies, 0.95)) if latencies else None,
        "model_ms_p50": round(_percentile(model_times, 0.5)) if model_times else None,
        "model_ms_p95": round(_percentile(model_times, 0.95)) if model_times else None,
        "calls_with_rate_limit_wait": sum(1 for e in fresh if (e.get("waited_ms") or 0) > 0),
        "cost_per_check_usd": statistics.mean(costs) if len(costs) == len(fresh) else None,
    }
