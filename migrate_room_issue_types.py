"""
Database migration to add issue types to room issues.

Adds:
- issue_type column (Hot Water, HVAC, Plumbing, Other)
- New status values (limited_use, monitor) while keeping existing ones

This allows staff to categorize room issues and track hot water problems
specifically for better operational visibility.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")


def migrate_room_issue_types():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("MIGRATING ROOM ISSUES TO SUPPORT ISSUE TYPES")
    print("=" * 60)

    try:
        # Check if migration already applied
        cursor.execute("PRAGMA table_info(room_issues)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'issue_type' in columns:
            print("[INFO] Migration already applied. Skipping.")
            conn.close()
            return

        # 1. Create backup
        print("\n[1/5] Creating backup of existing room_issues...")
        cursor.execute("DROP TABLE IF EXISTS room_issues_backup")
        cursor.execute("""
            CREATE TABLE room_issues_backup AS
            SELECT * FROM room_issues
        """)
        backup_count = cursor.execute("SELECT COUNT(*) FROM room_issues_backup").fetchone()[0]
        print(f"      Backed up {backup_count} existing room issues")

        # 2. Rename current table
        print("\n[2/5] Renaming current room_issues table...")
        cursor.execute("ALTER TABLE room_issues RENAME TO room_issues_old")

        # 3. Create new table with issue_type column and updated status values
        print("\n[3/5] Creating new room_issues table schema...")
        cursor.execute("""
            CREATE TABLE room_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT NOT NULL,
                issue_type TEXT CHECK(issue_type IN ('Hot Water', 'HVAC', 'Plumbing', 'Other')) DEFAULT 'Other',
                status TEXT CHECK(status IN ('out_of_order','use_if_needed','limited_use','monitor')) NOT NULL,
                note TEXT,
                state TEXT CHECK(state IN ('active','resolved')) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
                updated_at TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)

        # 4. Migrate existing data
        print("\n[4/5] Migrating existing room issues...")
        cursor.execute("SELECT * FROM room_issues_old")
        old_issues = cursor.fetchall()

        migrated_count = 0
        for old_issue in old_issues:
            # Map old 'use_if_needed' to 'limited_use' for clearer naming
            # Keep 'out_of_order' as is
            old_status = old_issue['status']
            new_status = 'limited_use' if old_status == 'use_if_needed' else old_status

            cursor.execute("""
                INSERT INTO room_issues
                (id, room_number, issue_type, status, note, state, created_at, updated_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                old_issue['id'],
                old_issue['room_number'],
                'Other',  # Default to 'Other' for existing issues
                new_status,
                old_issue['note'],
                old_issue['state'],
                old_issue['created_at'],
                old_issue['updated_at'],
                old_issue['resolved_at']
            ))
            migrated_count += 1

        print(f"      Migrated {migrated_count} room issues")
        print(f"      Mapped 'use_if_needed' -> 'limited_use' for clarity")

        # 5. Drop old table
        print("\n[5/5] Cleaning up...")
        cursor.execute("DROP TABLE room_issues_old")

        conn.commit()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"[OK] Added 'issue_type' column with values:")
        print(f"     - Hot Water (for tracking hot water problems)")
        print(f"     - HVAC (for heating/cooling issues)")
        print(f"     - Plumbing (for plumbing problems)")
        print(f"     - Other (for general issues)")
        print(f"[OK] Updated status values:")
        print(f"     - out_of_order (room cannot be assigned)")
        print(f"     - limited_use (room can be used if desperate)")
        print(f"     - monitor (watch for issues)")
        print(f"[OK] Migrated {migrated_count} existing room issues")
        print("\nBackup table 'room_issues_backup' preserved for safety.")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print("Rolling back changes...")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_room_issue_types()
