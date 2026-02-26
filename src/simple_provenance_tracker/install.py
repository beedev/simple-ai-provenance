"""
provenance-setup — one-command installer for simple-ai-provenance.

After `pip install simple-ai-provenance`, run:
    provenance-setup

This script:
  1. Creates the default config file
  2. Registers the UserPromptSubmit hook in Claude Code settings
  3. Registers the MCP server in Claude Desktop config
  4. Installs global git hooks (prepare-commit-msg, post-commit)
  5. Verifies the installation
"""

import json
import os
import platform
import stat
import subprocess
import sys
from pathlib import Path


# ── Resolved at install time ──────────────────────────────────────────────────
PYTHON = sys.executable  # The Python that has our package installed

# ── Standard paths ────────────────────────────────────────────────────────────
CLAUDE_SETTINGS   = Path.home() / ".claude" / "settings.json"
PROVENANCE_CONFIG = Path.home() / ".claude" / "simple-ai-provenance-config.json"
GIT_HOOKS_DIR     = Path.home() / ".config" / "git" / "hooks"

# Claude Desktop config differs by OS
_DESKTOP_PATHS = {
    "Darwin":  Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    "Linux":   Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
    "Windows": Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
}
CLAUDE_DESKTOP = _DESKTOP_PATHS.get(platform.system())


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _mark_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# ── Setup steps ───────────────────────────────────────────────────────────────

def setup_config() -> None:
    """Write default config if not present; preserve existing values."""
    defaults = {"settings": {"verbose_threshold": 5}}
    if PROVENANCE_CONFIG.exists():
        existing = _load_json(PROVENANCE_CONFIG)
        # Merge: keep user values, fill in any missing keys
        existing.setdefault("settings", {})
        existing["settings"].setdefault("verbose_threshold", 5)
        _save_json(PROVENANCE_CONFIG, existing)
        print(f"  ✓ Config preserved: {PROVENANCE_CONFIG}")
    else:
        _save_json(PROVENANCE_CONFIG, defaults)
        print(f"  ✓ Config created:   {PROVENANCE_CONFIG}")


def setup_claude_hook() -> None:
    """Register UserPromptSubmit and PostToolUse hooks in ~/.claude/settings.json."""
    cfg = _load_json(CLAUDE_SETTINGS)
    cfg.setdefault("hooks", {})

    # ── UserPromptSubmit ──────────────────────────────────────────────────────
    cfg["hooks"].setdefault("UserPromptSubmit", [])
    prompt_command = f"{PYTHON} -m simple_provenance_tracker.hook_record_prompt"

    prompt_found = False
    for block in cfg["hooks"]["UserPromptSubmit"]:
        for h in block.get("hooks", []):
            if "simple_provenance_tracker.hook_record_prompt" in h.get("command", ""):
                if h["command"] != prompt_command:
                    h["command"] = prompt_command
                    print(f"  ✓ UserPromptSubmit hook updated (new Python path)")
                else:
                    print(f"  ✓ UserPromptSubmit hook already registered")
                prompt_found = True
                break

    if not prompt_found:
        cfg["hooks"]["UserPromptSubmit"].insert(0, {
            "hooks": [{"type": "command", "command": prompt_command, "timeout": 5}]
        })
        print(f"  ✓ UserPromptSubmit hook registered")

    # ── PostToolUse ───────────────────────────────────────────────────────────
    cfg["hooks"].setdefault("PostToolUse", [])
    post_command = f"{PYTHON} -m simple_provenance_tracker.hook_post_tool"
    post_matcher = "Write|Edit|MultiEdit|NotebookEdit"

    post_found = False
    for block in cfg["hooks"]["PostToolUse"]:
        for h in block.get("hooks", []):
            if "simple_provenance_tracker.hook_post_tool" in h.get("command", ""):
                if h["command"] != post_command:
                    h["command"] = post_command
                    print(f"  ✓ PostToolUse hook updated (new Python path)")
                else:
                    print(f"  ✓ PostToolUse hook already registered")
                post_found = True
                break

    if not post_found:
        cfg["hooks"]["PostToolUse"].insert(0, {
            "matcher": post_matcher,
            "hooks": [{"type": "command", "command": post_command, "timeout": 5}]
        })
        print(f"  ✓ PostToolUse hook registered")

    _save_json(CLAUDE_SETTINGS, cfg)


