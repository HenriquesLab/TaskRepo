"""Duration parsing utilities for TaskRepo."""

import re
from datetime import timedelta


def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '1w', '2d', '3m', '1y' to timedelta.

    Supported units:
    - d: days
    - w: weeks (7 days)
    - m: months (30 days)
    - y: years (365 days)

    Args:
        duration_str: Duration string (e.g., "1w", "2d", "3m", "1y")

    Returns:
        timedelta object

    Raises:
        ValueError: If format is invalid

    Examples:
        >>> parse_duration("1w")
        datetime.timedelta(days=7)
        >>> parse_duration("2d")
        datetime.timedelta(days=2)
        >>> parse_duration("3m")
        datetime.timedelta(days=90)
    """
    # Match pattern: number followed by unit (d/w/m/y)
    pattern = r"^(\d+)(d|w|m|y)$"
    match = re.match(pattern, duration_str.lower().strip())

    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Use format like '1w' (weeks), '2d' (days), '3m' (months), '1y' (years)"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    # Convert to days based on unit
    if unit == "d":
        days = amount
    elif unit == "w":
        days = amount * 7
    elif unit == "m":
        days = amount * 30
    elif unit == "y":
        days = amount * 365
    else:
        raise ValueError(f"Unknown time unit: {unit}")

    return timedelta(days=days)


def format_duration(duration_str: str) -> str:
    """Format duration string for display.

    Args:
        duration_str: Duration string (e.g., "1w", "2d")

    Returns:
        Human-readable duration (e.g., "+1 week", "+2 days")

    Examples:
        >>> format_duration("1w")
        '+1 week'
        >>> format_duration("2d")
        '+2 days'
        >>> format_duration("3m")
        '+3 months'
    """
    pattern = r"^(\d+)(d|w|m|y)$"
    match = re.match(pattern, duration_str.lower().strip())

    if not match:
        return duration_str

    amount = int(match.group(1))
    unit = match.group(2)

    # Map units to display names
    unit_names = {
        "d": "day" if amount == 1 else "days",
        "w": "week" if amount == 1 else "weeks",
        "m": "month" if amount == 1 else "months",
        "y": "year" if amount == 1 else "years",
    }

    unit_name = unit_names.get(unit, unit)
    return f"+{amount} {unit_name}"
