import pytest
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
import sys
import os

# Add parent directory to path to import shift_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shift_utils

TIMEZONE = ZoneInfo("America/New_York")

class TestShiftUtils:
    
    def test_get_current_shift_id_morning(self):
        # 07:00 - 15:00 is Shift 1
        dt = datetime(2025, 1, 1, 10, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 1
        
        # Boundary start
        dt = datetime(2025, 1, 1, 7, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 1
        
    def test_get_current_shift_id_evening(self):
        # 15:00 - 23:00 is Shift 2
        dt = datetime(2025, 1, 1, 16, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 2
        
        # Boundary start
        dt = datetime(2025, 1, 1, 15, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 2

    def test_get_current_shift_id_night(self):
        # 23:00 - 07:00 (next day) is Shift 3
        
        # Before midnight
        dt = datetime(2025, 1, 1, 23, 30, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 3
        
        # After midnight
        dt = datetime(2025, 1, 2, 2, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 3
        
        # Boundary start
        dt = datetime(2025, 1, 1, 23, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_current_shift_id(dt) == 3

    def test_get_shift_date(self):
        # Standard day
        dt = datetime(2025, 1, 1, 10, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_shift_date(dt) == date(2025, 1, 1)
        
        # Late night (before midnight) -> Same day
        dt = datetime(2025, 1, 1, 23, 30, tzinfo=TIMEZONE)
        assert shift_utils.get_shift_date(dt) == date(2025, 1, 1)
        
        # Early morning (after midnight) -> Previous day (logical shift date)
        dt = datetime(2025, 1, 2, 2, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_shift_date(dt) == date(2025, 1, 1)
        
        # Morning start (07:00) -> Current day
        dt = datetime(2025, 1, 2, 7, 0, tzinfo=TIMEZONE)
        assert shift_utils.get_shift_date(dt) == date(2025, 1, 2)

    def test_is_shift_active(self):
        # Current time is Noon on Jan 1st (Shift 1)
        current_dt = datetime(2025, 1, 1, 12, 0, tzinfo=TIMEZONE)
        
        # Shift 1, Jan 1 should be active
        assert shift_utils.is_shift_active(1, date(2025, 1, 1), current_dt)
        
        # Shift 2, Jan 1 should NOT be active
        assert not shift_utils.is_shift_active(2, date(2025, 1, 1), current_dt)
        
        # Shift 1, Jan 2 should NOT be active
        assert not shift_utils.is_shift_active(1, date(2025, 1, 2), current_dt)

    def test_is_shift_active_night_rollover(self):
        # Current time is 2AM on Jan 2nd (still Shift 3 of Jan 1st)
        current_dt = datetime(2025, 1, 2, 2, 0, tzinfo=TIMEZONE)
        
        # Shift 3, Jan 1 should be active
        assert shift_utils.is_shift_active(3, date(2025, 1, 1), current_dt)
        
        # Shift 3, Jan 2 should NOT be active
        assert not shift_utils.is_shift_active(3, date(2025, 1, 2), current_dt)
        
        # Shift 1, Jan 2 should NOT be active yet
        assert not shift_utils.is_shift_active(1, date(2025, 1, 2), current_dt)

if __name__ == "__main__":
    # Create instance and run tests manually
    test = TestShiftUtils()
    try:
        test.test_get_current_shift_id_morning()
        print("PASS: test_get_current_shift_id_morning")
        test.test_get_current_shift_id_evening()
        print("PASS: test_get_current_shift_id_evening")
        test.test_get_current_shift_id_night()
        print("PASS: test_get_current_shift_id_night")
        test.test_get_shift_date()
        print("PASS: test_get_shift_date")
        test.test_is_shift_active()
        print("PASS: test_is_shift_active")
        test.test_is_shift_active_night_rollover()
        print("PASS: test_is_shift_active_night_rollover")
        print("\nALL TESTS PASSED")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
