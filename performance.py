"""Measure speed, tokens and cost of one check, with the cache OFF so every call is real.

    python performance.py              # 24 messages from data/labeled.csv, writes results/performance.{json,md}
    python performance.py --n 12

Only the text analysis is measured (the part every check needs). Screenshots add one more model call (Gemini, free tier).
"""
import argparse
import csv
import json
import time
from datetime import datetime

from app import settings
from app.analyzer import analyze
from app.usage import load_prices, summarize


def render_markdown(r: dict) -> str:
    ms = lambda v: "n/a" if v is None else f"{v} ms"
    lines = [
        "# Speed and cost of one check", "",
        f"Measured {r['generated']} on {r['n_messages']} messages from `data/labeled.csv`, cache off, "
        f"model `{r['model']}` via {r['provider']}. {r['failed']} calls failed.", "",
        "| Measure | Value |", "|---|---|",
        f"| **Answer time, median** | **{ms(r.get('model_ms_p50'))}** |",
        f"| Answer time, slowest 5% (95th percentile) | {ms(r.get('model_ms_p95'))} |",
        f"| Calls that had to wait after a rate-limit error | {r.get('calls_with_rate_limit_wait')} of {r.get('calls')} |",
        f"| Tokens in, average | {r.get('tokens_in_avg')} |",
        f"| Tokens out, average | {r.get('tokens_out_avg')} |",
    ]
    if r.get("cost_per_check_usd") is not None:
        lines += [f"| **Cost per check (list price)** | **${r['cost_per_check_usd']:.5f}** |",
                  f"| Cost per 1,000 checks | ${r['cost_per_1000_checks_usd']:.2f} |"]
    lines += ["", "**How to read this.** Most checks take about the median; a few take several seconds longer because the "
              "model provider itself is sometimes slow (we ran on a free tier). We ran on free tiers, so our real spend was $0: "
              f"the cost row is what the same tokens would cost at the list price (input ${r.get('price_input_per_m')}/M tokens, "
              f"output ${r.get('price_output_per_m')}/M tokens; source: {r.get('price_source')}). The 95th percentile of "
              f"{r['n_messages']} samples is only a rough guide.",
              "A screenshot adds one more model call (Gemini, free tier) that is not included here."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--render-only", action="store_true", help="rewrite performance.md from performance.json, no API calls")
    args = ap.parse_args()
    if args.render_only:
        (settings.RESULTS_DIR / "performance.md").write_text(
            render_markdown(json.loads((settings.RESULTS_DIR / "performance.json").read_text(encoding="utf-8"))), encoding="utf-8")
        return

    rows = list(csv.DictReader(open(settings.DATA_DIR / "labeled.csv", encoding="utf-8")))
    step = max(1, len(rows) // args.n)
    sample = rows[::step][: args.n]

    entries, failed = [], 0
    for i, r in enumerate(sample, 1):
        v = analyze(r["text"], provider=args.provider, fallback=False, use_cache=False)
        if v.degraded:
            failed += 1
        entries += v.usage
        print(f"  {i}/{len(sample)} {r['id']}: {v.verdict} {v.usage[-1]['latency_ms'] if v.usage else '-'} ms", flush=True)
        time.sleep(args.delay)

    s = summarize(entries)
    model = next((e["model"] for e in entries), "")
    price = load_prices().get(model, {})
    result = {
        "generated": datetime.now().isoformat(timespec="seconds"), "provider": args.provider, "model": model,
        "n_messages": len(sample), "failed": failed, **s,
        "cost_per_1000_checks_usd": s["cost_per_check_usd"] * 1000 if s.get("cost_per_check_usd") is not None else None,
        "price_input_per_m": price.get("input"), "price_output_per_m": price.get("output"), "price_source": price.get("source"),
    }
    (settings.RESULTS_DIR / "performance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    (settings.RESULTS_DIR / "performance.md").write_text(render_markdown(result), encoding="utf-8")
    print(render_markdown(result))


if __name__ == "__main__":
    main()
