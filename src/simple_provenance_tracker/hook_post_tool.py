#!/usr/bin/env python3
"""
Claude Code PostToolUse hook.

Fires after Write / Edit / MultiEdit / NotebookEdit tool calls.
If the file being written lives in a different git repo than the session's
primary repo, records a cross-repo reference in prompt_repos so that the
prompt shows up in that repo's PR description.

Hook stdin format:
{
  "session_id":      "uuid",
  "tool_name":       "Write",
  "tool_input":      {"file_path": "/path/to/file", ...},
  "tool_response":   {...},
  "cwd":             "/current/working/dir"
}

This script must NEVER crash or block — Claude will pause waiting for it.
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


DB_PATH = Path.home() / ".claude" / "provenance" / "provenance.db"
TRACKED_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _get_repo_root(path: str) -> str:
    directory = str(Path(path).parent)
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return directory


def _get_branch(repo_path: str) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return "unknown"


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    tool_name = data.get("tool_name", "")
    if tool_name not in TRACKED_TOOLS:
        return

    session_id = data.get("session_id", "")
    tool_input = data.get("tool_input", {})
    cwd = data.get("cwd") or os.getcwd()

    if not session_id or not tool_input:
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    # Resolve to absolute path
    if not Path(file_path).is_absolute():
        file_path = str(Path(cwd) / file_path)

    try:
        if not DB_PATH.exists():
            return  # DB not initialised yet, nothing to cross-reference

        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")

        # Get session's primary repo
        row = conn.execute(
            "SELECT repo_path FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            conn.close()
            return
        primary_repo = row[0]

        file_repo = _get_repo_root(file_path)
        if not file_repo or file_repo == primary_repo:
            conn.close()
            return  # Same repo — no cross-reference needed

        # Find the most recent prompt for this session
        row = conn.execute(
            "SELECT prompt_id FROM prompts WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not row:
            conn.close()
            return
        prompt_id = row[0]

        branch = _get_branch(file_repo)
        conn.execute(
            "INSERT OR IGNORE INTO prompt_repos (prompt_id, repo_path, branch_name) VALUES (?, ?, ?)",
            (prompt_id, file_repo, branch),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never block Claude


if __name__ == "__main__":
    main()
