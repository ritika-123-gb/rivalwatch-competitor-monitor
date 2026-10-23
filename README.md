# Rivalwatch — competitor monitoring

A dependency-free Python web app for tracking competitor publishing and pricing pages. The app crawls public HTML itself, discovering likely blog/resource pages through homepage links, RSS/Atom feeds, `robots.txt`, and sitemaps. It extracts article URLs, titles, publication dates and meta descriptions, then stores URLs in SQLite so later checks only flag articles not seen before. Pricing pages are fingerprinted from visible text and changes are alerted with new posts.

## Run locally

Requires Python 3.10+. No pip dependencies.

```powershell
python app.py
```

Open http://localhost:8080. Set `PORT` or `MONITOR_DB` to change the port/database location. The database is stored beside the app by default.

## Optional integrations

DataForSEO search-volume enrichment uses the Google Ads search volume endpoint. Set these environment variables before starting:

```powershell
$env:DATAFORSEO_LOGIN = "your-api-login"
$env:DATAFORSEO_PASSWORD = "your-api-password"
$env:DATAFORSEO_LOCATION = "2840" # United States location code
$env:DATAFORSEO_LANGUAGE = "en"
python app.py
```

Without credentials, a target keyword is inferred from the title and volume is labeled unavailable. API errors (including invalid credentials) do not break the crawl and are stored per article.

Paste an incoming Slack webhook in the UI or set `SLACK_WEBHOOK_URL` on the server. Slack receives a summary only when new articles or pricing changes are found. The UI webhook is sent with the scan and is not saved by the app.

## Behavior and limits

- A first check saves all discoverable posts as a baseline; later checks mark only previously unseen URLs as new.
- The first pricing-page check establishes a baseline. Later visible-text changes trigger alerts. Prices rendered only by JavaScript may be missed.
- The crawler bounds sitemap/listing discovery and article fetches. JavaScript-only sites, bot challenges, rate limits and unusual CMS layouts can limit discovery. Fetch errors are shown in the check result.
- Dates/descriptions depend on standard metadata and `<time>` elements and may be absent.
- This starter has no authentication. Use HTTPS and add authentication before public deployment. Respect website terms and crawl limits.

## Publish

Push this folder to a GitHub repository and deploy to a Python host with outbound HTTPS and persistent storage for SQLite. A public hosting URL, GitHub repo and Loom demo require the user's hosting, GitHub and Loom accounts; this folder is ready to run and publish when connected to those accounts.
