"""Безопасные git-команды через subprocess без shell."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ai_assistant.models import GitBranch

SAFE_REF_RE = re.compile(r"^[A-Za-z0-9_./~^@{}\-]+$")


class GitError(RuntimeError):
    """Ошибка git или недопустимый аргумент."""


def validate_ref(ref: str) -> str:
    if not ref or ref.startswith("-") or not SAFE_REF_RE.match(ref) or ".." in ref:
        raise GitError(f"Недопустимая git-ссылка: {ref!r}")
    return ref


def validate_repo_path(path: str) -> str:
    """Запрещает абсолютные пути, выход из repo и NUL-байты."""
    candidate = path.replace("\\", "/").strip()
    if not candidate or candidate.startswith("/") or "\x00" in candidate:
        raise GitError(f"Недопустимый путь в репозитории: {path!r}")
    if any(part == ".." for part in candidate.split("/")):
        raise GitError(f"Путь выходит за пределы репозитория: {path!r}")
    return candidate


def run_git(repo: Path, args: list[str], timeout: float = 30.0) -> str:
    """Запускает `git -C repo ...` с shell=False."""
    command = ["git", "-C", str(repo), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git не найден в PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git не ответил за {timeout:.0f} с.") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        raise GitError(message or f"git завершился с кодом {completed.returncode}")
    return completed.stdout


def git_branch(repo: Path) -> GitBranch:
    """Ветка, короткий HEAD и признак незакоммиченных изменений."""
    branch = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    head = run_git(repo, ["rev-parse", "--short", "HEAD"]).strip()
    dirty = bool(run_git(repo, ["status", "--porcelain"]).strip())
    return GitBranch(branch=branch or "DETACHED", head=head, dirty=dirty)


def list_files(repo: Path, glob: str = "**/*") -> list[str]:
    """Список файлов внутри repo по glob, без выхода за пределы каталога."""
    root = repo.resolve()
    matches: list[str] = []
    for path in sorted(root.glob(glob)):
        if not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            continue
        matches.append(relative.as_posix())
        if len(matches) >= 500:
            break
    return matches


def git_diff(repo: Path, base: str, head: str = "HEAD", max_chars: int = 100_000) -> str:
    """Diff диапазона base...head с ограничением размера."""
    validate_ref(base)
    validate_ref(head)
    output = run_git(repo, ["diff", "--no-color", f"{base}...{head}"])
    if len(output) > max_chars:
        return output[:max_chars] + f"\n\n[diff обрезан: показано {max_chars} символов из {len(output)}]"
    return output


def git_show(repo: Path, ref: str, path: str, max_chars: int = 200_000) -> str:
    """Содержимое файла на указанной git-ссылке (только чтение)."""
    validate_ref(ref)
    safe_path = validate_repo_path(path)
    output = run_git(repo, ["show", f"{ref}:{safe_path}"])
    return output[:max_chars]


def changed_files(repo: Path, base: str, head: str = "HEAD") -> list[str]:
    """Изменённые файлы по `git diff --name-status base...head`."""
    validate_ref(base)
    validate_ref(head)
    output = run_git(repo, ["diff", "--name-status", f"{base}...{head}"])
    files: list[str] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append(parts[-1].strip())
    return files


def read_diff_file(path: Path, max_chars: int = 100_000) -> str:
    if not path.is_file():
        raise GitError(f"Файл diff не найден: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n[diff обрезан: показано {max_chars} символов из {len(text)}]"
    return text


def diff_file_paths(diff_text: str) -> list[str]:
    """Извлекает пути из unified diff (для офлайн-режима)."""
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path != "/dev/null" and path not in paths:
                paths.append(path)
    return paths
