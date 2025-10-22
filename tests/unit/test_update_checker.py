"""Tests for update checker functionality."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from taskrepo.utils.update_checker import (
    check_for_updates,
    should_check_for_updates,
    update_check_cache,
)


@pytest.fixture
def mock_pypi_response():
    """Mock PyPI JSON API response."""
    return {
        "info": {
            "version": "0.9.9",
            "name": "taskrepo",
        }
    }


@pytest.fixture
def temp_cache_file(tmp_path, monkeypatch):
    """Create a temporary cache file for testing."""
    cache_path = tmp_path / ".taskrepo-update-check"
    # Mock get_cache_file to return our temp path
    monkeypatch.setattr("taskrepo.utils.update_checker.get_cache_file", lambda: cache_path)
    return cache_path


def test_check_for_updates_newer_version_available(mock_pypi_response):
    """Test that check_for_updates detects newer version."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_pypi_response).encode()
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = check_for_updates()
        assert result == "0.9.9"


def test_check_for_updates_no_update_needed(mock_pypi_response):
    """Test that check_for_updates returns None when version is current."""
    mock_pypi_response["info"]["version"] = "0.0.1"  # Older version
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_pypi_response).encode()
    mock_response.__enter__ = lambda self: self
    mock_response.__exit__ = lambda self, *args: None

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = check_for_updates()
        assert result is None


def test_check_for_updates_network_failure():
    """Test that check_for_updates handles network failures gracefully."""
    with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
        result = check_for_updates()
        assert result is None  # Should fail silently


def test_check_for_updates_timeout():
    """Test that check_for_updates handles timeouts gracefully."""
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Timeout")):
        result = check_for_updates()
        assert result is None  # Should fail silently


def test_should_check_for_updates_no_cache(temp_cache_file):
    """Test that should_check_for_updates returns True when no cache exists."""
    assert not temp_cache_file.exists()
    assert should_check_for_updates() is True


def test_should_check_for_updates_old_cache(temp_cache_file):
    """Test that should_check_for_updates returns True when cache is old."""
    old_timestamp = datetime.now() - timedelta(hours=25)
    cache_data = {"last_check": old_timestamp.isoformat()}

    temp_cache_file.write_text(json.dumps(cache_data))

    assert should_check_for_updates() is True


def test_should_check_for_updates_recent_cache(temp_cache_file):
    """Test that should_check_for_updates returns False when cache is recent."""
    recent_timestamp = datetime.now() - timedelta(hours=1)
    cache_data = {"last_check": recent_timestamp.isoformat()}

    temp_cache_file.write_text(json.dumps(cache_data))

    assert should_check_for_updates() is False


def test_should_check_for_updates_corrupted_cache(temp_cache_file):
    """Test that should_check_for_updates handles corrupted cache gracefully."""
    temp_cache_file.write_text("corrupted json data")

    # Should return True (allow check) when cache is corrupted
    assert should_check_for_updates() is True


def test_update_check_cache(temp_cache_file):
    """Test that update_check_cache writes timestamp to cache file."""
    update_check_cache()

    assert temp_cache_file.exists()
    cache_data = json.loads(temp_cache_file.read_text())
    assert "last_check" in cache_data

    # Verify timestamp is recent (within last minute)
    last_check = datetime.fromisoformat(cache_data["last_check"])
    assert datetime.now() - last_check < timedelta(minutes=1)


def test_update_check_cache_failure(temp_cache_file, monkeypatch):
    """Test that update_check_cache handles write failures gracefully."""

    # Make the cache file unwritable
    def mock_open_fail(*args, **kwargs):
        raise PermissionError("Cannot write")

    monkeypatch.setattr("builtins.open", mock_open_fail)

    # Should not raise exception
    update_check_cache()
