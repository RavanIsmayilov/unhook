"""Evaluate the analyzer on data/labeled.csv and compare it with a keyword baseline.

    python eval.py                          # uses ANALYZER_PROVIDER from .env
    python eval.py --providers gemini,groq  # compare providers (no silent fallback, so results are fair)
    python eval.py --limit 10               # first 10 rows only

CSV columns: id, text, label (scam/safe), variant (az/translit/az_ru), source.
Rows of the same message in different writings share an id prefix: S001-az, S001-translit, S001-az_ru.
LLM answers are cached, so re-running costs nothing for unchanged messages.
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from app import llm, settings
from app.analyzer import analyze

VARIANTS = ["az", "translit", "az_ru"]

# A deliberately simple baseline: flag the message if it contains any of these (or any link).
KEYWORDS = [
    "bonus", "bonusu", "kart", "kartı", "kartınız", "karta", "kod", "kodu", "təcili", "tecili", "uduş", "udus",
    "qazandınız", "qazandiniz", "hədiyyə", "hediyye", "hədiyyə", "link", "keçid", "kecid", "təsdiq", "tesdiq",
    "bloklan", "blok", "parol", "şifrə", "sifre", "kredit", "pul", "ödəniş", "odenis", "iş elanı", "gəlir",
    "бонус", "карта", "карты", "код", "срочно", "выигр", "подарок", "ссылк", "заблок", "перейд",
]
URL_RE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|top|xyz|az|ru|info|click|site)\b", re.IGNORECASE)


def baseline_predict(text: str) -> str:
    lowered = text.lower()
    hit = URL_RE.search(lowered) or any(k in lowered for k in KEYWORDS)
    return "scam" if hit else "safe"


def load_dataset(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("text", "").strip()]
    for r in rows:
        if r["label"] not in ("scam", "safe"):
            raise ValueError(f"row {r['id']}: label must be 'scam' or 'safe', got {r['label']!r}")
        if r["variant"] not in VARIANTS:
            raise ValueError(f"row {r['id']}: variant must be one of {VARIANTS}, got {r['variant']!r}")
    return rows


def run_baseline(rows: list[dict]) -> list[dict]:
    return [
        {**r, "verdict": baseline_predict(r["text"]), "confidence": None, "reasons": [], "scheme": "",
         "degraded": False, "provider": "baseline", "model": "keyword filter", "link_flags": []}
        for r in rows
    ]


MAX_CONSECUTIVE_FAILURES = 3


def skipped_result(r: dict, provider: str) -> dict:
    return {**r, "verdict": "suspicious", "confidence": None, "reasons": ["skipped: provider unavailable"],
            "scheme": "", "degraded": True, "provider": provider, "model": "", "link_flags": []}


def run_provider(provider: str, rows: list[dict], delay: float) -> list[dict]:
    results = []
    failures_in_a_row = 0
    for i, r in enumerate(rows, 1):
        if failures_in_a_row >= MAX_CONSECUTIVE_FAILURES:  # quota exhausted or provider down: don't burn time
            if failures_in_a_row == MAX_CONSECUTIVE_FAILURES:
                print(f"  [{provider}] {failures_in_a_row} failures in a row, skipping the rest. Re-run later: "
                      "answers already received are cached.", file=sys.stderr)
                failures_in_a_row += 1
            results.append(skipped_result(r, provider))
            continue
        calls_before = llm.stats["api_calls"]
        v = analyze(r["text"], provider=provider, fallback=False)
        failures_in_a_row = failures_in_a_row + 1 if v.degraded else 0
        results.append({
            **r, "verdict": v.verdict, "confidence": v.confidence, "reasons": v.reasons, "scheme": v.scheme,
            "degraded": v.degraded, "provider": v.provider or provider, "model": v.model,
            "link_flags": [f for l in v.links for f in l.flags],
        })
        print(f"  [{provider}] {i}/{len(rows)} {r['id']}: {v.verdict}{' (degraded)' if v.degraded else ''}", file=sys.stderr)
        if llm.stats["api_calls"] > calls_before and i < len(rows):
            time.sleep(delay)  # free-tier rate limits; cached answers skip the wait
    return results


# ---------------------------------------------------------------- metrics

def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def compute_metrics(results: list[dict]) -> dict:
    ok = [r for r in results if not r["degraded"]]
    scams = [r for r in ok if r["label"] == "scam"]
    safes = [r for r in ok if r["label"] == "safe"]
    flagged = lambda r: r["verdict"] in ("scam", "suspicious")  # the user gets a warning
    strict = lambda r: r["verdict"] == "scam"
    metrics = {
        "n": len(results), "n_scam": len(scams), "n_safe": len(safes), "n_degraded": len(results) - len(ok),
        "recall_flagged": _rate(sum(map(flagged, scams)), len(scams)),
        "recall_strict": _rate(sum(map(strict, scams)), len(scams)),
        "fpr_flagged": _rate(sum(map(flagged, safes)), len(safes)),
        "fpr_strict": _rate(sum(map(strict, safes)), len(safes)),
        "recall_flagged_by_variant": {
            v: _rate(sum(map(flagged, g)), len(g)) for v in VARIANTS if (g := [r for r in scams if r["variant"] == v])
        },
    }
    metrics["consistency_verdict"], metrics["consistency_flagged"], metrics["consistency_groups"] = consistency(ok)
    return metrics


def group_of(row_id: str) -> str:
    return row_id.rsplit("-", 1)[0]


def consistency(ok_results: list[dict]) -> tuple[float | None, float | None, int]:
    """Same message in several writings -> same verdict? Returns (exact verdict, flagged-or-not, number of groups)."""
    groups: dict[str, list[dict]] = {}
    for r in ok_results:
        groups.setdefault(group_of(r["id"]), []).append(r)
    multi = [g for g in groups.values() if len({r["variant"] for r in g}) >= 2]
    same = sum(len({r["verdict"] for r in g}) == 1 for g in multi)
    same_flag = sum(len({r["verdict"] != "safe" for r in g}) == 1 for g in multi)
    return _rate(same, len(multi)), _rate(same_flag, len(multi)), len(multi)


# ---------------------------------------------------------------- reports

def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def system_label(name: str, results: list[dict]) -> str:
    models = {r["model"] for r in results if r["model"]}
    return f"{name} ({', '.join(sorted(models))})" if name != "baseline" and models else name


def markdown_report(all_metrics: dict[str, dict], labels: dict[str, str], n_rows: int) -> str:
    lines = [
        "# Unhook evaluation", "",
        f"Dataset: {n_rows} messages. Generated {datetime.now():%Y-%m-%d %H:%M}.", "",
        "*Flagged* = verdict `scam` or `suspicious` (the user gets a warning). *Strict* = only `scam`.",
        "Degraded results (no model answer) are excluded from the metrics and counted separately.", "",
        "| System | Recall (flagged) | Recall (strict) | False positives (flagged) | False positives (strict) "
        "| Translit consistency | Degraded |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, m in all_metrics.items():
        cons = f"{pct(m['consistency_verdict'])} ({m['consistency_groups']} groups)" if m["consistency_groups"] else "n/a"
        lines.append(
            f"| {labels[name]} | {pct(m['recall_flagged'])} | {pct(m['recall_strict'])} | {pct(m['fpr_flagged'])} "
            f"| {pct(m['fpr_strict'])} | {cons} | {m['n_degraded']} |"
        )
    lines += ["", "## Recall on scams by writing (flagged)", "", "| System | az | translit | az_ru |", "|---|---|---|---|"]
    for name, m in all_metrics.items():
        by = m["recall_flagged_by_variant"]
        lines.append(f"| {labels[name]} | " + " | ".join(pct(by.get(v)) for v in VARIANTS) + " |")
    any_m = next(iter(all_metrics.values()))
    lines += ["", f"Scam messages: {any_m['n_scam']}, safe messages: {any_m['n_safe']}."]
    if n_rows < 30:
        lines.append(f"\n> **Small dataset ({n_rows} rows).** These numbers are not statistically meaningful yet.")
    return "\n".join(lines) + "\n"


def failure_type(r: dict) -> str | None:
    if r["degraded"]:
        return "no model answer (degraded)"
    if r["label"] == "scam":
        return {"safe": "MISSED scam", "suspicious": "weak: scam only marked suspicious"}.get(r["verdict"])
    return {"scam": "FALSE ALARM: safe marked scam", "suspicious": "soft false alarm: safe marked suspicious"}.get(r["verdict"])


def failures_report(all_results: dict[str, list[dict]]) -> str:
    lines = ["# Wrong predictions", ""]
    for name, results in all_results.items():
        bad = [(r, t) for r in results if (t := failure_type(r))]
        lines += [f"## {name}: {len(bad)} of {len(results)}", ""]
        for r, kind in bad:
            lines += [f"### {r['id']} ({r['variant']}): {kind}", "", f"- label: `{r['label']}`, predicted: `{r['verdict']}`"
                      + (f" (confidence {r['confidence']:.2f})" if r["confidence"] is not None else "")]
            if r["provider"] != "baseline":
                lines.append(f"- provider: {r['provider']} / {r['model']}")
            lines.append(f"- text: {r['text']}")
            if r["reasons"]:
                lines.append("- model's reasons:")
                lines += [f"  - {x}" for x in r["reasons"]]
            if r["link_flags"]:
                lines.append(f"- link flags: {', '.join(r['link_flags'])}")
            lines.append("")
        if not bad:
            lines += ["No wrong predictions.", ""]
    return "\n".join(lines)


def evaluate(rows: list[dict], providers: list[str], delay: float, out_dir: Path) -> dict:
    all_results = {"baseline": run_baseline(rows)}
    for p in providers:
        print(f"Running {p} on {len(rows)} messages...", file=sys.stderr)
        all_results[p] = run_provider(p, rows, delay)
    all_metrics = {name: compute_metrics(res) for name, res in all_results.items()}
    labels = {name: system_label(name, res) for name, res in all_results.items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    md = markdown_report(all_metrics, labels, len(rows))
    (out_dir / "eval_results.md").write_text(md, encoding="utf-8")
    (out_dir / "failures.md").write_text(failures_report(all_results), encoding="utf-8")
    (out_dir / "eval_results.json").write_text(json.dumps({
        "generated": datetime.now().isoformat(timespec="seconds"), "n_rows": len(rows), "systems": labels,
        "metrics": all_metrics, "predictions": all_results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": md, "metrics": all_metrics}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(settings.DATA_DIR / "labeled.csv"))
    ap.add_argument("--providers", default=settings.ANALYZER_PROVIDER, help="comma-separated: gemini,groq")
    ap.add_argument("--delay", type=float, default=settings.CALL_DELAY_SECONDS, help="seconds between API calls")
    ap.add_argument("--limit", type=int, default=0, help="only the first N rows")
    args = ap.parse_args()

    rows = load_dataset(Path(args.data))
    if args.limit:
        rows = rows[: args.limit]
    out = evaluate(rows, [p.strip() for p in args.providers.split(",") if p.strip()], args.delay, settings.RESULTS_DIR)
    print(out["markdown"])
    print(f"Saved to {settings.RESULTS_DIR}/ (eval_results.json, eval_results.md, failures.md)")


if __name__ == "__main__":
    main()
