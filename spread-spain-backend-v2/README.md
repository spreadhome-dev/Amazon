# Spread Spain — Amazon Product Monitor Backend

## What's Included

```
spread-spain-backend/
├── app.py          ← Flask REST API server (main entry point)
├── scraper.py      ← Playwright + BeautifulSoup Amazon scraper
├── database.py     ← SQLite setup & connection helper
├── requirements.txt
├── setup.py        ← One-click installer
├── dashboard.html  ← Frontend (open in browser)
└── README.md
```

---

## Quick Start (5 minutes)

### Step 1 — Install Python
Download Python 3.10–3.13 from https://python.org  
✅ During install: check **"Add Python to PATH"**  
⚠️  Python 3.14 works but is very new — 3.12 or 3.13 recommended.

### Step 2 — Open a Command Prompt in the backend folder
Right-click the `spread-spain-backend` folder → **"Open in Terminal"**  
(or open Command Prompt and `cd` to the folder)

> ⚠️ **Do NOT run setup.py by double-clicking** — that opens `pythonw.exe` which can't install packages.  
> Always run from a **Command Prompt / Terminal**.

### Step 3 — Run Setup (one time only)
```
python setup.py
```
This will:
- Create a `venv` virtual environment
- Install all packages inside it
- Download the Chromium browser for scraping
- Create `START_SERVER.bat` for easy startup

### Step 4 — Start the Server
**Option A:** Double-click `START_SERVER.bat`  

**Option B:** Command Prompt:
```
venv\Scripts\python app.py
```

You'll see:
```
🚀 Spread Spain Backend starting on http://localhost:5000
📅 Auto-scrape scheduled every 6 hours
```

### Step 5 — Open the Dashboard
Open `dashboard.html` in your browser.  
The green **BACKEND ONLINE** badge confirms the connection.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/api/health`              | Check server is running |
| GET  | `/api/products`            | Get all monitored products |
| POST | `/api/products`            | Add & scrape a single product |
| DELETE | `/api/products/<url>`    | Remove a product |
| POST | `/api/products/bulk`       | Add multiple URLs (background) |
| POST | `/api/products/refresh`    | Re-scrape all products |
| POST | `/api/products/refresh-one`| Re-scrape one product |
| GET  | `/api/history?url=...`     | Price/rating history |
| GET  | `/api/stats`               | Summary stats |
| GET  | `/api/scheduler`           | Scheduler status |
| POST | `/api/scheduler`           | Change scrape interval |

### Example — Add a product
```bash
curl -X POST http://localhost:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/dp/B0EXAMPLE"}'
```

### Example — Change auto-scrape to every 2 hours
```bash
curl -X POST http://localhost:5000/api/scheduler \
  -H "Content-Type: application/json" \
  -d '{"hours": 2}'
```

---

## Features

### 🕷️ Scraper
- Real Playwright browser (Chromium) — handles JavaScript-rendered pages
- Anti-bot measures: randomised user agents, realistic headers, homepage warmup
- Extracts: title, price, MRP, rating, reviews, BSR rank, stock status, image
- Auto-retry on failure (up to 3 attempts)
- Detects CAPTCHA and logs it

### 🗄️ Database (SQLite — no setup required)
- `products` table: all product data
- `history` table: price/rating/rank snapshots over time
- Stored at `products.db` in the same folder

### ⏰ Scheduler
- Default: every 6 hours
- Changeable from the dashboard dropdown (30 min → 24 hr)
- Runs in background — server stays responsive

### 🌐 REST API
- CORS enabled — works with the frontend on any port
- All responses are JSON

---

## Troubleshooting

**"Backend offline" banner shows**  
→ Make sure `python app.py` is running in your terminal

**Scrape returns no data**  
→ Amazon shows CAPTCHA — wait 10 minutes, try a different product first  
→ Check your internet connection  
→ Make sure Playwright Chromium installed: `python -m playwright install chromium`

**Port 5000 already in use**  
→ Change the port at the bottom of `app.py`:  
`app.run(host="0.0.0.0", port=5001, debug=False)`  
→ Also update the `API` variable in `dashboard.html`:  
`const API = "http://localhost:5001/api";`

**Slow scraping**  
→ Amazon scraping takes 5–15 seconds per product  
→ Bulk imports run in background — dismiss the progress bar and check back

---

## Notes on Amazon Scraping
- Amazon actively fights scrapers. Large batches may trigger temporary blocks.
- For best results: keep under 50 products refreshing at once
- The 6-hour schedule is intentionally conservative to avoid bans
- Data is for internal monitoring only (Spread Spain's own products)
