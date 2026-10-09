# Unhook: pitch kit (deck outline, 3-minute script, video script, Q&A)

*Track: AI Enterprise Solutions. Every number below comes from `results/` (see `results/SUMMARY.md`); if you re-run a test,
re-check the numbers before you say them.*

## 0. Komanda üçün qısa izah (Azərbaycanca)
- **Nə edirik:** şübhəli mesajı (mətn və ya screenshot) yoxlayırıq: fırıldaqdırmı, niyə, nə etməli. Translit və rus qarışıq mətni də başa düşür.
- **Enterprise hissəsi:** bank və mobil operatorun fırıldaq komandası öz brendinin adından gedən kampaniyaları görür, saxta domenlərin siyahısını yükləyir, yeni kampaniyada avtomatik xəbərdarlıq (webhook) alır.
- **Qəbul metrikamız:** real bank bildirişlərini fırıldaq saymamaq (açar-söz filtrində 50%, bizdə 0%), fırıldaqları tapmaq (88.9% yerinə 100%), bir yoxlamanın qiyməti (~$0.00042).
- **Mütləq deyin (qaydadır və hakimlər yoxlayacaq):** testlərimiz kiçikdir və mesajları AI yazıb; layihənin ilk versiyası hackathon başlamazdan əvvəl yazılıb (`DISCLOSURE.md`-də dəqiq yazılıb). Bunu gizlətməyin: təşkilatçılar dürüstlüyü mükafatlandırır.
- **Azercell mentorlarına bir sual verin (workflow-u təsdiqləmək üçün):** *"Fırıldaq kampaniyasını bugün necə aşkarlayırsınız və neçə saata?"* Cavabı slayd 3-də yazın.

## 1. One sentence
Unhook tells a customer in seconds whether a message is a scam, in Azerbaijani including translit and Azerbaijani+Russian text,
and gives a bank or mobile operator a live view, a blocklist and an alert for scam campaigns that use their brand.

## 2. Deck outline (10 slides; the first round reads the deck, so every slide must make sense without a speaker)

| # | Slide title | What is on it | The one number or visual |
|---|---|---|---|
| 1 | Unhook: get unhooked before you get scammed | Name, one sentence, team Aura, QR to the live demo | Demo QR |
| 2 | The problem | Two real-looking messages side by side: a scam ("salam, bonusunuz hazirdir: bonus-azercell.top") and a real bank notice ("Kapital Bank: 4821 kodu heç kimə verməyin..."). Caption: one is a scam, one is not; spelling and keywords cannot tell them apart | The two messages |
| 3 | Who it is for, and the workflow today | Customer: gets the message, cannot tell. Fraud team of a bank/operator: learns about a campaign from complaints, reads messages by hand, decides what to block. **State this as your understanding and mark it "to be validated with Azercell mentors"** | A 3-box flow: message → complaint → manual triage |
| 4 | What Unhook does | Flow: message or screenshot → remove personal data → link and domain-age check → AI verdict with reasons in Azerbaijani → saved as a redacted report → campaign dashboard, blocklist, webhook | Architecture diagram |
| 5 | Live demo (the core scenario) | Screenshots in order: (1) scam checked → red verdict with reasons and actions, (2) real bank notice → not called a scam, (3) the dashboard shows the new campaign, (4) the blocklist CSV and a webhook arriving | 4 screenshots |
| 6 | What AI does, and what plain code does | AI: reads the message in three writing styles, reads screenshots, explains in Azerbaijani, proposes the scheme. Code: removes personal data first, compares domains with official ones, checks domain age, forbids "safe" next to a fake link, groups reports into campaigns | Two columns: AI / code |
| 7 | Does it work? Quality testing | Table: keyword filter vs Unhook on 45 messages (below). One line on each failure of the baseline. Attacker test. Our own limits | Table below |
| 8 | Feasibility: cost, data, integration | Cost per check about $0.00042 at list price ($0.42 per 1,000), answer time about 1.6 s median; needs no customer data to start; integrates by API key + webhook (`/integration`); privacy: personal data removed before the AI sees the text | Cost and speed numbers |
| 9 | What is different | (a) Azerbaijani translit and Azerbaijani+Russian text as first-class input, (b) campaign view for companies, not only a per-message answer, (c) a second AI attacks the detector, (d) domain age as an infrastructure signal | 4 bullets |
| 10 | Honest limits and next step | Limits: test messages written by AI, small set, free-tier speed; next: pilot in "watch only" mode with one operator or bank, local model so messages never leave the company, add voice-call scams. Ask: one pilot partner | Next-step list |

