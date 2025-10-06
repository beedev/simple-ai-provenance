"""Simple MCP Server for AI Provenance Tracking using existing schema."""

import asyncio
import json
import uuid
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio

# Use local database module
from .database import DatabaseManager, AICommitExecution, get_database


app = Server("simple-ai-provenance")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available provenance tracking tools."""
    return [
        types.Tool(
            name="track_conversation",
            description="Track AI conversation for provenance (from knowledge graph)",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The AI prompt text"
                    },
                    "response_text": {
                        "type": "string", 
                        "description": "The AI response text"
                    },
                    "repo_path": {
                        "type": "string",
                        "description": "Git repository path",
                        "default": "."
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context from knowledge graph"
                    }
                },
                "required": ["prompt_text", "response_text"]
            }
        ),
        
        types.Tool(
            name="commit_with_provenance",
            description="Perform git commit with automatic AI provenance enhancement",
            inputSchema={
                "type": "object",
                "properties": {
                    "commit_message": {
                        "type": "string",
                        "description": "Original commit message"
                    },
                    "repo_path": {
                        "type": "string", 
                        "description": "Git repository path",
                        "default": "."
                    }
                },
                "required": ["commit_message"]
            }
        ),
        
        types.Tool(
            name="get_conversation_history",
            description="Get AI conversation history for a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Git repository path",
                        "default": "."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of conversations to return",
                        "default": 10
                    }
                }
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "track_conversation":
        return await handle_track_conversation(arguments)
    elif name == "commit_with_provenance":
        return await handle_commit_with_provenance(arguments)
    elif name == "get_conversation_history":
        return await handle_get_history(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_track_conversation(arguments: dict) -> list[types.TextContent]:
    """Track AI conversation in database using existing schema."""
    try:
        prompt_text = arguments["prompt_text"]
        response_text = arguments["response_text"]
        repo_path = os.path.abspath(arguments.get("repo_path", "."))
        context = arguments.get("context", {})
        
        # Get current git branch
        branch_name = _get_current_branch(repo_path)
        
        # Get database manager
        db = await get_database()
        
        # Generate execution ID
        exec_id = uuid.uuid4()
        
        # Create execution record using existing schema
        execution = AICommitExecution(
            exec_id=exec_id,
            timestamp=datetime.now(timezone.utc),
            repo_path=repo_path,
            branch_name=branch_name,
            model_provider="claude",  # Detected from knowledge graph
            model_name="sonnet-4",   # Detected from knowledge graph
            prompt_text=prompt_text,
            response_text=response_text,
            commit_message="",  # Will be set when commit happens
            files_changed=[],   # Will be populated during commit
            execution_successful=True,
            validation_passed=True,
            commit_included=False,  # Not yet included in any commit
            user_context=context,
            ai_footer=f"🤖 AI Conversation (ID: {exec_id})"
        )
        
        # Store in database
        await db.store_execution(execution)
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "exec_id": str(exec_id),
                "message": "AI conversation tracked successfully",
                "repo_path": repo_path,
                "branch": branch_name,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, indent=2)
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to track conversation: {str(e)}"
            })
        )]


async def handle_commit_with_provenance(arguments: dict) -> list[types.TextContent]:
    """Complete git commit with automatic AI provenance enhancement."""
    try:
        original_message = arguments["commit_message"]
        repo_path = os.path.abspath(arguments.get("repo_path", "."))
        
        # Get database manager
        db = await get_database()
        
        # Get all uncommitted conversations for this repo
        conversations = await db.get_uncommitted_executions(repo_path)
        
        # Build enhanced commit message automatically
        if conversations:
            enhanced_lines = [original_message, ""]
            
            if len(conversations) == 1:
                conv = conversations[0]
                enhanced_lines.extend([
                    "🤖 AI-Generated Content:",
                    f"   Prompt: {conv.prompt_text[:80]}{'...' if len(conv.prompt_text) > 80 else ''}",
                    f"   Model: {conv.model_provider}/{conv.model_name}",
                    f"   ID: {conv.exec_id}",
                    ""
                ])
            else:
                enhanced_lines.extend([
                    f"🤖 {len(conversations)} AI Conversations Included:",
                    ""
                ])
                for i, conv in enumerate(conversations[:3], 1):
                    enhanced_lines.extend([
                        f"   {i}. {conv.prompt_text[:60]}{'...' if len(conv.prompt_text) > 60 else ''}",
                        f"      ID: {conv.exec_id}",
                        ""
                    ])
                if len(conversations) > 3:
                    enhanced_lines.append(f"   ... and {len(conversations) - 3} more")
                enhanced_lines.append("")
            
            enhanced_lines.append("📊 Full provenance available in ai_commit.ai_commit_executions")
            final_message = "\n".join(enhanced_lines)
        else:
            final_message = original_message
        
        # Perform the actual git commit
        import subprocess
        try:
            # Stage all changes
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            
            # Commit with enhanced message
            result = subprocess.run(
                ["git", "commit", "-m", final_message], 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            # Get the commit hash
            commit_hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                cwd=repo_path, 
                capture_output=True, 
                text=True, 
                check=True
            )
            commit_hash = commit_hash_result.stdout.strip()
            
            # NOW mark conversations as committed
            if conversations:
                exec_ids = [str(conv.exec_id) for conv in conversations]
                await db.mark_executions_committed(exec_ids, commit_hash, final_message)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "commit_hash": commit_hash,
                    "final_message": final_message,
                    "conversations_included": len(conversations),
                    "message": f"Committed with {len(conversations)} AI conversations tracked"
                }, indent=2)
            )]
            
        except subprocess.CalledProcessError as e:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Git commit failed: {e.stderr or e.stdout}"
                })
            )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to commit with provenance: {str(e)}"
            })
        )]


async def handle_get_history(arguments: dict) -> list[types.TextContent]:
    """Get AI conversation history for a repository."""
    try:
        repo_path = os.path.abspath(arguments.get("repo_path", "."))
        limit = arguments.get("limit", 10)
        
        # Get database manager
        db = await get_database()
        
        # For now, get all conversations (we can add a method later for repo-specific history)
        from sqlalchemy import select
        async with await db.get_session() as session:
            query = select(AICommitExecution).where(
                AICommitExecution.repo_path == repo_path
            ).order_by(AICommitExecution.timestamp.desc()).limit(limit)
            
            result = await session.execute(query)
            conversations = result.scalars().all()
            
            history = []
            for conv in conversations:
                history.append({
                    "exec_id": str(conv.exec_id),
                    "timestamp": conv.timestamp.isoformat(),
                    "branch": conv.branch_name,
                    "prompt": conv.prompt_text[:100] + ("..." if len(conv.prompt_text) > 100 else ""),
                    "response": conv.response_text[:100] + ("..." if len(conv.response_text) > 100 else ""),
                    "commit_included": conv.commit_included,
                    "commit_hash": conv.final_commit_hash
                })
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "repo_path": repo_path,
                "total_conversations": len(history),
                "conversations": history
            }, indent=2)
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to get history: {str(e)}"
            })
        )]


def _get_current_branch(repo_path: str) -> str:
    """Get current git branch."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "main"


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server(app) as (read_stream, write_stream):
        await app.run(read_stream, write_stream, InitializationOptions())


if __name__ == "__main__":
    asyncio.run(main())