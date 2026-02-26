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

# ── AI Provenance ──────────────────────────────────────────
#
# Session 1  (2026-02-26 14:30, id: a1b2c3d4, 3 prompts)
#   • fix the auth bug in login.py
#   • add error handling for the edge cases
#   • write unit tests for the new endpoints
#
# Files: src/auth/login.py, tests/test_auth.py
#
# ─────────────────────────────────────────────────────────
```

### Commit message (> 5 prompts — condensed)

```
refactor: connection pooling

# ── AI Provenance ──────────────────────────────────────────
#
# 12 prompts · 2 sessions over 1h 23m
#
# Session 1  (09:00, id: a1b2c3d4, 5 prompts)
# Session 2  (10:30, id: e5f6g7h8, 7 prompts)
#
# First: refactor the database connection pooling module
# Last:  add retry logic with exponential backoff
#
# Full history: call get_session_summary in Claude
# Files: src/db/pool.py, src/db/retry.py (+3 more)
#
# ─────────────────────────────────────────────────────────
```

The `#` lines are git comment lines — visible in your editor but not stored in the final commit message.

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
    "verbose_threshold": 5
  }
}
```

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
