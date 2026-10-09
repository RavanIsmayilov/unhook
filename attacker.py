"""Attacker agent: a second LLM writes scam variants meant to evade the detector, we measure what slips through.

    python attacker.py                       # 5 seeds x 6 variants
    python attacker.py --seeds 9 --n 8       # bigger run
    python attacker.py --skip-safe-check     # skip the false-positive check (saves API calls)

Pipeline
  1. seeds: scam messages from data/labeled.csv (one writing per message group)
  2. the attacker model generates N variants per seed (translit, AZ+RU mix, synonyms, new pretexts, typos, ...)
  3. the analyzer runs on every variant -> detection rate; missed ones go to data/attack_misses.csv
  4. a few missed variants become few-shot examples in the analyzer prompt. "After" is measured only on the
     variants that were NOT used as examples (held out), and we re-check false positives on the safe messages.
"""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from app import llm, settings
from app.analyzer import analyze

TECHNIQUES = {
    "translit": "write it in Azerbaijani WITHOUT the special letters (no ə ı ö ü ş ç ğ), the way people type on a phone",
    "az_ru": "mix Azerbaijani and Russian words and phrases inside the same message",
    "synonyms": "replace the typical scam keywords (bonus, hədiyyə, təcili, kart, kod, link, uduş) with synonyms or paraphrases",
    "new_pretext": "invent a different pretext or organization for the same goal (toll fee, marketplace buyer, scholarship, "
                   "courier, utility refund, ...)",
    "typos": "use deliberate typos, odd spacing, digits instead of letters (0 for o, 1 for i) or dots inside words",
    "no_link": "contain no link at all; ask the victim to call, reply, or write on WhatsApp/Telegram instead",
    "formal_tone": "read like a polite, professional official notice, with no urgency words and no exclamation marks",
    "short_sms": "be a very short SMS, under 120 characters",
}
VARIANT_TO_WRITING = {"translit": "translit", "az_ru": "az_ru"}  # every other technique stays in Azerbaijani

ATTACKER_SYSTEM = """You are a red-team assistant for a defensive research project: we are testing our own scam-message
detector for Azerbaijan and need hard test cases that it might miss. You rewrite a seed scam message into new variants.

Rules:
- Every variant MUST still be a scam attempt (it still pushes the reader to pay, hand over card data or a code, or
  click/call something), otherwise it is not a valid test case. Keep the same scam goal as the seed.
- Use ONLY invented domains (for example lookalikes ending in .top, .xyz, .click) and invented phone numbers such as
  +994 55 000 00 00. No real people, no real working links.
- Do NOT reuse the seed's domain. Invent a new one for every variant: some lookalikes of the brand, some generic
  domains that do not mention the brand at all (for example random words ending in .top/.xyz/.site), some short links.
- Each variant must be clearly different from the others. Write natural-sounding messages, like real SMS/Telegram text.
- Follow the requested technique for each variant exactly.
Return a JSON object: {"variants": [{"technique": "<name>", "text": "<message>"}, ...]}"""

VARIANTS_SCHEMA = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"technique": {"type": "string"}, "text": {"type": "string"}},
                "required": ["technique", "text"],
            },
        }
    },
    "required": ["variants"],
}

MISSES_COLUMNS = ["id", "text", "label", "variant", "source", "technique", "seed_id", "verdict", "confidence", "analyzer"]


# ---------------------------------------------------------------- generation

def load_seeds(path: Path, limit: int) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    seeds = [r for r in rows if r["label"] == "scam" and r["variant"] == "az"]
    return seeds[:limit]


def _validate_variants(text: str) -> None:
    data = json.loads(text)
    if not isinstance(data["variants"], list) or not data["variants"]:
        raise ValueError("no variants")


