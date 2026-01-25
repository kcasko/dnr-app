"""
Shift Utilities for DNR App.

Handles shift definitions, time calculations, and locking logic.
"""
from datetime import datetime, time, timedelta
import zoneinfo

# Define Timezone
TIMEZONE = zoneinfo.ZoneInfo("America/New_York")

# Shift Definitions
# Shift 1: 07:00 - 15:00
# Shift 2: 15:00 - 23:00
# Shift 3: 23:00 - 07:00 (Crosses midnight)

SHIFT_1_START = time(7, 0)
SHIFT_2_START = time(15, 0)
SHIFT_3_START = time(23, 0)

def get_current_time():
    """Get current time in app timezone."""
    return datetime.now(TIMEZONE)

def get_current_shift_id(current_dt=None):
    """
    Determine the current shift ID based on time.
    
    Args:
        current_dt (datetime, optional): Time to check. Defaults to now.
        
    Returns:
        int: 1, 2, or 3
    """
    if current_dt is None:
        current_dt = get_current_time()
        
    t = current_dt.time()
    
    if SHIFT_1_START <= t < SHIFT_2_START:
        return 1
    elif SHIFT_2_START <= t < SHIFT_3_START:
        return 2
    else:
        # Shift 3 covers 23:00 to 07:00
        return 3

def get_shift_date(current_dt=None):
    """
    Get the 'logical' date of the shift.
    
    For Shift 1 and 2, it's the actual date.
    For Shift 3 (23:00-07:00), it belongs to the date where the shift STARTED.
    i.e. 01:00 AM on Jan 2nd is part of the Jan 1st Shift 3.
    
    Args:
        current_dt (datetime, optional): Time to check. Defaults to now.
        
    Returns:
        date: The logical date of the shift.
    """
    if current_dt is None:
        current_dt = get_current_time()
        
    t = current_dt.time()
    d = current_dt.date()
    
    # If it's after midnight but before start of Shift 1 (07:00), 
    # it belongs to the previous day's Shift 3.
    if t < SHIFT_1_START:
        return d - timedelta(days=1)
    
    return d

def is_shift_active(shift_id, shift_date, current_dt=None):
    """
    Check if a specific shift is currently active.
    
    Args:
        shift_id (int): Shift ID to check (1, 2, or 3)
        shift_date (date|str): Logical date of the shift.
        current_dt (datetime, optional): Time to check against. Defaults to now.
        
    Returns:
        bool: True if the shift is currently active.
    """
    if current_dt is None:
        current_dt = get_current_time()
        
    # Parse shift_date if it's a string
    if isinstance(shift_date, str):
        try:
            # Handle standard ISO format YYYY-MM-DD
            if "T" in shift_date:
                shift_date = datetime.fromisoformat(shift_date).date()
            else:
                shift_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
        except ValueError:
            # If parsing fails or complex format, try to infer from timestamp
            # This fallback is riskier, better to pass clean dates.
            pass

    current_shift = get_current_shift_id(current_dt)
    current_shift_date = get_shift_date(current_dt)
    
    return (shift_id == current_shift) and (shift_date == current_shift_date)
