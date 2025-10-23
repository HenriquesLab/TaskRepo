"""Display constants for task status and priority rendering."""

# Status display mappings
STATUS_COLORS = {
    "pending": "yellow",
    "in_progress": "blue",
    "completed": "green",
    "cancelled": "red",
}

STATUS_EMOJIS = {
    "pending": "⏳",
    "in_progress": "🔄",
    "completed": "✅",
    "cancelled": "❌",
}

# Priority display mappings
PRIORITY_COLORS = {
    "H": "red",
    "M": "yellow",
    "L": "green",
}

PRIORITY_EMOJIS = {
    "H": "🔴",
    "M": "🟡",
    "L": "🟢",
}
