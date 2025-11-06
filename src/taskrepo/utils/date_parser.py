"""Date and duration parsing utilities for TaskRepo."""

import re
from datetime import datetime, timedelta
from typing import Union

from dateutil import parser as dateutil_parser

from taskrepo.utils.duration import parse_duration


def _parse_weekday_reference(input_str: str, today: datetime) -> datetime | None:
    """Parse weekday references like 'next monday', 'this friday', or just 'monday'.

    Args:
        input_str: Input string to parse (already lowercased)
        today: Reference date (datetime at midnight)

    Returns:
        datetime if valid weekday reference, None otherwise

    Examples:
        >>> today = datetime(2025, 11, 5)  # Wednesday
        >>> _parse_weekday_reference("next monday", today)
        datetime(2025, 11, 10, 0, 0)  # Next Monday
        >>> _parse_weekday_reference("monday", today)
        datetime(2025, 11, 10, 0, 0)  # Next Monday
        >>> _parse_weekday_reference("friday", today)
        datetime(2025, 11, 7, 0, 0)  # This Friday
    """
    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    # Check for patterns: "next monday", "this monday", or just "monday"
    parts = input_str.split()

    target_weekday_name = None

    if len(parts) == 1:
        # Just "monday" - means next occurrence
        if parts[0] in weekdays:
            target_weekday_name = parts[0]
    elif len(parts) == 2:
        modifier, weekday = parts
        if weekday in weekdays and modifier in ["next", "this"]:
            target_weekday_name = weekday

    if target_weekday_name is None:
        return None

    target_weekday = weekdays[target_weekday_name]
    current_weekday = today.weekday()

    # Calculate days until target weekday
    # For all cases ("monday", "next monday", "this monday"),
    # find the next occurrence of that weekday
    days_ahead = (target_weekday - current_weekday) % 7
    if days_ahead == 0:
        # If today is the target weekday, use next week
        days_ahead = 7

    return today + timedelta(days=days_ahead)


def parse_date_or_duration(input_str: str) -> tuple[Union[datetime, timedelta], bool]:
    """Parse date or duration string to either datetime or timedelta.

    Supports multiple formats:
    - Durations: "1w", "2d", "3m", "1y" (returns timedelta, False)
    - Day keywords: "today", "tomorrow", "yesterday" (returns datetime, True)
    - Relative keywords: "next week", "next month", "next year" (returns datetime, True)
    - Weekday references: "next monday", "this friday", "monday" (returns datetime, True)
    - ISO dates: "2025-10-30" (returns datetime, True)
    - Natural dates: "Oct 30", "October 30 2025" (returns datetime, True)

    Args:
        input_str: Date or duration string to parse

    Returns:
        Tuple of (parsed_value, is_absolute_date)
        - If is_absolute_date is True, parsed_value is a datetime
        - If is_absolute_date is False, parsed_value is a timedelta

    Raises:
        ValueError: If format cannot be parsed

    Examples:
        >>> parse_date_or_duration("1w")
        (datetime.timedelta(days=7), False)
        >>> parse_date_or_duration("tomorrow")
        (datetime(2025, 10, 24, 0, 0), True)
        >>> parse_date_or_duration("2025-10-30")
        (datetime(2025, 10, 30, 0, 0), True)
    """
    input_str = input_str.strip().lower()

    # Try duration format first (1w, 2d, etc.)
    duration_pattern = r"^(\d+)(d|w|m|y)$"
    if re.match(duration_pattern, input_str):
        try:
            duration = parse_duration(input_str)
            return (duration, False)
        except ValueError:
            pass  # Fall through to other parsers

    # Handle day keywords
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)

    if input_str == "today":
        return (today, True)
    elif input_str == "tomorrow":
        return (today + timedelta(days=1), True)
    elif input_str == "yesterday":
        return (today - timedelta(days=1), True)

    # Handle relative keywords
    if input_str == "next week":
        return (today + timedelta(weeks=1), True)
    elif input_str == "next month":
        # Approximate: add 30 days
        return (today + timedelta(days=30), True)
    elif input_str == "next year":
        # Approximate: add 365 days
        return (today + timedelta(days=365), True)

    # Handle weekday references (next monday, this friday, etc.)
    weekday_result = _parse_weekday_reference(input_str, today)
    if weekday_result is not None:
        return (weekday_result, True)

    # Try ISO date format (YYYY-MM-DD)
    iso_date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    if re.match(iso_date_pattern, input_str):
        try:
            parsed = datetime.strptime(input_str, "%Y-%m-%d")
            return (parsed, True)
        except ValueError as e:
            raise ValueError(f"Invalid ISO date format: {input_str}") from e

    # Try natural language date parsing with dateutil
    try:
        # Use dateutil parser for flexible date parsing
        # Note: this can be quite permissive, so we put it last
        parsed = dateutil_parser.parse(input_str, default=today)

        # Normalize to midnight (remove time component)
        parsed = datetime(parsed.year, parsed.month, parsed.day)

        return (parsed, True)
    except (ValueError, dateutil_parser.ParserError) as e:
        # If all parsers fail, raise a helpful error
        raise ValueError(
            f"Invalid date or duration format: '{input_str}'. "
            "Supported formats:\n"
            "  - Durations: 1w, 2d, 3m, 1y\n"
            "  - Keywords: today, tomorrow, yesterday, next week, next month, next year\n"
            "  - Weekdays: next monday, this friday, monday\n"
            "  - ISO dates: 2025-10-30\n"
            "  - Natural dates: Oct 30, October 30 2025"
        ) from e


