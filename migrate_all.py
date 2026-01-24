"""
DNR App – Unified Migration Script (Corrected)
Safe to run multiple times.
"""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "/home/sleepinn/dnr-app/dnr.db"


def table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cursor.fetchall()]


def migrate_housekeeping(cursor):
    print("→ Checking housekeeping_service_dates")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS housekeeping_service_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            service_date DATE NOT NULL,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (request_id)
                REFERENCES housekeeping_requests(id)
                ON DELETE CASCADE
        )
    """)

    print("✓ housekeeping_service_dates ensured")


def migrate_in_house_messages(cursor):
    print("→ Checking in_house_messages")

    if not table_exists(cursor, "in_house_messages"):
        print("⚠ in_house_messages table missing, skipping")
        return

    if not column_exists(cursor, "in_house_messages", "archived"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived INTEGER DEFAULT 0
        """)
        print("✓ added archived")

    if not column_exists(cursor, "in_house_messages", "archived_at"):
        cursor.execute("""
            ALTER TABLE in_house_messages
            ADD COLUMN archived_at TEXT
        """)
        print("✓ added archived_at")

    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")

    cursor.execute("""
        UPDATE in_house_messages
        SET archived = 1,
            archived_at = ?
        WHERE expires_at IS NOT NULL
          AND expires_at <= ?
          AND archived = 0
    """, (now, now))

    print(f"✓ auto-archived {cursor.rowcount} expired messages")


def migrate_schema_version(cursor):
    print("→ Ensuring schema_version table")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM schema_version")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
            INSERT INTO schema_version (version, applied_at)
            VALUES (?, ?)
        """, (1, datetime.now(timezone.utc).isoformat()))
        print("✓ schema version initialized to 1")
    else:
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        version = cursor.fetchone()[0]
        print(f"✓ schema version already present ({version})")


def main():
    print("=== DNR MIGRATION START ===")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    migrate_housekeeping(cursor)
    migrate_in_house_messages(cursor)
    migrate_schema_version(cursor)

    conn.commit()
    conn.close()

    print("=== MIGRATION COMPLETE ===")


if __name__ == "__main__":
    main()