def generate_variants(seed: dict, n: int, provider: str, model: str) -> list[dict]:
    names = list(TECHNIQUES)
    assigned = [names[i % len(names)] for i in range(n)]
    plan = "\n".join(f"{i + 1}. technique \"{t}\": {TECHNIQUES[t]}" for i, t in enumerate(assigned))
    prompt = f"Seed scam message:\n<seed>\n{seed['text']}\n</seed>\n\nWrite exactly {n} variants:\n{plan}"
    result = llm.generate(provider, ATTACKER_SYSTEM, prompt, schema=VARIANTS_SCHEMA, temperature=0.9, max_tokens=4000,
                          use_cache=False, fallback=False, validate=_validate_variants, model=model or None)
    group = seed["id"].rsplit("-", 1)[0]
    variants, seen = [], {seed["text"].strip().lower()}
    for i, item in enumerate(json.loads(result.text)["variants"]):
        text = str(item.get("text", "")).strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        technique = item.get("technique") if item.get("technique") in TECHNIQUES else assigned[min(i, n - 1)]
        variants.append({"id": f"A{group}-{len(variants) + 1:02d}", "seed_id": seed["id"], "technique": technique,
                         "text": text, "label": "scam", "variant": VARIANT_TO_WRITING.get(technique, "az"),
                         "attacker_model": result.model})
    return variants


# ---------------------------------------------------------------- detection

def detect(variants: list[dict], provider: str, delay: float, extra_examples: list[dict] | None = None,
           tag: str = "") -> list[dict]:
    results = []
    for i, v in enumerate(variants, 1):
        calls_before = llm.stats["api_calls"]
        verdict = analyze(v["text"], provider=provider, fallback=False, extra_examples=extra_examples)
        results.append({**v, "verdict": verdict.verdict, "confidence": verdict.confidence, "degraded": verdict.degraded,
                        "analyzer_model": verdict.model, "reasons": verdict.reasons})
        print(f"  [{tag or provider}] {i}/{len(variants)} {v['id']} ({v['technique']}): {verdict.verdict}"
              f"{' (degraded)' if verdict.degraded else ''}", file=sys.stderr)
        if llm.stats["api_calls"] > calls_before and i < len(variants):
            time.sleep(delay)
    return results


def rates(results: list[dict]) -> dict:
    ok = [r for r in results if not r["degraded"]]
    n = len(ok)
    return {
        "n": n, "degraded": len(results) - n,
        "detected_flagged": sum(r["verdict"] in ("scam", "suspicious") for r in ok) / n if n else None,
        "detected_strict": sum(r["verdict"] == "scam" for r in ok) / n if n else None,
        "missed": sum(r["verdict"] == "safe" for r in ok),
    }


def by_technique(results: list[dict]) -> dict[str, dict]:
    out = {}
    for t in TECHNIQUES:
        group = [r for r in results if r["technique"] == t]
        if group:
            out[t] = rates(group)
    return out


def pick_fewshot(results: list[dict], k: int) -> list[dict]:
    """Choose up to k missed variants (preferring different techniques), but never more than half of the misses,
    so that some missed variants stay held out and the before/after comparison can show a difference."""
    misses = [r for r in results if not r["degraded"] and r["verdict"] == "safe"]
    k = min(k, len(misses) // 2)
    chosen, used = [], set()
    for r in misses:  # first pass: one per technique
        if r["technique"] not in used and len(chosen) < k:
            chosen.append(r)
            used.add(r["technique"])
    for r in misses:
        if r not in chosen and len(chosen) < k:
            chosen.append(r)
    return chosen


def save_misses(results: list[dict], path: Path, analyzer: str) -> int:
    """Append missed variants to data/attack_misses.csv (skips texts that are already there)."""
    existing = set()
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            existing = {r["text"] for r in csv.DictReader(f)}
    new = [r for r in results if not r["degraded"] and r["verdict"] == "safe" and r["text"] not in existing]
    write_header = not path.exists() or path.stat().st_size == 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MISSES_COLUMNS)
        if write_header:
            w.writeheader()
        for r in new:
            w.writerow({"id": r["id"], "text": r["text"], "label": "scam", "variant": r["variant"],
                        "source": f"attacker agent ({r['attacker_model']})", "technique": r["technique"],
                        "seed_id": r["seed_id"], "verdict": r["verdict"], "confidence": round(r["confidence"], 2),
                        "analyzer": analyzer})
    return len(new)


# ---------------------------------------------------------------- safe-message check

def false_positive_rates(rows: list[dict], provider: str, delay: float, extra_examples=None, tag="") -> dict:
    results = detect(rows, provider, delay, extra_examples, tag)
    ok = [r for r in results if not r["degraded"]]
    n = len(ok)
    return {"n": n, "degraded": len(results) - n,
            "fpr_flagged": sum(r["verdict"] != "safe" for r in ok) / n if n else None,
            "fpr_strict": sum(r["verdict"] == "scam" for r in ok) / n if n else None}


