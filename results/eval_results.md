# Unhook evaluation

Dataset: 45 messages. Generated 2026-10-09 12:20.

*Flagged* = verdict `scam` or `suspicious` (the user gets a warning). *Strict* = only `scam`.
Degraded results (no model answer) are excluded from the metrics and counted separately.

| System | Recall (flagged) | Recall (strict) | False positives (flagged) | False positives (strict) | Translit consistency | Degraded |
|---|---|---|---|---|---|---|
| baseline | 88.9% | 88.9% | 50.0% | 50.0% | 100.0% (15 groups) | 0 |
| groq (openai/gpt-oss-120b) | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% (15 groups) | 0 |

## Recall on scams by writing (flagged)

| System | az | translit | az_ru |
|---|---|---|---|
| baseline | 88.9% | 88.9% | 88.9% |
| groq (openai/gpt-oss-120b) | 100.0% | 100.0% | 100.0% |

Scam messages: 27, safe messages: 18.
