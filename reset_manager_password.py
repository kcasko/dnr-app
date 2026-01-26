import sqlite3
import bcrypt
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def reset_password():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    username = input("Enter the manager username (default: 'manager'): ").strip() or 'manager'
    new_password = input("Enter new password: ").strip()
    
    if not new_password:
        print("Password cannot be empty.")
        return

    # Hash using bcrypt
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Check if user exists
    user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    
    if user:
        conn.execute("UPDATE users SET password_hash = ?, is_active = 1 WHERE username = ?", (hashed, username))
        print(f"Updated password for existing user: {username}")
    else:
        print(f"User '{username}' does not exist.")
        create = input("Create this user as a Manager? (y/n): ").lower()
        if create == 'y':
            conn.execute("""
                INSERT INTO users (username, password_hash, role, is_active, force_password_change)
                VALUES (?, ?, 'manager', 1, 0)
            """, (username, hashed))
            print(f"Created new manager user: {username}")
        else:
            print("Operation cancelled.")
            conn.close()
            return
            
    conn.commit()
    conn.close()
    print("Password reset successfully.")

if __name__ == "__main__":
    reset_password()
