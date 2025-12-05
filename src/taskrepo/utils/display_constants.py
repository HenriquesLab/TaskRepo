"""Display constants for task status and priority rendering."""

# Status display mappings
STATUS_COLORS = {
    "pending": "yellow",
    "in-progress": "blue",
    "completed": "green",
    "cancelled": "red",
}

STATUS_EMOJIS = {
    "pending": "⏳",
    "in-progress": "🔄",
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

# Author/committer display colors (for history view)
# Using highly distinct, vivid colors that work in most terminals
AUTHOR_COLORS = [
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "bright_red",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_magenta",
    "bright_cyan",
    "orange1",
    "purple",
    "violet",
]

# Repository display colors (for history view with multiple repos)
REPO_COLORS = [
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "bright_red",
    "bright_green",
]

# Project display colors
PROJECT_COLORS = [
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "bright_red",
    "bright_green",
]


def get_author_color(author_name: str) -> str:
    """Get a consistent color for an author name using hash-based assignment.

    Args:
        author_name: Author's name (from git commit)

    Returns:
        Rich color name string
    """
    if not author_name:
        return "white"  # Fallback for missing author

    # Hash the author name and map to color index
    color_index = hash(author_name) % len(AUTHOR_COLORS)
    return AUTHOR_COLORS[color_index]


def get_repo_color(repo_name: str) -> str:
    """Get a consistent color for a repository name using hash-based assignment.

    Args:
        repo_name: Repository name

    Returns:
        Rich color name string
    """
    if not repo_name:
        return "white"  # Fallback for missing repo

    # Hash the repo name and map to color index
    color_index = hash(repo_name) % len(REPO_COLORS)
    return REPO_COLORS[color_index]


def get_project_color(project_name: str) -> str:
    """Get a consistent color for a project name using hash-based assignment.

    Args:
        project_name: Project name

    Returns:
        Rich color name string
    """
    if not project_name:
        return "white"  # Fallback for missing project

    # Hash the project name and map to color index
    color_index = hash(project_name) % len(PROJECT_COLORS)
    return PROJECT_COLORS[color_index]
