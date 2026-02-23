"""
Spread Spain — Amazon Product Monitor Backend
Flask REST API + Playwright scraper + SQLite + APScheduler
Run: python app.py
"""

from __future__ import annotations
from flask import Flask, jsonify, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3, threading, logging, json
from datetime import datetime
from scraper import scrape_product
from database import init_db, get_db

# ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Allow frontend on any port to call this API

init_db()

scrape_lock = threading.Lock()

# ─────────────────────────────────────────
#  SCHEDULER
# ─────────────────────────────────────────
def scheduled_scrape_all():
    """Auto-scrape all monitored products on a schedule."""
    log.info("⏰ Scheduled scrape started")
    with get_db() as db:
        urls = [row[0] for row in db.execute("SELECT url FROM products").fetchall()]
    for url in urls:
        try:
            data = scrape_product(url)
            if data:
                _upsert_product(url, data, source="scheduler")
        except Exception as e:
            log.error(f"Scheduler scrape failed for {url}: {e}")
    log.info(f"⏰ Scheduled scrape done — {len(urls)} products")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(scheduled_scrape_all, "interval", hours=6, id="auto_scrape")
scheduler.start()

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def _upsert_product(url, data, source="api"):
    """Insert or update a product and record a history snapshot."""
    with get_db() as db:
        now = datetime.utcnow().isoformat()
        existing = db.execute("SELECT id FROM products WHERE url=?", (url,)).fetchone()
        if existing:
            db.execute("""
                UPDATE products SET
                  title=?, category=?, price=?, mrp=?, rating=?,
                  reviews=?, rank=?, stock=?, image=?, last_scraped=?
                WHERE url=?
            """, (
                data.get("title"), data.get("category"), data.get("price"),
                data.get("mrp"), data.get("rating"), data.get("reviews"),
                data.get("rank"), data.get("stock"), data.get("image"),
                now, url
            ))
        else:
            db.execute("""
                INSERT INTO products
                  (url, asin, title, category, price, mrp, rating, reviews, rank, stock, image, added_at, last_scraped)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                url, data.get("asin"), data.get("title"), data.get("category"),
                data.get("price"), data.get("mrp"), data.get("rating"),
                data.get("reviews"), data.get("rank"), data.get("stock"),
                data.get("image"), now, now
            ))

        # History snapshot
        db.execute("""
            INSERT INTO history (url, price, rating, rank, reviews, scraped_at)
            VALUES (?,?,?,?,?,?)
        """, (url, data.get("price"), data.get("rating"),
              data.get("rank"), data.get("reviews"), now))
        db.commit()

def _row_to_dict(row):
    return dict(zip(
        ["id","url","asin","title","category","price","mrp","rating",
         "reviews","rank","stock","image","added_at","last_scraped"], row
    ))

# ─────────────────────────────────────────
#  ROUTES — PRODUCTS
# ─────────────────────────────────────────
@app.route("/api/products", methods=["GET"])
def get_products():
    """Return all monitored products."""
    with get_db() as db:
        rows = db.execute("SELECT * FROM products ORDER BY added_at DESC").fetchall()
    return jsonify([_row_to_dict(r) for r in rows])


@app.route("/api/products", methods=["POST"])
def add_product():
    """Add a new product URL and scrape it immediately."""
    body = request.get_json()
    url = (body or {}).get("url", "").strip()
    if not url or "amazon.in/dp/" not in url:
        return jsonify({"error": "Invalid Amazon India URL"}), 400

    with get_db() as db:
        exists = db.execute("SELECT id FROM products WHERE url=?", (url,)).fetchone()
    if exists:
        return jsonify({"error": "Product already monitored"}), 409

    with scrape_lock:
        data = scrape_product(url)
    if not data:
        return jsonify({"error": "Scrape failed — product may be unavailable"}), 502

    _upsert_product(url, data)
    with get_db() as db:
        row = db.execute("SELECT * FROM products WHERE url=?", (url,)).fetchone()
    return jsonify(_row_to_dict(row)), 201


@app.route("/api/products/<path:url>", methods=["DELETE"])
def delete_product(url):
    """Remove a product from monitoring."""
    with get_db() as db:
        db.execute("DELETE FROM products WHERE url=?", (url,))
        db.execute("DELETE FROM history WHERE url=?", (url,))
        db.commit()
    return jsonify({"ok": True})


@app.route("/api/products/refresh", methods=["POST"])
def refresh_all():
    """Scrape all products now (runs in background thread)."""
    def _run():
        scheduled_scrape_all()
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Refresh started in background"})


@app.route("/api/products/refresh-one", methods=["POST"])
def refresh_one():
    """Scrape a single product now."""
    body = request.get_json()
    url = (body or {}).get("url", "").strip()
    with scrape_lock:
        data = scrape_product(url)
    if not data:
        return jsonify({"error": "Scrape failed"}), 502
    _upsert_product(url, data)
    with get_db() as db:
        row = db.execute("SELECT * FROM products WHERE url=?", (url,)).fetchone()
    return jsonify(_row_to_dict(row))


@app.route("/api/products/bulk", methods=["POST"])
def bulk_add():
    """Add multiple URLs at once (CSV import). Scrapes in background."""
    body = request.get_json()
    urls = (body or {}).get("urls", [])
    added, skipped = 0, 0

    def _bulk_scrape(pending_urls):
        for u in pending_urls:
            try:
                data = scrape_product(u)
                if data:
                    _upsert_product(u, data, source="bulk")
            except Exception as e:
                log.error(f"Bulk scrape error {u}: {e}")

    new_urls = []
    with get_db() as db:
        existing = {r[0] for r in db.execute("SELECT url FROM products").fetchall()}
    for url in urls:
        url = url.strip()
        if not url or "amazon.in/dp/" not in url:
            continue
        if url in existing:
            skipped += 1
            continue
        new_urls.append(url)
        added += 1

    t = threading.Thread(target=_bulk_scrape, args=(new_urls,), daemon=True)
    t.start()

    return jsonify({"ok": True, "queued": added, "skipped": skipped,
                    "message": f"{added} products queued for scraping"})


# ─────────────────────────────────────────
#  ROUTES — HISTORY
# ─────────────────────────────────────────
@app.route("/api/history", methods=["GET"])
def get_history():
    """Get price/rating/rank history for a product."""
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url param required"}), 400
    with get_db() as db:
        rows = db.execute(
            "SELECT price, rating, rank, reviews, scraped_at FROM history WHERE url=? ORDER BY scraped_at",
            (url,)
        ).fetchall()
    return jsonify([{"price":r[0],"rating":r[1],"rank":r[2],"reviews":r[3],"scraped_at":r[4]} for r in rows])


# ─────────────────────────────────────────
#  ROUTES — SCHEDULER
# ─────────────────────────────────────────
@app.route("/api/scheduler", methods=["GET"])
def get_scheduler_info():
    """Return current scheduler status."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
            "interval_hours": job.trigger.interval.total_seconds() / 3600
        })
    return jsonify({"running": scheduler.running, "jobs": jobs})


