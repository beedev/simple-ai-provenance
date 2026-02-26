"""SQLite database for AI provenance tracking — zero external dependencies."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


DB_PATH = Path.home() / ".claude" / "provenance" / "provenance.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                repo_path    TEXT NOT NULL DEFAULT '',
                branch_name  TEXT NOT NULL DEFAULT '',
                cwd          TEXT NOT NULL DEFAULT '',
                started_at   TEXT NOT NULL,
                last_active  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompts (
                prompt_id    TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                repo_path    TEXT NOT NULL DEFAULT '',
                branch_name  TEXT NOT NULL DEFAULT '',
                cwd          TEXT NOT NULL DEFAULT '',
                prompt_text  TEXT NOT NULL,
                timestamp    TEXT NOT NULL,
                committed    INTEGER NOT NULL DEFAULT 0,
                commit_hash  TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_prompts_session
                ON prompts(session_id);
            CREATE INDEX IF NOT EXISTS idx_prompts_repo
                ON prompts(repo_path);
            CREATE INDEX IF NOT EXISTS idx_prompts_uncommitted
                ON prompts(repo_path, committed)
                WHERE committed = 0;

            CREATE TABLE IF NOT EXISTS prompt_repos (
                prompt_id   TEXT NOT NULL,
                repo_path   TEXT NOT NULL,
                branch_name TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (prompt_id, repo_path)
            );

            CREATE INDEX IF NOT EXISTS idx_prompt_repos_repo
                ON prompt_repos(repo_path);
        """)
        conn.commit()
    finally:
        conn.close()


def upsert_session(
    session_id: str,
    repo_path: str,
    branch_name: str,
    cwd: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO sessions (session_id, repo_path, branch_name, cwd, started_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                last_active  = excluded.last_active,
                repo_path    = CASE WHEN excluded.repo_path  != '' THEN excluded.repo_path  ELSE sessions.repo_path  END,
                branch_name  = CASE WHEN excluded.branch_name != '' THEN excluded.branch_name ELSE sessions.branch_name END,
                cwd          = excluded.cwd
            """,
            (session_id, repo_path, branch_name, cwd, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def insert_prompt(
    session_id: str,
    prompt_text: str,
    repo_path: str,
    branch_name: str,
    cwd: str,
) -> str:
    """Insert a prompt. Returns the new prompt_id."""
    prompt_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO prompts
                (prompt_id, session_id, repo_path, branch_name, cwd, prompt_text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (prompt_id, session_id, repo_path, branch_name, cwd, prompt_text, now),
        )
        conn.commit()
    finally:
        conn.close()
    return prompt_id


def get_uncommitted_prompts(repo_path: str) -> List[sqlite3.Row]:
    """All uncommitted prompts for a repo, oldest first."""
    conn = _connect()
    try:
        return conn.execute(
            """
            SELECT p.*, s.started_at AS session_started
            FROM   prompts p
            LEFT JOIN sessions s USING (session_id)
            WHERE  p.repo_path = ? AND p.committed = 0
            ORDER  BY p.timestamp ASC
            """,
            (repo_path,),
        ).fetchall()
    finally:
        conn.close()


def get_session_prompts(session_id: str) -> List[sqlite3.Row]:
    """All prompts for a session, oldest first."""
    conn = _connect()
    try:
        return conn.execute(
            "SELECT * FROM prompts WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
    finally:
        conn.close()


def get_session_info(session_id: str) -> Optional[sqlite3.Row]:
    conn = _connect()
    try:
        return conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()


def list_sessions(repo_path: str, limit: int = 10) -> List[sqlite3.Row]:
    """Recent sessions for a repo with prompt counts."""
    conn = _connect()
    try:
        return conn.execute(
            """
            SELECT s.*,
                   COUNT(p.prompt_id)                          AS total_prompts,
                   SUM(CASE WHEN p.committed = 0 THEN 1 END)  AS uncommitted_prompts
            FROM   sessions s
            LEFT JOIN prompts p USING (session_id)
            WHERE  s.repo_path = ?
            GROUP  BY s.session_id
            ORDER  BY s.last_active DESC
            LIMIT  ?
            """,
            (repo_path, limit),
        ).fetchall()
    finally:
        conn.close()


def add_prompt_repo(prompt_id: str, repo_path: str, branch_name: str) -> None:
    """Record that a prompt touched files in a repo other than its session's primary repo."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO prompt_repos (prompt_id, repo_path, branch_name) VALUES (?, ?, ?)",
            (prompt_id, repo_path, branch_name),
        )
        conn.commit()
    finally:
        conn.close()


def get_cross_repo_prompts(repo_path: str) -> List[sqlite3.Row]:
    """Prompts that touched files in repo_path even though the session started elsewhere."""
    conn = _connect()
    try:
        return conn.execute(
            """
            SELECT p.*, s.started_at AS session_started
            FROM   prompt_repos pr
            JOIN   prompts p USING (prompt_id)
            LEFT JOIN sessions s USING (session_id)
            WHERE  pr.repo_path = ?
            ORDER  BY p.timestamp ASC
            """,
            (repo_path,),
        ).fetchall()
    finally:
        conn.close()


def get_prompts_for_commits(commit_hashes: List[str]) -> List[sqlite3.Row]:
    """All prompts attributed to a set of commit hashes (for PR-level rollup)."""
    if not commit_hashes:
        return []
    placeholders = ",".join("?" * len(commit_hashes))
    conn = _connect()
    try:
        return conn.execute(
            f"""
            SELECT p.*, s.started_at AS session_started
            FROM   prompts p
            LEFT JOIN sessions s USING (session_id)
            WHERE  p.commit_hash IN ({placeholders})
            ORDER  BY p.timestamp ASC
            """,
            commit_hashes,
        ).fetchall()
    finally:
        conn.close()


def mark_committed(repo_path: str, commit_hash: str) -> int:
    """Mark all uncommitted prompts for a repo as committed. Returns count updated."""
    conn = _connect()
    try:
        cur = conn.execute(
            """
            UPDATE prompts
            SET    committed = 1, commit_hash = ?
            WHERE  repo_path = ? AND committed = 0
            """,
            (commit_hash, repo_path),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
