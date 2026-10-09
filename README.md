# Unhook

> **Get unhooked before you get scammed.**

**The problem.** People in Azerbaijan get scam messages every day ("your Azercell bonus is ready, click here", "your card is
blocked, send the code"). Scammers write in Azerbaijani with and without special letters (translit: `salam, bonusunuz hazirdir`),
in Russian, or in a mix, so simple keyword filters miss them, and they also flag real bank notifications. Banks and mobile
operators only learn about a campaign when customers complain.

**Who it is for.** (1) Anyone who gets a suspicious message: send it (text or screenshot) and get a verdict in Azerbaijani with
the reasons and what to do. (2) Fraud teams at banks and telecoms: see campaigns that impersonate their brand, get a blocklist of
fake domains, and an alert (webhook) when a new one appears.

**How it works.** Personal data is removed first (cards, phones, one-time codes). A link checker compares domains with the
official ones and looks up how old a domain is. A language model (open-weight, free tier) reads the message and returns a strict
JSON verdict. Code-level guardrails stop it from calling a fake link "safe". Reports are grouped into campaigns by text and
domain.

**Try it now.**
- Website (no setup): <https://unhook-hack.vercel.app>. Pages: `/` check a message, `/dashboard`, `/radar`, `/challenge`,
  `/results`, `/integration`, `/partner`. The backend runs on the team's laptop for the demo, so if a page says "connection lost",
  the laptop is offline: see the results files below, or run it yourself (next section).
- Telegram: `@unhook_az_bot` (send text or a screenshot).
- Example messages to try: `salam, bonusunuz hazirdir: bonus-azercell.top/qazan` (scam) and
  `Kapital Bank: 4821 kodu heç kimə verməyin. Ödəniş 25.00 AZN təsdiqləndi.` (a real-looking bank notice that must NOT be called a scam).

**Where the results are.** Start with `results/SUMMARY.md` (one page, plain numbers, honest limits). Details: `results/eval_results.md`,
`results/failures.md`, `results/attack_results.md`, `results/performance.md`. Models, data and components:
`DISCLOSURE.md`.

| Part | What it is | Where |
|---|---|---|
| Citizen side | Telegram bot (Azerbaijani) and a mobile web page in Azerbaijani, English and Russian (switcher in the header; `?lang=en` also works): send a message or screenshot, get a verdict in the chosen language | `bot.py`, `web/` (page `/`) |
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

*Family-group mode:* add the bot to a group. It checks only messages that contain a link (to save the free API quota)
and stays silent unless it finds a scam or something suspicious. `/yoxla` as a **reply** to any message checks that
message. For the bot to *see* ordinary group messages, switch off its privacy mode once: BotFather → `/setprivacy` →
choose the bot → **Disable**, then remove and re-add the bot to the group. Without that, only `/yoxla` replies work.

**API** (`uvicorn api:app --port 8000`, interactive docs at <http://localhost:8000/docs>):

| Endpoint | Purpose |
|---|---|
| `POST /check` | `{"text": "...", "image_base64": "..."}` returns the verdict (same pipeline as the bot) |
| `GET /stats` | totals, verdicts, schemes, top brands/domains, last 7 days |
| `GET /campaigns` | grouped reports. Query: `brand`, `min_reports`, `limit` |
| `GET /reports/recent` | latest redacted reports. Query: `limit` |
| `GET /results` | evaluation and attacker results for the judges' page |
| `GET /blocklist` | suspicious domains seen in scam reports (for banks). Query: `format=csv`, `brand`, `min_reports` |
| `GET /partner/me`, `/partner/summary`, `/partner/campaigns`, `/partner/blocklist` | **Partner API** for companies: header `X-API-Key`, sees only its own brand |
| `POST /partner/check`, `/partner/check/batch` | check one message, or up to 10 at once (for an SMS gateway or a bank app) |
| `POST /challenge`, `GET /challenge/stats` | the "fool the AI" game; attempts are stored apart from real reports |
| `POST /feedback` | "was this answer right?" from the website. `GET /feedback/recent` lists the disagreements |

**Web app** (`web/`, Next.js + Tailwind):

```bash
cd web && npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev                 # http://localhost:3000
```

Pages: `/` check a message or screenshot (mobile first; after each answer people can say whether it was right),
`/dashboard` live fraud dashboard (refreshes every 5 s): stats, campaigns, a **domain blocklist** banks can download as CSV,
and the people who said our answer was wrong; `/results` evaluation and attack results; `/radar` a public "scams spreading now" page with share buttons;
`/challenge` a game where visitors try to fool the detector (their winning messages become test cases:
`python challenge_misses.py`); `/partner` and `/integration` for companies (below); `/qr` a big QR code of the site
address to show on a projector (type the Vercel address into the box if the page was opened on localhost).

**For companies (banks, telecoms): partner API, panel and webhooks.** Each company gets its own API key that shows only
its own brand (an Azercell key never sees Kapital Bank's campaigns). Keys are stored as hashes and shown once:

```bash
python partners.py create "Azercell" --brand Azercell --webhook https://example.com/hook   # prints the key once
python partners.py demo                     # two demo partners (Azercell, Kapital Bank), new keys each time
python partners.py list                     # who has a key
python partners.py revoke "Azercell"        # key stops working immediately
python partners.py test-webhook "Azercell"  # sends a sample event to its webhook
```

The company pastes the key on `/partner` (brand-only panel with campaigns and a CSV blocklist) or sends it as
`X-API-Key` to the `/partner/...` endpoints. `/integration` is the public documentation page with copy-paste `curl`
examples. With a webhook set, every new scam or suspicious report that impersonates the partner's brand is POSTed to
its URL as JSON, signed with HMAC-SHA256 (`X-Unhook-Signature`). Free way to try a webhook: <https://webhook.site>.

**Demo data** for the dashboard (no API keys needed). Demo rows are marked `source="demo"`:

```bash
python seed_demo.py          # add ~70 demo reports
python seed_demo.py --clear  # remove them again
```

**Real messages for the evaluation** (the sample data is synthetic, real messages make the numbers credible): put one
message per line in `data/real_messages.txt` as `scam | text` or `safe | text`, then run `python add_real.py`. It removes
cards, phones, IBANs and one-time codes **before** writing to `data/labeled.csv` (which goes to Git). Check the new rows.

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

The bot and SQLite are long-running, so the **backend stays on your machine**; only the web app goes to Vercel. A tunnel gives
the backend a public address. The live demo uses an **ngrok** tunnel with a free fixed address; a Cloudflare quick tunnel is a
no-account alternative.

1. Start the API: `uvicorn api:app --port 8000` (and `python bot.py` in a second terminal).
2. Open the tunnel (pick one):
   - **ngrok, fixed address (what the demo uses).** Make a free account, `brew install ngrok`,
     `ngrok config add-authtoken <your token>`, find your free "dev domain" in the ngrok dashboard (Domains), then
     `ngrok http --url=<your-dev-domain>.ngrok-free.dev 8000`. The address never changes, so you set it in Vercel once.
   - **Cloudflare quick tunnel (no account, but a new address on every restart):** `brew install cloudflared`, then
     `cloudflared tunnel --protocol http2 --url http://localhost:8000`.
   Check `https://<tunnel address>/health` in a browser: it must show `{"status":"ok"}`.
3. Deploy `web/` to Vercel: **Add New → Project**, import the Git repo, Root Directory `web`, environment variable
   `NEXT_PUBLIC_API_URL` = the tunnel address (no trailing slash, as a plain "Config" variable). Or deploy from the folder
   with `cd web && npx vercel --prod --build-env NEXT_PUBLIC_API_URL=<tunnel address>`.
4. Open the Vercel address and make a QR code of it (`/qr` shows one).

Things to know:
- `NEXT_PUBLIC_API_URL` is baked in at build time: if the tunnel address changes, update the variable in Vercel and **redeploy
  without the build cache**. The website sends an `ngrok-skip-browser-warning` header (ngrok's free plan otherwise shows a
  warning page to browsers); other hosts ignore it.
- If you use your own domain for the site, add it to `CORS_ORIGINS` in `.env` and restart the API.
- The public endpoints (`/check`, `/stats`, ...) have no login. Anyone with the address can call `/check` and use up your free
  API quota, so share the link only with people you trust. Only the `/partner/...` endpoints need a key.
- The demo backend runs on a laptop: keep it awake, on power and online. If it is off, the website shows "connection lost".

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
config/    official_domains.yaml (official domains, brand names, suspicious words/TLDs: edit me), pricing.yaml (token prices)
app/       analyzer.py (core: redaction -> link check -> model -> guardrails)   llm.py (Gemini/Groq, retries, cache, fallback chain, queue)
           linkcheck.py  redact.py  domainage.py (how old a domain is)  clustering.py (campaigns)  blocklist.py  webhooks.py
           db.py  service.py (analyze + store)  stats.py  usage.py (tokens, latency, cost)  results.py  formatting.py  schemas.py  settings.py
api.py     FastAPI backend (website, dashboard, partner API)            bot.py          Telegram bot
eval.py    evaluation + keyword baseline                                attacker.py     attacker agent
performance.py  speed and cost per check                                 make_summary.py  writes results/SUMMARY.md
partners.py     partner API keys                                         add_real.py      add real messages to the test set
seed_demo.py    demo data for the dashboard                              challenge_misses.py  website-challenge wins -> test cases
data/      labeled.csv (test messages), attack_misses.csv               results/        eval, attack, performance and SUMMARY.md
web/       Next.js app (/, /dashboard, /radar, /challenge, /results, /integration, /partner, /qr)
tests/     pytest (offline, no API keys needed)
DISCLOSURE.md   every model, library, data source and template we used, and the build timeline
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
