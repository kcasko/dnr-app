"""
Setup test users for Playwright production tests
"""
import sqlite3
import os
import sys

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import hash_password, get_db_connection

def setup_test_users():
    """Create test users in the database"""
    print("Setting up test users...")
    
    conn = get_db_connection()
    
    # Check if test_manager exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", ('test_manager',)).fetchone()
    
    if existing:
        print("Test users already exist. Updating passwords...")
        # Update passwords
        manager_hash = hash_password('TestPass123')
        conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                    (manager_hash, 'test_manager'))
    else:
        print("Creating test users...")
        # Create test manager
        manager_hash = hash_password('TestPass123')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, 'manager', 1, 0)
        """, ('test_manager', manager_hash))
    
    # Check if test_user exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", ('test_user',)).fetchone()
    
    if not existing:
        # Create test front desk user
        user_hash = hash_password('FrontDesk123')
        conn.execute("""
            INSERT INTO users (username, password_hash, role, is_active, force_password_change)
            VALUES (?, ?, 'front_desk', 1, 0)
        """, ('test_user', user_hash))
    
    conn.commit()
    conn.close()
    
    print("✓ Test users ready:")
    print("  - test_manager / TestPass123 (manager)")
    print("  - test_user / FrontDesk123 (front_desk)")

if __name__ == "__main__":
    setup_test_users()
