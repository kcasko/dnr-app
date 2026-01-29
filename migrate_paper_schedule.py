"""
Database migration to support paper-style schedule format.

Adds:
- department column (FRONT DESK, HOUSEKEEPING, etc.)
- shift_time column (e.g., "7am-3pm", "ON")
- phone_number column
- Makes shift_id nullable for backward compatibility
- Migrates existing shift-based data to paper format
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

# Department mapping based on user roles
ROLE_TO_DEPARTMENT = {
    'manager': 'FRONT DESK',
    'front_desk': 'FRONT DESK',
    'housekeeping': 'HOUSEKEEPING',
    'maintenance': 'MAINTENANCE',
}

# Shift ID to time range mapping
SHIFT_TIME_MAP = {
    1: '7am-3pm',
    2: '3pm-11pm',
    3: '11pm-7am'
}

def migrate_paper_schedule():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("MIGRATING SCHEDULES TO PAPER-STYLE FORMAT")
    print("=" * 60)

    try:
        # Check if migration already applied
        cursor.execute("PRAGMA table_info(schedules)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'department' in columns:
            print("[INFO] Migration already applied. Skipping.")
            conn.close()
            return

        # 1. Create backup of existing schedules
        print("\n[1/6] Creating backup of existing schedules...")
        cursor.execute("DROP TABLE IF EXISTS schedules_backup")
        cursor.execute("""
            CREATE TABLE schedules_backup AS
            SELECT * FROM schedules
        """)
        backup_count = cursor.execute("SELECT COUNT(*) FROM schedules_backup").fetchone()[0]
        print(f"      Backed up {backup_count} existing schedule entries")

        # 2. Drop existing unique index
        print("\n[2/6] Dropping old unique index...")
        cursor.execute("DROP INDEX IF EXISTS idx_schedules_unique_staff")

        # 3. Rename current table
        print("\n[3/6] Renaming current schedules table...")
        cursor.execute("ALTER TABLE schedules RENAME TO schedules_old")

        # 4. Create new schedules table with additional columns
        print("\n[4/6] Creating new schedules table schema...")
        cursor.execute("""
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                staff_name TEXT,
                shift_date TEXT NOT NULL,
                shift_id INTEGER CHECK(shift_id IN (1, 2, 3)),  -- Nullable now
                shift_time TEXT,  -- NEW: "7am-3pm", "ON", etc.
                department TEXT,  -- NEW: "FRONT DESK", "HOUSEKEEPING", etc.
                phone_number TEXT,  -- NEW: Staff phone number
                role TEXT,
                note TEXT,
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 5. Migrate existing data
        print("\n[5/6] Migrating existing schedule data to paper format...")
        cursor.execute("SELECT * FROM schedules_old")
        old_schedules = cursor.fetchall()

        migrated_count = 0
        for old_row in old_schedules:
            # Get user info to determine department
            department = None
            if old_row['user_id']:
                user = cursor.execute(
                    "SELECT role FROM users WHERE id = ?",
                    (old_row['user_id'],)
                ).fetchone()
                if user:
                    department = ROLE_TO_DEPARTMENT.get(user['role'], 'FRONT DESK')

            # If no department determined, try from role field
            if not department and old_row['role']:
                department = ROLE_TO_DEPARTMENT.get(old_row['role'].lower(), 'FRONT DESK')

            # Default to FRONT DESK if still unknown
            if not department:
                department = 'FRONT DESK'

            # Map shift_id to shift_time
            shift_time = SHIFT_TIME_MAP.get(old_row['shift_id'], '7am-3pm')

            # Insert migrated record
            cursor.execute("""
                INSERT INTO schedules
                (user_id, staff_name, shift_date, shift_id, shift_time, department,
                 phone_number, role, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                old_row['user_id'],
                old_row['staff_name'],
                old_row['shift_date'],
                old_row['shift_id'],  # Keep for backward compat
                shift_time,
                department,
                None,  # phone_number (not in old data)
                old_row['role'],
                old_row['note'],
                old_row['created_at']
            ))
            migrated_count += 1

        print(f"      Migrated {migrated_count} schedule entries")

        # 6. Create new indexes
        print("\n[6/6] Creating new indexes...")
        cursor.execute("DROP INDEX IF EXISTS idx_schedules_date")
        cursor.execute("DROP INDEX IF EXISTS idx_schedules_department")
        cursor.execute("""
            CREATE UNIQUE INDEX idx_schedules_unique_staff
            ON schedules(shift_date, staff_name, department, shift_time)
        """)
        cursor.execute("CREATE INDEX idx_schedules_date ON schedules(shift_date)")
        cursor.execute("CREATE INDEX idx_schedules_department ON schedules(department)")

        # 7. Drop old table
        cursor.execute("DROP TABLE schedules_old")

        # 8. Create schedule_uploads table to track uploaded files
        print("\n[BONUS] Creating schedule_uploads tracking table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                week_start_date TEXT NOT NULL,
                uploaded_by_user_id INTEGER,
                upload_timestamp TIMESTAMP DEFAULT (datetime('now','localtime')),
                parsed_entries_count INTEGER DEFAULT 0,
                status TEXT CHECK(status IN ('pending', 'confirmed', 'cancelled')) DEFAULT 'pending',
                FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id)
            )
        """)
        cursor.execute("CREATE INDEX idx_uploads_week ON schedule_uploads(week_start_date)")

        conn.commit()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"[OK] Added 'department', 'shift_time', 'phone_number' columns")
        print(f"[OK] Migrated {migrated_count} existing entries to paper format")
        print(f"[OK] Created schedule_uploads tracking table")
        print(f"[OK] Updated indexes for better query performance")
        print("\nBackup table 'schedules_backup' preserved for safety.")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print("Rolling back changes...")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_paper_schedule()
