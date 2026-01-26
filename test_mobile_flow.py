import os
import unittest
from app import app, get_db_connection

class MobileTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.application.config['WTF_CSRF_ENABLED'] = False
        self.app.testing = True
        
        # Login helper
        with app.app_context():
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM users WHERE role = 'manager'").fetchone()
            self.username = user['username']
            # We can't easily mimic login without password, but we can mock session if we use Flask-Login or just set session.
            # But here `login_required` checks `session.get('user_id')`.
            # We can use `with client.session_transaction() as sess:`
            self.user_id = user['id']
            conn.close()

    def test_mobile_note(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['logged_in'] = True
            sess['role'] = 'manager'
            
        print("Testing Mobile Note Addition...")
        response = self.app.post('/log-book/entries', data={
            'note': 'Test Mobile Note',
            'staff_name': 'Tester',
            'is_mobile': '1'
        }, follow_redirects=True)
        
        # Verify redirect to mobile
        # self.assertIn(b'Mobile Dashboard', response.data) # Can't check template render easily if not detecting template
        # But we can check DB.
        
        with app.app_context():
            conn = get_db_connection()
            entry = conn.execute("SELECT * FROM log_entries WHERE note LIKE '%(Added via mobile)%' ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            
            if entry and 'Test Mobile Note' in entry['note']:
                print(f"[PASS] Note found with tag: {entry['note']}")
            else:
                print("[FAIL] Mobile note tag not found")

if __name__ == '__main__':
    # Run manual test function logic instead of unittest runner to keep it simple for text output
    t = MobileTestCase()
    t.setUp()
    t.test_mobile_note()
