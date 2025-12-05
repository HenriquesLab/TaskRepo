"""Tests for countdown calculation utilities."""

from datetime import datetime

from taskrepo.utils.countdown import (
    calculate_countdown,
    format_countdown_for_display,
    format_countdown_for_readme,
)


def test_countdown_today_same_time():
    """Test countdown shows 'today' when due date is same day and time."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 10, 10, 0, 0)
    text, status, urgency = calculate_countdown(due, now)
    assert text == "now"
    assert status == "today"
    assert urgency == "critical"


def test_countdown_today_earlier_in_day():
    """Test countdown shows 'today' when due date is earlier on same day (the bug we fixed)."""
    now = datetime(2025, 11, 10, 14, 30, 0)  # 2:30 PM
    due = datetime(2025, 11, 10, 0, 0, 0)  # Midnight (earlier)
    text, status, urgency = calculate_countdown(due, now)
    # Should show "today" not "-1d"
    assert text == "today"
    assert status == "today"
    assert urgency == "high"


def test_countdown_today_later_in_day():
    """Test countdown shows 'today' when due date is later on same day."""
    now = datetime(2025, 11, 10, 8, 0, 0)  # 8 AM
    due = datetime(2025, 11, 10, 23, 59, 0)  # 11:59 PM (later)
    text, status, urgency = calculate_countdown(due, now)
    assert text == "today"
    assert status == "today"
    assert urgency == "high"


def test_countdown_yesterday():
    """Test countdown shows negative days for yesterday."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 9, 10, 0, 0)  # Yesterday
    text, status, urgency = calculate_countdown(due, now)
    assert text == "-1d"
    assert status == "overdue"
    assert urgency == "critical"


def test_countdown_overdue_days():
    """Test countdown shows negative days for overdue tasks (less than 1 week)."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 5, 10, 0, 0)  # 5 days ago
    text, status, urgency = calculate_countdown(due, now)
    assert text == "-5d"
    assert status == "overdue"
    assert urgency == "critical"


def test_countdown_overdue_weeks():
    """Test countdown shows negative weeks for overdue tasks (1+ week)."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 1, 10, 0, 0)  # 9 days ago
    text, status, urgency = calculate_countdown(due, now)
    assert text == "-2w"  # Ceiling: 7-13 days = 2 weeks
    assert status == "overdue"
    assert urgency == "critical"


def test_countdown_tomorrow():
    """Test countdown shows 'tomorrow' for next day."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 11, 10, 0, 0)  # Tomorrow
    text, status, urgency = calculate_countdown(due, now)
    assert text == "tomorrow"
    assert status == "soon"
    assert urgency == "medium"


def test_countdown_days():
    """Test countdown shows days for 2-6 days away."""
    now = datetime(2025, 11, 10, 10, 0, 0)

    # 2 days
    due = datetime(2025, 11, 12, 10, 0, 0)
    text, status, urgency = calculate_countdown(due, now)
    assert text == "2d"
    assert status == "soon"
    assert urgency == "medium"

    # 3 days
    due = datetime(2025, 11, 13, 10, 0, 0)
    text, status, urgency = calculate_countdown(due, now)
    assert text == "3d"
    assert status == "soon"
    assert urgency == "medium"

    # 6 days
    due = datetime(2025, 11, 16, 10, 0, 0)
    text, status, urgency = calculate_countdown(due, now)
    assert text == "6d"
    assert status == "soon"
    assert urgency == "medium"


def test_countdown_one_week():
    """Test countdown shows '1 week' for exactly 7 days."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 17, 10, 0, 0)  # Exactly 7 days
    text, status, urgency = calculate_countdown(due, now)
    assert text == "1 week"
    assert status == "soon"
    assert urgency == "medium"


def test_countdown_next_week():
    """Test countdown shows weeks for dates 1-6 weeks away."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 11, 20, 10, 0, 0)  # 10 days away
    text, status, urgency = calculate_countdown(due, now)
    assert text == "2 weeks"  # Ceiling: 7-13 days = 2 weeks
    assert status == "future"
    assert urgency == "low"


def test_countdown_months():
    """Test countdown shows months for dates 45+ days away."""
    now = datetime(2025, 11, 10, 10, 0, 0)
    due = datetime(2025, 12, 25, 10, 0, 0)  # 45 days away
    text, status, urgency = calculate_countdown(due, now)
    assert text == "2 months"  # Ceiling: 45 days = 2 months
    assert status == "future"
    assert urgency == "low"


def test_format_countdown_for_display():
    """Test formatting countdown for TUI display."""
    # Overdue
    text, color = format_countdown_for_display("-2d", "overdue")
    assert text == "-2d"
    assert color == "red"

    # Today
    text, color = format_countdown_for_display("today", "today")
    assert text == "today"
    assert color == "yellow"

    # Soon
    text, color = format_countdown_for_display("1 week", "soon")
    assert text == "1 week"
    assert color == "yellow"

    # Future
    text, color = format_countdown_for_display("2 months", "future")
    assert text == "2 months"
    assert color == "green"


def test_format_countdown_for_readme():
    """Test formatting countdown for README generation."""
    # Overdue days
    text, emoji = format_countdown_for_readme("-2d", "overdue")
    assert text == "overdue by 2 days"
    assert emoji == "⚠️"

    # Overdue single day
    text, emoji = format_countdown_for_readme("-1d", "overdue")
    assert text == "overdue by 1 day"
    assert emoji == "⚠️"

    # Overdue weeks
    text, emoji = format_countdown_for_readme("-2w", "overdue")
    assert text == "overdue by 2 weeks"
    assert emoji == "⚠️"

    # Now
    text, emoji = format_countdown_for_readme("now", "today")
    assert text == "due now"
    assert emoji == "⏰"

    # Today
    text, emoji = format_countdown_for_readme("today", "today")
    assert text == "today"
    assert emoji == "⏰"

    # Soon
    text, emoji = format_countdown_for_readme("1 week", "soon")
    assert text == "1 week"
    assert emoji == "⏰"

    # Future
    text, emoji = format_countdown_for_readme("2 months", "future")
    assert text == "2 months"
    assert emoji == "📅"


def test_countdown_midnight_boundary():
    """Test countdown handles midnight boundary correctly."""
    # 1 second before midnight
    now = datetime(2025, 11, 10, 23, 59, 59)
    due = datetime(2025, 11, 10, 0, 0, 0)  # Same day, midnight
    text, status, urgency = calculate_countdown(due, now)
    assert text == "today"
    assert status == "today"

    # 1 second after midnight (next day)
    now = datetime(2025, 11, 11, 0, 0, 1)
    due = datetime(2025, 11, 10, 23, 59, 59)  # Previous day
    text, status, urgency = calculate_countdown(due, now)
    assert text == "-1d"
    assert status == "overdue"
