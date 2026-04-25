from __future__ import annotations

import sqlite3
from pathlib import Path


def init_db(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                media_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channel_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                state TEXT NOT NULL,
                external_id TEXT,
                title_override TEXT,
                description_override TEXT,
                price_override REAL,
                attributes_override_json TEXT NOT NULL,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(product_id, channel),
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS publish_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                adapter TEXT NOT NULL,
                listing_state TEXT NOT NULL,
                external_id TEXT,
                result_json TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS channel_settings (
                channel TEXT PRIMARY KEY,
                default_category TEXT,
                default_currency TEXT,
                default_attributes_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
