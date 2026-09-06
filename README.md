# simple-ai-provenance

Track every AI prompt you send in Claude Code, annotate git commits with what was asked, and query the full history of any session.

## What it does

- **Auto-captures every prompt** you send in Claude Code via a hook — no manual steps
- **Annotates commits** with the prompts that produced the code, via global git hooks
- **Answers "what did I do in this session?"** through MCP tools callable inside Claude
- **Generates PR descriptions** with the full AI audit trail across every commit on the branch
- **Tracks cross-repo work** — if Claude is opened in one repo but edits files in another, prompts follow the files
- **Stays compact** — commit messages switch from verbose (all prompts) to condensed (summary) above a configurable threshold

## Install

```bash
pip install simple-ai-provenance
provenance-setup
```

Then **restart Claude Code and Claude Desktop**.

That's it. Every prompt from that point forward is recorded automatically.

## How it works

```
You type a prompt
    ↓
UserPromptSubmit hook fires → written to ~/.claude/provenance/provenance.db
    ↓
Claude writes/edits files
    ↓
PostToolUse hook fires → cross-repo reference stored if files are in a different repo
    ↓
git commit -m "fix: ..."
    ↓
prepare-commit-msg hook appends AI provenance block
    ↓
post-commit hook marks those prompts as committed
```

### Commit message (≤ 5 prompts — verbose)

```
fix: auth bug

── AI Provenance ──────────────────────────────────────────

Session 1  (2026-02-26 14:30, id: a1b2c3d4, 3 prompts)
  • fix the auth bug in login.py
  • add error handling for the edge cases
  • write unit tests for the new endpoints

Files: src/auth/login.py, tests/test_auth.py

─────────────────────────────────────────────────────────
```

### Commit message (> 5 prompts — long form)

Above the threshold the block stays complete — every prompt is still listed,
just tighter, and capped by `max_prompt_lines`.

```
refactor: connection pooling

── AI Provenance ──────────────────────────────────────────

12 prompts · 2 sessions over 1h 23m

Session 1  (09:00, id: a1b2c3d4, 5 prompts)
  • refactor the database connection pooling module
  • pool should be lazy, not built at import time
  • ... (each prompt on its own line)

Session 2  (10:30, id: e5f6g7h8, 7 prompts)
  • add retry logic with exponential backoff
  • ...

(+2 more prompts — call get_session_summary in Claude)

Files: src/db/pool.py, src/db/retry.py (+3 more)

─────────────────────────────────────────────────────────
```

The block is plain text and is stored in the commit message. Earlier versions
prefixed every line with `#`, which made the block's survival depend on how the
commit was made: `git commit -m` keeps comment lines (cleanup mode
`whitespace`), while any editor-based commit deletes them (cleanup mode
`strip`). An audit trail that disappears depending on how you commit is not an
audit trail, so as of 3.2.0 the block is written as ordinary message text.

### Commits made in a batch

One piece of work is often split into several commits made seconds apart.
Provenance is not consumed by the first of them: a commit also picks up the
prompts attached to commits made in the same repo within `batch_window_minutes`
(default 10), so every commit in the burst carries the same block.

## MCP Tools

Once installed, these tools are available inside any Claude session:

| Tool | What it does |
|---|---|
| `get_session_summary` | Prompts + files touched + tools used for a session |
| `get_uncommitted_work` | All prompts since last commit, grouped by session |
| `generate_commit_context` | Formatted provenance block for a commit message |
| `generate_pr_description` | Full AI audit trail across all commits on the current branch |
| `mark_committed` | Mark pending prompts as committed (auto-called by git hook) |
| `list_sessions` | Recent sessions with prompt counts |
| `configure` | Get or set config (e.g. `verbose_threshold`) |

## Configuration

Config lives at `~/.claude/simple-ai-provenance-config.json`:

```json
{
  "settings": {
    "verbose_threshold": 5,
    "batch_window_minutes": 10,
    "max_prompt_lines": 40
  }
}
```

| Setting | Default | What it does |
|---|---|---|
| `verbose_threshold` | 5 | At or below this many prompts, the block uses the roomier verbose layout |
| `batch_window_minutes` | 10 | Commits made within this window share provenance instead of the first one consuming it |
| `max_prompt_lines` | 40 | Most prompt lines printed in one block; the rest are summarised as `+N more` |

