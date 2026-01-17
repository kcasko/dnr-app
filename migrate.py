import sqlite3

DB_PATH = "dnr.db"
CURRENT_SCHEMA_VERSION = 2


def ensure_schema_version_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
        """
    )
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.commit()


def get_schema_version(conn):
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        raise RuntimeError("schema_version table is empty or missing")
    try:
        return int(row[0])
    except (TypeError, ValueError):
        raise RuntimeError("schema_version is invalid")


def set_schema_version(conn, version: int):
    conn.execute("UPDATE schema_version SET version = ?", (version,))
    conn.commit()


def migration_2(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            author_name TEXT NOT NULL,
            note TEXT NOT NULL,
            related_record_id INTEGER,
            related_maintenance_id INTEGER,
            is_system_event BOOLEAN DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    conn.commit()


def run_migrations(conn, current_version: int):
    if current_version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError("schema_version is newer than this codebase")

    migrations = {
        2: migration_2,
    }

    version = current_version
    while version < CURRENT_SCHEMA_VERSION:
        next_version = version + 1
        migration = migrations.get(next_version)
        if not migration:
            raise RuntimeError(f"Missing migration for version {next_version}")
        migration(conn)
        set_schema_version(conn, next_version)
        version = next_version


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema_version_table(conn)
        current_version = get_schema_version(conn)
        run_migrations(conn, current_version)
        print(f"OK: schema at version {get_schema_version(conn)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
