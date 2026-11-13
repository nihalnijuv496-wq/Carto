import os
import sqlite3

DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
)
DB_PATH = os.path.join(DATA_DIR, "world.db")


def getConnection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initDb():
    conn = getConnection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS maps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            seed INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            population INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (map_id) REFERENCES maps(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
