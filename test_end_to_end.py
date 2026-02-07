"""
End-to-end test for DNR App database operations
Tests: add/remove/modify records, authentication, CSRF
"""
import os
import sys
import sqlite3
import json
from datetime import date, timedelta

# Set test environment BEFORE importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DB_PATH'] = 'test_dnr.db'

# Import app after environment setup
from app import app, get_db_connection, hash_password, is_setup_required
import init_db

def setup_test_db():
    """Create a clean test database with a test user"""
    db_path = os.environ.get('DB_PATH')
    
    # Remove existing test db
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass  # Will be replaced
    
    # Save original DB_PATH and replace
    original_db_path = init_db.DB_PATH
    init_db.DB_PATH = db_path
    
    try:
        # Use init_db to create complete schema
        init_db.init_db()
    finally:
        # Restore original
        init_db.DB_PATH = original_db_path
    
    # Add test users
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Insert test manager user
    password_hash = hash_password('TestPass123')
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, is_active, force_password_change)
        VALUES (?, ?, 'manager', 1, 0)
    """, ('test_manager', password_hash))
    
    # Insert test front_desk user
    password_hash2 = hash_password('FrontDesk123')
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, is_active, force_password_change)
        VALUES (?, ?, 'front_desk', 1, 0)
    """, ('test_user', password_hash2))
    
    conn.commit()
    conn.close()
    
    print("✓ Test database created successfully")

def test_setup_required():
    """Test is_setup_required function"""
    print("\n[TEST] is_setup_required() function")
    
    # Should return False since we have users
    result = is_setup_required()
    assert result == False, "Should return False when users exist"
    print("✓ is_setup_required() returns False with existing users")

def test_authentication():
    """Test user authentication"""
    print("\n[TEST] User Authentication")
    
    with app.test_client() as client:
        # Test login
        response = client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        }, follow_redirects=False)
        
        assert response.status_code == 302, f"Expected redirect, got {response.status_code}"
        print("✓ Login successful")
        
        # Test access to protected route
        response = client.get('/dnr')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Access to protected route successful")

def test_csrf_token():
    """Test CSRF token endpoint"""
    print("\n[TEST] CSRF Token")
    
    with app.test_client() as client:
        # Login first
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        # Get CSRF token
        response = client.get('/api/csrf-token')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        assert 'csrf_token' in data, "CSRF token not in response"
        assert data['csrf_token'] is not None, "CSRF token is None"
        print("✓ CSRF token endpoint working")

def test_add_dnr_record():
    """Test adding a DNR record"""
    print("\n[TEST] Add DNR Record")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        # Add record
        record_data = {
            'guest_name': 'John Test Doe',
            'ban_type': 'permanent',
            'reasons': ['Damage under review', 'Noise complaints multiple incidents'],
            'reason_detail': 'Broke TV and disturbed other guests',
            'staff_initials': 'TM',
            'incident_date': str(date.today())
        }
        
        response = client.post('/api/records',
            data=json.dumps(record_data),
            content_type='application/json',
            headers={'X-CSRFToken': 'test-token'}
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.data}"
        
        data = json.loads(response.data)
        assert 'id' in data, "Record ID not returned"
        record_id = data['id']
        print(f"✓ Record added successfully (ID: {record_id})")
        
        # Verify in database
        conn = get_db_connection()
        record = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        conn.close()
        
        assert record is not None, "Record not found in database"
        assert record['guest_name'] == 'John Test Doe', "Guest name mismatch"
        assert record['status'] == 'active', "Status should be active"
        print("✓ Record verified in database")
        
        return record_id

def test_add_timeline_entry(record_id):
    """Test adding timeline entry to a record"""
    print("\n[TEST] Add Timeline Entry")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        # Add timeline entry
        timeline_data = {
            'note': 'Guest called to apologize',
            'staff_initials': 'TM'
        }
        
        response = client.post(f'/api/records/{record_id}/timeline',
            data=json.dumps(timeline_data),
            content_type='application/json',
            headers={'X-CSRFToken': 'test-token'}
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.data}"
        print("✓ Timeline entry added successfully")
        
        # Verify in database
        conn = get_db_connection()
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM timeline_entries WHERE record_id = ? AND is_system = 0",
            (record_id,)
        ).fetchone()['cnt']
        conn.close()
        
        assert count >= 1, "Timeline entry not found in database"
        print("✓ Timeline entry verified in database")

