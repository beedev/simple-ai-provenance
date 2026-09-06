#!/usr/bin/env python3
"""Which recorded lines are not something the human typed.

Claude Code's UserPromptSubmit hook fires for more than typed prompts: the
harness re-enters the session with task notifications, subagent messages and
local command output. Those are machine traffic. Recording them as prompts
inflates the audit trail and puts noise into commit messages.

Deliberately NOT filtered:
  • `<channel ...>` — a real message the user sent from Telegram or similar.
  • `/slash-commands` — the user typed those.

Kept stdlib-only and dependency-free: both the recording hook and the git
hooks import it, and neither may ever crash.
"""

import re

# Opening tags that mark harness traffic. Matched by tag name, because these
# carry attributes in practice (`<agent-message from="...">`), so a plain
# prefix match silently misses them.
META_TAGS = (
    "task-notification",      # harness re-entry when a background task ends
    "agent-message",          # a subagent or teammate speaking, not the user
    "local-command-stdout",   # output of a local command, echoed back
    "system-reminder",        # injected context, never typed
    "command-name",           # slash-command expansion metadata
)

META_LITERALS = (
    "[Request interrupted",
    "[Skipping",
    "The user doesn't want to proceed",
)

_TAG_RE = re.compile(r"<(?:%s)(?:\s|>|/)" % "|".join(META_TAGS), re.IGNORECASE)


def is_meta_prompt(text: str) -> bool:
    """True when `text` is harness traffic rather than user input."""
    if not text or not text.strip():
        return True
    head = text.lstrip()
    return head.startswith(META_LITERALS) or bool(_TAG_RE.match(head))
