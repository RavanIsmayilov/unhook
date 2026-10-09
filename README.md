# Unhook

> **Get unhooked before you get scammed.**

Unhook checks suspicious messages for scams in **Azerbaijani**, including translit (`salam, bonusunuz hazirdir`) and mixed
Azerbaijani + Russian text, and shows banks and telecoms the scam campaigns that impersonate their brand.

| Part | What it is | Where |
|---|---|---|
| Citizen side | Telegram bot and a mobile web page: send a message or screenshot, get a verdict in Azerbaijani | `bot.py`, `web/` (page `/`) |
| Business side | API + dashboard: reports grouped into campaigns, brands under attack, live stats | `api.py`, `web/` (page `/dashboard`) |
| Attacker agent | A different AI model writes scam variants to fool the detector; misses become test cases | `attacker.py` |
| Evaluation | Recall, false positives and translit consistency vs a keyword baseline | `eval.py`, `web/` (page `/results`) |

## Quick start (3 commands)

You need Python 3.11+ and API keys (both free): Gemini from <https://aistudio.google.com/apikey>, Groq from
<https://console.groq.com/keys>, and a Telegram bot token from `@BotFather` (`/newbot`).

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env        # then open .env and paste your keys
python bot.py               # Telegram bot.  API instead: uvicorn api:app --port 8000
```

Try the analyzer without Telegram:

```bash
python -m app.analyzer "salam, bonusunuz hazirdir: bonus-azercell.top/qazan"
python -m app.analyzer --image screenshot.png
```

## Configuration (`.env`)

| Variable | Meaning |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Google Gemini. Used to **read screenshots** (vision) and as an optional analyzer |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq. Default analyzer, and the text-only fallback when Gemini is out of quota |
| `ANALYZER_PROVIDER` | `groq` or `gemini`: who judges messages (default `groq`) |
| `GROQ_FALLBACK_MODELS`, `GEMINI_FALLBACK_MODELS` | Other free models to try when the main one is rate-limited (comma-separated) |
| `ATTACKER_PROVIDER`, `ATTACKER_MODEL` | Who writes attack variants. Use a different model than the analyzer, e.g. `qwen/qwen3.8-27b` |
| `CALL_DELAY_SECONDS` | Pause between API calls in `eval.py` / `attacker.py` (free-tier rate limits) |
| `TELEGRAM_BOT_TOKEN` | Bot token from `@BotFather` |
| `CORS_ORIGINS` | Websites allowed to call the API from a browser (`localhost:3000` by default; `*.vercel.app` is always allowed) |
| `DATABASE_URL` | SQLite file, default `unhook.db` next to the code |

Model names change often. List what your key can use and edit `.env` if a call returns "model not found":
`python -c "from groq import Groq; import os; print([m.id for m in Groq(api_key=os.environ['GROQ_API_KEY']).models.list().data])"`

**Free-tier limits are real.** `gemini-3.5-flash` allowed only **20 requests per day** on a free key when we tested it.
That is why Groq is the default analyzer. The code never retries a daily quota, and walks a fallback chain for
text. Screenshots need Gemini (Groq has no vision here), so they stop working until the daily quota resets.

## Run each part

**Telegram bot** (`python bot.py`): `/start` explains the bot. Send text, forward a message, or send a screenshot.
Every check is stored as a redacted report in `unhook.db`.

**API** (`uvicorn api:app --port 8000`, interactive docs at <http://localhost:8000/docs>):

| Endpoint | Purpose |
|---|---|
| `POST /check` | `{"text": "...", "image_base64": "..."}` returns the verdict (same pipeline as the bot) |
| `GET /stats` | totals, verdicts, schemes, top brands/domains, last 7 days |
| `GET /campaigns` | grouped reports. Query: `brand`, `min_reports`, `limit` |
| `GET /reports/recent` | latest redacted reports. Query: `limit` |
| `GET /results` | evaluation and attacker results for the judges' page |
| `GET /blocklist` | suspicious domains seen in scam reports (for banks). Query: `format=csv`, `brand`, `min_reports` |
| `POST /feedback` | "was this answer right?" from the website. `GET /feedback/recent` lists the disagreements |

**Web app** (`web/`, Next.js + Tailwind):

```bash
cd web && npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev                 # http://localhost:3000
```

Pages: `/` check a message or screenshot (mobile first; after each answer people can say whether it was right),
`/dashboard` live fraud dashboard (refreshes every 5 s): stats, campaigns, a **domain blocklist** banks can download as CSV,
and the people who said our answer was wrong; `/results` evaluation and attack results; `/qr` a big QR code of the site
address to show on a projector (type the Vercel address into the box if the page was opened on localhost).

**Demo data** for the dashboard (no API keys needed). Demo rows are marked `source="demo"`:

```bash
python seed_demo.py          # add ~70 demo reports
python seed_demo.py --clear  # remove them again
```

**Evaluation**: fill `data/labeled.csv`, then

```bash
python eval.py --providers groq            # or: --providers gemini,groq
```

It prints a table and writes `results/eval_results.json`, `results/eval_results.md` and `results/failures.md`.
Answers are cached, so re-running costs nothing for unchanged messages. A provider that fails 3 times in a row is
skipped, and its missing answers are reported as `degraded` and excluded from the metrics.

`data/labeled.csv` columns: `id, text, label (scam/safe), variant (az/translit/az_ru), source`. Give the three writings
of one message ids with the same prefix (`S002-az`, `S002-translit`, `S002-az_ru`); that is how translit consistency is measured.

**Attacker agent**:

```bash
python attacker.py --attacker-model qwen/qwen3.8-27b
```

It generates variants, measures how many the analyzer misses, appends misses to `data/attack_misses.csv`, then adds a
few misses to the analyzer prompt as few-shot examples and measures again **on the variants that were not used as
examples**, plus the false-positive rate on safe messages. Report: `results/attack_results.md`.
Review the misses by hand: an LLM-written "scam" can drift into a harmless message.

**Tests**: `pytest -q` (offline, no API keys needed).

## Put the dashboard online (Vercel + your laptop)

The bot and SQLite are long-running, so the **backend stays on your machine**; only the web app goes to Vercel.

1. Install the tunnel once: `brew install cloudflared`
2. Start the API: `uvicorn api:app --port 8000` (and `python bot.py` in a second terminal)
3. Expose it: `cloudflared tunnel --url http://localhost:8000`. It prints an address like
   `https://random-words.trycloudflare.com`. Check `https://random-words.trycloudflare.com/health` in a browser.
