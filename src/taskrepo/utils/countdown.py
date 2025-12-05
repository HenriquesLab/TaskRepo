"""Countdown calculation utilities for due dates.

Centralized logic for calculating countdown text from due dates,
used by both TUI display and README generation.
"""

from datetime import datetime


def calculate_countdown(due_date: datetime, now: datetime | None = None) -> tuple[str, str, str]:
    """Calculate countdown information from a due date.

    This is the centralized countdown calculation logic used by both
    TUI display and README generation.

    Args:
        due_date: The due date to calculate countdown for
        now: Current time (defaults to datetime.now())

    Returns:
        Tuple of (countdown_text, status, urgency_level)
        - countdown_text: Human-readable text like "today", "-2d", "1 week"
        - status: "overdue", "today", "soon", or "future"
        - urgency_level: "critical", "high", "medium", or "low"

    Examples:
        >>> from datetime import datetime, timedelta
        >>> now = datetime(2025, 11, 10, 10, 0, 0)
        >>> # Same day
        >>> calculate_countdown(datetime(2025, 11, 10, 14, 0, 0), now)
        ('today', 'today', 'high')
        >>> # Yesterday
        >>> calculate_countdown(datetime(2025, 11, 9, 10, 0, 0), now)
        ('-1d', 'overdue', 'critical')
        >>> # Tomorrow
        >>> calculate_countdown(datetime(2025, 11, 11, 10, 0, 0), now)
        ('1 week', 'soon', 'medium')
    """
    if now is None:
        now = datetime.now()

    # IMPORTANT: Check if same calendar date FIRST (before calculating time difference)
    # This prevents "today" from showing as overdue when due_date is earlier in the day
    if due_date.date() == now.date():
        # Same day - check time
        diff = due_date - now
        hours = diff.seconds // 3600 if diff.total_seconds() >= 0 else 0
        if hours < 1 and diff.total_seconds() >= 0:
            return "now", "today", "critical"
        else:
            return "today", "today", "high"

    # Calculate difference for non-today dates
    diff = due_date - now
    days = diff.days
    hours = diff.seconds // 3600

    # Handle overdue
    if days < 0:
        abs_days = abs(days)
        if abs_days < 7:
            # Show in days for less than 1 week overdue: -1d, -2d, etc.
            text = f"-{abs_days}d"
        else:
            # Show in weeks: -1w, -2w, etc.
            # Use ceiling division: 7-13 days = -2w, 14-20 days = -3w
            weeks = (abs_days + 6) // 7
            text = f"-{weeks}w"
        return text, "overdue", "critical"

    # Handle future dates (days == 0 case already handled above)
    if days == 0:
        # This branch should never be reached due to date() check above
        # but keep for safety
        if hours < 1:
            return "now", "today", "critical"
        else:
            return "today", "today", "high"

    # Handle future dates less than 7 days - show in days
    if days < 7:
        if days == 1:
            return "tomorrow", "soon", "medium"
        return f"{days}d", "soon", "medium"

    # Handle future dates 7+ days - show in weeks with ceiling division
    if days < 45:
        # Use ceiling division to round up to weeks
        weeks = (days + 6) // 7  # Ceiling: 7-13 days → 1 week, 14-20 days → 2 weeks, etc.
        if weeks == 1:
            return "1 week", "soon", "medium"
        return f"{weeks} weeks", "future", "low"

    # Handle months (45+ days)
    # Use ceiling division to round UP (more conservative)
    months = (days + 29) // 30  # Ceiling division: rounds up
    if months == 1:
        return "1 month", "future", "low"
    return f"{months} months", "future", "low"


def format_countdown_for_display(countdown_text: str, status: str) -> tuple[str, str]:
    """Format countdown for TUI display.

    Args:
        countdown_text: Countdown text from calculate_countdown()
        status: Status from calculate_countdown()

    Returns:
        Tuple of (countdown_text, color_name) for TUI display
    """
    # Map status to colors
    color_map = {
        "overdue": "red",
        "today": "yellow",
        "soon": "yellow",
        "future": "green",
    }
    return countdown_text, color_map.get(status, "green")


def format_countdown_for_readme(countdown_text: str, status: str) -> tuple[str, str]:
    """Format countdown for README generation.

    Args:
        countdown_text: Countdown text from calculate_countdown()
        status: Status from calculate_countdown()

    Returns:
        Tuple of (formatted_text, emoji) for README display
    """
    # Expand abbreviated text for README
    if countdown_text.startswith("-"):
        # Overdue format
        if countdown_text.endswith("d"):
            days = int(countdown_text[1:-1])
            if days == 1:
                text = "overdue by 1 day"
            else:
                text = f"overdue by {days} days"
        elif countdown_text.endswith("w"):
            weeks = int(countdown_text[1:-1])
            if weeks == 1:
                text = "overdue by 1 week"
            else:
                text = f"overdue by {weeks} weeks"
        else:
            text = countdown_text
        return text, "⚠️"
    elif countdown_text == "now":
        return "due now", "⏰"
    elif countdown_text == "today":
        return "today", "⏰"
    else:
        # Future dates - use as-is
        emoji = "⏰" if status == "soon" else "📅"
        return countdown_text, emoji
