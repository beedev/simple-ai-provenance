"""MCP Server for AI Provenance Tracking."""

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio

from .mcp_tools import MCPToolHandlers


app = Server("simple-ai-provenance")
tool_handlers = MCPToolHandlers()


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_session_summary",
            description=(
                "Get a summary of what was done in a session: prompts sent, "
                "files touched, tools used. Defaults to the most recent session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session ID to summarise. Omit for the most recent session.",
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Git repo path. Auto-detects from cwd if omitted.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_uncommitted_work",
            description=(
                "Get all AI prompts and git file changes since the last commit. "
                "Use this before committing to see what provenance to include."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Git repo path. Auto-detects from cwd if omitted.",
                    },
                },
            },
        ),
        types.Tool(
            name="generate_commit_context",
            description=(
                "Generate a formatted provenance block for a commit message. "
                "Lists each prompt by session, plus files changed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "commit_message": {
                        "type": "string",
                        "description": "Your base commit message. Provenance is appended below it.",
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Git repo path. Auto-detects from cwd if omitted.",
                    },
                },
            },
        ),
        types.Tool(
            name="mark_committed",
            description=(
                "Mark all uncommitted prompts for this repository as committed. "
                "Call this after running git commit."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "commit_hash": {
                        "type": "string",
                        "description": "The git commit hash. Auto-reads HEAD if omitted.",
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Git repo path. Auto-detects from cwd if omitted.",
                    },
                },
            },
        ),
        types.Tool(
            name="list_sessions",
            description="List recent sessions recorded for this repository with prompt counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Git repo path. Auto-detects from cwd if omitted.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of sessions to return (default 10).",
                        "default": 10,
                    },
                },
            },
        ),
        types.Tool(
            name="configure",
            description=(
                "Get or set provenance settings. "
                "Call with no arguments to see current config. "
                "Pass verbose_threshold to change when commit messages switch from verbose to condensed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "verbose_threshold": {
                        "type": "integer",
                        "description": (
                            "Prompts per commit below which every prompt is shown verbatim. "
                            "Above this count the message shows a condensed summary. Default: 5."
                        ),
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_session_summary":
        return await tool_handlers.handle_get_session_summary(arguments)
    elif name == "get_uncommitted_work":
        return await tool_handlers.handle_get_uncommitted_work(arguments)
    elif name == "generate_commit_context":
        return await tool_handlers.handle_generate_commit_context(arguments)
    elif name == "mark_committed":
        return await tool_handlers.handle_mark_committed(arguments)
    elif name == "list_sessions":
        return await tool_handlers.handle_list_sessions(arguments)
    elif name == "configure":
        return await tool_handlers.handle_configure(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="simple-ai-provenance",
                server_version="3.0.0",
                capabilities={},
            ),
        )


def run() -> None:
    """Sync entry point for pip-installed console script."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    run()