**Slide 7 table (copy exactly):**

| System | Scams caught | Harmless messages wrongly flagged | Same answer in all 3 writing styles |
|---|---|---|---|
| Keyword filter (how simple filters work today) | 88.9% | 50% | 100% |
| Unhook | 100% | 0% | 100% |

Under the table: "45 messages written by us (27 scam, 18 harmless), each important message in Azerbaijani, translit and
Azerbaijani+Russian. The keyword filter wrongly flagged every real bank notice with a one-time code. Attacker test: a second AI
wrote 71 evasive variants; Unhook flagged 71 of 71. We do not claim this proves robustness: the set is small and
written by AI."

## 3. Three-minute speaker script (about 430 words, one speaker; **bold** = the moment to click the demo)

Every day people in Azerbaijan get messages like this one: "Hello, your bonus is ready, click here." And messages like this: "Kapital Bank: do not share code 4821." One is a scam. One is a real bank notice. A simple filter that looks for words like *bonus*, *card*, *code* flags both, so people stop trusting any warning. And scammers write in Azerbaijani without special letters, in Russian, or in a mix.

This is Unhook. **[Demo: paste the scam message on the website.]** In a few seconds it says: scam, which type, why — the link imitates Azercell, the domain is new — and what to do. **[Demo: paste the bank notice.]** The real notice is not called a scam. **[Demo: upload a screenshot.]** It also reads screenshots.

But our customer is not only the person who receives the message. It is the fraud team of a bank or an operator. Today, in our understanding, they learn about a campaign when customers complain, and they read messages by hand. **[Demo: open the dashboard.]** Here, every check becomes an anonymous report. Similar messages, even in different spellings, are grouped into one campaign: "fake Kapital Bank page, eight reports, last one an hour ago." The team downloads a blocklist of the fake domains, and gets a webhook the moment a new campaign targets their brand.

How is AI used? A language model reads the message, in three writing styles, and explains in Azerbaijani. But we do not trust it blindly. Code removes personal data before the model sees anything, compares every link with official domains, checks how old the domain is, and never allows "safe" next to a fake link.

Does it work? We tested 45 messages. Against a keyword filter, Unhook catches 100% of scams against 88.9%, and wrongly flags 0% of harmless messages against 50%. We also had a second AI try to fool it with 71 rewritten scams: it flagged 71. We want to be honest: those messages were written by AI and the set is small. That is why we built a public page where anyone can try to fool it, and a tool to add real messages.

Is it worth adopting? One check costs about $0.00042 at list price, answers in about 1.6 seconds, and needs no customer data to start. The next step is a pilot in watch-only mode with one operator or bank, with a local model so that messages never leave the company.

Unhook. Get unhooked before you get scammed.

## 4. Two-minute video script (the core scenario, running; screen recording, voice-over optional)

