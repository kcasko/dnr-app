"""
Add schedule data based on user-provided text to test paper view.
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
    print("ADDING SAMPLE SCHEDULE DATA (USER VERIFIED)")
    print("=" * 60)

    # Target specific week per user request: Feb 2, 2026
    current_week_start = date(2026, 2, 2)

    print(f"\nAdding schedule for week of: {current_week_start.strftime('%B %d, %Y')}")

    # Data Source: User provided text on 2026-01-29
    sample_staff = [
        # --- FRONT DESK ---
        {
            'name': 'Amber',
            'department': 'FRONT DESK',
            'phone': '269-251-8354',
            'schedule': {
                0: '7am-6pm',         # Monday
                1: '3pm-11pm',        # Tuesday
                2: '7am-11pm',        # Wednesday (clarified by user)
                3: '3pm-11pm',        # Thursday
                4: '3pm-11pm',        # Friday
                5: None,              # Saturday: OFF
                6: '7am-3pm',         # Sunday
            }
        },
        {
            'name': 'Katelee',
            'department': 'FRONT DESK',
            'phone': '616-888-9297',
            'schedule': {
                0: '7am-3pm',         # Monday
                1: '9:30am-7pm',      # Tuesday
                2: '7am-3pm',         # Wednesday
                3: '7am-3pm',         # Thursday
                4: '7am-3pm',         # Friday
                5: '7am-6pm',         # Saturday
                6: '3pm-8pm',         # Sunday
            }
        },
        {
            'name': 'Pam',
            'department': 'FRONT DESK',
            'phone': '269-999-4871', # Using phone from previous script if available
            'schedule': {
                0: '6pm-11pm',        # Monday
                1: None,              # Tuesday: OFF for Front Desk (has Breakfast shift)
                2: ['7am-9:30am', '11pm-7am'], # Wednesday (Double shift)
                3: None,              # Thursday: OFF
                4: '6pm-11pm',        # Friday
                5: None,              # Saturday: OFF
                6: None,              # Sunday: OFF
            }
        },
        {
            'name': 'Pam',
            'department': 'BREAKFAST ATTENDANT',
            'phone': '269-999-4871',
            'schedule': {
                0: None,
                1: '8:45am-12:45pm',  # Tuesday breakfast shift
                2: None,
                3: None,
                4: None,
                5: None,
                6: None,
            }
        },
        {
            'name': 'Stacie',
            'department': 'FRONT DESK',
            'phone': '269-716-6216',
            'schedule': {
                0: '11pm-7am',        # Monday
                1: '11pm-7am',        # Tuesday
                2: None,              # Wed: OFF
                3: None,              # Thu: OFF
                4: None,              # Fri: OFF
                5: None,              # Sat: OFF
                6: None,              # Sun: OFF
            }
        },
        {
            'name': 'Kristi',
            'department': 'FRONT DESK',
            'phone': '269-599-2057',
            'schedule': {
                0: None,              # Mon: OFF
                1: None,              # Tue: OFF
                2: '11pm-7am',        # Wednesday
                3: '11pm-7am',        # Thursday
                4: '11pm-7am',        # Friday
                5: '11pm-7am',        # Saturday
                6: '11pm-7am',        # Sunday
            }
        },
        
        # --- HOUSEKEEPING (Preserved) ---
        {
            'name': 'Peresh/Poonam',
            'department': 'HOUSEKEEPING',
            'phone': '331-425-9753',
            'schedule': {
                0: 'ON', 1: 'ON', 2: 'ON', 3: 'ON', 4: 'ON', 5: 'ON', 6: 'ON'
            }
        },
        # (Stephanie and Ellison had empty schedules in previous version, keeping them implies check-in/out logic or ad-hoc)
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
            if not shift_time:
                continue

            # Allow multiple shifts per day (list) or single string
            shift_values = shift_time if isinstance(shift_time, list) else [shift_time]

            for shift_val in shift_values:
                if not shift_val:
                    continue

                shift_date = current_week_start + timedelta(days=day_offset)

                cursor.execute("""
                    INSERT INTO schedules
                    (staff_name, shift_date, department, shift_time, phone_number, shift_id, created_at)
                    VALUES (?, ?, ?, ?, ?, NULL, datetime('now','localtime'))
                """, (
                    staff['name'],
                    shift_date.isoformat(),
                    staff['department'],
                    shift_val,
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
    print("SAMPLE DATA UPDATED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    add_sample_schedule()
