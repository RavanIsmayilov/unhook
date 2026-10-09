"""Write results/SUMMARY.md: one page with every headline number, in plain words, built from the result files.

    python make_summary.py        (run after eval.py, attacker.py and performance.py)
"""
import json
from datetime import datetime

from app import settings

R = settings.RESULTS_DIR


def load(name: str) -> dict | None:
    try:
        return json.loads((R / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def eval_section(ev: dict) -> list[str]:
    usable = {k: m for k, m in ev["metrics"].items() if m["n_degraded"] <= 0.1 * m["n"]}
    lines = [
        "## 1. Does it work, compared with how it is done today?", "",
        f"We tested {ev['n_rows']} messages (each important message written three ways: Azerbaijani, translit without special "
        "letters, and Azerbaijani mixed with Russian). **\"Today's approach\"** is a keyword filter: it flags a message if it "
        "contains words such as *bonus, kart, kod, təcili* or a link. This is how simple spam filters work.", "",
        "| System | Scams caught | Safe messages wrongly flagged | Same answer for all 3 writings | Messages scored |",
        "|---|---|---|---|---|",
    ]
    for key, m in usable.items():
        name = "Keyword filter (today)" if key == "baseline" else f"**Unhook**: {ev['systems'][key]}"
        lines.append(f"| {name} | {pct(m['recall_flagged'])} | {pct(m['fpr_flagged'])} | "
                     f"{pct(m['consistency_verdict'], 0)} of {m['consistency_groups']} messages | {m['n'] - m['n_degraded']} |")
    lines += ["", "*Scams caught* = scam messages that got a warning (\"scam\" or \"suspicious\"). *Wrongly flagged* = harmless messages "
              "(for example real bank notifications with a one-time code) that also got a warning. Lower is better.", ""]
    skipped = [k for k in ev["metrics"] if k not in usable]
    if skipped:
        lines += [f"Left out of the table because most messages got no answer (free API limit): {', '.join(skipped)}.", ""]
    return lines


def failures_section(ev: dict) -> list[str]:
    lines = ["### Where the systems were wrong", ""]
    for key, rows in ev["predictions"].items():
        bad = [r for r in rows if not r["degraded"] and ((r["label"] == "scam" and r["verdict"] == "safe") or
                                                            (r["label"] == "safe" and r["verdict"] != "safe"))]
        label = "Keyword filter" if key == "baseline" else f"Unhook ({key})"
        lines.append(f"- **{label}**: {len(bad)} wrong out of {len(rows)}.")
        for r in bad[:3]:
            kind = "missed a scam" if r["label"] == "scam" else "flagged a harmless message"
            lines.append(f"  - `{r['id']}` {kind}: \"{r['text'][:110]}\"")
    lines += ["", "Every wrong answer, with the model's reasons, is in `results/failures.md`.", ""]
    return lines


def attack_section(at: dict | None) -> list[str]:
    lines = ["## 2. Can another AI fool it?", ""]
    if not at:
        return lines + ["Not run yet (`python attacker.py`).", ""]
    before = at["before"]
    ok = [r for r in before if not r["degraded"]]
    missed = [r for r in ok if r["verdict"] == "safe"]
    cfg = at["config"]
    lines += [
        f"A second AI model (`{cfg['attacker_model']}`) was told to rewrite {cfg['n_seeds']} scam messages so the detector would "
        f"not notice: translit, Azerbaijani+Russian mix, synonyms, a new pretext, typos, no link, formal tone, short SMS. "
        f"It wrote **{len(before)} variants**; the detector (`{cfg['analyzer_model']}`) flagged **{len(ok) - len(missed)} of {len(ok)}** "
        f"and missed **{len(missed)}**.", "",
    ]
    if missed:
        lines += ["Missed variants are saved in `data/attack_misses.csv`; a few were added to the prompt and we re-measured on "
                  "variants that were NOT used as examples (see `results/attack_results.md`).", ""]
    else:
        lines += ["Nothing was missed, so there was nothing to learn from on this run. This does not prove the detector cannot be "
                  f"fooled: the attacker is an AI too, only {len(before)} variants were tried, and nobody checked by hand that every variant "
                  "is still a scam. The website has a public challenge page where people try to fool it; messages that succeed are "
                  "exported with `python challenge_misses.py`.", ""]
    return lines


def performance_section(p: dict | None) -> list[str]:
    lines = ["## 3. How fast and how expensive is one check?", ""]
    if not p:
        return lines + ["Not measured yet (`python performance.py`).", ""]
    ms = lambda v: "n/a" if v is None else f"{v / 1000:.1f} s"
    lines += [
        f"Measured on {p['n_messages']} messages with the cache off, model `{p['model']}` via {p['provider']}.", "",
        "| Measure | Value |", "|---|---|",
        f"| Answer time, median / slowest 5% | {ms(p.get('model_ms_p50'))} / {ms(p.get('model_ms_p95'))} |",
        f"| Calls that waited after a rate-limit error | {p.get('calls_with_rate_limit_wait')} of {p.get('calls')} |",
        f"| Tokens per check (in / out) | {p['tokens_in_avg']} / {p['tokens_out_avg']} |",
    ]
    if p.get("cost_per_check_usd") is not None:
        lines += [f"| Cost per check at list price | ${p['cost_per_check_usd']:.5f} (about ${p['cost_per_1000_checks_usd']:.2f} per 1,000 checks) |"]
    lines += ["", "We ran on free tiers, so our real spend was $0; the cost row prices the same tokens at the provider's list price "
              f"(source: {p.get('price_source')}). Screenshots add one more model call that is not included.", ""]
    return lines


def main() -> None:
    ev, at, perf = load("eval_results.json"), load("attack_results.json"), load("performance.json")
    out = [
        "# Unhook: test results at a glance", "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. Built from `results/eval_results.json`, `attack_results.json` and "
        "`performance.json`; re-create with `python make_summary.py`.", "",
        "Unhook checks a suspicious message (text or screenshot) and says whether it is a scam, in Azerbaijani, including "
        "translit and Azerbaijani+Russian text.", "",
    ]
    out += (eval_section(ev) + failures_section(ev)) if ev else ["## 1. Not run yet (`python eval.py --providers groq`)", ""]
    out += attack_section(at) + performance_section(perf)
    out += [
        "## 4. What these numbers do NOT show", "",
        "- The 45 test messages were **written by an AI (Claude) for this project**, not collected from real people, so real "
        "scams may look different. Add real ones with `python add_real.py` and re-run `eval.py`.",
        "- 45 messages is small: read the percentages as a direction, not a precise accuracy.",
        "- A perfect score on a small set we wrote ourselves is not proof; it is why the attacker test and the public challenge exist.",
        "- Both the detector and the attacker are language models and can share blind spots.",
        "- Speed depends on the free tier of the model provider: a few answers take several seconds longer than the median, and at high load answers can queue or fall back to a smaller model.",
        "", "## 5. Files", "",
        "| File | What it holds |", "|---|---|",
        "| `results/eval_results.md` / `.json` | full quality table, recall by writing style |",
        "| `results/failures.md` | every wrong answer with the model's reasons |",
        "| `results/attack_results.md` / `.json` | attacker test: per technique, before/after |",
        "| `data/attack_misses.csv` | variants that fooled the detector (empty if none) |",
        "| `results/performance.md` / `.json` | speed, tokens and cost |",
        "| `data/labeled.csv` | the test messages and where each came from |", "",
    ]
    (R / "SUMMARY.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
