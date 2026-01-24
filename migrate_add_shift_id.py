"""
One-time migration: add shift_id column to log_entries table.
Does not alter or drop existing data.
"""
import sqlite3

DB_PATH = "dnr.db"


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    if not column_exists(cursor, "log_entries", "shift_id"):
        cursor.execute(
            """
            ALTER TABLE log_entries
            ADD COLUMN shift_id INTEGER CHECK(shift_id IN (1, 2, 3))
            """
        )
        print("Added shift_id column to log_entries")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_shift ON log_entries(shift_id)")

    conn.commit()
    conn.close()
    print("OK: migration complete")


if __name__ == "__main__":
    main()