4. Deploy `web/` to Vercel. Either connect a Git repo (Vercel: **Add New → Project**, Root Directory `web`, environment
   variable `NEXT_PUBLIC_API_URL` = the tunnel address without a trailing slash), or deploy straight from the folder with
   the CLI, no Git needed:
   ```bash
   cd web
   npx vercel login
   npx vercel --prod --build-env NEXT_PUBLIC_API_URL=https://random-words.trycloudflare.com
   ```
   The first run asks a few questions (scope, project name; answer the defaults, and say **no** to "link to existing project").
5. Open the Vercel URL. Make a QR code of it for the audience.

Things to know:
- `NEXT_PUBLIC_API_URL` is baked in at build time. A quick tunnel gets a **new address every time it restarts**, so
  after restarting it you must update the variable in Vercel and **redeploy**. Start the tunnel once, early, and leave it running.
- If you use your own domain for the site, add it to `CORS_ORIGINS` in `.env` and restart the API.
- The API has no login. Anyone with the address can call `/check` and use up your free API quota, so share the link only with people you trust.
- Keep the laptop awake and online during the demo.

## How it works

1. **Redaction first.** Card numbers, phone numbers, IBANs, emails and one-time codes are masked (`[CARD]`, `[PHONE]`, `[OTP]`)
   before text is sent to any LLM and before anything is stored. Domains are kept because the analysis needs them.
2. **Link checker.** URLs are compared with `config/official_domains.yaml` (**edit this list**; the starter list is not verified).
   It flags lookalikes (edit distance, `0/1` for `o/l`), brand names inside other domains, words like `bonus`/`promo`,
   unusual TLDs and URL shorteners.
3. **LLM verdict** as strict JSON: `verdict`, `scheme`, `reasons`, `actions`, `confidence`, `explanation_az`, all user
   text in Azerbaijani (Latin script). Real bank notifications (OTP, payment confirmations) are handled carefully:
   when unsure the answer is `suspicious`, not `scam`.
4. **Guardrails in code:** a lookalike link can never be `safe`; a `scam` with confidence under 0.6 becomes `suspicious`.
   If no LLM answers, the result is link-check-only and marked `degraded`.
5. **Campaigns:** TF-IDF on character n-grams + DBSCAN groups similar texts (letters like `ə`→`e` are folded, so translit
   matches), and reports sharing the same non-official domain are merged.

## Project layout

```
config/official_domains.yaml   official domains, brand names, suspicious words/TLDs (edit me)
app/       analyzer.py (core) · llm.py (Gemini/Groq, retries, cache) · linkcheck.py · redact.py · clustering.py
           db.py · service.py · stats.py · results.py · formatting.py · schemas.py · settings.py
bot.py     Telegram bot            api.py        FastAPI backend         seed_demo.py   demo data
eval.py    evaluation + baseline   attacker.py   attacker agent
data/      labeled.csv · attack_misses.csv        results/      eval and attack results
web/       Next.js app (/, /dashboard, /results)  tests/        pytest
DISCLOSURE.md                  every model, library, data source and template we used
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `TELEGRAM_BOT_TOKEN is empty` | put the token in `.env` (line must start with `TELEGRAM_BOT_TOKEN=`, nothing before it) |
| `... is not set -> falling back to groq` | `GEMINI_API_KEY` missing or the `.env` line is malformed |
| `429 RESOURCE_EXHAUSTED` ... `PerDay` | free daily quota used up; use Groq, wait for the reset, or pick another model |
| `model not found` | the model was retired; list models (see Configuration) and edit `.env` |
| `degraded: true` in a result | no LLM answered; read the `[llm]` / `[analyzer]` lines in the terminal |
| Dashboard says "Əlaqə yoxdur" | API not running, or `NEXT_PUBLIC_API_URL` is wrong / the tunnel address changed |
| Browser console shows a CORS error | add the site's address to `CORS_ORIGINS` and restart the API |
| Bot still uses old settings | restart `python bot.py` after editing `.env` |