| Time | Show | Say or caption |
|---|---|---|
| 0:00 | Title card with the QR | "Unhook: is this message a scam?" |
| 0:05 | Website: paste "salam, bonusunuz hazirdir: bonus-azercell.top/qazan", press Yoxla | "A scam message, in translit" |
| 0:20 | Verdict card: red, scheme, reasons, domain age, actions | "Scam. Why. What to do." |
| 0:35 | Paste the Kapital Bank notice | "A real bank notice is not called a scam" |
| 0:50 | Upload a screenshot | "It reads screenshots too" |
| 1:05 | Dashboard: the new report and the campaign list; open a campaign | "For the bank: campaigns, not single messages" |
| 1:25 | Blocklist CSV download; a webhook arriving on webhook.site | "Fake domains to block; alert when a campaign hits your brand" |
| 1:45 | Results page: the table, then the limits box | "Tested against a keyword filter. And what we cannot claim." |
| 1:55 | End card: QR + "Telegram: @unhook_az_bot" | |

Tip: record on a phone for the first half (judges will use phones), on a laptop for the dashboard.

## 5. Q&A cheat sheet (honest answers)

- **"Your test set was written by AI. Why trust the numbers?"** You should not trust them as accuracy: they show direction. The keyword filter's weakness is structural (it cannot tell a real notice from a scam), so it shows on any set. We built a public "fool the AI" page and a tool that adds real messages, and the first thing we do with a pilot partner is score real traffic in watch-only mode.
- **"100%? That is suspicious."** Agreed. 45 messages, written by us, mostly clear-cut. The attacker test found no miss in 71 variants, but the attacker is also an AI. We expect misses on real traffic and we log them: the feedback buttons and the challenge page turn them into test cases.
- **"Messages go to a third-party AI. What about privacy?"** Cards, phones, IBANs, emails and one-time codes are removed before the text leaves our server, and only redacted text is stored. Screenshots are the exception: they are sent to Gemini to be read. For a bank, the plan is a local model inside the company.
- **"Why not just ask ChatGPT?"** A chat answer is one person, one message. We add what a chat cannot: personal-data removal, domain and domain-age checks, code guardrails, a strict answer format, tests against a baseline, and above all campaigns across many reports with a blocklist and webhooks.
- **"What does it cost?"** About $0.00042 per check at list price ($0.42 per 1,000), measured; we ran on free tiers so we paid nothing. Token counts are logged on every check.
- **"How fast?"** About 1.6 seconds median; the slowest 5% take about 10 seconds because of free-tier provider delays.
- **"Who pays, and how do you earn?"** Citizens use it free. Banks and operators pay for the dashboard, blocklist feed and alerts. We have not validated pricing yet.
- **"What if scammers adapt?"** That is what the attacker agent is for: a second AI keeps trying to evade the detector, misses become test cases, and a few can be added to the prompt (we measure the effect on variants the prompt has not seen, and check that harmless messages are not flagged more).
- **"What does it not do?"** Voice-call scams, other languages, QR-code scams, and it cannot know if a real bank message is real; it flags what looks risky. It can be wrong: people are told to call the bank on its official number.
- **"Was it all built during the hackathon?"** No, and we say so in `DISCLOSURE.md`: a first version of the analyzer, bot, evaluation and API was written the evening before; the partner API, webhooks, radar, challenge, group mode, speed and cost measurement, domain-age check, deployment and the real attacker and evaluation runs were done after the start.
- **"Does it work for the Azercell workflow?"** We designed for a bank or operator fraud team; the exact workflow is an assumption we want to validate with you.

## 6. Demo checklist (do this 10 minutes before you go on stage)
1. Laptop on power, `caffeinate -dims` running, internet working.
2. Three terminals open: API (`uvicorn api:app --port 8000`), tunnel (`cloudflared tunnel --url http://localhost:8000`), bot (`python bot.py`).
3. The Vercel site points at the current tunnel address (if the tunnel was restarted, update `NEXT_PUBLIC_API_URL` and redeploy).
4. Open the website on a phone with mobile data, check the example message, the dashboard and the QR.
5. Keep these example messages ready (they are fast because their answers are cached): the scam, the bank notice, the Russian-mix one.
6. If the demo breaks on stage: say so, switch to the recorded video, then show `results/SUMMARY.md`.
