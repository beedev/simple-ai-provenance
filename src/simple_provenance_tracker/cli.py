"""CLI entry point: sap-pr — create a GitHub PR with AI provenance pre-filled."""

import argparse
import os
import subprocess
import sys

from . import database as db
from .mcp_tools import _detect_repo, build_pr_body


def pr_create_main() -> None:
    """sap-pr: wraps `gh pr create` with AI provenance pre-filled in the body."""
    parser = argparse.ArgumentParser(
        prog="sap-pr",
        description="Create a GitHub PR with AI provenance pre-filled in the body.",
        add_help=True,
    )
    parser.add_argument(
        "--base",
        default="main",
        metavar="BRANCH",
        help="Base branch to diff against (default: main)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        metavar="PATH",
        help="Repo path (auto-detected from cwd if omitted)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated PR body and exit without calling gh",
    )

    # parse_known_args so any extra flags (--title, --assignee, etc.) pass through to gh
    args, extra_gh_args = parser.parse_known_args()

    repo_path = _detect_repo(args.repo or os.getcwd())
    body = build_pr_body(repo_path, args.base)

    if args.dry_run:
        print(body)
        return

    cmd = ["gh", "pr", "create", "--body", body] + extra_gh_args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)
