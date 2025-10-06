#!/usr/bin/env python3
"""Manual conversation capture for Claude Code sessions."""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simple_provenance_tracker.database import get_database, AICommitExecution


async def capture_conversation_manually(prompt: str, response: str, repo_path: str = ".") -> str:
    """
    Manually capture a conversation for immediate tracking.
    
    Args:
        prompt: User's prompt/question
        response: AI's response
        repo_path: Repository path
        
    Returns:
        Execution ID of stored conversation
    """
    try:
        # Get database manager
        db = await get_database()
        
        # Get current branch
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            branch_name = result.stdout.strip() if result.returncode == 0 else "main"
        except:
            branch_name = "main"
        
        # Create execution record
        from uuid import uuid4
        exec_id = uuid4()
        
        execution = AICommitExecution(
            exec_id=exec_id,
            timestamp=datetime.now(timezone.utc),
            branch_name=branch_name,
            repo_path=os.path.abspath(repo_path),
            prompt_text=prompt,
            response_text=response,
            model_provider="claude",
            model_name="sonnet-4",
            validation_passed=True,
            commit_included=False,
            commit_message="",  # Empty until actual commit
            commit_body="",     # Empty until actual commit  
            execution_successful=False,  # Not part of any execution yet
            prompt_tokens=0,
            completion_tokens=0,
            execution_time_ms=0,
            user_context={"source": "manual_capture", "session": "claude_code"},
            ai_footer=f"🤖 Manual Capture (ID: {exec_id})"
        )
        
        # Store in database
        await db.store_execution(execution)
        
        print(f"✅ Manually captured conversation: {exec_id}")
        return str(exec_id)
        
    except Exception as e:
        print(f"❌ Failed to capture conversation: {e}")
        raise


async def capture_current_session():
    """Capture key conversations from the current development session."""
    
    conversations = [
        {
            "prompt": "How come commit info is stored when the code was not commited?",
            "response": "Great observation! You've identified an important issue. Let me examine the logic... The `enhance_commit_with_provenance` tool is incorrectly marking conversations as committed even though no actual git commit has happened. This is a logic error - the tool should only prepare the enhanced commit message, not mark anything as committed."
        },
        {
            "prompt": "even the enhance commit message should be derived as part of commit by looking at the DB and selecting all rows where commit flag is false an then consolidating the message",
            "response": "You're absolutely right! The current design is flawed. The `enhance_commit_with_provenance` tool shouldn't be a separate MCP tool at all. Instead, the enhanced commit message should be automatically generated during the actual git commit process by: 1. Looking at the database for all conversations where `commit_included=False` 2. Automatically building the enhanced message 3. Only then marking them as committed"
        },
        {
            "prompt": "Also add git hook for cleaner implementation",
            "response": "Excellent idea! Let me add git hooks for a cleaner implementation that automatically captures AI conversations during any git commit."
        },
        {
            "prompt": "git hook should trigger the ai conversation summary and added to the commit comment", 
            "response": "Perfect! Let me implement a git hook that automatically triggers AI conversation summarization and adds it to the commit message. This will make the integration seamless with VS Code commits."
        },
        {
            "prompt": "So much activity happned but the message that was captured was basic. Almost 40 files deleted and several new files added as part of initial commit - none of my prompts are also captured in DB. Is Knowledge graph interception working",
            "response": "You're absolutely right! The git hook captured an old test conversation, but none of our actual development work from this session is being captured. Let me check if the knowledge graph interception is working."
        }
    ]
    
    print("🔄 Capturing current development session conversations...")
    
    captured_ids = []
    for conv in conversations:
        try:
            exec_id = await capture_conversation_manually(
                conv["prompt"], 
                conv["response"], 
                "/Users/bharath/mcp-ai-commit"
            )
            captured_ids.append(exec_id)
        except Exception as e:
            print(f"❌ Failed to capture conversation: {e}")
    
    print(f"✅ Captured {len(captured_ids)} conversations from current session")
    return captured_ids


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "capture-session":
        asyncio.run(capture_current_session())
    else:
        print("Usage: python claude_code_conversation_capture.py capture-session")