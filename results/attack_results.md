# Attacker agent results

Generated 2026-10-09 12:54.

- Attacker: `groq` / `qwen/qwen3.8-27b`
- Analyzer under attack: `groq` / `openai/gpt-oss-120b`
- Seeds: 9, variants generated: 71

A variant is **missed** when the analyzer says `safe`. *Flagged* = `scam` or `suspicious`; *strict* = `scam` only.

## 1. Detection of attack variants (current prompt)

| Technique | Variants | Detected (flagged) | Detected (strict) | Missed |
|---|---|---|---|---|
| translit | 8 | 100.0% | 100.0% | 0 |
| az_ru | 9 | 100.0% | 100.0% | 0 |
| synonyms | 9 | 100.0% | 100.0% | 0 |
| new_pretext | 9 | 100.0% | 100.0% | 0 |
| typos | 9 | 100.0% | 100.0% | 0 |
| no_link | 9 | 100.0% | 100.0% | 0 |
| formal_tone | 9 | 100.0% | 100.0% | 0 |
| short_sms | 9 | 100.0% | 100.0% | 0 |
| **all** | 71 | **100.0%** | **100.0%** | **0** |

## 2. Before vs after adding missed variants as few-shot examples

No variant was missed, so there was nothing to add. The detector held up on this run.

## 3. Missed variants (0)

Saved to `data/attack_misses.csv`. **Review them by hand:** an LLM-written 'scam' can drift into a harmless message, and then the detector was right.


## Caveats

- Variants are written by an LLM, so the labels are not human-verified.
- Small samples: treat percentages as indicative, not precise.
- The attacker and analyzer are different models, but both are LLMs and share some blind spots.
