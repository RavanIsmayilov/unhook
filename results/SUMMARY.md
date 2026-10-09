# Unhook: test results at a glance

Generated 2026-10-09 17:26. Built from `results/eval_results.json`, `attack_results.json` and `performance.json`; re-create with `python make_summary.py`.

Unhook checks a suspicious message (text or screenshot) and says whether it is a scam, in Azerbaijani, including translit and Azerbaijani+Russian text.

## 1. Does it work, compared with how it is done today?

We tested 45 messages (each important message written three ways: Azerbaijani, translit without special letters, and Azerbaijani mixed with Russian). **"Today's approach"** is a keyword filter: it flags a message if it contains words such as *bonus, kart, kod, təcili* or a link. This is how simple spam filters work.

| System | Scams caught | Safe messages wrongly flagged | Same answer for all 3 writings | Messages scored |
|---|---|---|---|---|
| Keyword filter (today) | 88.9% | 50.0% | 100% of 15 messages | 45 |
| **Unhook**: groq (openai/gpt-oss-120b) | 100.0% | 0.0% | 100% of 15 messages | 45 |

*Scams caught* = scam messages that got a warning ("scam" or "suspicious"). *Wrongly flagged* = harmless messages (for example real bank notifications with a one-time code) that also got a warning. Lower is better.

### Where the systems were wrong

- **Keyword filter**: 12 wrong out of 45.
  - `B001-az` flagged a harmless message: "Kapital Bank: 4821 kodu heç kimə verməyin. Ödəniş 25.00 AZN təsdiqləndi."
  - `B001-translit` flagged a harmless message: "Kapital Bank: 4821 kodu hec kime vermeyin. Odenis 25.00 AZN tesdiqlendi."
  - `B001-az_ru` flagged a harmless message: "Kapital Bank: Kod 4821 никому не сообщайте. Ödəniş 25.00 AZN təsdiqləndi."
- **Unhook (groq)**: 0 wrong out of 45.

Every wrong answer, with the model's reasons, is in `results/failures.md`.

## 2. Can another AI fool it?

A second AI model (`qwen/qwen3.8-27b`) was told to rewrite 9 scam messages so the detector would not notice: translit, Azerbaijani+Russian mix, synonyms, a new pretext, typos, no link, formal tone, short SMS. It wrote **71 variants**; the detector (`openai/gpt-oss-120b`) flagged **71 of 71** and missed **0**.

Nothing was missed, so there was nothing to learn from on this run. This does not prove the detector cannot be fooled: the attacker is an AI too, only 71 variants were tried, and nobody checked by hand that every variant is still a scam. The website has a public challenge page where people try to fool it; messages that succeed are exported with `python challenge_misses.py`.

## 3. How fast and how expensive is one check?

Measured on 24 messages with the cache off, model `openai/gpt-oss-120b` via groq.

| Measure | Value |
|---|---|
| Answer time, median / slowest 5% | 1.6 s / 10.4 s |
| Calls that waited after a rate-limit error | 0 of 24 |
| Tokens per check (in / out) | 1167 / 404 |
| Cost per check at list price | $0.00042 (about $0.42 per 1,000 checks) |

We ran on free tiers, so our real spend was $0; the cost row prices the same tokens at the provider's list price (source: Groq list price as reported by third-party price trackers (2026-10-09); verify at groq.com/pricing). Screenshots add one more model call that is not included.

## 4. What these numbers do NOT show

- The 45 test messages were **written by an AI (Claude) for this project**, not collected from real people, so real scams may look different. Add real ones with `python add_real.py` and re-run `eval.py`.
- 45 messages is small: read the percentages as a direction, not a precise accuracy.
- A perfect score on a small set we wrote ourselves is not proof; it is why the attacker test and the public challenge exist.
- Both the detector and the attacker are language models and can share blind spots.
- Speed depends on the free tier of the model provider: a few answers take several seconds longer than the median, and at high load answers can queue or fall back to a smaller model.

## 5. Files

| File | What it holds |
|---|---|
| `results/eval_results.md` / `.json` | full quality table, recall by writing style |
| `results/failures.md` | every wrong answer with the model's reasons |
| `results/attack_results.md` / `.json` | attacker test: per technique, before/after |
| `data/attack_misses.csv` | variants that fooled the detector (empty if none) |
| `results/performance.md` / `.json` | speed, tokens and cost |
| `data/labeled.csv` | the test messages and where each came from |
