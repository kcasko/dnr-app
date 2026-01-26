"""
Migration to fix schedules table for non-user staff (e.g. Housekeeping).
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def migrate_fix_schedule():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Migrating schedules table...")
    
    # Cleanup previous failed runs if any
    cursor.execute("DROP TABLE IF EXISTS schedules_old")
    
    # 1. Rename existing table
    cursor.execute("ALTER TABLE schedules RENAME TO schedules_old")
    
    # 2. Create new table with NULLable user_id and new staff_name column
    cursor.execute("""
        CREATE TABLE schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, -- Nullable for non-login staff
            staff_name TEXT, -- For display (link to user.username or manual entry)
            shift_date TEXT NOT NULL,
            shift_id INTEGER NOT NULL CHECK(shift_id IN (1, 2, 3)),
            role TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # 3. Copy data
    # Note: user_id in old table was NOT NULL. We copy it.
    # We should also populate staff_name from users table for existing records if any?
    # But currently the table should be empty or only have test data.
    # Let's just copy straight across.
    
    cursor.execute("""
        INSERT INTO schedules (id, user_id, shift_date, shift_id, role, note, created_at)
        SELECT id, user_id, shift_date, shift_id, role, note, created_at
        FROM schedules_old
    """)
    
    # Update staff_name from user table join for consistency
    cursor.execute("""
        UPDATE schedules 
        SET staff_name = (SELECT username FROM users WHERE users.id = schedules.user_id)
        WHERE user_id IS NOT NULL
    """)

    # 4. Drop old table (This removes old indexes associated with it)
    cursor.execute("DROP TABLE schedules_old")

    # 5. Recreate Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(shift_date)")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_schedules_unique_staff ON schedules(shift_date, shift_id, staff_name)")
    
    conn.commit()
    conn.close()
    print("Migration (Fix Schedule) completed.")

if __name__ == "__main__":
    migrate_fix_schedule()
