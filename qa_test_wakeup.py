import unittest
import os
import sys
from datetime import datetime, date, timedelta, time

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, get_db_connection

class TestQAWakeup(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        self.reset_db()
        
    def reset_db(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM wakeup_calls")
        conn.execute("DELETE FROM users WHERE username = 'staff_qa'")
        
        # Create User
        import bcrypt
        pw_hash = bcrypt.hashpw(b'password', bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES ('staff_qa', ?, 'front_desk', 1)
        """, (pw_hash,))
        
        conn.commit()
        conn.close()

    def login(self):
        return self.client.post('/login', data={'username': 'staff_qa', 'password': 'password'}, follow_redirects=True)

    # 6. WAKE-UP CALLS
    def test_creation_flow(self):
        print("\n--- Testing Wake-up Call Creation ---")
        self.login()
        
        today = date.today().isoformat()
        
        # Create Call
        data = {
            'room_number': '101',
            'call_date': today,
            'call_time': '07:00'
        }
        
        # Endpoint: /wakeup-calls (POST) handles adding
        
        resp = self.client.post('/wakeup-calls', data=data, follow_redirects=True)
        # Check for success message or redirect to list with success
        # The app returns redirect(url_for('wakeup_calls_list', success="Call added"))
        # But flash/args might not be in data if we follow redirect and template doesn't render it simply.
        # We can just check DB.
        
        # Verify DB
        conn = get_db_connection()
        call = conn.execute("SELECT * FROM wakeup_calls WHERE room_number = '101'").fetchone()
        self.assertIsNotNone(call)
        self.assertEqual(call['status'], 'pending')
        print("[Pass] Wake-up call scheduled successfully")
        conn.close()

    def test_due_window_logic(self):
        print("\n--- Testing Due Window Logic ---")
        self.login()
        
        conn = get_db_connection()
        now = datetime.now()
        
        # Create 3 calls:
        # 1. Past Due (1 hour ago)
        # 2. Due Now (In 5 mins)
        # 3. Future (In 2 hours)
        
        past = (now - timedelta(hours=1)).strftime('%H:%M')
        soon = (now + timedelta(minutes=5)).strftime('%H:%M')
        future = (now + timedelta(hours=2)).strftime('%H:%M')
        today = date.today().isoformat()
        
        # Insert directly to DB to bypass "past time" checks if any
        user = conn.execute("SELECT id FROM users WHERE username = 'staff_qa'").fetchone()
        
        # Schema uses logged_by_user_id
        conn.execute("INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id) VALUES (?, ?, ?, 'pending', ?)", ('101', today, past, user['id']))
        conn.execute("INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id) VALUES (?, ?, ?, 'pending', ?)", ('102', today, soon, user['id']))
        conn.execute("INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id) VALUES (?, ?, ?, 'pending', ?)", ('103', today, future, user['id']))
        conn.commit()
        conn.close()
        
        # Check Overview for Alerts
        # The logic is likely in inject_alerts (which we saw in app.py).
        # It calls get_due_wakeup_calls().
        # Logic: call_dt <= now + 10 mins.
        
        # 101 (Past): Yes
        # 102 (Soon): Yes (5 mins < 10 mins)
        # 103 (Future): No (2 hours > 10 mins)
        
        resp = self.client.get('/overview')
        
        # Retrieve the count from the HTML or check via API
        # Better: use the API /api/overview-alerts that overview calls via JS
        resp_api = self.client.get('/api/overview-alerts')
        data = resp_api.get_json()
        
        self.assertEqual(data['wakeup_alert_count'], 2) # 101 and 102
        print("[Pass] Wake-up call due window logic is correct (Past + Soon included, Future excluded)")

    def test_completion_flow(self):
        print("\n--- Testing Completion Flow ---")
        self.login()
        conn = get_db_connection()
        today = date.today().isoformat()
        user = conn.execute("SELECT id FROM users WHERE username = 'staff_qa'").fetchone()
        conn.execute("INSERT INTO wakeup_calls (room_number, call_date, call_time, status, logged_by_user_id) VALUES (?, ?, ?, 'pending', ?)", ('104', today, '09:00', user['id']))
        call_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        
        # Complete Call
        # Endpoint: /wakeup-calls/{id}/update
        resp = self.client.post(f'/wakeup-calls/{call_id}/update', data={'status': 'completed', 'outcome_note': 'Done'}, follow_redirects=True)
        # self.assertIn(b'Call updated', resp.data) # Flash message might be missing
        
        conn = get_db_connection()
        call = conn.execute("SELECT * FROM wakeup_calls WHERE id = ?", (call_id,)).fetchone()
        self.assertEqual(call['status'], 'completed')
        conn.close()
        print("[Pass] Wake-up call marked completed")

if __name__ == '__main__':
    unittest.main()
