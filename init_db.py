"""
This script is for local development only. Do not run in production.
Database initialization script for Restricted Guests Log (DNR System)
Run this once to create/reset the database schema.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Drop existing tables if they exist (for clean reset)
    cursor.execute("DROP TABLE IF EXISTS log_entries")
    cursor.execute("DROP TABLE IF EXISTS maintenance_items")
    cursor.execute("DROP TABLE IF EXISTS photos")
    cursor.execute("DROP TABLE IF EXISTS timeline_entries")
    cursor.execute("DROP TABLE IF EXISTS password_attempts")
    cursor.execute("DROP TABLE IF EXISTS records")
    cursor.execute("DROP TABLE IF EXISTS incidents")
    cursor.execute("DROP TABLE IF EXISTS room_issues")
    cursor.execute("DROP TABLE IF EXISTS staff_announcements")
    cursor.execute("DROP TABLE IF EXISTS checklist_items")
    cursor.execute("DROP TABLE IF EXISTS checklist_templates")
    cursor.execute("DROP TABLE IF EXISTS in_house_messages")
    cursor.execute("DROP TABLE IF EXISTS housekeeping_request_events")
    cursor.execute("DROP TABLE IF EXISTS housekeeping_requests")
    cursor.execute("DROP TABLE IF EXISTS important_numbers")
    cursor.execute("DROP TABLE IF EXISTS how_to_guides")
    cursor.execute("DROP TABLE IF EXISTS food_local_spots")

    # Main records table
    cursor.execute("""
        CREATE TABLE records (
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
    """)
    # status: 'active', 'expired', 'lifted'
    # ban_type: 'temporary', 'permanent'
    # expiration_type: 'date', 'resolved', 'manager_review' (only for temporary)

    # Timeline entries table
    cursor.execute("""
        CREATE TABLE timeline_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            staff_initials TEXT,
            note TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)

    # Photos table
    cursor.execute("""
        CREATE TABLE photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES records(id)
        )
    """)

    # Failed password attempts log (silent logging)
    cursor.execute("""
        CREATE TABLE password_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER,
            attempt_date TEXT NOT NULL,
            ip_address TEXT
        )
    """)

    # Maintenance items table
    cursor.execute("""
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
    """)

    # Log book entries table
    cursor.execute("""
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
    """)

    # Room issues table
    cursor.execute("""
        CREATE TABLE room_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            status TEXT CHECK(status IN ('out_of_order','use_if_needed')) NOT NULL,
            note TEXT,
            state TEXT CHECK(state IN ('active','resolved')) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP
        )
    """)

    # Staff notices table
    cursor.execute("""
        CREATE TABLE staff_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            starts_at TIMESTAMP,
            ends_at TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Important numbers
    cursor.execute("""
        CREATE TABLE important_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            phone TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)

    # How-to guides
    cursor.execute("""
        CREATE TABLE how_to_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)

    # Food and local spots
    cursor.execute("""
        CREATE TABLE food_local_spots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime'))
        )
    """)

    # Cleaning checklist templates
    cursor.execute("""
        CREATE TABLE checklist_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Cleaning checklist items
    cursor.execute("""
        CREATE TABLE checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            item_text TEXT NOT NULL,
            FOREIGN KEY (template_id) REFERENCES checklist_templates(id)
        )
    """)

    # In-house messages
    cursor.execute("""
        CREATE TABLE in_house_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_name TEXT NOT NULL,
            message_body TEXT NOT NULL,
            author_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            is_read INTEGER DEFAULT 0,
            read_at TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)

    # Housekeeping requests
    cursor.execute("""
        CREATE TABLE housekeeping_requests (
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
    """)

    cursor.execute("""
        CREATE TABLE housekeeping_request_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housekeeping_request_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            note TEXT NOT NULL,
            is_system_event INTEGER DEFAULT 1,
            FOREIGN KEY (housekeeping_request_id) REFERENCES housekeeping_requests(id)
        )
    """)

    # Seed default cleaning checklists
    templates = [
        ("Standard Room Cleaning", "Full clean for checkout rooms."),
        ("Stayover Refresh", "Light refresh for occupied rooms."),
        ("Special Condition Cleaning", "Extra steps for high-impact rooms."),
    ]
    template_ids = {}
    for name, description in templates:
        cursor.execute("""
            INSERT INTO checklist_templates (name, description, is_active)
            VALUES (?, ?, 1)
        """, (name, description))
        template_ids[name] = cursor.lastrowid

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
    cursor.executemany("""
        INSERT INTO checklist_items (template_id, position, item_text)
        VALUES (?, ?, ?)
    """, checklist_items)

    # Create indexes
    cursor.execute("CREATE INDEX idx_records_guest_name ON records(guest_name)")
    cursor.execute("CREATE INDEX idx_records_status ON records(status)")
    cursor.execute("CREATE INDEX idx_timeline_record ON timeline_entries(record_id)")
    cursor.execute("CREATE INDEX idx_photos_record ON photos(record_id)")
    cursor.execute("CREATE INDEX idx_log_entries_created_at ON log_entries(created_at)")
    cursor.execute("CREATE INDEX idx_log_entries_record ON log_entries(related_record_id)")
    cursor.execute("CREATE INDEX idx_log_entries_maintenance ON log_entries(related_maintenance_id)")
    cursor.execute("CREATE INDEX idx_maintenance_status ON maintenance_items(status)")
    cursor.execute("CREATE INDEX idx_room_issues_status ON room_issues(status)")
    cursor.execute("CREATE INDEX idx_room_issues_state ON room_issues(state)")
    cursor.execute("CREATE INDEX idx_staff_announcements_active ON staff_announcements(is_active)")
    cursor.execute("CREATE INDEX idx_checklist_templates_active ON checklist_templates(is_active)")
    cursor.execute("CREATE INDEX idx_checklist_items_template ON checklist_items(template_id)")
    cursor.execute("CREATE INDEX idx_in_house_messages_recipient ON in_house_messages(recipient_name)")
    cursor.execute("CREATE INDEX idx_in_house_messages_expires ON in_house_messages(expires_at)")
    cursor.execute("CREATE INDEX idx_housekeeping_requests_room ON housekeeping_requests(room_number)")
    cursor.execute("CREATE INDEX idx_housekeeping_requests_archived ON housekeeping_requests(archived_at)")
    cursor.execute("CREATE INDEX idx_housekeeping_requests_dates ON housekeeping_requests(start_date, end_date)")
    cursor.execute("CREATE INDEX idx_housekeeping_events_request ON housekeeping_request_events(housekeeping_request_id)")
    cursor.execute("CREATE INDEX idx_important_numbers_label ON important_numbers(label)")
    cursor.execute("CREATE INDEX idx_how_to_guides_title ON how_to_guides(title)")
    cursor.execute("CREATE INDEX idx_food_local_spots_name ON food_local_spots(name)")

    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