def load_safe_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{"id": r["id"], "text": r["text"], "technique": "safe", "label": "safe", "variant": r["variant"],
                 "seed_id": "", "attacker_model": ""} for r in csv.DictReader(f) if r["label"] == "safe"]


# ---------------------------------------------------------------- report

def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def build_report(cfg: dict, before: list[dict], fewshot: list[dict], heldout_before: dict, heldout_after: dict | None,
                 fp_before: dict | None, fp_after: dict | None) -> str:
    all_rates = rates(before)
    lines = [
        "# Attacker agent results", "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}.", "",
        f"- Attacker: `{cfg['attacker_provider']}` / `{cfg['attacker_model']}`",
        f"- Analyzer under attack: `{cfg['analyzer_provider']}` / `{cfg['analyzer_model']}`",
        f"- Seeds: {cfg['n_seeds']}, variants generated: {len(before)}", "",
        "A variant is **missed** when the analyzer says `safe`. *Flagged* = `scam` or `suspicious`; *strict* = `scam` only.",
        "", "## 1. Detection of attack variants (current prompt)", "",
        "| Technique | Variants | Detected (flagged) | Detected (strict) | Missed |", "|---|---|---|---|---|",
    ]
    for t, r in by_technique(before).items():
        lines.append(f"| {t} | {r['n']} | {pct(r['detected_flagged'])} | {pct(r['detected_strict'])} | {r['missed']} |")
    lines.append(f"| **all** | {all_rates['n']} | **{pct(all_rates['detected_flagged'])}** | "
                 f"**{pct(all_rates['detected_strict'])}** | **{all_rates['missed']}** |")
    if all_rates["degraded"]:
        lines.append(f"\n{all_rates['degraded']} variants got no analyzer answer and are excluded.")

    lines += ["", "## 2. Before vs after adding missed variants as few-shot examples", ""]
    n_missed = rates(before)["missed"]
    if not fewshot:
        lines.append("No variant was missed, so there was nothing to add. The detector held up on this run."
                     if n_missed == 0 else
                     f"Only {n_missed} variant was missed. At least 2 misses are needed to use some as examples and keep "
                     "others held out, so the before/after comparison was skipped. Run with more seeds or variants.")
    else:
        lines += [
            f"{len(fewshot)} missed variants were added to the analyzer prompt. To avoid grading on the training examples, "
            f"the comparison uses only the **{heldout_before['n']} held-out variants** that were not used as examples.", "",
            "| | Before | After |", "|---|---|---|",
            f"| Detected on held-out variants (flagged) | {pct(heldout_before['detected_flagged'])} | "
            f"{pct(heldout_after['detected_flagged']) if heldout_after else 'n/a'} |",
            f"| Detected on held-out variants (strict) | {pct(heldout_before['detected_strict'])} | "
            f"{pct(heldout_after['detected_strict']) if heldout_after else 'n/a'} |",
        ]
        if fp_before and fp_after:
            lines += [
                f"| False positives on {fp_before['n']} safe messages (flagged) | {pct(fp_before['fpr_flagged'])} | {pct(fp_after['fpr_flagged'])} |",
                f"| False positives on {fp_before['n']} safe messages (strict) | {pct(fp_before['fpr_strict'])} | {pct(fp_after['fpr_strict'])} |",
                "", "The false-positive rows show what the extra examples cost: a detector that flags everything would also "
                "'improve'.",
            ]
        else:
            lines.append("\n(False-positive check skipped.)")
        lines += ["", "Few-shot examples used:", ""]
        lines += [f"- `{r['id']}` ({r['technique']}): {r['text']}" for r in fewshot]

    misses = [r for r in before if not r["degraded"] and r["verdict"] == "safe"]
    lines += ["", f"## 3. Missed variants ({len(misses)})", "",
              "Saved to `data/attack_misses.csv`. **Review them by hand:** an LLM-written 'scam' can drift into a harmless "
              "message, and then the detector was right.", ""]
    lines += [f"- `{r['id']}` ({r['technique']}, confidence {r['confidence']:.2f}): {r['text']}" for r in misses]
    lines += ["", "## Caveats", "",
              "- Variants are written by an LLM, so the labels are not human-verified.",
              "- Small samples: treat percentages as indicative, not precise.",
              "- The attacker and analyzer are different models, but both are LLMs and share some blind spots."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

def run(seeds: list[dict], n: int, few_shot: int, attacker_provider: str, attacker_model: str,
        analyzer_provider: str, delay: float, safe_rows: list[dict] | None, out_dir: Path, misses_path: Path) -> str:
    variants = []
    for seed in seeds:
        print(f"Generating {n} variants of {seed['id']}...", file=sys.stderr)
        try:
            variants += generate_variants(seed, n, attacker_provider, attacker_model)
        except (llm.LLMUnavailable, ValueError, KeyError) as e:
            print(f"  skipped {seed['id']}: {type(e).__name__}: {e}", file=sys.stderr)
    if not variants:
        raise SystemExit("No variants were generated. Check the attacker provider/model and API key.")

    print(f"Running the analyzer on {len(variants)} variants...", file=sys.stderr)
    before = detect(variants, analyzer_provider, delay, tag="before")
    saved = save_misses(before, misses_path, analyzer_provider)
    print(f"{saved} new missed variants appended to {misses_path}", file=sys.stderr)

    fewshot = pick_fewshot(before, few_shot)
    heldout_before = heldout_after = fp_before = fp_after = None
    if fewshot:
        used = {r["id"] for r in fewshot}
        held_ids = [r for r in before if r["id"] not in used]
        heldout_before = rates(held_ids)
        examples = [{"text": r["text"], "label": "scam"} for r in fewshot]
        print(f"Re-running on {len(held_ids)} held-out variants with {len(examples)} few-shot examples...", file=sys.stderr)
        after = detect([{k: v for k, v in r.items() if k in variants[0]} for r in held_ids], analyzer_provider, delay,
                       examples, tag="after")
        heldout_after = rates(after)
        if safe_rows:
            print(f"Checking false positives on {len(safe_rows)} safe messages...", file=sys.stderr)
            fp_before = false_positive_rates(safe_rows, analyzer_provider, delay, None, "safe-before")
            fp_after = false_positive_rates(safe_rows, analyzer_provider, delay, examples, "safe-after")

    cfg = {"attacker_provider": attacker_provider, "attacker_model": variants[0]["attacker_model"],
           "analyzer_provider": analyzer_provider, "analyzer_model": next((r["analyzer_model"] for r in before if r["analyzer_model"]), ""),
           "n_seeds": len(seeds)}
    report = build_report(cfg, before, fewshot, heldout_before, heldout_after, fp_before, fp_after)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "attack_results.md").write_text(report, encoding="utf-8")
    (out_dir / "attack_results.json").write_text(json.dumps({
        "config": cfg, "before": before, "fewshot_ids": [r["id"] for r in fewshot], "heldout_before": heldout_before,
        "heldout_after": heldout_after, "false_positives_before": fp_before, "false_positives_after": fp_after,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(settings.DATA_DIR / "labeled.csv"))
    ap.add_argument("--seeds", type=int, default=5, help="how many seed scam messages")
    ap.add_argument("--n", type=int, default=6, help="variants per seed")
    ap.add_argument("--few-shot", type=int, default=5, help="how many missed variants to add to the prompt")
    ap.add_argument("--attacker-provider", default=settings.ATTACKER_PROVIDER)
    ap.add_argument("--attacker-model", default=settings.ATTACKER_MODEL)
    ap.add_argument("--analyzer-provider", default=settings.ANALYZER_PROVIDER)
    ap.add_argument("--delay", type=float, default=settings.CALL_DELAY_SECONDS)
    ap.add_argument("--skip-safe-check", action="store_true")
    args = ap.parse_args()

    seeds = load_seeds(Path(args.data), args.seeds)
    if not seeds:
        sys.exit("No scam seeds (variant 'az') found in the labeled data.")
    safe_rows = None if args.skip_safe_check else load_safe_rows(Path(args.data))
    report = run(seeds, args.n, args.few_shot, args.attacker_provider, args.attacker_model, args.analyzer_provider,
                 args.delay, safe_rows, settings.RESULTS_DIR, settings.DATA_DIR / "attack_misses.csv")
    print(report)
    print(f"Saved to {settings.RESULTS_DIR}/ (attack_results.md, attack_results.json) and data/attack_misses.csv")


if __name__ == "__main__":
    main()
