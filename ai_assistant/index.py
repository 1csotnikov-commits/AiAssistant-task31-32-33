"""Индексация README/docs/Python и поиск через SQLite FTS5."""

from __future__ import annotations

import ast
import hashlib
import re
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ai_assistant.config import Settings, get_settings
from ai_assistant.models import Chunk, IndexStats, RetrievedChunk

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WORD_RE = re.compile(r"[\w]+", re.UNICODE)
MAX_CHUNK_LINES = 80

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    id UNINDEXED,
    path UNINDEXED,
    title,
    kind UNINDEXED,
    start_line UNINDEXED,
    end_line UNINDEXED,
    text,
    tokenize='unicode61'
);
"""


def iter_source_files(repo: Path) -> list[Path]:
    """README.md, docs/**/*.md|yaml|yml|json и ai_assistant/**/*.py."""
    repo = repo.resolve()
    found: list[Path] = []
    readme = repo / "README.md"
    if readme.is_file():
        found.append(readme)
    docs = repo / "docs"
    if docs.is_dir():
        for suffix in ("*.md", "*.yaml", "*.yml", "*.json"):
            found.extend(docs.rglob(suffix))
    code = repo / "ai_assistant"
    if code.is_dir():
        found.extend(code.rglob("*.py"))
    result: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(found):
        resolved = path.resolve()
        if resolved in seen or "__pycache__" in resolved.parts or not resolved.is_file():
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def relative_path(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.name


def _make_chunk(path: str, title: str, kind: str, start: int, end: int, text: str) -> Chunk:
    return Chunk(
        id=f"{path}:{start}-{end}",
        path=path,
        title=title.strip() or path,
        kind="code" if kind == "code" else "doc",
        start_line=max(1, start),
        end_line=max(start, end),
        text=text.strip("\n"),
    )


def _windows(lines: list[str], size: int = 60) -> Iterable[tuple[int, int, str]]:
    for offset in range(0, len(lines), size):
        block = lines[offset : offset + size]
        if any(line.strip() for line in block):
            yield offset + 1, offset + len(block), "\n".join(block)


def _windows_chunks(rel: str, name: str, lines: list[str], kind: str = "doc") -> list[Chunk]:
    chunks: list[Chunk] = []
    for start, end, block in _windows(lines):
        chunks.append(_make_chunk(rel, f"{name}: {start}-{end}", kind, start, end, block))
    return chunks


def chunk_text(path: Path, text: str, kind: Literal["doc", "code"] = "doc") -> list[Chunk]:
    """Разбивает текст без структуры на окна по 60 строк."""
    return _windows_chunks(path.as_posix(), path.name, text.splitlines(), kind)


def _node_start(node: ast.stmt) -> int:
    positions = [node.lineno]
    for decorator in getattr(node, "decorator_list", []):
        positions.append(decorator.lineno)
    return min(positions)


def chunk_python(path: Path, text: str, repo: Path | None = None) -> list[Chunk]:
    """Чанки по функциям/классам/методам; fallback — окна по 60 строк."""
    rel = relative_path(path, repo) if repo else path.as_posix()
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _windows_chunks(rel, path.name, lines, "code")

    chunks: list[Chunk] = []
    nodes = [node for node in tree.body if isinstance(node, ast.stmt)]
    first_start = min((_node_start(node) for node in nodes), default=len(lines) + 1)
    if first_start > 1:
        preamble = "\n".join(lines[: first_start - 1])
        if any(line.strip() and not line.strip().startswith("#") for line in preamble.splitlines()):
            chunks.append(_make_chunk(rel, f"{path.stem} (module)", "code", 1, first_start - 1, preamble))

    for node in nodes:
        if isinstance(node, ast.ClassDef) and node.end_lineno:
            body = [item for item in node.body if isinstance(item, ast.stmt)]
            methods = [item for item in body if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)]
            header_end = max(_node_start(node), (_node_start(methods[0]) - 1) if methods else node.end_lineno)
            header = "\n".join(lines[_node_start(node) - 1 : header_end])
            chunks.append(_make_chunk(rel, node.name, "code", _node_start(node), header_end, header))
            for method in methods:
                if not method.end_lineno:
                    continue
                start = _node_start(method)
                block = "\n".join(lines[start - 1 : method.end_lineno])
                title = f"{node.name}.{method.name}"
                if method.end_lineno - start + 1 > 150:
                    for index, (win_start, win_end, part) in enumerate(_windows(block.splitlines(), 60)):
                        part_title = title if index == 0 else f"{title} (часть {index + 1})"
                        chunks.append(
                            _make_chunk(rel, part_title, "code", start + win_start - 1, start + win_end - 1, part)
                        )
                else:
                    chunks.append(_make_chunk(rel, title, "code", start, method.end_lineno, block))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.end_lineno:
            start = _node_start(node)
            block = "\n".join(lines[start - 1 : node.end_lineno])
            chunks.append(_make_chunk(rel, node.name, "code", start, node.end_lineno, block))
        elif node.end_lineno:
            start = _node_start(node)
            block = "\n".join(lines[start - 1 : node.end_lineno])
            if len(block.splitlines()) >= 3:
                chunks.append(_make_chunk(rel, f"{path.stem}:{start}", "code", start, node.end_lineno, block))

    if not chunks:
        return _windows_chunks(rel, path.name, lines, "code")
    return chunks


def chunk_file(path: Path, repo: Path, text: str) -> list[Chunk]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return chunk_python(path, text, repo)
    if suffix == ".md":
        return chunk_markdown(path, text, repo)
    return chunk_text(Path(relative_path(path, repo)), text, "doc")


def _fts_query(query: str) -> str:
    tokens = [token.lower() for token in WORD_RE.findall(query) if len(token) > 1]
    if not tokens:
        return ""
    alternatives: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        variants = [token]
        if len(token) >= 5:
            variants.append(token[:5])
        for variant in variants:
            escaped = variant.replace('"', '""')
            expression = f'"{escaped}"' if len(variant) < 5 else f'"{escaped}"*'
            if expression not in seen:
                seen.add(expression)
                alternatives.append(expression)
    return " OR ".join(alternatives)


def chunk_markdown(path: Path, text: str, repo: Path | None = None) -> list[Chunk]:
    """Режет Markdown по заголовкам, сохраняя номера строк."""
    rel = relative_path(path, repo) if repo else path.as_posix()
    lines = text.splitlines()
    sections: list[tuple[str, int, int, str]] = []
    title = path.stem
    start = 1
    buffer: list[str] = []
    for number, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            if buffer and any(item.strip() for item in buffer):
                sections.append((title, start, number - 1, "\n".join(buffer)))
            title = match.group(2).strip()
            start = number
            buffer = [line]
        else:
            buffer.append(line)
    if buffer and any(item.strip() for item in buffer):
        sections.append((title, start, max(1, len(lines)), "\n".join(buffer)))
    if not sections:
        return _windows_chunks(rel, path.name, lines)
    chunks: list[Chunk] = []
    for section_title, section_start, section_end, block in sections:
        if len(block.splitlines()) > MAX_CHUNK_LINES:
            for offset, part in enumerate(_windows(block.splitlines(), 60)):
                part_start = section_start + part[0] - 1
                part_end = section_start + part[1] - 1
                part_title = section_title if offset == 0 else f"{section_title} (продолжение)"
                chunks.append(_make_chunk(rel, part_title, "doc", part_start, part_end, part[2]))
        else:
            chunks.append(_make_chunk(rel, section_title, "doc", section_start, section_end, block))
    return chunks
class Index:
    """SQLite FTS5-индекс репозитория."""

    def __init__(self, repo: Path, index_path: Path | None = None, settings: Settings | None = None) -> None:
        self.repo = repo.resolve()
        self.settings = settings or get_settings()
        self.path = (index_path or self.settings.index_path(self.repo)).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        return connection

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def build(self, force: bool = False) -> IndexStats:
        """Индексирует новые/изменённые файлы и удаляет исчезнувшие."""
        files = iter_source_files(self.repo)
        current_paths = {relative_path(path, self.repo) for path in files}
        stats = IndexStats(repo=str(self.repo), index_path=str(self.path), files=len(files))
        with self._connect() as connection:
            known = {row["path"]: row["sha256"] for row in connection.execute("SELECT path, sha256 FROM files")}
            removed = sorted(set(known) - current_paths)
            for rel in removed:
                self._delete_file(connection, rel)
            stats.removed_files = len(removed)

            for path in files:
                rel = relative_path(path, self.repo)
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if not force and known.get(rel) == digest:
                    stats.unchanged_files += 1
                    continue
                chunks = [chunk for chunk in chunk_file(path, self.repo, text) if chunk.text.strip()]
                self._delete_file(connection, rel)
                rows = [
                    (chunk.id, chunk.path, chunk.title, chunk.kind, chunk.start_line, chunk.end_line, chunk.text)
                    for chunk in chunks
                ]
                connection.executemany(
                    "INSERT OR REPLACE INTO chunks (id, path, title, kind, start_line, end_line, text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                connection.executemany(
                    "INSERT INTO chunks_fts (id, path, title, kind, start_line, end_line, text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                connection.execute(
                    "INSERT OR REPLACE INTO files (path, sha256, indexed_at) VALUES (?, ?, ?)",
                    (rel, digest, datetime.now(UTC).isoformat(timespec="seconds")),
                )
                stats.added_files += 1
            stats.chunks = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return stats

    @staticmethod
    def _delete_file(connection: sqlite3.Connection, rel: str) -> None:
        connection.execute("DELETE FROM chunks_fts WHERE path = ?", (rel,))
        connection.execute("DELETE FROM chunks WHERE path = ?", (rel,))
        connection.execute("DELETE FROM files WHERE path = ?", (rel,))


    def search(
        self,
        query: str,
        k: int = 5,
        kind: Literal["doc", "code"] | None = None,
        paths: Iterable[str] | None = None,
    ) -> list[RetrievedChunk]:
        """FTS5-поиск с fallback на case-insensitive substring."""
        if not self.exists or k <= 0:
            return []
        filters: list[str] = []
        params: list[object] = []
        if kind:
            filters.append("c.kind = ?")
            params.append(kind)
        path_list = list(paths or [])
        if path_list:
            filters.append(f"c.path IN ({', '.join('?' for _ in path_list)})")
            params.extend(path_list)
        where_extra = " AND " + " AND ".join(filters) if filters else ""

        match = _fts_query(query)
        if match:
            sql = (
                "SELECT c.*, bm25(chunks_fts) AS rank FROM chunks_fts "
                "JOIN chunks c ON c.id = chunks_fts.id "
                f"WHERE chunks_fts MATCH ?{where_extra} ORDER BY rank LIMIT ?"
            )
            try:
                with self._connect() as connection:
                    rows = connection.execute(sql, [match, *params, k]).fetchall()
                if rows:
                    return [
                        RetrievedChunk(
                            id=row["id"],
                            path=row["path"],
                            title=row["title"],
                            kind=row["kind"],
                            start_line=row["start_line"],
                            end_line=row["end_line"],
                            text=row["text"],
                            score=round(-float(row["rank"]), 4),
                        )
                        for row in rows
                    ]
            except sqlite3.OperationalError:
                pass
        return self._substring_search(query, k, kind, path_list)

    def _substring_search(
        self,
        query: str,
        k: int,
        kind: Literal["doc", "code"] | None,
        paths: list[str],
    ) -> list[RetrievedChunk]:
        tokens = [token.lower() for token in WORD_RE.findall(query) if len(token) > 1]
        if not tokens:
            return []
        clauses: list[str] = []
        params: list[object] = []
        for token in tokens:
            clauses.append("(lower(c.text) LIKE ? OR lower(c.title) LIKE ? OR lower(c.path) LIKE ?)")
            params.extend([f"%{token}%", f"%{token}%", f"%{token}%"])
        filters = [f"({' OR '.join(clauses)})"]
        if kind:
            filters.append("c.kind = ?")
            params.append(kind)
        if paths:
            filters.append(f"c.path IN ({', '.join('?' for _ in paths)})")
            params.extend(paths)
        sql = f"SELECT c.* FROM chunks c WHERE {' AND '.join(filters)} LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(sql, [*params, max(k * 6, 20)]).fetchall()
        scored: list[RetrievedChunk] = []
        for row in rows:
            haystack = f"{row['title']}\n{row['text']}".lower()
            score = sum(haystack.count(token) for token in tokens)
            scored.append(
                RetrievedChunk(
                    id=row["id"],
                    path=row["path"],
                    title=row["title"],
                    kind=row["kind"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    text=row["text"],
                    score=float(score),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:k]

    def count(self) -> int:
        if not self.exists:
            return 0
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])


def ensure_index(repo: Path, settings: Settings | None = None) -> tuple[Index, IndexStats | None]:
    """Возвращает индекс; если он пуст — строит."""
    index = Index(repo, settings=settings)
    if not index.exists or index.count() == 0:
        return index, index.build()
    return index, None

