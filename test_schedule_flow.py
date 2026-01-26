import sqlite3
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def test_schedule():
    print("Testing Schedule Logic...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Setup: Ensure a manager exists (we assume from previous test or migration)
    manager = conn.execute("SELECT id FROM users WHERE role = 'manager'").fetchone()
    if not manager:
        print("[FAIL] No manager found for test setup")
        return
        
    test_date = datetime.date.today().isoformat()
    shift_id = 1
    
    # 1. Clean up previous test
    conn.execute("DELETE FROM schedules WHERE note = 'TEST_ENTRY'")
    conn.commit()

    # 2. Add Schedule Entry (Manager Action)
    print(f"Adding schedule for {test_date}, Shift {shift_id}...")
    try:
        conn.execute("""
            INSERT INTO schedules (staff_name, shift_date, shift_id, role, note)
            VALUES (?, ?, ?, ?, ?)
        """, ("Test Staff", test_date, shift_id, "Cleaner", "TEST_ENTRY"))
        conn.commit()
        print("[PASS] Added schedule entry")
    except Exception as e:
        print(f"[FAIL] Adding schedule failed: {e}")
        return

    # 3. Verify Entry Exists
    entry = conn.execute("""
        SELECT * FROM schedules 
        WHERE shift_date = ? AND shift_id = ? AND note = 'TEST_ENTRY'
    """, (test_date, shift_id)).fetchone()
    
    if entry and entry['staff_name'] == "Test Staff":
        print(f"[PASS] Verified schedule entry: {entry['staff_name']} - {entry['role']}")
    else:
        print("[FAIL] Schedule entry not found or incorrect")
        
    # 4. Remove Entry
    if entry:
        conn.execute("DELETE FROM schedules WHERE id = ?", (entry['id'],))
        conn.commit()
        print("[PASS] Removed schedule entry")
        
    conn.close()

if __name__ == "__main__":
    test_schedule()
