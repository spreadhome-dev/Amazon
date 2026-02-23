"""
database.py — SQLite setup and connection helper
"""

import sqlite3, logging
from contextlib import contextmanager

log = logging.getLogger(__name__)
DB_PATH = "products.db"

# ─────────────────────────────────────────
def init_db():
    """Create tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    UNIQUE NOT NULL,
                asin        TEXT,
                title       TEXT,
                category    TEXT,
                price       TEXT,
                mrp         TEXT,
                rating      TEXT,
                reviews     TEXT,
                rank        TEXT,
                stock       TEXT,
                image       TEXT,
                added_at    TEXT,
                last_scraped TEXT
            );

            CREATE TABLE IF NOT EXISTS history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT NOT NULL,
                price       TEXT,
                rating      TEXT,
                rank        TEXT,
                reviews     TEXT,
                scraped_at  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
            CREATE INDEX IF NOT EXISTS idx_history_time ON history(scraped_at);
        """)
    log.info(f"✅ Database initialised at {DB_PATH}")

# ─────────────────────────────────────────
@contextmanager
def get_db():
    """Context manager for a SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
