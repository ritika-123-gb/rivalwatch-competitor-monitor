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
python app.py



