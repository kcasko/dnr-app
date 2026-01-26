import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Auto-detect path based on common locations if not in current dir
DB_PATH = os.path.join(BASE_DIR, "dnr.db")
# If not found, try the path from the user's log
if not os.path.exists(DB_PATH):
    potential_path = "/home/sleepinn/dnr-app/dnr.db"
    if os.path.exists(potential_path):
        DB_PATH = potential_path

def fix_orphans():
    print(f"Checking database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # We must disable foreign keys to delete the orphans without triggering more issues?
    # Actually, deleting the child is fine. The issue is the parent is missing.
    # So deleting the item that says "I have a parent X" when X doesn't exist is correct.
    # However, sometimes we might want to check if we can restore? No, getting ID=0 or similar implies bad data.
    
    cursor = conn.cursor()
    
    # 1. Get violations
    print("Scanning for violations...")
    violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
    
    if not violations:
        print("No violations found! db is healthy.")
        conn.close()
        return

    print(f"Found {len(violations)} orphaned records.")
    
    # Group by table for cleaner output
    # violation structure: (table, rowid, parent, fkid)
    
    for table, rowid, parent, fkid in violations:
        print(f"Removing record {rowid} from '{table}' (orphaned from '{parent}')")
        # Use rowid to delete exactly that row
        cursor.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
        
    conn.commit()
    
    # Verify
    remaining = cursor.execute("PRAGMA foreign_key_check").fetchall()
    if remaining:
        print(f"⚠ Warning: {len(remaining)} violations still exist.")
    else:
        print("✓ All orphans cleaned up successfully.")
        
    conn.close()

if __name__ == "__main__":
    fix_orphans()
