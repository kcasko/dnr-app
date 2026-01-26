import sqlite3
import os
import datetime
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def debug_overview():
    print(f"Testing overview logic against {DB_PATH}")
    
    try:
        conn = get_db()
        
        print("1. Room Issues...")
        ooo_count = conn.execute("SELECT COUNT(*) FROM room_issues WHERE status = 'out_of_order' AND state = 'active'").fetchone()[0]
        print(f"   OOO: {ooo_count}")
        
        uin_count = conn.execute("SELECT COUNT(*) FROM room_issues WHERE status = 'use_if_needed' AND state = 'active'").fetchone()[0]
        print(f"   UIN: {uin_count}")
        
        print("2. Maintenance...")
        maint_count = conn.execute("SELECT COUNT(*) FROM maintenance_items WHERE status IN ('open', 'in_progress') AND priority IN ('high', 'urgent')").fetchone()[0]
        print(f"   Critical Maint: {maint_count}")
        
        print("3. Announcements...")
        now = datetime.datetime.now()
        now_str = now.isoformat()
        announcements = conn.execute("""
            SELECT * FROM staff_announcements 
            WHERE is_active = 1 
            AND (starts_at IS NULL OR starts_at <= ?)
            AND (ends_at IS NULL OR ends_at >= ?)
            ORDER BY created_at DESC
        """, (now_str, now_str)).fetchall()
        print(f"   Announcements: {len(announcements)}")
        
        print("4. Feed...")
        feed = conn.execute("""
            SELECT * FROM log_entries 
            ORDER BY created_at DESC 
            LIMIT 20
        """).fetchall()
        print(f"   Feed items: {len(feed)}")
        
        print("5. Schedule...")
        today_str = date.today().isoformat()
        shifts = conn.execute("""
            SELECT s.*, u.username 
            FROM schedules s
            LEFT JOIN users u ON s.user_id = u.id
            WHERE shift_date = ?
            ORDER BY shift_id
        """, (today_str,)).fetchall()
        print(f"   Shifts: {len(shifts)}")
        
        conn.close()
        print("SUCCESS: Data fetching completed without error.")
        
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_overview()
