# Disclosure

Everything used to build and run Unhook, as required by the hackathon rules. Update this file if you change a model,
provider or data source before submitting.

## 1. AI models used inside the product (at run time)

| Model | Provider / access | What it does in Unhook |
|---|---|---|
| `openai/gpt-oss-120b` | Groq API (free tier), `groq` SDK | **Analyzer**: judges every text message (default). Also the fallback if Gemini is unavailable |
| `gemini-3.5-flash` | Google AI Studio / Gemini API (free tier), `google-genai` SDK | **Screenshot reading** (vision / OCR); optional analyzer (`ANALYZER_PROVIDER=gemini`) |
| `qwen/qwen3.8-27b` | Groq API (free tier) | **Attacker agent**: writes scam variants meant to evade the detector. A different model family from the analyzer on purpose |

When a model is rate-limited the product automatically tries other free models of the same providers (defaults:
`gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` for screenshots; `openai/gpt-oss-20b`, `qwen/qwen3.8-27b` for text).
Every stored report and every answer records which model produced it.

Model names are configuration (`.env`), not code, and may differ in your run. The values in the evaluation reports
(`results/`) show the exact model used for each number.

**What is sent to these providers**
- Text is redacted first (card numbers, phone numbers, IBANs, emails, one-time codes), so those never leave the machine.
  Link domains are kept on purpose.
- **Screenshots are sent to Gemini as they are.** Pixels cannot be redacted before reading. Only the *transcribed* text is
  redacted before the analysis step. Do not upload screenshots that contain data you do not want a third party to see.
- Free-tier terms of Google and Groq apply, including how they may handle submitted content.

## 2. AI assistance in building the project

The code, the prompts, the synthetic dataset and this documentation were written with **Claude Code (Anthropic;
model Claude Sonnet 5.5)** working under the direction of the team, who ran, tested and reviewed the results.
The team is responsible for the final submission.

## 3. Data

| Data | Source |
|---|---|
| `data/labeled.csv` (45 messages: 27 scam, 18 safe, each in az / translit / az_ru) | **Synthetic**: written by Claude for this project, not collected from real people. Marked `synthetic (written by Claude)` in the `source` column |
| `data/attack_misses.csv` | Generated at run time by the attacker model (`attacker.py`). Labels are not human-verified |
| Demo reports (`seed_demo.py`, `source="demo"`) | Derived from `data/labeled.csv`; fabricated on purpose so the dashboard has something to show. Not real user reports |
| `config/official_domains.yaml` | Written from general knowledge of Azerbaijani banks, operators and services. **Not verified against official sources**; the team should review it |
| Keyword baseline list in `eval.py` | Written by us (bonus, kart, kod, təcili, ... plus a few Russian words) |
| Telegram reports stored in `unhook.db` | Created by users of the bot; stored **redacted** only |
| Website feedback ("was this answer right?") | Created by visitors; stores the report id, agree/disagree, the label they suggest, and an optional note (redacted) |
| Partner API keys (`partners.py`) | Created by the team for partner companies. Only a SHA-256 hash of each key is stored, plus a short prefix and the partner's webhook URL and signing secret |
| Webhook events | Sent to a partner's URL when a flagged report mentions its brand: redacted message text, verdict, scheme, domains, brand. Nothing else |
| "Fool the AI" challenge messages | Typed by website visitors, stored redacted, kept apart from real reports and never sent to partners. Their labels are unverified (people claim they are scams) |
| Educational tips (`web/lib/tips.ts`) | General advice written by us (Claude) for each scam type. It contains no statistics |
| Domain blocklist (`/blocklist`) | Computed from the stored reports; automatic and not reviewed by a person |

No external datasets, scraped data or third-party scam corpora were used.

## 4. Libraries

**Python** (see `requirements.txt`; versions we ran):
`fastapi 0.143.0`, `uvicorn 0.54.0`, `SQLAlchemy 2.1.4` (SQLite), `python-telegram-bot 22.8`, `scikit-learn 1.9.1`
(TF-IDF, DBSCAN), `google-genai 2.29.0`, `groq 1.7.0`, `pydantic 2.14.0`, `python-dotenv 1.2.4`, `PyYAML 6.0.3`,
`pytest 9.1.1`, `httpx 0.28.1` (webhook delivery). Standard library: `sqlite3` (LLM answer cache), `csv`, `json`.

**Web app** (`web/package.json`): `next 16.4.0`, `react 19.3.0`, `react-dom 19.3.0`, `tailwindcss 4.3.3`,
`@tailwindcss/postcss 4.3.3`, `typescript 5.9.3`, `qrcode` (QR code on the `/qr` page, MIT licence). No chart library: charts are plain HTML/CSS.

All of these are open-source packages used unmodified under their own licenses.

## 5. Services and tools

- Telegram Bot API (bot `@unhook_az_bot`)
- Google AI Studio (Gemini API) and Groq Cloud (see section 1)
- Cloudflare Tunnel (`cloudflared`) to expose the local API; Vercel to host the web app
- Git is not used by the tooling; nothing was pushed anywhere by the assistant

## 6. Templates, design assets and code from elsewhere

- **No website template, UI kit or starter repository** was used. The Next.js app was written by hand (the standard
  Next.js folder conventions and `tsconfig`/PostCSS config are the only boilerplate).
- Chart colors and chart rules (limited palette, 2-color emphasis charts, table view for every chart, light/dark steps)
  follow a data-visualization guideline and reference palette bundled with Claude Code; the two chart colors were
  checked with its colorblind-safety validator.
- Fonts: system font stack only. Icons: emoji and one hand-drawn SVG logo.
- No code was copied from other projects that we are aware of.

## 7. Privacy summary

- Redaction (cards, phones, IBANs, emails, OTP/PIN/CVV codes) happens **before** text goes to an LLM and **before** storage.
- The database stores only redacted text, the verdict, domains and link flags. It does not store full URLs, user names
  or Telegram IDs.
- LLM answers are cached on disk (`.cache/llm_cache.sqlite`) keyed by a hash of the redacted prompt.
- Screenshots are not stored, but are sent to Gemini for reading (see section 1).

- Telegram group mode: in a group the bot reads only messages that contain a link, sends them (redacted) to the same
  analyzer and stores them redacted like any other report. Members of the group are not told per message, so tell the group when you add the bot.

## 8. Known limitations (so the numbers are read correctly)

- The evaluation set is small and synthetic. Percentages show direction, not precise accuracy.
- Attack variants are written by an LLM; a "missed scam" may actually be harmless text.
- Free-tier quotas limit how often the models can be called (Gemini: 20 requests/day for `gemini-3.5-flash` when we tested).
  Results from a provider that could not answer all messages are reported as incomplete and not compared.
- The analyzer is an AI and can be wrong. It is an aid, not a guarantee: users should still call their bank on its official number.