@app.route("/api/scheduler", methods=["POST"])
def update_scheduler():
    """Change scrape interval. Body: { 'hours': 6 }"""
    body = request.get_json()
    hours = float((body or {}).get("hours", 24))
    hours = max(0.5, min(hours, 24))  # Clamp 30min–24hr
    scheduler.reschedule_job("auto_scrape", trigger="interval", hours=hours)
    return jsonify({"ok": True, "hours": hours,
                    "next_run": str(scheduler.get_job("auto_scrape").next_run_time)})


# ─────────────────────────────────────────
#  ROUTES — STATS
# ─────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Dashboard summary stats."""
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        in_stock = db.execute("SELECT COUNT(*) FROM products WHERE LOWER(stock) LIKE '%in stock%'").fetchone()[0]
        avg_rating = db.execute("SELECT AVG(CAST(rating AS REAL)) FROM products WHERE rating != 'N/A' AND rating IS NOT NULL").fetchone()[0]
        low_rating = db.execute("SELECT COUNT(*) FROM products WHERE CAST(rating AS REAL) < 4.0 AND rating != 'N/A'").fetchone()[0]
        oos = total - in_stock
    return jsonify({
        "total": total,
        "in_stock": in_stock,
        "out_of_stock": oos,
        "avg_rating": round(avg_rating, 2) if avg_rating else None,
        "low_rating_count": low_rating,
        "active_alerts": oos + low_rating
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})
@app.route("/")
def home():
    return "Server is running successfully ✅"


# ─────────────────────────────────────────
if __name__ == "__main__":
    log.info("🚀 Spread Spain Backend starting on http://localhost:5000")
    log.info("📅 Auto-scrape scheduled every 6 hours")
    app.run(host="0.0.0.0", port=5000, debug=False)
