from app import get_db_connection
import bcrypt

def setup():
    conn = get_db_connection()
    
    # Clean up
    conn.execute("DELETE FROM users WHERE username = 'manager_qa'")
    
    # Create Manager
    pw = b'manager123'
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt()).decode('utf-8')
    
    conn.execute("""
        INSERT INTO users (username, password_hash, role, is_active, force_password_change)
        VALUES ('manager_qa', ?, 'manager', 1, 0)
    """, (hashed,))
    
    conn.commit()
    conn.close()
    print("User 'manager_qa' created with password 'manager123'")


if __name__ == '__main__':
    setup()