def test_get_record(record_id):
    """Test retrieving a record"""
    print("\n[TEST] Get DNR Record")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        response = client.get(f'/api/records/{record_id}')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        assert data['id'] == record_id, "Record ID mismatch"
        assert data['guest_name'] == 'John Test Doe', "Guest name mismatch"
        assert len(data['timeline']) >= 2, "Timeline should have entries"
        print("✓ Record retrieved successfully")

def test_list_records():
    """Test listing all records"""
    print("\n[TEST] List DNR Records")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        response = client.get('/api/records')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 1, "Should have at least one record"
        print(f"✓ Listed {len(data)} record(s)")

def test_lift_ban(record_id):
    """Test lifting a ban"""
    print("\n[TEST] Lift DNR Ban")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_manager',
            'password': 'TestPass123'
        })
        
        # Lift ban
        lift_data = {
            'password': 'TestPass123',
            'lift_type': 'manager_override',
            'lift_reason': 'Test: Verified guest identity was mistaken',
            'initials': 'TM'
        }
        
        response = client.post(f'/api/records/{record_id}/lift',
            data=json.dumps(lift_data),
            content_type='application/json',
            headers={'X-CSRFToken': 'test-token'}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        print("✓ Ban lifted successfully")
        
        # Verify in database
        conn = get_db_connection()
        record = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        conn.close()
        
        assert record['status'] == 'lifted', "Status should be lifted"
        assert record['lifted_type'] == 'manager_override', "Lift type mismatch"
        assert record['lifted_initials'] == 'TM', "Initials mismatch"
        print("✓ Ban lift verified in database")

def test_temporary_ban_with_expiration():
    """Test adding temporary ban with expiration date"""
    print("\n[TEST] Add Temporary Ban with Expiration")
    
    with app.test_client() as client:
        # Login
        client.post('/login', data={
            'username': 'test_user',
            'password': 'FrontDesk123'
        })
        
        # Add temporary ban
        expiration = str(date.today() + timedelta(days=30))
        record_data = {
            'guest_name': 'Jane Temporary',
            'ban_type': 'temporary',
            'reasons': ['Smoking in non smoking room'],
            'reason_detail': '30-day ban for policy violation',
            'staff_initials': 'TU',
            'incident_date': str(date.today()),
            'expiration_type': 'date',
            'expiration_date': expiration
        }
        
        response = client.post('/api/records',
            data=json.dumps(record_data),
            content_type='application/json',
            headers={'X-CSRFToken': 'test-token'}
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.data}"
        
        data = json.loads(response.data)
        record_id = data['id']
        print(f"✓ Temporary ban added (ID: {record_id})")
        
        # Verify in database
        conn = get_db_connection()
        record = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        conn.close()
        
        assert record['ban_type'] == 'temporary', "Ban type should be temporary"
        assert record['expiration_date'] == expiration, "Expiration date mismatch"
        print("✓ Temporary ban verified in database")

def cleanup_test_db():
    """Remove test database"""
    db_path = os.environ.get('DB_PATH')
    if os.path.exists(db_path):
        # Give time for connections to close
        import time
        time.sleep(0.5)
        try:
            os.remove(db_path)
            print("\n✓ Test database cleaned up")
        except PermissionError:
            print("\n⚠ Warning: Could not delete test database (still in use)")

def run_all_tests():
    """Run all end-to-end tests"""
    print("=" * 60)
    print("DNR APP - END-TO-END DATABASE OPERATION TESTS")
    print("=" * 60)
    
    try:
        # Setup
        setup_test_db()
        
        # Core tests
        test_setup_required()
        test_authentication()
        test_csrf_token()
        
        # DNR record tests
        record_id = test_add_dnr_record()
        test_add_timeline_entry(record_id)
        test_get_record(record_id)
        test_list_records()
        test_lift_ban(record_id)
        test_temporary_ban_with_expiration()
        
        # Success
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nTest Summary:")
        print("  ✓ Setup required check")
        print("  ✓ User authentication")
        print("  ✓ CSRF token generation")
        print("  ✓ Add DNR record (permanent)")
        print("  ✓ Add DNR record (temporary with expiration)")
        print("  ✓ Add timeline entry")
        print("  ✓ Get single record")
        print("  ✓ List all records")
        print("  ✓ Lift/Remove ban")
        print("\n" + "=" * 60)
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cleanup_test_db()

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
