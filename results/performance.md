# Speed and cost of one check

Measured 2026-10-09T15:10:27 on 24 messages from `data/labeled.csv`, cache off, model `openai/gpt-oss-120b` via groq. 0 calls failed.

| Measure | Value |
|---|---|
| **Answer time, median** | **1645 ms** |
| Answer time, slowest 5% (95th percentile) | 10428 ms |
| Calls that had to wait after a rate-limit error | 0 of 24 |
| Tokens in, average | 1167 |
| Tokens out, average | 404 |
| **Cost per check (list price)** | **$0.00042** |
| Cost per 1,000 checks | $0.42 |

**How to read this.** Most checks take about the median; a few take several seconds longer because the model provider itself is sometimes slow (we ran on a free tier). We ran on free tiers, so our real spend was $0: the cost row is what the same tokens would cost at the list price (input $0.15/M tokens, output $0.6/M tokens; source: Groq list price as reported by third-party price trackers (2026-10-09); verify at groq.com/pricing). The 95th percentile of 24 samples is only a rough guide.
A screenshot adds one more model call (Gemini, free tier) that is not included here.
