"""Тесты git-инструментов на временном репозитории."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ai_assistant.git_tools import GitError, changed_files, git_branch, git_diff, git_show, list_files


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True, capture_output=True)


def test_git_branch_and_dirty(git_repo: Path) -> None:
    branch = git_branch(git_repo)
    assert branch.branch == "main"
    assert len(branch.head) >= 7
    assert branch.dirty is False

    (git_repo / "new.txt").write_text("dirty", encoding="utf-8")
    assert git_branch(git_repo).dirty is True


def test_list_files_is_limited_to_repo(git_repo: Path) -> None:
    files = list_files(git_repo, "**/*")
    assert "README.md" in files
    assert all(not item.startswith("..") for item in files)


def test_diff_and_changed_files(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("# Git repo\n\nNew line.\n", encoding="utf-8")
    _commit(git_repo, "update readme")
    diff = git_diff(git_repo, "HEAD~1", "HEAD")
    assert "New line" in diff
    assert changed_files(git_repo, "HEAD~1", "HEAD") == ["README.md"]
    limited = git_diff(git_repo, "HEAD~1", "HEAD", max_chars=10)
    assert "diff обрезан" in limited


def test_git_show_and_path_validation(git_repo: Path) -> None:
    assert "Git repo" in git_show(git_repo, "HEAD", "README.md")
    with pytest.raises(GitError):
        git_show(git_repo, "HEAD", "../secret.txt")
