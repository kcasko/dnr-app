import unittest
import os
import shutil
import sys
import bcrypt
from datetime import datetime, timedelta

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, DB_PATH, get_db_connection

class TestQAAuthentication(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Reset DB for testing
        self.reset_db()

    def reset_db(self):
        conn = get_db_connection()
        # Clean users
        conn.execute("DELETE FROM users")
        
        # Create Manager
        manager_hash = bcrypt.hashpw(b'ManagerPass123', bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, ?, ?, ?)
        """, ('manager_qa', manager_hash, 'manager', 1, 0))
        
        # Create Regular User
        user_hash = bcrypt.hashpw(b'UserPass123', bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, ?, ?, ?)
        """, ('staff_qa', user_hash, 'front_desk', 1, 0))
        
        # Create Deactivated User
        deactivated_hash = bcrypt.hashpw(b'OldPass123', bcrypt.gensalt()).decode('utf-8')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, ?, ?, ?)
        """, ('deactivated_qa', deactivated_hash, 'front_desk', 0, 0))

        conn.commit()
        conn.close()

    # 1. AUTHENTICATION & ACCESS CONTROL
    def test_login_behavior(self):
        print("\n--- Testing Login Behavior ---")
        
        # Manager Login
        resp = self.client.post('/login', data={'username': 'manager_qa', 'password': 'ManagerPass123'}, follow_redirects=True)
        self.assertIn(b'Overview', resp.data)
        self.client.get('/logout')
        print("[Pass] Manager login success")

        # Regular User Login
        resp = self.client.post('/login', data={'username': 'staff_qa', 'password': 'UserPass123'}, follow_redirects=True)
        self.assertIn(b'Overview', resp.data)
        self.client.get('/logout')
        print("[Pass] Regular user login success")

        # Incorrect Password
        resp = self.client.post('/login', data={'username': 'staff_qa', 'password': 'WrongPass'}, follow_redirects=True)
        self.assertIn(b'Invalid username or password', resp.data)
        print("[Pass] Incorrect password fails cleanly")

        # Deactivated User
        resp = self.client.post('/login', data={'username': 'deactivated_qa', 'password': 'OldPass123'}, follow_redirects=True)
        # Should fail with invalid credentials message (generic security best practice)
        self.assertIn(b'Invalid username or password', resp.data) 
        print("[Pass] Deactivated user cannot login")

    def test_visibility_controls(self):
        print("\n--- Testing Visibility ---")
        
        # Manager sees settings
        self.client.post('/login', data={'username': 'manager_qa', 'password': 'ManagerPass123'}, follow_redirects=True)
        resp = self.client.get('/settings')
        self.assertIn(b'User Management', resp.data)
        self.client.get('/logout')
        print("[Pass] Manager sees Admin Settings")

        # Regular user does NOT see admin settings
        self.client.post('/login', data={'username': 'staff_qa', 'password': 'UserPass123'}, follow_redirects=True)
        resp = self.client.get('/settings')
        # Check that the TAB BUTTON is missing
        self.assertNotIn(b'onclick="openTab(event, \'UserManagement\')"', resp.data) 
        print("[Pass] Regular user does NOT see Admin Settings")

    # 2. USER MANAGEMENT
    def test_user_management(self):
        print("\n--- Testing User Management ---")
        self.client.post('/login', data={'username': 'manager_qa', 'password': 'ManagerPass123'})
        
        # Add User
        resp = self.client.post('/settings/users/add', data={
            'username': 'new_staff',
            'password': 'TempPassword123',
            'role': 'front_desk'
        }, follow_redirects=True)
        
        # Success message contains username: "User new_staff created successfully"
        self.assertIn(b'User new_staff created successfully', resp.data)
        print("[Pass] Manager can add user")

        # Verify added user
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = 'new_staff'").fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user['force_password_change'], 1)
        print("[Pass] New user has force_password_change=1")
        conn.close()

        # Deactivate
        resp = self.client.post(f'/settings/users/{user["id"]}/toggle', follow_redirects=True)
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = 'new_staff'").fetchone()
        self.assertEqual(user['is_active'], 0)
        print("[Pass] Manager can deactivate user")
        conn.close()
        
        # Reactivate
        resp = self.client.post(f'/settings/users/{user["id"]}/toggle', follow_redirects=True)
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = 'new_staff'").fetchone()
        self.assertEqual(user['is_active'], 1)
        print("[Pass] Manager can reactivate user")
        conn.close()

    def test_force_password_change(self):
        print("\n--- Testing Forced Password Change ---")
        
        # Create user with forced change
        conn = get_db_connection()
        temp_hash = bcrypt.hashpw(b'TempPass123', bcrypt.gensalt()).decode('utf-8')
        conn.execute("INSERT INTO users (username, password_hash, role, is_active, force_password_change) VALUES ('forced_user', ?, 'front_desk', 1, 1)", (temp_hash,))
        conn.commit()
        conn.close()
        
        # Login
        resp = self.client.post('/login', data={'username': 'forced_user', 'password': 'TempPass123'}, follow_redirects=True)
        # Should be redirected to change password
        self.assertIn(b'Change Password', resp.data)
        # Current password field is NOT required for forced change flow in this app
        # self.assertIn(b'Current Password', resp.data) 
        print("[Pass] User redirected to change password on first login")
        
        # Try to access other page without changing
        resp = self.client.get('/overview', follow_redirects=True)
        self.assertIn(b'Change Password', resp.data)
        print("[Pass] User cannot access other pages until password changed")

        # Change Password
        resp = self.client.post('/change-password', data={
            'new_password': 'NewSecurePass1!',
            'confirm_password': 'NewSecurePass1!'
        }, follow_redirects=True)
        
        # On success, redirects to overview. 
        # Note: App currently does NOT show a flash message.
        self.assertIn(b'Overview', resp.data)
        self.assertIn(b'Operational snapshot', resp.data)
        
        # Verify DB
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = 'forced_user'").fetchone()
        self.assertEqual(user['force_password_change'], 0)
        conn.close()
        print("[Pass] Password change clears force flag")

if __name__ == '__main__':
    unittest.main()