Prompts that are not user input — harness task notifications, subagent messages,
local command output, system reminders — are filtered out at record time and
again when a block is built, so entries recorded by earlier versions never reach
a commit message.

Change it via the MCP tool inside Claude:

```
configure verbose_threshold=10
```

Or directly edit the JSON file.

## Requirements

- Python 3.9+
- Claude Code (Claude CLI)
- Claude Desktop (optional — for MCP tools in the desktop app)
- Git

## PR integration

`sap-pr` wraps `gh pr create` with the AI provenance block pre-filled in the body:

```bash
cd your-repo
sap-pr                        # gh prompts you interactively for title etc.
sap-pr --title "feat: auth"   # skip the interactive title prompt
sap-pr --base develop         # diff against a branch other than main
sap-pr --dry-run              # preview the body without creating the PR
```

The generated PR body lists every AI prompt grouped by session, across all commits on the branch.

## How sessions are scoped

Each Claude Code session is scoped to the git repository detected from the working directory. Prompts from different projects never mix.

```
Session in ~/projects/api  → recorded under repo /Users/you/projects/api
Session in ~/projects/web  → recorded under repo /Users/you/projects/web
```

**Cross-repo tracking**: if Claude is opened in `workspace/` but edits files in `workspace/my-service/`, the `PostToolUse` hook detects the file's actual git root and stores a cross-reference. Running `sap-pr` inside `my-service/` will include those prompts.

## Troubleshooting

### Windows

**`pip` or `provenance-setup` not found**

If `pip install simple-ai-provenance` fails or `provenance-setup` is not recognized:

```powershell
# Use the Python launcher (ships with Python for Windows)
py -m pip install simple-ai-provenance
py -m simple_provenance_tracker.install
```

Ensure Python is in your PATH. The Windows Python installer has an "Add to PATH" checkbox — if you missed it, re-run the installer and enable it.

**Cannot modify Claude settings**

If `provenance-setup` reports it could not write `settings.json`:

1. Close Claude Code completely
2. Re-run `provenance-setup` (or `py -m simple_provenance_tracker.install`)

Claude Code may lock `~/.claude/settings.json` while running.

**MCP server not listed in Claude Code**

Use the absolute Python path in your MCP config. Find it with:

```powershell
py -c "import sys; print(sys.executable)"
```

Then in `~/.claude.json` (or `%USERPROFILE%\.claude.json`):

```json
{
  "mcpServers": {
    "simple-ai-provenance": {
      "command": "C:/Users/YOU/AppData/Local/Programs/Python/Python311/python.exe",
      "args": ["-m", "simple_provenance_tracker.mcp_server"]
    }
  }
}
```

**Git hooks not firing**

Ensure Git for Windows is installed. Verify the hooks path:

```powershell
git config --global core.hooksPath
# Should show: C:\Users\YOU\.config\git\hooks
```

### macOS

**`simple-ai-provenance: command not found`**

The CLI may be installed into a Python `bin/` directory that isn't in your shell's PATH. Find and add it:

```bash
# Find where it was installed
python3 -c "import sys; print(sys.executable)"
# e.g. /Library/Frameworks/Python.framework/Versions/3.11/bin/python3

# Add the bin directory to your shell profile
echo 'export PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

If your active shell is **bash** (not zsh), also add to `~/.bash_profile` and `~/.bashrc`.

**MCP server not listed in Claude Code**

Register globally with the absolute Python path in `~/.claude.json`:

```json
{
  "mcpServers": {
    "simple-ai-provenance": {
      "command": "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
      "args": ["-m", "simple_provenance_tracker.mcp_server"]
    }
  }
}
```

Validate JSON: `python3 -m json.tool ~/.claude.json >/dev/null && echo OK`

Then restart Claude Code.

### General

If MCP tools still don't appear after setup, the two most common checks are:

1. Can the CLI be found? (`which simple-ai-provenance` on macOS, `where simple-ai-provenance` on Windows)
2. Is the Claude config valid JSON? (`python3 -m json.tool ~/.claude.json`)

## Uninstall

```bash
# Remove git hooks
git config --global --unset core.hooksPath

# Remove the UserPromptSubmit block from ~/.claude/settings.json

# Remove the simple-ai-provenance entry from Claude Desktop config

# Remove data (optional)
rm -rf ~/.claude/provenance/
rm ~/.claude/simple-ai-provenance-config.json

pip uninstall simple-ai-provenance
```

## License

AGPL-3.0-or-later
