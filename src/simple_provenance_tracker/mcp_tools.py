"""MCP tool handler implementations."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import mcp.types as types

from . import database as db
from .jsonl_parser import parse_session_activity


CONFIG_PATH = Path.home() / ".claude" / "simple-ai-provenance-config.json"
_DEFAULT_CONFIG = {"settings": {"verbose_threshold": 5}}


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return _DEFAULT_CONFIG.copy()


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def _detect_repo(path: str) -> str:
    """Walk up from path to find the git root, fallback to path itself."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return path


def _current_branch(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _git_diff_stat(repo_path: str) -> str:
    """Return git diff --stat for staged + unstaged changes."""
    try:
        r = subprocess.run(
            ["git", "diff", "--stat", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_changed_files(repo_path: str) -> List[str]:
    """Files changed since HEAD (staged + unstaged)."""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return [f for f in r.stdout.strip().splitlines() if f]
    except Exception:
        pass
    return []


def _fmt_ts(ts: str) -> str:
    """Format ISO timestamp to readable local form."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts


def _text(data: Any) -> List[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


# ─── Tool handlers ────────────────────────────────────────────────────────────

class MCPToolHandlers:

    def __init__(self):
        db.init_db()

    # ------------------------------------------------------------------
    # get_session_summary
    # ------------------------------------------------------------------
    async def handle_get_session_summary(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Summarise what was done in a session."""
        repo_path = _detect_repo(args.get("repo_path") or os.getcwd())
        session_id = args.get("session_id")

        # If no session_id, use the most recent session for this repo
        if not session_id:
            sessions = db.list_sessions(repo_path, limit=1)
            if not sessions:
                return _text({"error": "No sessions recorded for this repository yet."})
            session_id = sessions[0]["session_id"]

        session = db.get_session_info(session_id)
        if not session:
            return _text({"error": f"Session {session_id} not found in provenance database."})

        prompts = db.get_session_prompts(session_id)
        cwd = session["cwd"] or repo_path
        activity = parse_session_activity(session_id, cwd)

        summary = {
            "session_id": session_id,
            "repo_path": session["repo_path"],
            "branch": session["branch_name"],
            "started_at": _fmt_ts(session["started_at"]),
            "last_active": _fmt_ts(session["last_active"]),
            "prompt_count": len(prompts),
            "prompts": [
                {
                    "id": p["prompt_id"],
                    "timestamp": _fmt_ts(p["timestamp"]),
                    "text": p["prompt_text"],
                    "committed": bool(p["committed"]),
                    "commit_hash": p["commit_hash"],
                }
                for p in prompts
            ],
            "files_written": activity["files_written"],
            "files_read": activity["files_read"],
            "tools_used": activity["tools_used"],
            "bash_commands_sample": activity["bash_commands"][:10],
        }

        return _text(summary)

    # ------------------------------------------------------------------
    # get_uncommitted_work
    # ------------------------------------------------------------------
    async def handle_get_uncommitted_work(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """All prompts + git changes since the last commit."""
        repo_path = _detect_repo(args.get("repo_path") or os.getcwd())
        prompts = db.get_uncommitted_prompts(repo_path)

        # Group prompts by session
        sessions_seen: Dict[str, List] = {}
        for p in prompts:
            sid = p["session_id"]
            sessions_seen.setdefault(sid, []).append(p)

        session_blocks = []
        for sid, ps in sessions_seen.items():
            session_blocks.append({
                "session_id": sid,
                "started_at": _fmt_ts(ps[0]["session_started"] or ps[0]["timestamp"]),
                "prompts": [
                    {"timestamp": _fmt_ts(p["timestamp"]), "text": p["prompt_text"]}
                    for p in ps
                ],
            })

        git_files = _git_changed_files(repo_path)
        git_stat = _git_diff_stat(repo_path)

        return _text({
            "repo_path": repo_path,
            "branch": _current_branch(repo_path),
            "total_uncommitted_prompts": len(prompts),
            "sessions": session_blocks,
            "git_files_changed": git_files,
            "git_diff_stat": git_stat,
        })

    # ------------------------------------------------------------------
    # generate_commit_context
    # ------------------------------------------------------------------
    async def handle_generate_commit_context(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Generate a provenance block ready to append to a commit message."""
        repo_path = _detect_repo(args.get("repo_path") or os.getcwd())
        base_message = args.get("commit_message", "")
        prompts = db.get_uncommitted_prompts(repo_path)

        lines = []
        if base_message:
            lines.append(base_message)
            lines.append("")

        if not prompts:
            lines.append("No AI prompts tracked for this commit.")
        else:
            lines.append("## AI Provenance")
            lines.append("")

            # Group by session
            sessions_seen: Dict[str, List] = {}
            for p in prompts:
                sessions_seen.setdefault(p["session_id"], []).append(p)

            for idx, (sid, ps) in enumerate(sessions_seen.items(), 1):
                started = _fmt_ts(ps[0]["session_started"] or ps[0]["timestamp"])
                lines.append(f"**Session {idx}** ({started}, id: {sid[:8]})")
                for p in ps:
                    # Truncate long prompts to keep commit message readable
                    text = p["prompt_text"]
                    if len(text) > 120:
                        text = text[:117] + "..."
                    lines.append(f"  - {text}")
                lines.append("")

            # Git changes
            git_files = _git_changed_files(repo_path)
            if git_files:
                lines.append(f"**Files changed:** {', '.join(git_files[:20])}")
                if len(git_files) > 20:
                    lines.append(f"  ...and {len(git_files) - 20} more")
                lines.append("")

        lines.append(f"_Tracked by simple-ai-provenance | {len(prompts)} prompt(s)_")

        return [types.TextContent(type="text", text="\n".join(lines))]

    # ------------------------------------------------------------------
    # mark_committed
    # ------------------------------------------------------------------
    async def handle_mark_committed(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Mark all uncommitted prompts for a repo as committed."""
        repo_path = _detect_repo(args.get("repo_path") or os.getcwd())
        commit_hash = args.get("commit_hash", "")

        if not commit_hash:
            # Try to get HEAD hash automatically
            try:
                r = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    commit_hash = r.stdout.strip()
            except Exception:
                pass

        if not commit_hash:
            return _text({"error": "Could not determine commit hash. Provide commit_hash explicitly."})

        count = db.mark_committed(repo_path, commit_hash)
        return _text({
            "success": True,
            "commit_hash": commit_hash,
            "prompts_marked": count,
            "repo_path": repo_path,
        })

    # ------------------------------------------------------------------
    # list_sessions
    # ------------------------------------------------------------------
    async def handle_list_sessions(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """List recent sessions for a repository."""
        repo_path = _detect_repo(args.get("repo_path") or os.getcwd())
        limit = int(args.get("limit", 10))
        sessions = db.list_sessions(repo_path, limit)

        return _text({
            "repo_path": repo_path,
            "sessions": [
                {
                    "session_id": s["session_id"],
                    "branch": s["branch_name"],
                    "started_at": _fmt_ts(s["started_at"]),
                    "last_active": _fmt_ts(s["last_active"]),
                    "total_prompts": s["total_prompts"],
                    "uncommitted_prompts": s["uncommitted_prompts"] or 0,
                }
                for s in sessions
            ],
        })

    # ------------------------------------------------------------------
    # configure
    # ------------------------------------------------------------------
    async def handle_configure(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get or set provenance configuration."""
        cfg = _load_config()
        cfg.setdefault("settings", {})

        if not args:
            # Read-only: return current config
            return _text({
                "config_path": str(CONFIG_PATH),
                "settings": cfg["settings"],
            })

        changed = {}
        if "verbose_threshold" in args:
            value = int(args["verbose_threshold"])
            if value < 1:
                return _text({"error": "verbose_threshold must be ≥ 1"})
            cfg["settings"]["verbose_threshold"] = value
            changed["verbose_threshold"] = value

        if changed:
            _save_config(cfg)

        return _text({
            "config_path": str(CONFIG_PATH),
            "settings": cfg["settings"],
            "updated": changed,
        })
