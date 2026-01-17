"""
One-time migration: add log_entries and maintenance_items tables if missing.
Does not alter or drop existing data.
"""
import sqlite3

DB_PATH = "dnr.db"


def table_exists(cursor, name: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    if not table_exists(cursor, "maintenance_items"):
        cursor.execute(
            """
            CREATE TABLE maintenance_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                updated_at TIMESTAMP,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                priority TEXT CHECK(priority IN ('low','medium','high','urgent')) DEFAULT 'medium',
                status TEXT CHECK(status IN ('open','in_progress','blocked','completed')) DEFAULT 'open',
                completed_at TIMESTAMP
            )
            """
        )

    if not table_exists(cursor, "log_entries"):
        cursor.execute(
            """
            CREATE TABLE log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                author_name TEXT NOT NULL,
                note TEXT NOT NULL,
                related_record_id INTEGER,
                related_maintenance_id INTEGER,
                is_system_event BOOLEAN DEFAULT 0,
                FOREIGN KEY (related_record_id) REFERENCES records(id),
                FOREIGN KEY (related_maintenance_id) REFERENCES maintenance_items(id)
            )
            """
        )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_created_at ON log_entries(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_record ON log_entries(related_record_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_maintenance ON log_entries(related_maintenance_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_items(status)")

    conn.commit()
    conn.close()
    print("OK: migration complete")


if __name__ == "__main__":
    main()
