# Rivalwatch — competitor monitoring

A dependency-free Python web app for tracking competitor publishing and pricing pages. The app crawls public HTML itself, discovering likely blog/resource pages through homepage links, RSS/Atom feeds, `robots.txt`, and sitemaps. It extracts article URLs, titles, publication dates and meta descriptions, then stores URLs in SQLite so later checks only flag articles not seen before. Pricing pages are fingerprinted from visible text and changes are alerted with new posts.

## Run locally

Requires Python 3.10+. No pip dependencies.

powershell
python app.py


Open http://localhost:8080. Set `PORT` or `MONITOR_DB` to change the port/database location. The database is stored beside the app by default.

## Optional integrations

DataForSEO search-volume enrichment uses the Google Ads search volume endpoint. Set these environment variables before starting:

powershell
$env:DATAFORSEO_LOGIN = "your-api-login"
$env:DATAFORSEO_PASSWORD = "your-api-password"
$env:DATAFORSEO_LOCATION = "2840" # United States location code
$env:DATAFORSEO_LANGUAGE = "en"
python app.py


Without credentials, a target keyword is inferred from the title and volume is labeled unavailable. API errors (including invalid credentials) do not break the crawl and are stored per article.

Paste an incoming Slack webhook in the UI or set `SLACK_WEBHOOK_URL` on the server. Slack receives a summary only when new articles or pricing changes are found. The UI webhook is sent with the scan and is not saved by the app.

