"""GitHub integration utilities."""

import platform
import shutil
import subprocess
from pathlib import Path


class GitHubError(Exception):
    """Exception raised for GitHub-related errors."""

    pass


def check_gh_cli_installed() -> bool:
    """Check if GitHub CLI (gh) is installed.

    Returns:
        True if gh is installed, False otherwise
    """
    return shutil.which("gh") is not None


def get_gh_install_message() -> str:
    """Get platform-specific installation message for GitHub CLI.

    Returns:
        Installation message with platform-specific instructions
    """
    base_msg = "GitHub CLI (gh) is not installed."

    # Check if on macOS and if Homebrew is installed
    if platform.system() == "Darwin" and shutil.which("brew"):
        return f"{base_msg} Install it with:\n  brew install gh"

    # Default message for other platforms or macOS without Homebrew
    return f"{base_msg} Install it from: https://cli.github.com/"


def check_gh_auth() -> bool:
    """Check if user is authenticated with GitHub CLI.

    Returns:
        True if authenticated, False otherwise
    """
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def check_github_repo_exists(org: str, repo_name: str) -> bool:
    """Check if a GitHub repository exists.

    Args:
        org: GitHub organization or username
        repo_name: Repository name

    Returns:
        True if repository exists, False otherwise
    """
    # Check prerequisites
    if not check_gh_cli_installed():
        return False

    if not check_gh_auth():
        return False

    # Build the repository identifier
    full_repo_name = f"{org}/{repo_name}"

    try:
        # Use gh repo view to check if repo exists
        # If it exists, command returns 0; if not, returns non-zero
        result = subprocess.run(
            ["gh", "repo", "view", full_repo_name],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_github_repo(org: str, repo_name: str, visibility: str = "private") -> str:
    """Create a GitHub repository using gh CLI.

    Args:
        org: GitHub organization or username
        repo_name: Repository name
        visibility: Repository visibility ('public' or 'private')

    Returns:
        URL of the created repository

    Raises:
        GitHubError: If repository creation fails
    """
    # Check prerequisites
    if not check_gh_cli_installed():
        raise GitHubError(get_gh_install_message())

    if not check_gh_auth():
        raise GitHubError(
            "Not authenticated with GitHub.\n"
            "Check your auth status: gh auth status\n"
            "To authenticate, run: gh auth login"
        )

    # Build the repository identifier
    full_repo_name = f"{org}/{repo_name}"

    # Build command
    visibility_flag = f"--{visibility}"
    cmd = ["gh", "repo", "create", full_repo_name, visibility_flag, "--confirm"]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Extract URL from output (gh prints the URL)
        url = f"https://github.com/{full_repo_name}"
        return url

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to create GitHub repository: {error_msg}") from e


def setup_git_remote(repo_path: Path, remote_url: str, remote_name: str = "origin"):
    """Set up git remote for a local repository.

    Args:
        repo_path: Path to the local git repository
        remote_url: URL of the remote repository
        remote_name: Name of the remote (default: origin)

    Raises:
        GitHubError: If remote setup fails
    """
    try:
        subprocess.run(
            ["git", "remote", "add", remote_name, remote_url], cwd=repo_path, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to add git remote: {error_msg}") from e


def clone_github_repo(org: str, repo_name: str, target_path: Path):
    """Clone a GitHub repository to a local path.

    Args:
        org: GitHub organization or username
        repo_name: Repository name
        target_path: Path where the repository should be cloned

    Raises:
        GitHubError: If clone fails or prerequisites not met
    """
    # Check prerequisites
    if not check_gh_cli_installed():
        raise GitHubError(get_gh_install_message())

    if not check_gh_auth():
        raise GitHubError(
            "Not authenticated with GitHub.\n"
            "Check your auth status: gh auth status\n"
            "To authenticate, run: gh auth login"
        )

    # Build the repository identifier
    full_repo_name = f"{org}/{repo_name}"

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Use gh repo clone to clone the repository
        cmd = ["gh", "repo", "clone", full_repo_name, str(target_path)]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to clone GitHub repository: {error_msg}") from e


def push_to_remote(repo_path: Path, branch: str = "main", remote_name: str = "origin"):
    """Push local commits to remote repository.

    Args:
        repo_path: Path to the local git repository
        branch: Branch to push (default: main)
        remote_name: Name of the remote (default: origin)

    Raises:
        GitHubError: If push fails
    """
    try:
        subprocess.run(
            ["git", "push", "-u", remote_name, branch], cwd=repo_path, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to push to remote: {error_msg}") from e


def list_github_repos(org: str, pattern: str | None = None) -> list[dict]:
    """List repositories from a GitHub organization/user.

    Args:
        org: GitHub organization or username
        pattern: Optional pattern to filter repository names (e.g., 'tasks-*')

    Returns:
        List of repository dictionaries with 'name' and 'url' keys

    Raises:
        GitHubError: If listing fails or prerequisites not met
    """
    import json

    # Check prerequisites
    if not check_gh_cli_installed():
        raise GitHubError(get_gh_install_message())

    if not check_gh_auth():
        raise GitHubError(
            "Not authenticated with GitHub.\n"
            "Check your auth status: gh auth status\n"
            "To authenticate, run: gh auth login"
        )

    try:
        # Use gh repo list to fetch repositories
        cmd = ["gh", "repo", "list", org, "--json", "name,url", "--limit", "1000"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse JSON output
        repos = json.loads(result.stdout)

        # Filter by pattern if provided
        if pattern:
            # Convert shell-style glob pattern to simple prefix match
            # For now, we'll handle 'tasks-*' as 'starts with tasks-'
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                repos = [r for r in repos if r["name"].startswith(prefix)]
            else:
                # Exact match
                repos = [r for r in repos if r["name"] == pattern]

        return repos

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        raise GitHubError(f"Failed to list GitHub repositories: {error_msg}") from e
    except json.JSONDecodeError as e:
        raise GitHubError(f"Failed to parse GitHub response: {e}") from e
