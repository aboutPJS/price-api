"""
Time utility functions for calculating time differences.
Supports Copenhagen timezone and different output formats.
"""

from datetime import datetime, timedelta
from typing import Union
import pytz


def calculate_time_until(start_time: datetime, format_type: str = "hours") -> Union[str, int]:
    """
    Calculate time remaining until a future datetime.
    
    Args:
        start_time: Target datetime (assumed to be timezone-naive, representing Copenhagen time)
        format_type: Output format - "hours" for "HH:MM" string, "minutes" for integer minutes
    
    Returns:
        String in "HH:MM" format if format_type="hours", integer minutes if format_type="minutes"
    
    Raises:
        ValueError: If start_time is in the past or format_type is invalid
    """
    # Copenhagen timezone
    copenhagen_tz = pytz.timezone('Europe/Copenhagen')
    
    # Get current time in Copenhagen
    now_copenhagen = datetime.now(copenhagen_tz)
    
    # Make start_time timezone-aware (assume it's in Copenhagen time)
    if start_time.tzinfo is None:
        start_time_copenhagen = copenhagen_tz.localize(start_time)
    else:
        start_time_copenhagen = start_time.astimezone(copenhagen_tz)
    
    # Calculate the difference
    time_diff = start_time_copenhagen - now_copenhagen
    
    # Check if start_time is in the past
    if time_diff.total_seconds() <= 0:
        if format_type == "hours":
            return "00:00"
        elif format_type == "minutes":
            return 0
        else:
            raise ValueError("format_type must be 'hours' or 'minutes'")
    
    # Convert to total minutes
    total_minutes = int(time_diff.total_seconds() / 60)
    
    if format_type == "hours":
        # Format as HH:MM
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
    elif format_type == "minutes":
        # Return as integer minutes
        return total_minutes
    else:
        raise ValueError("format_type must be 'hours' or 'minutes'")


def get_next_complete_hour(reference_time: datetime = None) -> datetime:
    """
    Get the next complete hour after the reference time in Copenhagen timezone.
    
    Args:
        reference_time: Reference datetime. If None, uses current Copenhagen time.
    
    Returns:
        Datetime rounded up to the next complete hour (minutes and seconds set to 0)
        Returns timezone-naive datetime in Copenhagen local time for database compatibility.
        
    Examples (Copenhagen time):
        - 12:00 -> 13:00 (if it's exactly 12:00, next complete hour is 13:00)
        - 12:05 -> 13:00 (round up to next hour)
        - 12:59 -> 13:00 (round up to next hour)
    """
    copenhagen_tz = pytz.timezone('Europe/Copenhagen')
    
    if reference_time is None:
        # Get current time in Copenhagen timezone
        copenhagen_now = datetime.now(copenhagen_tz)
    else:
        # Convert reference time to Copenhagen timezone if it has timezone info
        if reference_time.tzinfo is None:
            # Assume it's already Copenhagen time if timezone-naive
            copenhagen_now = copenhagen_tz.localize(reference_time)
        else:
            copenhagen_now = reference_time.astimezone(copenhagen_tz)
    
    # Always round up to the next hour
    next_hour = copenhagen_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    # Return timezone-naive datetime for database compatibility (database assumes Copenhagen time)
    return next_hour.replace(tzinfo=None)
