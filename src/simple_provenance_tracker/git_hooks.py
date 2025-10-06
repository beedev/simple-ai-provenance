#!/usr/bin/env python3
"""Git hooks for automatic AI conversation capture and commit enhancement."""

import asyncio
import os
import sys
import json
from pathlib import Path
from typing import List, Optional

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simple_provenance_tracker.database import DatabaseManager, get_database


async def enhance_commit_message(commit_msg_file: str, repo_path: str) -> bool:
    """
    Enhance commit message with AI conversation provenance.
    
    Args:
        commit_msg_file: Path to the commit message file
        repo_path: Repository path
        
    Returns:
        True if message was enhanced, False otherwise
    """
    try:
        # Read current commit message
        with open(commit_msg_file, 'r') as f:
            original_message = f.read().strip()
        
        # Skip if this is a merge commit or already has AI provenance
        if (original_message.startswith('Merge ') or 
            '🤖 AI-Generated Content:' in original_message):
            return False
        
        # Get database manager
        db = await get_database()
        
        # Get uncommitted conversations for this repo
        conversations = await db.get_uncommitted_executions(repo_path)
        
        if not conversations:
            print("ℹ️  No AI conversations to include in commit", file=sys.stderr)
            return False
        
        # Build enhanced commit message
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
        
        # Write enhanced message back to file
        enhanced_message = "\n".join(enhanced_lines)
        with open(commit_msg_file, 'w') as f:
            f.write(enhanced_message)
        
        # Store conversation IDs for post-commit hook
        temp_file = os.path.join(repo_path, '.git', 'AI_CONVERSATIONS_TO_MARK')
        conversation_ids = [str(conv.exec_id) for conv in conversations]
        with open(temp_file, 'w') as f:
            json.dump({
                'conversation_ids': conversation_ids,
                'enhanced_message': enhanced_message
            }, f)
        
        print(f"✅ Enhanced commit with {len(conversations)} AI conversations", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ Error enhancing commit message: {e}", file=sys.stderr)
        return False


async def mark_conversations_committed(repo_path: str, commit_hash: str) -> bool:
    """
    Mark conversations as committed after successful commit.
    
    Args:
        repo_path: Repository path
        commit_hash: Git commit hash
        
    Returns:
        True if conversations were marked, False otherwise
    """
    try:
        temp_file = os.path.join(repo_path, '.git', 'AI_CONVERSATIONS_TO_MARK')
        
        if not os.path.exists(temp_file):
            return False
        
        # Read conversation data
        with open(temp_file, 'r') as f:
            data = json.load(f)
        
        conversation_ids = data['conversation_ids']
        enhanced_message = data['enhanced_message']
        
        # Get database manager
        db = await get_database()
        
        # Mark conversations as committed
        await db.mark_executions_committed(conversation_ids, commit_hash, enhanced_message)
        
        # Clean up temp file
        os.remove(temp_file)
        
        print(f"✅ Marked {len(conversation_ids)} conversations as committed", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ Error marking conversations as committed: {e}", file=sys.stderr)
        return False


def prepare_commit_msg_hook():
    """Git prepare-commit-msg hook entry point."""
    if len(sys.argv) < 2:
        print("Usage: prepare-commit-msg <commit-msg-file> [commit-source] [commit-sha]", file=sys.stderr)
        sys.exit(1)
    
    commit_msg_file = sys.argv[1]
    repo_path = os.getcwd()
    
    # Run async enhancement
    try:
        asyncio.run(enhance_commit_message(commit_msg_file, repo_path))
    except Exception as e:
        print(f"❌ Hook failed: {e}", file=sys.stderr)
        # Don't fail the commit on hook errors
        sys.exit(0)


def post_commit_hook():
    """Git post-commit hook entry point."""
    repo_path = os.getcwd()
    
    try:
        # Get the commit hash
        import subprocess
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, text=True, check=True)
        commit_hash = result.stdout.strip()
        
        # Mark conversations as committed
        asyncio.run(mark_conversations_committed(repo_path, commit_hash))
    except Exception as e:
        print(f"❌ Post-commit hook failed: {e}", file=sys.stderr)
        # Don't fail on hook errors


def install_git_hooks(repo_path: str = ".") -> bool:
    """
    Install git hooks for AI conversation tracking.
    
    Args:
        repo_path: Repository path
        
    Returns:
        True if hooks were installed successfully
    """
    try:
        hooks_dir = os.path.join(repo_path, '.git', 'hooks')
        
        if not os.path.exists(hooks_dir):
            print(f"❌ Git hooks directory not found: {hooks_dir}", file=sys.stderr)
            return False
        
        # Create prepare-commit-msg hook
        prepare_hook_path = os.path.join(hooks_dir, 'prepare-commit-msg')
        prepare_hook_content = f"""#!/usr/bin/env python3
# AI Provenance Tracking - Prepare Commit Message Hook
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from simple_provenance_tracker.git_hooks import prepare_commit_msg_hook
prepare_commit_msg_hook()
"""
        
        with open(prepare_hook_path, 'w') as f:
            f.write(prepare_hook_content)
        os.chmod(prepare_hook_path, 0o755)
        
        # Create post-commit hook
        post_hook_path = os.path.join(hooks_dir, 'post-commit')
        post_hook_content = f"""#!/usr/bin/env python3
# AI Provenance Tracking - Post Commit Hook
import sys
sys.path.insert(0, '{Path(__file__).parent.parent}')
from simple_provenance_tracker.git_hooks import post_commit_hook
post_commit_hook()
"""
        
        with open(post_hook_path, 'w') as f:
            f.write(post_hook_content)
        os.chmod(post_hook_path, 0o755)
        
        print("✅ Git hooks installed successfully")
        print(f"   - prepare-commit-msg: {prepare_hook_path}")
        print(f"   - post-commit: {post_hook_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to install git hooks: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        repo_path = sys.argv[2] if len(sys.argv) > 2 else "."
        install_git_hooks(repo_path)
    else:
        print("Usage: python git_hooks.py install [repo_path]")