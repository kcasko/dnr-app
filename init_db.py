import sqlite3

DB_PATH = "dnr.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        incident_date TEXT NOT NULL,
        room_number TEXT,
        reason TEXT NOT NULL,
        description TEXT NOT NULL,
        staff_initials TEXT NOT NULL,
        ban_type TEXT NOT NULL CHECK (ban_type IN ('permanent', 'temporary')),
        expires_on TEXT,
        active INTEGER NOT NULL CHECK (active IN (0, 1))
     );
     """)
    
    conn.execute("""
                 CREATE INDEX IF NOT EXISTS idx_incidents_name
                 ON incidents (last_name, first_name);
                 """)
    
    conn.commit()
    conn.close()
    print(f"OK: initialized {DB_PATH}")

if __name__ == "__main__":
    main()
