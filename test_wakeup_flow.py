import sqlite3
import os
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def test_wakeup():
    print("Testing Wakeup Call Logic...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Setup
    manager = conn.execute("SELECT id FROM users WHERE role = 'manager'").fetchone()
    if not manager:
        print("[FAIL] No manager user found")
        return
        
    today = datetime.date.today().isoformat()
    now_time = datetime.datetime.now().strftime("%H:%M")
    
    # 1. Cleanup
    conn.execute("DELETE FROM wakeup_calls WHERE room_number = 'TEST_ROOM'")
    conn.commit()
    
    # 2. Add Call
    print("Adding wakeup call...")
    conn.execute("""
        INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id, request_source)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("TEST_ROOM", today, now_time, "pending", manager['id'], "test_script"))
    conn.commit()
    
    # 3. Verify
    call = conn.execute("SELECT * FROM wakeup_calls WHERE room_number = 'TEST_ROOM' AND status = 'pending'").fetchone()
    if call:
        print(f"[PASS] Call created for {call['room_number']} at {call['call_time']}")
    else:
        print("[FAIL] Call creation failed")
        return
        
    # 4. Update Status
    print("Completing call...")
    conn.execute("UPDATE wakeup_calls SET status = 'completed', outcome_note = 'Test Done' WHERE id = ?", (call['id'],))
    conn.commit()
    
    # 5. Verify Update
    updated = conn.execute("SELECT * FROM wakeup_calls WHERE id = ?", (call['id'],)).fetchone()
    if updated['status'] == 'completed':
        print("[PASS] Call status updated to completed")
    else:
        print(f"[FAIL] Call update failed. Status: {updated['status']}")
        
    # 6. Cleanup
    conn.execute("DELETE FROM wakeup_calls WHERE room_number = 'TEST_ROOM'")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    test_wakeup()
