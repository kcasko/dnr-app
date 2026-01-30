"""
Diagnose schedule data for paper view.
"""
import sqlite3
import os
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def diagnose_schedule_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("DIAGNOSING SCHEDULE DATA FOR PAPER VIEW")
    print("=" * 60)

    # 1. Check if migration was applied
    print("\n[1/5] Checking if paper schedule migration was applied...")
    cursor.execute("PRAGMA table_info(schedules)")
    columns = [col[1] for col in cursor.fetchall()]

    print(f"  Columns in schedules table: {columns}")

    has_department = 'department' in columns
    has_shift_time = 'shift_time' in columns
    has_phone_number = 'phone_number' in columns

    print(f"  - Has 'department' column: {has_department}")
    print(f"  - Has 'shift_time' column: {has_shift_time}")
    print(f"  - Has 'phone_number' column: {has_phone_number}")

    if not (has_department and has_shift_time and has_phone_number):
        print("\n  ⚠ WARNING: Migration not applied! Run: python migrate_paper_schedule.py")
        conn.close()
        return

    # 2. Check if there's any schedule data
    print("\n[2/5] Checking for schedule data...")
    cursor.execute("SELECT COUNT(*) as count FROM schedules")
    total_count = cursor.fetchone()['count']
    print(f"  Total schedule entries: {total_count}")

    if total_count == 0:
        print("  ℹ No schedule data exists. Paper view will be empty.")
        print("  Add some schedule entries to test paper view.")
        conn.close()
        return

    # 3. Check current week's schedule
    print("\n[3/5] Checking current week's schedule...")
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    week_dates = [current_week_start + timedelta(days=i) for i in range(7)]
    start_str = week_dates[0].isoformat()
    end_str = week_dates[-1].isoformat()

    cursor.execute("""
        SELECT * FROM schedules
        WHERE shift_date BETWEEN ? AND ?
        ORDER BY shift_date, department, staff_name
    """, (start_str, end_str))

    current_week_schedules = cursor.fetchall()
    print(f"  Current week ({start_str} to {end_str}): {len(current_week_schedules)} entries")

    if len(current_week_schedules) == 0:
        print("  ℹ No schedule for current week. Try navigating to a different week or add entries.")

    # 4. Show sample data
    print("\n[4/5] Sample schedule entries...")
    cursor.execute("SELECT * FROM schedules LIMIT 5")
    sample_entries = cursor.fetchall()

    for i, entry in enumerate(sample_entries, 1):
        print(f"\n  Entry {i}:")
        print(f"    Staff: {entry['staff_name']}")
        print(f"    Date: {entry['shift_date']}")
        print(f"    Department: {entry['department']}")
        print(f"    Shift Time: {entry['shift_time']}")
        print(f"    Shift ID: {entry['shift_id']}")
        print(f"    Phone: {entry['phone_number']}")

    # 5. Simulate paper_schedule_data preparation
    print("\n[5/5] Simulating paper_schedule_data preparation for current week...")

    paper_schedule_data = {}

    for s in current_week_schedules:
        name = s['staff_name']
        department = s['department'] or 'FRONT DESK'
        shift_time = s['shift_time'] or ''
        phone = s['phone_number']
        shift_date = s['shift_date']

        if department not in paper_schedule_data:
            paper_schedule_data[department] = {}

        if name not in paper_schedule_data[department]:
            paper_schedule_data[department][name] = {
                'phone': phone,
                'days': {}
            }

        paper_schedule_data[department][name]['days'][shift_date] = shift_time

    print(f"  Departments in paper_schedule_data: {list(paper_schedule_data.keys())}")

    for dept, staff_dict in paper_schedule_data.items():
        print(f"\n  Department: {dept}")
        print(f"    Staff count: {len(staff_dict)}")
        for staff_name, staff_info in list(staff_dict.items())[:3]:  # Show first 3
            print(f"      - {staff_name}: {len(staff_info['days'])} days scheduled")
            print(f"        Days: {list(staff_info['days'].keys())}")

    if not paper_schedule_data:
        print("\n  ⚠ paper_schedule_data is EMPTY!")
        print("  This explains why paper view shows nothing.")
        print("\n  Possible reasons:")
        print("    1. No schedule entries for current week")
        print("    2. Migration didn't populate department/shift_time correctly")
        print("\n  To fix:")
        print("    - Add schedule entries via the Schedule page")
        print("    - Or navigate to a week that has schedule data")
    else:
        print("\n  ✓ paper_schedule_data looks good!")
        print("  Paper view should display correctly.")

    conn.close()

    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    diagnose_schedule_data()
