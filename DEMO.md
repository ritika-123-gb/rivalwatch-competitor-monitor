# Two-minute demo outline

1. **0:00–0:20 — Overview.** Show the empty watchlist and explain the three signals: content, pricing, and keyword demand.
2. **0:20–0:55 — First scan.** Enter a real competitor with an active blog (for example `hubspot.com`) and start monitoring. Show the crawl status, discovered posts, dates/descriptions in the saved data, and keyword field. Set DataForSEO credentials first if you want live search-volume estimates; otherwise the UI labels the volume unavailable.
3. **0:55–1:15 — Verify deduplication.** Run Check all on the same domain. Show that no previously stored URL is repeated as new.
4. **1:15–1:35 — Pricing and alerts.** Explain pricing page baselines and changes. Add an incoming Slack webhook to demonstrate the summary when a new post or pricing change is detected.
5. **1:35–1:55 — Failure handling.** Try a domain that does not resolve, then show how missing/invalid DataForSEO credentials leave article discovery intact while volume is marked unavailable.
6. **1:55–2:00 — Close.** Point out the SQLite history and the deployment README.

Use an account/domain you are authorized to monitor. The first scan establishes the baseline; to demonstrate an alert during a recording, use a test site with a post that is absent on the initial scan and added before the second scan.
