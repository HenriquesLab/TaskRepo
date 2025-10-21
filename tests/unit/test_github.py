"""Unit tests for GitHub utilities."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from taskrepo.utils.github import (
    GitHubError,
    check_gh_auth,
    check_gh_cli_installed,
    create_github_repo,
    push_to_remote,
    setup_git_remote,
)


def test_check_gh_cli_installed():
    """Test checking if gh CLI is installed."""
    with patch("shutil.which") as mock_which:
        # Test when gh is installed
        mock_which.return_value = "/usr/bin/gh"
        assert check_gh_cli_installed() is True

        # Test when gh is not installed
        mock_which.return_value = None
        assert check_gh_cli_installed() is False


def test_check_gh_auth():
    """Test checking GitHub authentication status."""
    with patch("subprocess.run") as mock_run:
        # Test when authenticated
        mock_run.return_value = MagicMock(returncode=0)
        assert check_gh_auth() is True

        # Test when not authenticated
        mock_run.return_value = MagicMock(returncode=1)
        assert check_gh_auth() is False


def test_create_github_repo_not_installed():
    """Test creating repo when gh CLI is not installed."""
    with patch("taskrepo.utils.github.check_gh_cli_installed", return_value=False):
        with pytest.raises(GitHubError, match="not installed"):
            create_github_repo("testorg", "test-repo", "private")


def test_create_github_repo_not_authenticated():
    """Test creating repo when not authenticated."""
    with patch("taskrepo.utils.github.check_gh_cli_installed", return_value=True):
        with patch("taskrepo.utils.github.check_gh_auth", return_value=False):
            with pytest.raises(GitHubError, match="Not authenticated"):
                create_github_repo("testorg", "test-repo", "private")


def test_create_github_repo_success():
    """Test successful GitHub repository creation."""
    with patch("taskrepo.utils.github.check_gh_cli_installed", return_value=True):
        with patch("taskrepo.utils.github.check_gh_auth", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                url = create_github_repo("testorg", "test-repo", "private")

                assert url == "https://github.com/testorg/test-repo"
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "gh" in args
                assert "repo" in args
                assert "create" in args
                assert "testorg/test-repo" in args
                assert "--private" in args


def test_create_github_repo_failure():
    """Test failed GitHub repository creation."""
    import subprocess

    with patch("taskrepo.utils.github.check_gh_cli_installed", return_value=True):
        with patch("taskrepo.utils.github.check_gh_auth", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(1, "gh", stderr="Repository already exists")

                with pytest.raises(GitHubError, match="Failed to create"):
                    create_github_repo("testorg", "test-repo", "private")


def test_setup_git_remote():
    """Test setting up git remote."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            setup_git_remote(repo_path, "https://github.com/testorg/test-repo.git")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "git" in args
            assert "remote" in args
            assert "add" in args
            assert "origin" in args
            assert "https://github.com/testorg/test-repo.git" in args


def test_push_to_remote():
    """Test pushing to remote."""
    with TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            push_to_remote(repo_path, "main", "origin")

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "git" in args
            assert "push" in args
            assert "-u" in args
            assert "origin" in args
            assert "main" in args
