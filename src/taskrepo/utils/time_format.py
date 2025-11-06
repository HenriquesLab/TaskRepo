"""Time formatting utilities for human-readable relative timestamps."""

import time
from typing import Optional


def format_time_ago(timestamp: Optional[float]) -> str:
    """Format Unix timestamp as relative time.

    Args:
        timestamp: Unix timestamp (seconds since epoch), or None

    Returns:
        Human-readable relative time string

    Examples:
        >>> import time
        >>> format_time_ago(time.time() - 5)
        'just now'
        >>> format_time_ago(time.time() - 90)
        '1m ago'
        >>> format_time_ago(time.time() - 3600)
        '1h ago'
        >>> format_time_ago(time.time() - 86400)
        '1d ago'
        >>> format_time_ago(None)
        'never'
    """
    if timestamp is None:
        return "never"

    elapsed = time.time() - timestamp

    # Handle negative elapsed time (clock skew or future timestamps)
    if elapsed < 0:
        return "just now"

    # Less than 10 seconds
    if elapsed < 10:
        return "just now"

    # Less than 1 minute
    if elapsed < 60:
        seconds = int(elapsed)
        return f"{seconds}s ago"

    # Less than 1 hour
    if elapsed < 3600:
        minutes = int(elapsed / 60)
        return f"{minutes}m ago"

    # Less than 1 day
    if elapsed < 86400:
        hours = int(elapsed / 3600)
        return f"{hours}h ago"

    # 1 day or more
    days = int(elapsed / 86400)
    return f"{days}d ago"


def format_interval(seconds: int) -> str:
    """Format time interval in seconds to human-readable string.

    Args:
        seconds: Time interval in seconds

    Returns:
        Human-readable interval string

    Examples:
        >>> format_interval(30)
        '30s'
        >>> format_interval(90)
        '1m'
        >>> format_interval(300)
        '5m'
        >>> format_interval(3600)
        '1h'
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h"
    else:
        days = seconds // 86400
        return f"{days}d"
