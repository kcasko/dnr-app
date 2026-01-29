"""
Add schedule data based on schedule.jpg to test paper view.
"""
import sqlite3
import os
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dnr.db")

def add_sample_schedule():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("ADDING SAMPLE SCHEDULE DATA")
    print("=" * 60)

    # Get current week (Monday - Sunday)
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())

    print(f"\nAdding schedule for week of: {current_week_start.strftime('%B %d, %Y')}")

    # Staff and schedule derived from schedule2.jpg (OCR-assisted + manual verification)
    sample_staff = [
        # Front Desk
        {
            'name': 'Katelee',
            'department': 'FRONT DESK',
            'phone': '616-888-9297',
            'schedule': {
                0: None,                 # Monday
                1: '7am-3pm',             # Tuesday
                2: '9:30am-7pm',          # Wednesday
                3: '7am-3pm',             # Thursday
                4: '7am-3pm',             # Friday
                5: '7am-6pm',             # Saturday
                6: '3pm-8pm',             # Sunday
            }
        },
        {
            'name': 'Amber',
            'department': 'FRONT DESK',
            'phone': '269-251-8354',
            'schedule': {
                0: '7am-6pm',             # Monday
                1: '3pm-11pm',            # Tuesday
                2: '7pm-11pm',            # Wednesday
                3: '3pm-11pm',            # Thursday
                4: '3pm-11pm',            # Friday
                5: None,                  # Saturday
                6: '7am-3pm',             # Sunday
            }
        },
        {
            'name': 'Pam',
            'department': 'FRONT DESK',
            'phone': None,
            'schedule': {
                0: None,                  # Monday
                1: '6pm-11pm',            # Tuesday
                2: '7am-9:30am / 11pm-7am',  # Wednesday
                3: None,                  # Thursday
                4: None,                  # Friday
                5: '6pm-11pm',            # Saturday
                6: None,                  # Sunday
            }
        },
        {
            'name': 'New Hire',
            'department': 'FRONT DESK',
            'phone': None,
            'schedule': {
                0: None,
                1: None,
                2: None,
                3: None,
                4: None,
                5: '6pm-11pm',
                6: None,
            }
        },
        {
            'name': 'Kristi',
            'department': 'FRONT DESK',
            'phone': '269-599-2057',
            'schedule': {
                0: None,                  # Monday
                1: None,                  # Tuesday
                2: None,                  # Wednesday
                3: '11pm-7am',            # Thursday
                4: '11pm-7am',            # Friday
                5: '11pm-7am',            # Saturday
                6: '11pm-7am',            # Sunday
            }
        },
        {
            'name': 'Stacie',
            'department': 'FRONT DESK',
            'phone': '269-716-6216',
            'schedule': {
                0: '11pm-7am',            # Monday
                1: '11pm-7am',            # Tuesday
                2: None,                  # Wednesday
                3: '11pm-7am',            # Thursday
                4: '11pm-7am',            # Friday
                5: '11pm-7am',            # Saturday
                6: '11pm-7am',            # Sunday
            }
        },
        # Housekeeping
        {
            'name': 'Peresh/Poonam',
            'department': 'HOUSEKEEPING',
            'phone': '331-425-9753',
            'schedule': {
                # Live-in housekeepers: no set schedule, shown as ON all week
                0: 'ON',
                1: 'ON',
                2: 'ON',
                3: 'ON',
                4: 'ON',
                5: 'ON',
                6: 'ON',
            }
        },
        {
            'name': 'Stacie',
            'department': 'HOUSEKEEPING',
            'phone': None,
            'schedule': {
                # Live-in housekeepers: no set schedule, shown as ON all week
                0: 'ON',
                1: 'ON',
                2: 'ON',
                3: 'ON',
                4: 'ON',
                5: 'ON',
                6: 'ON',
            }
        },
        {
            'name': 'Stephanie',
            'department': 'HOUSEKEEPING',
            'phone': None,
            'schedule': {
                0: None,
                1: None,
                2: None,
                3: None,
                4: None,
                5: None,
                6: None,
            }
        },
        {
            'name': 'Ellison',
            'department': 'HOUSEKEEPING',
            'phone': '269-910-3171',
            'schedule': {
                0: None,
                1: None,
                2: None,
                3: None,
                4: None,
                5: None,
                6: None,
            }
        },
        # Breakfast
        {
            'name': 'Pam',
            'department': 'BREAKFAST BAR / Laundry',
            'phone': '269-999-4871',
            'schedule': {
                0: None,                  # Monday
                1: '8:45am-12:45pm',      # Tuesday
                2: None,                  # Wednesday
                3: None,                  # Thursday
                4: None,                  # Friday
                5: None,                  # Saturday
                6: None,                  # Sunday
            }
        },
    ]

    # Clear existing schedule for current week
    week_end = current_week_start + timedelta(days=6)
    cursor.execute("""
        DELETE FROM schedules
        WHERE shift_date BETWEEN ? AND ?
    """, (current_week_start.isoformat(), week_end.isoformat()))

    print(f"Cleared existing schedule for this week")

    # Insert sample data
    entries_added = 0
    for staff in sample_staff:
        for day_offset, shift_time in staff['schedule'].items():
            if shift_time:  # Only add if there's a shift
                shift_date = current_week_start + timedelta(days=day_offset)

                cursor.execute("""
                    INSERT INTO schedules
                    (staff_name, shift_date, department, shift_time, phone_number, shift_id, created_at)
                    VALUES (?, ?, ?, ?, ?, NULL, datetime('now','localtime'))
                """, (
                    staff['name'],
                    shift_date.isoformat(),
                    staff['department'],
                    shift_time,
                    staff['phone']
                ))
                entries_added += 1

    conn.commit()

    print(f"\nAdded {entries_added} schedule entries")

    # Show summary
    print("\nSchedule summary by department:")
    cursor.execute("""
        SELECT department, COUNT(*) as count
        FROM schedules
        WHERE shift_date BETWEEN ? AND ?
        GROUP BY department
        ORDER BY department
    """, (current_week_start.isoformat(), week_end.isoformat()))

    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} shifts")

    conn.close()

    print("\n" + "=" * 60)
    print("SAMPLE DATA ADDED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNow you can:")
    print("  1. Start the app: flask run")
    print("  2. Go to Schedule page")
    print("  3. Click 'Paper View' to see the department-grouped layout")
    print("=" * 60)

if __name__ == "__main__":
    add_sample_schedule()
