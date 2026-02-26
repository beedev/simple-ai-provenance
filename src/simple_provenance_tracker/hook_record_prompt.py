#!/usr/bin/env python3
"""
Claude Code UserPromptSubmit hook.

Called by Claude Code before each user prompt is processed.
Reads hook event JSON from stdin, records the prompt to SQLite.

Hook stdin format:
{
  "session_id":      "uuid",
  "transcript_path": "/path/to/session.jsonl",
  "cwd":             "/current/working/dir",
  "hook_event_name": "UserPromptSubmit",
  "prompt":          "the user's message text"   ← may or may not be present
}

This script must NEVER crash or block — Claude will pause waiting for it.
"""

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path.home() / ".claude" / "provenance" / "provenance.db"


def _init_db(conn: sqlite3.Connection) -> None:
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
    """)


def _get_repo_info(cwd: str):
    """Return (repo_root, branch). Falls back to cwd / 'unknown'."""
    repo_path = cwd
    branch = "unknown"
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            repo_path = r.stdout.strip()
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            branch = r.stdout.strip()
    except Exception:
        pass
    return repo_path, branch


def _get_prompt_from_transcript(transcript_path: str) -> str:
    """
    Fallback: read the most recent human text entry from the JSONL transcript.
    Used when the hook data doesn't include the 'prompt' field directly.
    """
    try:
        with open(transcript_path, encoding="utf-8") as f:
            lines = f.readlines()
        # Walk backwards to find the last user text entry
        for raw in reversed(lines):
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except Exception:
                continue
            if entry.get("type") != "user":
                continue
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content.strip()
                if text and not _is_meta(text):
                    return text
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "").strip()
                        if text and not _is_meta(text):
                            return text
    except Exception:
        pass
    return ""


def _is_meta(text: str) -> bool:
    prefixes = (
        "[Request interrupted",
        "The user doesn't want to proceed",
        "[Skipping",
        "<system-reminder>",
    )
    return any(text.startswith(p) for p in prefixes)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return  # Never block Claude

    session_id = data.get("session_id", "")
    cwd = data.get("cwd") or os.getcwd()
    transcript_path = data.get("transcript_path", "")

    # Get prompt — prefer direct field, fallback to transcript
    prompt_text = data.get("prompt", "").strip()
    if not prompt_text and transcript_path:
        prompt_text = _get_prompt_from_transcript(transcript_path)

    if not prompt_text or not session_id:
        return

    repo_path, branch = _get_repo_info(cwd)
    now = datetime.now(timezone.utc).isoformat()

    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        _init_db(conn)

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
            (session_id, repo_path, branch, cwd, now, now),
        )

        conn.execute(
            """
            INSERT INTO prompts
                (prompt_id, session_id, repo_path, branch_name, cwd, prompt_text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), session_id, repo_path, branch, cwd, prompt_text, now),
        )

        conn.commit()
        conn.close()
    except Exception:
        pass  # Never block Claude


if __name__ == "__main__":
    main()
