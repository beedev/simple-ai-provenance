#!/usr/bin/env python3
"""
Standalone git hooks helper for AI provenance tracking.

Intentionally uses only stdlib — no venv required, no external dependencies.
Called by the global git hooks (prepare-commit-msg, post-commit).

Usage:
    python3 git_hooks_helper.py prepare-commit-msg <repo_path>
    python3 git_hooks_helper.py post-commit <repo_path> <commit_hash>
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path.home() / ".claude" / "provenance" / "provenance.db"


# ─── Database helpers ─────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH), timeout=3)
    conn.row_factory = sqlite3.Row
    return conn


def get_uncommitted_prompts(repo_path: str):
    conn = _connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT p.*, s.started_at AS session_started
            FROM   prompts p
            LEFT JOIN sessions s USING (session_id)
            WHERE  p.repo_path = ? AND p.committed = 0
            ORDER  BY p.timestamp ASC
            """,
            (repo_path,),
        ).fetchall()
        return rows
    except Exception:
        return []
    finally:
        conn.close()


def mark_committed(repo_path: str, commit_hash: str) -> int:
    conn = _connect()
    if conn is None:
        return 0
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
    except Exception:
        return 0
    finally:
        conn.close()


# ─── Formatting ───────────────────────────────────────────────────────────────

def _fmt_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


def _git_changed_files(repo_path: str):
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        staged = [f for f in r.stdout.strip().splitlines() if f]

        # Also include unstaged tracked files if nothing staged
        if not staged:
            r2 = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=repo_path, capture_output=True, text=True, timeout=5,
            )
            staged = [f for f in r2.stdout.strip().splitlines() if f]

        return staged
    except Exception:
        return []


_CONFIG_PATH = Path.home() / ".claude" / "simple-ai-provenance-config.json"
_DEFAULT_THRESHOLD = 5


def _load_threshold() -> int:
    """Read verbose_threshold from config file. Falls back to default if absent or malformed."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        value = cfg.get("settings", {}).get("verbose_threshold", _DEFAULT_THRESHOLD)
        return int(value)
    except Exception:
        return _DEFAULT_THRESHOLD


def _duration_str(first_ts: str, last_ts: str) -> str:
    """Human-readable duration between two ISO timestamps."""
    try:
        t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        secs = int((t1 - t0).total_seconds())
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{secs // 60}m"
        h, m = divmod(secs // 60, 60)
        return f"{h}h {m}m" if m else f"{h}h"
    except Exception:
        return ""


def _truncate(text: str, limit: int = 90) -> str:
    return text[:limit - 3] + "..." if len(text) > limit else text


def build_provenance_block(repo_path: str) -> str:
    """Generate the provenance comment block for a commit message.

    ≤ 5 prompts  →  verbose: every prompt shown verbatim
    > 5 prompts  →  condensed: count, duration, first + last prompt only
    Full detail is always queryable via `get_session_summary` MCP tool.
    """
    prompts = get_uncommitted_prompts(repo_path)
    if not prompts:
        return ""

    # Group by session, preserving insertion order
    sessions = {}
    for p in prompts:
        sid = p["session_id"]
        if sid not in sessions:
            sessions[sid] = {
                "prompts": [],
                "started": p["session_started"] or p["timestamp"],
            }
        sessions[sid]["prompts"].append(p)

    total = len(prompts)
    git_files = _git_changed_files(repo_path)
    threshold = _load_threshold()

    lines = ["", "# ── AI Provenance ──────────────────────────────────────────", "#"]

    if total <= threshold:
        # ── Verbose mode ────────────────────────────────────────────────
        for idx, (sid, data) in enumerate(sessions.items(), 1):
            started = _fmt_ts(data["started"])
            n = len(data["prompts"])
            lines.append(f"# Session {idx}  ({started}, id: {sid[:8]}, {n} prompt{'s' if n > 1 else ''})")
            for p in data["prompts"]:
                lines.append(f"#   • {_truncate(p['prompt_text'])}")
            lines.append("#")
    else:
        # ── Condensed mode ───────────────────────────────────────────────
        # Overall span
        first_ts = prompts[0]["timestamp"]
        last_ts  = prompts[-1]["timestamp"]
        dur = _duration_str(first_ts, last_ts)
        span = f" over {dur}" if dur else ""

        lines.append(f"# {total} prompts · {len(sessions)} session{'s' if len(sessions) > 1 else ''}{span}")
        lines.append("#")

        # Per-session one-liner
        for idx, (sid, data) in enumerate(sessions.items(), 1):
            started = _fmt_ts(data["started"])
            n = len(data["prompts"])
            lines.append(f"# Session {idx}  ({started}, id: {sid[:8]}, {n} prompts)")

        lines.append("#")
        lines.append(f"# First: {_truncate(prompts[0]['prompt_text'], 80)}")
        lines.append(f"# Last:  {_truncate(prompts[-1]['prompt_text'], 80)}")
        lines.append("#")
        lines.append("# Full history: call get_session_summary in Claude")

    # Files line — always show, cap at 8 to stay readable
    if git_files:
        if len(git_files) <= 8:
            files_str = ", ".join(git_files)
        else:
            files_str = ", ".join(git_files[:8]) + f" (+{len(git_files) - 8} more)"
        lines.append(f"# Files: {files_str}")
        lines.append("#")

    lines.append("# ─────────────────────────────────────────────────────────")
    return "\n".join(lines)


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_prepare_commit_msg(args):
    """
    Append provenance block to the commit message file.
    args: [commit_msg_file, repo_path]
    """
    if len(args) < 2:
        sys.exit(0)

    commit_msg_file = args[0]
    repo_path = args[1]

    block = build_provenance_block(repo_path)
    if not block:
        sys.exit(0)

    try:
        with open(commit_msg_file, "a") as f:
            f.write(block + "\n")
    except Exception:
        pass  # Never fail a commit


def cmd_post_commit(args):
    """
    Mark all uncommitted prompts as committed.
    args: [repo_path, commit_hash]
    """
    if len(args) < 2:
        sys.exit(0)

    repo_path = args[0]
    commit_hash = args[1]

    count = mark_committed(repo_path, commit_hash)
    if count > 0:
        print(f"[provenance] {count} prompt(s) recorded for commit {commit_hash[:8]}", file=sys.stderr)


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: git_hooks_helper.py <prepare-commit-msg|post-commit> [args...]")
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    try:
        if command == "prepare-commit-msg":
            cmd_prepare_commit_msg(rest)
        elif command == "post-commit":
            cmd_post_commit(rest)
    except Exception:
        pass  # Never block a git operation
