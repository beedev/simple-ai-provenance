"""Parse Claude Code JSONL transcript files to extract session activity."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def get_jsonl_path(cwd: str, session_id: str) -> Path:
    """Construct the JSONL path for a given cwd + session_id."""
    project_folder = cwd.replace("/", "-")
    return Path.home() / ".claude" / "projects" / project_folder / f"{session_id}.jsonl"


def parse_session_activity(session_id: str, cwd: str) -> Dict[str, Any]:
    """Extract what happened in a session from its JSONL transcript.

    Returns a dict with:
        files_read      — set of file paths read
        files_written   — set of file paths written/edited
        tools_used      — {tool_name: count}
        bash_commands   — list of bash commands run (truncated)
        human_prompts   — list of {text, timestamp} for human messages
    """
    result: Dict[str, Any] = {
        "files_read": set(),
        "files_written": set(),
        "tools_used": {},
        "bash_commands": [],
        "human_prompts": [],
    }

    jsonl_path = get_jsonl_path(cwd, session_id)
    if not jsonl_path.exists():
        return result

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")

                if entry_type == "user":
                    _extract_human(entry, result)
                elif entry_type == "assistant":
                    _extract_tools(entry, result)
    except Exception:
        pass

    result["files_read"] = sorted(result["files_read"])
    result["files_written"] = sorted(result["files_written"])
    return result


def _extract_human(entry: Dict, result: Dict) -> None:
    msg = entry.get("message", {})
    ts = entry.get("timestamp", "")
    content = msg.get("content", "")

    if isinstance(content, str):
        text = content.strip()
        if text and not _is_meta(text):
            result["human_prompts"].append({"text": text, "timestamp": ts})
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "").strip()
                if text and not _is_meta(text):
                    result["human_prompts"].append({"text": text, "timestamp": ts})


def _extract_tools(entry: Dict, result: Dict) -> None:
    msg = entry.get("message", {})
    content = msg.get("content", [])
    if not isinstance(content, list):
        return

    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_use":
            continue

        name = item.get("name", "")
        inp = item.get("input", {})

        result["tools_used"][name] = result["tools_used"].get(name, 0) + 1

        if name in ("Read",):
            fp = inp.get("file_path", "")
            if fp:
                result["files_read"].add(fp)
        elif name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            fp = inp.get("file_path", "")
            if fp:
                result["files_written"].add(fp)
        elif name == "Bash":
            cmd = inp.get("command", "")
            if cmd:
                result["bash_commands"].append(cmd[:120])


def _is_meta(text: str) -> bool:
    """Return True for Claude-internal meta messages, not real user prompts."""
    prefixes = (
        "[Request interrupted",
        "The user doesn't want to proceed",
        "[Skipping",
        "<system-reminder>",
    )
    return any(text.startswith(p) for p in prefixes)
