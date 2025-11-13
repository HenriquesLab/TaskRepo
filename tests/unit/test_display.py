"""Tests for display utilities."""

from taskrepo.tui.display import display_width, pad_to_width, truncate_to_width


def test_display_width_basic_text():
    """Test display width with basic ASCII text."""
    assert display_width("hello") == 5
    assert display_width("test") == 4
    assert display_width("") == 0


def test_display_width_emoji():
    """Test display width with emojis (should count as 2 cells)."""
    assert display_width("📋") == 2
    assert display_width("✓") == 1  # Checkmark is typically 1 cell
    assert display_width("text 📋") == 7  # "text " (5) + emoji (2)


def test_display_width_box_drawing():
    """Test display width with box-drawing characters."""
    assert display_width("├─") == 2  # Each box-drawing char is 1 cell
    assert display_width("└─") == 2
    assert display_width("│") == 1
    assert display_width("├─ task") == 7  # "├─ " (3) + "task" (4)


def test_display_width_tree_with_emoji():
    """Test display width with tree characters and emoji combined."""
    # Tree character + task title + emoji counter
    text = "├─ Complete task 📋 3"
    # "├─ " (3) + "Complete task " (14) + "📋" (2) + " 3" (2) = 21
    assert display_width(text) == 21


def test_pad_to_width_basic():
    """Test padding basic text."""
    result = pad_to_width("hello", 10)
    assert len(result) == 10
    assert result == "hello     "


def test_pad_to_width_with_emoji():
    """Test padding text containing emoji."""
    # Emoji counts as 2 cells, so "📋" should only need 3 spaces to reach width 5
    result = pad_to_width("📋", 5)
    assert display_width(result) == 5
    # Visual: "📋   " (2 cells for emoji + 3 spaces)


def test_pad_to_width_with_tree_chars():
    """Test padding text with tree characters."""
    text = "├─ task"
    result = pad_to_width(text, 15)
    assert display_width(result) == 15


def test_truncate_to_width_basic():
    """Test truncating basic text."""
    result = truncate_to_width("hello world", 8)
    assert display_width(result) <= 8
    assert "..." in result


def test_truncate_to_width_with_emoji():
    """Test truncating text with emoji."""
    result = truncate_to_width("task 📋 emoji", 8)
    assert display_width(result) <= 8


def test_truncate_to_width_already_fits():
    """Test truncating text that already fits."""
    text = "short"
    result = truncate_to_width(text, 10)
    assert result == text


def test_id_zero_padding_consistency():
    """Test that zero-padded IDs maintain consistent width.

    This prevents column misalignment when transitioning from
    2-digit IDs (99) to 3-digit IDs (100).
    """
    # All IDs should be padded to 3 digits
    test_ids = [1, 9, 10, 99, 100, 999]

    for test_id in test_ids:
        display_id_str = f"{test_id:03d}"
        assert len(display_id_str) == 3, f"ID {test_id} should be 3 chars, got {len(display_id_str)}"

    # Verify specific cases
    assert f"{1:03d}" == "001"
    assert f"{99:03d}" == "099"
    assert f"{100:03d}" == "100"
    assert f"{999:03d}" == "999"
