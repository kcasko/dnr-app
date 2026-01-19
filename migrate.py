import sqlite3

DB_PATH = "dnr.db"
CURRENT_SCHEMA_VERSION = 7


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


def migration_3(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS room_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            status TEXT CHECK(status IN ('out_of_order','use_if_needed')) NOT NULL,
            note TEXT,
            state TEXT CHECK(state IN ('active','resolved')) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
        """
    )
    conn.execute(
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_room_issues_status ON room_issues(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_room_issues_state ON room_issues(state)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_staff_announcements_active ON staff_announcements(is_active)")
    conn.commit()


def migration_4(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checklist_templates_active ON checklist_templates(is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checklist_items_template ON checklist_items(template_id)")

    row = conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()
    existing = row[0] if row else 0
    if existing == 0:
        templates = [
            ("Standard Room Cleaning", "Full clean for checkout rooms."),
            ("Stayover Refresh", "Light refresh for occupied rooms."),
            ("Special Condition Cleaning", "Extra steps for high-impact rooms."),
        ]
        template_ids = {}
        for name, description in templates:
            conn.execute(
                "INSERT INTO checklist_templates (name, description, is_active) VALUES (?, ?, 1)",
                (name, description),
            )
            template_ids[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        checklist_items = [
            (template_ids["Standard Room Cleaning"], 1, "Strip linens and check mattress pad."),
            (template_ids["Standard Room Cleaning"], 2, "Dust all surfaces and sanitize high-touch areas."),
            (template_ids["Standard Room Cleaning"], 3, "Clean bathroom: toilet, sink, shower, floor."),
            (template_ids["Standard Room Cleaning"], 4, "Replace towels and amenities; restock supplies."),
            (template_ids["Standard Room Cleaning"], 5, "Vacuum floors and check under beds/furniture."),
            (template_ids["Standard Room Cleaning"], 6, "Set HVAC to standard temperature and close drapes."),
            (template_ids["Stayover Refresh"], 1, "Remove trash and replace liners."),
            (template_ids["Stayover Refresh"], 2, "Refresh towels and amenities as needed."),
            (template_ids["Stayover Refresh"], 3, "Wipe high-touch surfaces."),
            (template_ids["Stayover Refresh"], 4, "Quick bathroom tidy and spot clean."),
            (template_ids["Stayover Refresh"], 5, "Straighten bed and tidy room."),
            (template_ids["Special Condition Cleaning"], 1, "Open windows or run fan for ventilation."),
            (template_ids["Special Condition Cleaning"], 2, "Inspect for damage; report to manager."),
            (template_ids["Special Condition Cleaning"], 3, "Deep clean upholstery and hard surfaces."),
            (template_ids["Special Condition Cleaning"], 4, "Sanitize fridge, microwave, and high-use items."),
            (template_ids["Special Condition Cleaning"], 5, "Check for odor sources and treat as needed."),
        ]
        conn.executemany(
            "INSERT INTO checklist_items (template_id, position, item_text) VALUES (?, ?, ?)",
            checklist_items,
        )
    conn.commit()


def migration_5(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS in_house_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_name TEXT NOT NULL,
            message_body TEXT NOT NULL,
            author_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            is_read INTEGER DEFAULT 0,
            read_at TIMESTAMP,
            expires_at TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_in_house_messages_recipient ON in_house_messages(recipient_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_in_house_messages_expires ON in_house_messages(expires_at)")
    conn.commit()


def migration_6(conn):
    conn.execute(
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS how_to_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS food_local_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_important_numbers_label ON important_numbers(label)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_how_to_guides_title ON how_to_guides(title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_food_local_spots_name ON food_local_spots(name)")
    conn.commit()


def migration_7(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS housekeeping_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            frequency TEXT NOT NULL DEFAULT 'every_other_day' CHECK(frequency = 'every_other_day'),
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            archived_at TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS housekeeping_request_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housekeeping_request_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            note TEXT NOT NULL,
            is_system_event INTEGER DEFAULT 1,
            FOREIGN KEY (housekeeping_request_id) REFERENCES housekeeping_requests(id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_room ON housekeeping_requests(room_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_archived ON housekeeping_requests(archived_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_requests_dates ON housekeeping_requests(start_date, end_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping_events_request ON housekeeping_request_events(housekeeping_request_id)")
    conn.commit()


def run_migrations(conn, current_version: int):
    if current_version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError("schema_version is newer than this codebase")

    migrations = {
        2: migration_2,
        3: migration_3,
        4: migration_4,
        5: migration_5,
        6: migration_6,
        7: migration_7,
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
