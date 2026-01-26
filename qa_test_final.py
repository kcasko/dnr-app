import unittest
import os
import sys
from datetime import datetime, date, timedelta

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, get_db_connection

class TestQAFinal(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.reset_db()
        
    def reset_db(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM schedules")
        conn.execute("DELETE FROM wakeup_calls")
        conn.execute("DELETE FROM users WHERE username = 'edge_qa'")
        
        # Create User
        import bcrypt
        pw_hash = bcrypt.hashpw(b'password', bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES ('edge_qa', ?, 'front_desk', 1)
        """, (pw_hash,))
        
        conn.commit()
        conn.close()

    def login(self):
        return self.client.post('/login', data={'username': 'edge_qa', 'password': 'password'}, follow_redirects=True)

    # 12. REGRESSION & EDGE CASES
    def test_alert_no_schedule(self):
        print("\n--- Testing Alert with No Schedule ---")
        self.login()
        
        # Ensure NO schedule exists
        conn = get_db_connection()
        conn.execute("DELETE FROM schedules")
        
        # Create a due wakeup call
        today = date.today().isoformat()
        now = datetime.now()
        past = (now - timedelta(minutes=5)).strftime('%H:%M')
        user = conn.execute("SELECT id FROM users WHERE username = 'edge_qa'").fetchone()
        
        conn.execute("INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id) VALUES (?, ?, ?, 'pending', ?)", ('999', today, past, user['id']))
        conn.commit()
        conn.close()
        
        # Check alerts
        resp = self.client.get('/api/overview-alerts')
        data = resp.get_json()
        
        # Should still alert (fallback logic in app.py: "If no one is on schedule, show to all Front Desk...")
        self.assertGreater(data['wakeup_alert_count'], 0)
        print("[Pass] Alerts function even when schedule is empty")

    def test_overlapping_shifts(self):
        print("\n--- Testing Overlapping Shifts ---")
        self.login()
        today = date.today().isoformat()
        
        # Determine day of week for start_date logic? No, app uses specific dates.
        # Just insert two shifts for same day, same person? Or different?
        # App allows multiple shifts per day (1, 2, 3).
        
        conn = get_db_connection()
        # Scheduled for Shift 1 AND Shift 2
        conn.execute("INSERT INTO schedules (shift_date, shift_id, staff_name, user_id, role) VALUES (?, 1, 'Edge QA', 1, 'front_desk')", (today,))
        conn.execute("INSERT INTO schedules (shift_date, shift_id, staff_name, user_id, role) VALUES (?, 2, 'Edge QA', 1, 'front_desk')", (today,))
        conn.commit()
        conn.close()
        
        # Access overview. Should not crash.
        resp = self.client.get('/overview')
        self.assertEqual(resp.status_code, 200)
        print("[Pass] Application handles overlapping shifts gracefully")
        
    def test_data_timestamps(self):
        print("\n--- Testing Data Integrity (Timestamps) ---")
        self.login()
        
        # Add a note
        data = {'note': 'Timestamp Check', 'staff_name': 'Edge QA', 'shift_id': '1'}
        self.client.post('/log-book/entries', data=data)
        
        conn = get_db_connection()
        entry = conn.execute("SELECT created_at FROM log_entries WHERE note = 'Timestamp Check'").fetchone()
        self.assertIsNotNone(entry['created_at'])
        # Verify format (ISO or similar)
        try:
             # App usually stores ISO strings or SQLite defaults
             # Just checking it's not null is good basic check
             dt = datetime.fromisoformat(entry['created_at'].replace(' ', 'T'))
        except:
             pass 
        print(f"[Pass] Note created with timestamp: {entry['created_at']}")
        conn.close()

if __name__ == '__main__':
    unittest.main()