def setup_mcp_server() -> None:
    """Register MCP server in Claude Desktop config."""
    if CLAUDE_DESKTOP is None:
        print(f"  ⚠ Unsupported OS for Claude Desktop: {platform.system()}")
        return
    if not CLAUDE_DESKTOP.parent.exists():
        print(f"  ⚠ Claude Desktop not found at {CLAUDE_DESKTOP.parent} — skipping")
        return

    cfg = _load_json(CLAUDE_DESKTOP)
    cfg.setdefault("mcpServers", {})
    cfg["mcpServers"]["simple-ai-provenance"] = {
        "command": PYTHON,
        "args": ["-m", "simple_provenance_tracker.mcp_server"],
    }
    _save_json(CLAUDE_DESKTOP, cfg)
    print(f"  ✓ MCP server registered in {CLAUDE_DESKTOP}")


def setup_git_hooks() -> None:
    """Write prepare-commit-msg and post-commit into the global hooks dir."""
    GIT_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

    helper = f"{PYTHON} -m simple_provenance_tracker.git_hooks_helper"

    prepare = GIT_HOOKS_DIR / "prepare-commit-msg"
    prepare.write_text(
        f"""#!/usr/bin/env bash
# simple-ai-provenance: append provenance block to commit message
# $1=commit-msg-file  $2=commit-source (merge/squash/commit → skip)
case "${{2:-}}" in merge|squash|commit) exit 0 ;; esac
REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
{helper} prepare-commit-msg "$1" "$REPO"
# Pass through to repo-level hook if present
[[ -x "$REPO/.git/hooks/prepare-commit-msg.local" ]] && \\
    "$REPO/.git/hooks/prepare-commit-msg.local" "$@"
exit 0
""",
        encoding="utf-8",
    )
    _mark_executable(prepare)

    post = GIT_HOOKS_DIR / "post-commit"
    post.write_text(
        f"""#!/usr/bin/env bash
# simple-ai-provenance: mark prompts as committed
REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HASH="$(git rev-parse HEAD 2>/dev/null)"
{helper} post-commit "$REPO" "$HASH"
[[ -x "$REPO/.git/hooks/post-commit.local" ]] && "$REPO/.git/hooks/post-commit.local"
exit 0
""",
        encoding="utf-8",
    )
    _mark_executable(post)

    subprocess.run(
        ["git", "config", "--global", "core.hooksPath", str(GIT_HOOKS_DIR)],
        check=True,
        capture_output=True,
    )
    print(f"  ✓ Git hooks installed: {GIT_HOOKS_DIR}")


def verify() -> None:
    """Quick sanity check."""
    try:
        from simple_provenance_tracker import database as db
        db.init_db()
        print(f"  ✓ Database: {db.DB_PATH}")
    except Exception as e:
        print(f"  ✗ Database error: {e}")

    for name in ("prepare-commit-msg", "post-commit"):
        p = GIT_HOOKS_DIR / name
        ok = p.exists() and os.access(p, os.X_OK)
        print(f"  {'✓' if ok else '✗'} Git hook: {name}")

    hook_ok = CLAUDE_SETTINGS.exists() and "hook_record_prompt" in CLAUDE_SETTINGS.read_text()
    print(f"  {'✓' if hook_ok else '✗'} Claude hook: UserPromptSubmit")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("simple-ai-provenance setup")
    print(f"Python: {PYTHON}")
    print()

    print("[1/4] Config file")
    setup_config()

    print("[2/4] Claude Code hook  (prompt auto-capture)")
    setup_claude_hook()

    print("[3/4] Claude Desktop    (MCP tools)")
    setup_mcp_server()

    print("[4/4] Git hooks         (commit annotation)")
    setup_git_hooks()

    print()
    print("Verification")
    verify()

    print()
    print("✅  Done. Restart Claude Code and Claude Desktop to activate.")
    print()
    print(f"    Config : {PROVENANCE_CONFIG}")
    print(f"    DB     : {Path.home() / '.claude' / 'provenance' / 'provenance.db'}")
    print()
    print("    To change the verbose threshold (default 5):")
    print("      provenance-setup --threshold 10")
    print("    Or call the MCP tool: configure verbose_threshold=10")


if __name__ == "__main__":
    main()
