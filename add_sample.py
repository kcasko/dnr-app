import sqlite3
from datetime import date, timedelta

DB_PATH = "dnr.db"

def main():
    conn = sqlite3.connect(DB_PATH)

    today = date.today()
    in_14_days = today + timedelta(days=14)
    expired_7_days_ago = today - timedelta(days=7)

    rows = [
        ("John", "Smith", str(today), "214", "damage", "Broken TV screen reported by housekeeping.", "KC", "permanent", None, 1),
        ("Jane", "Smith", str(today), "109", "nonpayment", "Declined card at checkout after multiple attempts.", "KC", "temporary", str(in_14_days), 1),
        ("Alex", "Johnson", str(today), "305", "harassment", "Repeated harassment of front desk staff per incident report.", "KC", "temporary", str(expired_7_days_ago), 1),
    ]

    conn.executemany("""
        INSERT INTO incidents
        (first_name, last_name, incident_date, room_number, reason, description, staff_initials, ban_type, expires_on, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, rows)
    
    conn.commit()
    conn.close()
    print("OK: inserted sample rows")

if __name__ == "__main__":
    main()
        