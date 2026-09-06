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

try:
    from ._meta import is_meta_prompt
except Exception:                                   # pragma: no cover
    try:
        from simple_provenance_tracker._meta import is_meta_prompt
    except Exception:
        # Run as a loose script with no package around it — never fail a commit.
        def is_meta_prompt(text: str) -> bool:
            return not text


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


def _recent_commit_hashes(repo_path: str, minutes: int):
    """Commits made in this repo within the last `minutes`.

    A single body of work is often split across several commits made seconds
    apart. Those commits share provenance, so each one should carry it.
    """
    if minutes <= 0:
        return []
    try:
        r = subprocess.run(
            ["git", "log", "--since", f"{minutes} minutes ago", "--format=%H"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        return [h for h in r.stdout.strip().splitlines() if h]
    except Exception:
        return []


def get_prompts_for_commit(repo_path: str, batch_window: int):
    """Prompts that belong on the commit about to be written.

    Two groups, merged and de-duplicated:
      1. Prompts not yet attributed to any commit.
      2. Prompts attributed to a commit made within `batch_window` minutes.

    Group 2 is what stops the first commit of a batch from swallowing the whole
    history and leaving its siblings blank. Without file-level attribution this
    is the finest honest split available: all commits in one burst of work carry
    the same provenance.
    """
    conn = _connect()
    if conn is None:
        return []
    try:
        recent = _recent_commit_hashes(repo_path, batch_window)
        if recent:
            placeholders = ",".join("?" * len(recent))
            sql = f"""
                SELECT p.*, s.started_at AS session_started
                FROM   prompts p
                LEFT JOIN sessions s USING (session_id)
                WHERE  p.repo_path = ?
                  AND  (p.committed = 0 OR p.commit_hash IN ({placeholders}))
                ORDER  BY p.timestamp ASC
            """
            params = (repo_path, *recent)
        else:
            sql = """
                SELECT p.*, s.started_at AS session_started
                FROM   prompts p
                LEFT JOIN sessions s USING (session_id)
                WHERE  p.repo_path = ? AND p.committed = 0
                ORDER  BY p.timestamp ASC
            """
            params = (repo_path,)
        return conn.execute(sql, params).fetchall()
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
_DEFAULT_BATCH_WINDOW = 10   # minutes
_DEFAULT_MAX_PROMPT_LINES = 40


def _load_setting(key: str, default: int) -> int:
    """Read one integer setting from the config file. Falls back if absent or malformed."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        return int(cfg.get("settings", {}).get(key, default))
    except Exception:
        return default


def _load_threshold() -> int:
    return _load_setting("verbose_threshold", _DEFAULT_THRESHOLD)


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
    # Collapse to a single line first. Prompts can be multi-line (pasted text,
    # tool notifications); one prompt must stay one line or the block's shape —
    # and anything read off it — is wrong.
    text = " ".join((text or "").split())
    return text[:limit - 3] + "..." if len(text) > limit else text


def build_provenance_block(repo_path: str) -> str:
    """Generate the provenance block for a commit message.

    ≤ threshold prompts  →  every prompt verbatim, grouped by session
    >  threshold prompts →  every prompt still listed, shorter and capped
    Either way the block is an audit record: the prompts themselves, not a
    sample of them. Full detail stays queryable via `get_session_summary`.

    The block is plain text, deliberately not "#" comments — git's `strip`
    cleanup (any editor-based commit) would silently delete a comment block.
    """
    prompts = get_prompts_for_commit(repo_path, _load_setting("batch_window_minutes", _DEFAULT_BATCH_WINDOW))
    # Filter on read as well as on write: rows recorded before the write-side
    # filter existed stay in the database as history, but never reach a commit.
    prompts = [p for p in prompts if not is_meta_prompt(p["prompt_text"])]
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

    lines = ["", "── AI Provenance ──────────────────────────────────────────", ""]

    if total <= threshold:
        # ── Verbose: every prompt, generous truncation ───────────────────
        for idx, (sid, data) in enumerate(sessions.items(), 1):
            started = _fmt_ts(data["started"])
            n = len(data["prompts"])
            lines.append(f"Session {idx}  ({started}, id: {sid[:8]}, {n} prompt{'s' if n > 1 else ''})")
            for p in data["prompts"]:
                lines.append(f"  • {_truncate(p['prompt_text'])}")
            lines.append("")
    else:
        # ── Long: still every prompt, tighter and capped ─────────────────
        dur = _duration_str(prompts[0]["timestamp"], prompts[-1]["timestamp"])
        span = f" over {dur}" if dur else ""
        lines.append(f"{total} prompts · {len(sessions)} session{'s' if len(sessions) > 1 else ''}{span}")
        lines.append("")

        max_lines = _load_setting("max_prompt_lines", _DEFAULT_MAX_PROMPT_LINES)
        shown = 0
        for idx, (sid, data) in enumerate(sessions.items(), 1):
            started = _fmt_ts(data["started"])
            n = len(data["prompts"])
            lines.append(f"Session {idx}  ({started}, id: {sid[:8]}, {n} prompts)")
            for p in data["prompts"]:
                if shown >= max_lines:
                    break
                lines.append(f"  • {_truncate(p['prompt_text'], 100)}")
                shown += 1
            lines.append("")
            if shown >= max_lines:
                break

        if shown < total:
            lines.append(f"(+{total - shown} more prompts — call get_session_summary in Claude)")
            lines.append("")

    # Files line — always show, cap at 8 to stay readable
    if git_files:
        if len(git_files) <= 8:
            files_str = ", ".join(git_files)
        else:
            files_str = ", ".join(git_files[:8]) + f" (+{len(git_files) - 8} more)"
        lines.append(f"Files: {files_str}")
        lines.append("")

    lines.append("─────────────────────────────────────────────────────────")
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
