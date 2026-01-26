import unittest
import os
import sys
import json
from datetime import datetime, date, timedelta

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, get_db_connection

class TestQASchedule(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Reset DB state for schedule tests
        self.reset_db()
        
    def reset_db(self):
        conn = get_db_connection()
        conn.execute("DELETE FROM schedules")
        conn.execute("DELETE FROM users WHERE username IN ('manager_qa', 'staff_qa')")
        
        # Create Users
        # Manager
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES ('manager_qa', '$2b$12$MdNq.jJ7.r.q.q.q.q.q.O', 'manager', 1)
        """) # Hash doesn't matter for login mocking if we use a helper or just re-hash, 
             # but here I'll use a dummy hash or just assume valid for now if I use the previous test's setup logic.
             # Actually I need real login so I'll insert a known hash.
        
        # NOTE: Using a simple hash for 'password' for speed if acceptable, or real bcrypt.
        # I'll rely on the app's hash logic being robust, so I should generate one.
        import bcrypt
        pw_hash = bcrypt.hashpw(b'password', bcrypt.gensalt()).decode('utf-8')
        
        conn.execute("UPDATE users SET password_hash = ? WHERE username = 'manager_qa'", (pw_hash,))
        
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES ('staff_qa', ?, 'front_desk', 1)
        """, (pw_hash,))
        
        conn.commit()
        conn.close()

    def login(self, username, password='password'):
        return self.client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

    # 3. ROLES & PERMISSIONS (Schedule Context)
    def test_housekeeping_roles(self):
        print("\n--- Testing Housekeeping Roles ---")
        self.login('manager_qa')
        
        # Attempt to add a schedule for Housekeeping (no user_id)
        # Assuming the POST /schedule/add endpoint logic.
        # I need to know the endpoint. Most likely /schedule/add or /api/schedule
        
        # Let's try adding via the route form data structure
        today = date.today().isoformat()
        
        # Scenario: Housekeeping shift
        # Staff Name: "Maria", Role: "housekeeping", User: None
        data = {
            'action': 'add',
            'shift_date': today,
            'shift_id': 1, # Shift 1
            'custom_name': 'Maria', # Changed from staff_name check
            'role': 'housekeeping',
            'user_id': '', # Empty user ID
            'week_start': today # To handle redirect logic
        }
        
        resp = self.client.post('/schedule/update', data=data, follow_redirects=True)
        # Check for success (redirects to view_schedule usually)
        # We catch the redirect and check DB
        
        # Verify in DB
        conn = get_db_connection()
        shift = conn.execute("SELECT * FROM schedules WHERE role = 'housekeeping'").fetchone()
        self.assertIsNotNone(shift)
        self.assertIsNone(shift['user_id']) # Should be NULL or empty
        self.assertEqual(shift['staff_name'], 'Maria')
        print("[Pass] Housekeeping appears in Schedule without User Account")
        conn.close()

    # 4. SCHEDULE
    def test_schedule_permissions(self):
        print("\n--- Testing Schedule Permissions ---")
        
        # non-manager cannot add
        self.login('staff_qa')
        data = {
            'action': 'add',
            'shift_date': date.today().isoformat(),
            'shift_id': 2,
            'custom_name': 'Staff QA',
            'role': 'front_desk',
            'user_id': 2, # Mock ID
            'week_start': date.today().isoformat()
        }
        resp = self.client.post('/schedule/update', data=data, follow_redirects=True)
        # Should now render 403.html
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b'Access Denied', resp.data)
        print("[Pass] Non-manager blocked with 403 page")
        
        conn = get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM schedules WHERE shift_id=2").fetchone()[0]
        self.assertEqual(count, 0)
        print("[Pass] Non-manager cannot edit schedule")

    def test_current_week_visibility(self):
        print("\n--- Testing Current Week Visibility ---")
        self.login('manager_qa')
        
        # Add a shift for NEXT week
        next_week = (date.today() + timedelta(days=7)).isoformat()
        conn = get_db_connection()
        conn.execute("INSERT INTO schedules (shift_date, shift_id, staff_name, role) VALUES (?, 1, 'Future Staff', 'front_desk')", (next_week,))
        conn.commit()
        conn.close()
        
        # View Schedule Page
        resp = self.client.get('/schedule')
        
        # Should NOT see 'Future Staff'
        self.assertNotIn(b'Future Staff', resp.data)
        print("[Pass] Only current week is visible (Future shifts hidden)")

    # 5. SHIFT NOTES
    def test_shift_notes(self):
        print("\n--- Testing Shift Notes ---")
        self.login('staff_qa')
        
        # Add Note
        note_content = "Test Note Content 123"
        # Endpoint requires staff_name
        data = {
            'note': note_content,
            'staff_name': 'staff_qa',
            'shift_id': '1'
        }
        resp = self.client.post('/log-book/entries', data=data, follow_redirects=True)
        
        # Verify persistence
        resp = self.client.get('/log-book')
        self.assertIn(b'Test Note Content 123', resp.data)
        
        # Verify timestamp (approximate check that it exists)
        self.assertIn(date.today().isoformat().encode(), resp.data) # Date should be there
        print("[Pass] Shift notes persist and display correctly")

if __name__ == '__main__':
    unittest.main()
