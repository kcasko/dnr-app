import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def inspect_schema():
    print(f"Inspecting database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables_to_check = [
        "staff_announcements",
        "room_issues",
        "maintenance_items",
        "log_entries",
        "schedules"
    ]
    
    for table in tables_to_check:
        print(f"\n--- {table} ---")
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            if not columns:
                print("Table does not exist (or empty schema)")
                continue
                
            # columns: (cid, name, type, notnull, dflt_value, pk)
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
        except Exception as e:
            print(f"Error inspecting {table}: {e}")
            
    conn.close()

if __name__ == "__main__":
    inspect_schema()
