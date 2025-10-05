"""Git hooks for automatic AI provenance consolidation."""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from .interceptor import get_interceptor


def install_hooks(repo_path: str) -> bool:
    """Install git hooks for automatic AI provenance tracking."""
    hooks_dir = Path(repo_path) / ".git" / "hooks"
    
    if not hooks_dir.exists():
        print(f"❌ Git hooks directory not found: {hooks_dir}")
        return False
    
    # Create prepare-commit-msg hook
    hook_file = hooks_dir / "prepare-commit-msg"
    
    hook_content = f'''#!/usr/bin/env python3
"""Git hook to automatically consolidate AI provenance into commit messages."""

import sys
import asyncio
import os
sys.path.insert(0, "{Path(__file__).parent.parent / 'src'}")

from mcp_ai_commit.interceptor import get_interceptor


async def enhance_commit_message():
    """Enhance commit message with AI provenance from database."""
    if len(sys.argv) < 2:
        return
    
    commit_msg_file = sys.argv[1]
    commit_source = sys.argv[2] if len(sys.argv) > 2 else ""
    
    # Skip if this is a merge commit or similar
    if commit_source in ["merge", "squash", "commit"]:
        return
    
    # Read current commit message
    with open(commit_msg_file, 'r') as f:
        original_message = f.read().strip()
    
    # Skip if message is empty or just comments
    if not original_message or original_message.startswith('#'):
        return
    
    try:
        # Get current repository path
        repo_path = os.getcwd()
        
        # Consolidate AI interactions from database
        interceptor = get_interceptor()
        enhanced_message = await interceptor.consolidate_for_commit(repo_path, original_message)
        
        # Write enhanced message back to file
        if enhanced_message != original_message:
            with open(commit_msg_file, 'w') as f:
                f.write(enhanced_message)
            print("🤖 Enhanced commit message with AI provenance")
        
    except Exception as e:
        print(f"⚠️ Warning: Could not enhance commit with AI provenance: {{e}}")
        # Don't fail the commit, just warn


if __name__ == "__main__":
    asyncio.run(enhance_commit_message())
'''
    
    # Write hook file
    with open(hook_file, 'w') as f:
        f.write(hook_content)
    
    # Make executable
    os.chmod(hook_file, 0o755)
    
    print(f"✅ Installed git hook: {hook_file}")
    return True


def uninstall_hooks(repo_path: str) -> bool:
    """Remove AI provenance git hooks."""
    hooks_dir = Path(repo_path) / ".git" / "hooks"
    hook_file = hooks_dir / "prepare-commit-msg"
    
    if hook_file.exists():
        hook_file.unlink()
        print(f"✅ Removed git hook: {hook_file}")
        return True
    else:
        print(f"ℹ️ Hook not found: {hook_file}")
        return False


async def test_consolidation(repo_path: str, test_message: str) -> str:
    """Test the consolidation process."""
    interceptor = get_interceptor()
    return await interceptor.consolidate_for_commit(repo_path, test_message)