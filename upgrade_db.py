"""
Unified, idempotent migration for the current schema.
Run with:  python upgrade_db.py

This replaces the old one-off migrate_*.py scripts.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).with_name("dnr.db")


# --- helpers ---------------------------------------------------------------

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return column in [row[1] for row in cur.fetchall()]


def index_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


# --- core schema pieces ----------------------------------------------------

def ensure_users(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager','front_desk','night_audit')),
            is_active INTEGER DEFAULT 1,
            force_password_change INTEGER DEFAULT 0,
            notification_preferences TEXT DEFAULT '{"wakeup_calls": true}',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            last_login TIMESTAMP
        )
        """
    )


def ensure_login_attempts(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            attempt_count INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            last_attempt TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
        """
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_login_attempts_username ON login_attempts(username)"
    )


def ensure_log_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_items (
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

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            author_name TEXT NOT NULL,
            note TEXT NOT NULL,
            related_record_id INTEGER,
            related_maintenance_id INTEGER,
            is_system_event INTEGER DEFAULT 0,
            shift_id INTEGER CHECK(shift_id IN (1,2,3)),
            FOREIGN KEY (related_record_id) REFERENCES records(id),
            FOREIGN KEY (related_maintenance_id) REFERENCES maintenance_items(id)
        )
        """
    )

    if not column_exists(cur, "log_entries", "shift_id"):
        cur.execute(
            "ALTER TABLE log_entries ADD COLUMN shift_id INTEGER CHECK(shift_id IN (1,2,3))"
        )

    cur.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_created_at ON log_entries(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_record ON log_entries(related_record_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_log_entries_maintenance ON log_entries(related_maintenance_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_items(status)")


def ensure_records_core(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guest_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            ban_type TEXT NOT NULL,
            reasons TEXT NOT NULL,
            reason_detail TEXT,
            date_added TEXT NOT NULL,
            incident_date TEXT,
            expiration_type TEXT,
            expiration_date TEXT,
            lifted_date TEXT,
            lifted_type TEXT,
            lifted_reason TEXT,
            lifted_initials TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS timeline_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            staff_initials TEXT,
            note TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
        """
    )


def ensure_supporting_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS room_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            issue_type TEXT CHECK(issue_type IN ('Hot Water','HVAC','Plumbing','Other')) DEFAULT 'Other',
            status TEXT CHECK(status IN ('out_of_order','use_if_needed')) NOT NULL,
            note TEXT,
            state TEXT CHECK(state IN ('active','resolved')) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
        """
    )
    if not column_exists(cur, "room_issues", "issue_type"):
        cur.execute(
            "ALTER TABLE room_issues ADD COLUMN issue_type TEXT CHECK(issue_type IN ('Hot Water','HVAC','Plumbing','Other')) DEFAULT 'Other'"
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS important_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS how_to_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            filename TEXT,
            original_filename TEXT
        )
        """
    )
    if not column_exists(cur, "how_to_guides", "filename"):
        cur.execute("ALTER TABLE how_to_guides ADD COLUMN filename TEXT")
    if not column_exists(cur, "how_to_guides", "original_filename"):
        cur.execute("ALTER TABLE how_to_guides ADD COLUMN original_filename TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            filename TEXT,
            original_filename TEXT
        )
        """
    )
    if not column_exists(cur, "checklist_templates", "filename"):
        cur.execute("ALTER TABLE checklist_templates ADD COLUMN filename TEXT")
    if not column_exists(cur, "checklist_templates", "original_filename"):
        cur.execute("ALTER TABLE checklist_templates ADD COLUMN original_filename TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            item_text TEXT NOT NULL,
            FOREIGN KEY (template_id) REFERENCES checklist_templates(id)
        )
        """
    )


def ensure_in_house_messages(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS in_house_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_name TEXT NOT NULL,
            message_body TEXT NOT NULL,
            author_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            is_read INTEGER DEFAULT 0,
            read_at TIMESTAMP,
            expires_at TIMESTAMP,
            archived INTEGER DEFAULT 0,
            archived_at TEXT
        )
        """
    )
    if not column_exists(cur, "in_house_messages", "archived"):
        cur.execute("ALTER TABLE in_house_messages ADD COLUMN archived INTEGER DEFAULT 0")
    if not column_exists(cur, "in_house_messages", "archived_at"):
        cur.execute("ALTER TABLE in_house_messages ADD COLUMN archived_at TEXT")

    now = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    cur.execute(
        """
        UPDATE in_house_messages
        SET archived = 1, archived_at = ?
        WHERE expires_at IS NOT NULL
          AND expires_at <= ?
          AND archived = 0
        """,
        (now, now),
    )


def ensure_housekeeping(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS housekeeping_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            guest_name TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'every_3rd_day' CHECK(frequency IN ('none','every_3rd_day','daily','custom')),
            frequency_days INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            archived_at TIMESTAMP
        )
        """
    )
    if not column_exists(cur, "housekeeping_requests", "guest_name"):
        cur.execute("ALTER TABLE housekeeping_requests ADD COLUMN guest_name TEXT")
    if not column_exists(cur, "housekeeping_requests", "frequency_days"):
        cur.execute("ALTER TABLE housekeeping_requests ADD COLUMN frequency_days INTEGER")

    # housekeeping_service_dates with correct FK name
    if table_exists(cur, "housekeeping_service_dates"):
        has_request_id = column_exists(cur, "housekeeping_service_dates", "request_id")
        has_hk_request_id = column_exists(cur, "housekeeping_service_dates", "housekeeping_request_id")
        if has_request_id and not has_hk_request_id:
            cur.execute("ALTER TABLE housekeeping_service_dates RENAME TO housekeeping_service_dates_old")
            cur.execute(
                """
                CREATE TABLE housekeeping_service_dates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    housekeeping_request_id INTEGER NOT NULL,
                    service_date TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                    FOREIGN KEY (housekeeping_request_id)
                        REFERENCES housekeeping_requests(id)
                        ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                INSERT INTO housekeeping_service_dates (id, housekeeping_request_id, service_date, is_active, created_at)
                SELECT id, request_id, service_date, is_active, created_at
                FROM housekeeping_service_dates_old
                """
            )
            cur.execute("DROP TABLE housekeeping_service_dates_old")
    else:
        cur.execute(
            """
            CREATE TABLE housekeeping_service_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                housekeeping_request_id INTEGER NOT NULL,
                service_date TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (housekeeping_request_id)
                    REFERENCES housekeeping_requests(id)
                    ON DELETE CASCADE
            )
            """
        )

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_housekeeping_service_dates_request ON housekeeping_service_dates(housekeeping_request_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_housekeeping_service_dates_date ON housekeeping_service_dates(service_date, is_active)"
    )


def ensure_schedule(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            staff_name TEXT,
            shift_date TEXT NOT NULL,
            shift_id INTEGER CHECK(shift_id IN (1,2,3)),
            shift_time TEXT,
            department TEXT,
            phone_number TEXT,
            role TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    for col, ddl in [
        ("shift_time", "ALTER TABLE schedules ADD COLUMN shift_time TEXT"),
        ("department", "ALTER TABLE schedules ADD COLUMN department TEXT"),
        ("phone_number", "ALTER TABLE schedules ADD COLUMN phone_number TEXT"),
        ("staff_name", "ALTER TABLE schedules ADD COLUMN staff_name TEXT"),
    ]:
        if not column_exists(cur, "schedules", col):
            cur.execute(ddl)

    cur.execute("DROP INDEX IF EXISTS idx_schedules_unique_staff")
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_unique_staff
        ON schedules(shift_date, staff_name, department, shift_time)
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(shift_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_schedules_department ON schedules(department)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            week_start_date TEXT NOT NULL,
            uploaded_by_user_id INTEGER,
            upload_timestamp TIMESTAMP DEFAULT (datetime('now','localtime')),
            parsed_entries_count INTEGER DEFAULT 0,
            status TEXT CHECK(status IN ('pending','confirmed','cancelled')) DEFAULT 'pending',
            FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_uploads_week ON schedule_uploads(week_start_date)")


def ensure_wakeup_calls(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS wakeup_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            call_date TEXT NOT NULL,
            call_time TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            created_by TEXT,
            status TEXT DEFAULT 'pending',
            completed_at TIMESTAMP,
            completed_by TEXT
        )
        """
    )


# --- runner ---------------------------------------------------------------

def main():
    conn = connect()
    cur = conn.cursor()

    ensure_users(cur)
    ensure_login_attempts(cur)
    ensure_records_core(cur)
    ensure_log_tables(cur)
    ensure_supporting_tables(cur)
    ensure_in_house_messages(cur)
    ensure_housekeeping(cur)
    ensure_schedule(cur)
    ensure_wakeup_calls(cur)

    conn.commit()
    conn.close()
    print(f"Database upgraded/verified at {DB_PATH}")


if __name__ == "__main__":
    main()