def parse_date_with_error_handling(date_str: str, field_name: str = "date") -> datetime:
    """Parse date string with user-friendly error handling for CLI commands.

    This function wraps parse_date_or_duration() to provide consistent error
    messages across all CLI commands. It only supports absolute dates (not durations).

    Args:
        date_str: Date string to parse
        field_name: Name of field for error messages (e.g., "due date", "date")

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If the date string cannot be parsed, with a user-friendly message

    Examples:
        >>> parse_date_with_error_handling("tomorrow")
        datetime(2025, 10, 24, 0, 0)
        >>> parse_date_with_error_handling("2025-12-31")
        datetime(2025, 12, 31, 0, 0)
        >>> parse_date_with_error_handling("invalid")
        ValueError: Could not parse date 'invalid'
    """
    try:
        parsed_value, is_absolute = parse_date_or_duration(date_str)

        if not is_absolute:
            # If it's a duration (timedelta), reject it for date fields
            raise ValueError(
                f"Expected a date, got a duration: '{date_str}'. "
                f"Use absolute dates like 'tomorrow', '2025-12-31', or 'Oct 30'"
            )

        return parsed_value
    except ValueError as e:
        # Re-raise with a more concise error message for CLI
        error_msg = (
            f"Could not parse {field_name}: '{date_str}'\n"
            f"Supported formats:\n"
            f"  - Keywords: today, tomorrow, yesterday, next week, next month, next year\n"
            f"  - Weekdays: next monday, this friday, monday\n"
            f"  - ISO dates: 2025-12-31\n"
            f"  - Natural dates: Oct 30, October 30 2025, Dec 1"
        )
        raise ValueError(error_msg) from e


def format_date_input(input_str: str, parsed_value: Union[datetime, timedelta], is_absolute: bool) -> str:
    """Format date or duration input for display.

    Args:
        input_str: Original input string
        parsed_value: Parsed datetime or timedelta
        is_absolute: Whether this is an absolute date

    Returns:
        Human-readable formatted string

    Examples:
        >>> format_date_input("1w", timedelta(days=7), False)
        '+1 week'
        >>> format_date_input("tomorrow", datetime(2025, 10, 24), True)
        'tomorrow (2025-10-24)'
        >>> format_date_input("2025-10-30", datetime(2025, 10, 30), True)
        '2025-10-30'
    """
    if is_absolute:
        # For absolute dates, show the input and the parsed date
        assert isinstance(parsed_value, datetime)
        date_str = parsed_value.strftime("%Y-%m-%d")

        # If input is a keyword or weekday reference, show both input and date
        keywords = ["today", "tomorrow", "yesterday", "next week", "next month", "next year"]
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        input_lower = input_str.lower().strip()
        parts = input_lower.split()

        # Check if it's a keyword or weekday reference
        is_keyword = input_lower in keywords
        is_weekday_ref = (len(parts) == 1 and parts[0] in weekdays) or (
            len(parts) == 2 and parts[0] in ["next", "this"] and parts[1] in weekdays
        )

        if is_keyword or is_weekday_ref:
            return f"{input_str} ({date_str})"
        else:
            # For ISO dates or natural dates, just show the date
            return date_str
    else:
        # For durations, use the existing format_duration function
        from taskrepo.utils.duration import format_duration

        return format_duration(input_str)
