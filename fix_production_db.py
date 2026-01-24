
import sqlite3
import os
from datetime import date, timedelta

# Ensure we are working with the absolute path to the DB in the current directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def main():
    print(f"Checking database at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("ERROR: Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- Fixing housekeeping_service_dates table ---")
    
    # 1. Drop the table if it exists to ensure a clean slate
    print("Dropping 'housekeeping_service_dates' table...")
    cursor.execute("DROP TABLE IF EXISTS housekeeping_service_dates")
    
    # 2. Recreate the table with the correct schema
    print("Recreating 'housekeeping_service_dates' table...")
    cursor.execute("""
        CREATE TABLE housekeeping_service_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            housekeeping_request_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (housekeeping_request_id) REFERENCES housekeeping_requests(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_housekeeping_service_dates_request
        ON housekeeping_service_dates(housekeeping_request_id)
    """)
    cursor.execute("""
        CREATE INDEX idx_housekeeping_service_dates_date
        ON housekeeping_service_dates(service_date, is_active)
    """)

    # 3. Regenerate data from housekeeping_requests
    print("Regenerating service dates from existing requests...")
    
    cursor.execute("SELECT id, start_date, end_date, frequency, frequency_days FROM housekeeping_requests WHERE archived_at IS NULL")
    requests = cursor.fetchall()
    
    total_dates = 0
    for req in requests:
        req_id = req['id']
        start_str = req['start_date']
        end_str = req['end_date']
        freq = req['frequency']
        freq_days = req['frequency_days']
        
        if freq == 'none' or not start_str or not end_str:
            continue

        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except ValueError:
            print(f"Warning: Invalid dates for request {req_id}, skipping.")
            continue
            
        service_dates = []
        if freq == 'daily':
            curr = start_date
            while curr < end_date:
                service_dates.append(curr.isoformat())
                curr += timedelta(days=1)
        elif freq == 'every_3rd_day':
            curr = start_date
            while curr < end_date:
                service_dates.append(curr.isoformat())
                curr += timedelta(days=3)
        elif freq == 'custom' and freq_days:
            curr = start_date
            while curr < end_date:
                service_dates.append(curr.isoformat())
                curr += timedelta(days=int(freq_days))
        
        for sd in service_dates:
            cursor.execute("""
                INSERT INTO housekeeping_service_dates (housekeeping_request_id, service_date, is_active)
                VALUES (?, ?, 1)
            """, (req_id, sd))
            total_dates += 1

    conn.commit()
    print(f"Successfully guaranteed schema and generated {total_dates} service dates.")
    
    # Verify columns just in case
    cursor.execute("PRAGMA table_info(housekeeping_service_dates)")
    columns = [row['name'] for row in cursor.fetchall()]
    print(f"Table columns verified: {columns}")
    
    conn.close()

if __name__ == "__main__":
    main()
