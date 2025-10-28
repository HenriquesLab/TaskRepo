"""Banner display utility for TaskRepo CLI."""

from rich.console import Console
from rich.text import Text

from taskrepo.__version__ import __version__


def display_banner() -> None:
    """Display the TaskRepo ASCII banner with gradient colors."""
    console = Console()

    # ASCII art for "TaskRepo" in detailed block style
    lines = [
        "  dBBBBBBP dBBBBBb  .dBBBBP   dBP dBP dBBBBBb    dBBBP dBBBBBb  dBBBBP",
        "                BB  BP       d8P.dBP      dBP              dB' dBP.BP ",
        "   dBP      dBP BB  `BBBBb  dBBBBP    dBBBBK'  dBBP    dBBBP' dBP.BP  ",
        "  dBP      dBP  BB     dBP dBP BB    dBP  BB  dBP     dBP    dBP.BP   ",
        " dBP      dBBBBBBBdBBBBP' dBP dBP   dBP  dB' dBBBBP  dBP    dBBBBP    ",
        "                                                                      ",
    ]

    # Create left-to-right gradient: green -> yellow -> red
    banner = Text()
    for line in lines:
        # Split line into thirds for gradient effect
        line_len = len(line)
        third = line_len // 3

        # Left part: green
        banner.append(line[:third], style="bold green")
        # Middle part: yellow
        banner.append(line[third : third * 2], style="bold yellow")
        # Right part: red
        banner.append(line[third * 2 :], style="bold red")
        banner.append("\n")

    # Add version info below
    banner.append(f"TaskRepo v{__version__}\n", style="dim")

    console.print(banner)
