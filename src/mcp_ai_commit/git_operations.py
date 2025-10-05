"""Git operations for AI commit execution."""

import asyncio
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import git
import subprocess


class GitOperations:
    """Handles git operations for AI commit execution."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        
        try:
            self.repo = git.Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a valid git repository: {repo_path}")
    
    async def create_commit(self, commit_message: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create a git commit with the provided message.
        
        Returns:
            Tuple of (success, commit_hash, error_message)
        """
        try:
            # Ensure we have staged changes
            if not self._has_staged_changes():
                return False, None, "No staged changes found"
            
            # Create the commit
            commit = self.repo.index.commit(commit_message)
            commit_hash = commit.hexsha
            
            return True, commit_hash, None
            
        except Exception as e:
            return False, None, str(e)
    
    async def get_staged_changes(self) -> List[Dict[str, Any]]:
        """Get information about staged changes."""
        try:
            staged_changes = []
            
            # Get staged files
            staged_files = self.repo.index.diff("HEAD", cached=True)
            
            for item in staged_files:
                change_info = {
                    "path": item.a_path or item.b_path,
                    "change_type": item.change_type,
                    "old_file": item.a_path,
                    "new_file": item.b_path,
                    "is_binary": self._is_binary_change(item)
                }
                
                # Calculate line changes for text files
                if not change_info["is_binary"]:
                    additions, deletions = await self._calculate_line_changes(item)
                    change_info["additions"] = additions
                    change_info["deletions"] = deletions
                else:
                    change_info["additions"] = 0
                    change_info["deletions"] = 0
                
                staged_changes.append(change_info)
            
            return staged_changes
            
        except Exception as e:
            raise Exception(f"Failed to get staged changes: {str(e)}")
    
    async def validate_repository_state(self) -> Tuple[bool, List[str]]:
        """Validate that the repository is in a good state for committing."""
        issues = []
        
        try:
            # Check if repo is in a detached HEAD state
            if self.repo.head.is_detached:
                issues.append("Repository is in detached HEAD state")
            
            # Check if there are merge conflicts
            if self._has_merge_conflicts():
                issues.append("Repository has unresolved merge conflicts")
            
            # Check if we're in the middle of a rebase/merge
            git_dir = self.repo_path / ".git"
            if (git_dir / "MERGE_HEAD").exists():
                issues.append("Repository is in the middle of a merge")
            if (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists():
                issues.append("Repository is in the middle of a rebase")
            
            # Check if we have staged changes
            if not self._has_staged_changes():
                issues.append("No staged changes found")
            
            # Check write permissions
            if not self._check_write_permissions():
                issues.append("No write permissions to git directory")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            issues.append(f"Repository validation error: {str(e)}")
            return False, issues
    
    async def get_repository_info(self) -> Dict[str, str]:
        """Get repository information."""
        try:
            info = {
                "repo_path": str(self.repo_path),
                "current_branch": "unknown",
                "current_commit": "unknown",
                "remote_url": "unknown",
                "is_dirty": str(self.repo.is_dirty()),
                "has_staged_changes": str(self._has_staged_changes())
            }
            
            # Get current branch
            try:
                if not self.repo.head.is_detached:
                    info["current_branch"] = self.repo.active_branch.name
                else:
                    info["current_branch"] = "detached"
            except Exception:
                info["current_branch"] = "unknown"
            
            # Get current commit
            try:
                info["current_commit"] = self.repo.head.commit.hexsha
            except Exception:
                info["current_commit"] = "unknown"
            
            # Get remote URL
            try:
                if self.repo.remotes:
                    info["remote_url"] = self.repo.remotes.origin.url
            except Exception:
                info["remote_url"] = "unknown"
            
            return info
            
        except Exception as e:
            return {
                "repo_path": str(self.repo_path),
                "error": str(e)
            }
    
    async def preview_commit(self, commit_message: str) -> Dict[str, Any]:
        """Preview what a commit would look like without executing it."""
        try:
            # Get staged changes
            staged_changes = await self.get_staged_changes()
            
            # Get repository info
            repo_info = await self.get_repository_info()
            
            # Calculate statistics
            total_files = len(staged_changes)
            total_additions = sum(change.get("additions", 0) for change in staged_changes)
            total_deletions = sum(change.get("deletions", 0) for change in staged_changes)
            
            return {
                "commit_message": commit_message,
                "repository_info": repo_info,
                "staged_changes": staged_changes,
                "statistics": {
                    "total_files": total_files,
                    "total_additions": total_additions,
                    "total_deletions": total_deletions
                },
                "can_commit": self._has_staged_changes()
            }
            
        except Exception as e:
            return {
                "error": f"Failed to preview commit: {str(e)}",
                "can_commit": False
            }
    
    def _has_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        try:
            # Check if index differs from HEAD
            return len(list(self.repo.index.diff("HEAD", cached=True))) > 0
        except Exception:
            # Might be initial commit - check if index has entries
            return len(self.repo.index.entries) > 0
    
    def _has_merge_conflicts(self) -> bool:
        """Check if there are unresolved merge conflicts."""
        try:
            # Check for unmerged paths
            unmerged = self.repo.index.unmerged_blobs()
            return len(unmerged) > 0
        except Exception:
            return False
    
    def _check_write_permissions(self) -> bool:
        """Check if we have write permissions to the git directory."""
        try:
            git_dir = self.repo_path / ".git"
            return git_dir.exists() and git_dir.is_dir() and git_dir.stat().st_mode & 0o200
        except Exception:
            return False
    
    def _is_binary_change(self, diff_item) -> bool:
        """Check if a diff item represents a binary file change."""
        try:
            # Check if either blob is binary
            if diff_item.a_blob and diff_item.a_blob.size > 0:
                sample = diff_item.a_blob.data_stream.read(1024)
                if b'\0' in sample:
                    return True
            
            if diff_item.b_blob and diff_item.b_blob.size > 0:
                sample = diff_item.b_blob.data_stream.read(1024)
                if b'\0' in sample:
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def _calculate_line_changes(self, diff_item) -> Tuple[int, int]:
        """Calculate line additions and deletions for a diff item."""
        try:
            # Use git diff to get accurate line counts
            if diff_item.change_type == 'A':  # Added file
                if diff_item.b_blob:
                    content = diff_item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                    return len(content.splitlines()), 0
                return 0, 0
            
            elif diff_item.change_type == 'D':  # Deleted file
                if diff_item.a_blob:
                    content = diff_item.a_blob.data_stream.read().decode('utf-8', errors='ignore')
                    return 0, len(content.splitlines())
                return 0, 0
            
            elif diff_item.change_type == 'M':  # Modified file
                # For modified files, we'd need to do a proper diff
                # This is a simplified calculation
                if diff_item.a_blob and diff_item.b_blob:
                    old_content = diff_item.a_blob.data_stream.read().decode('utf-8', errors='ignore')
                    new_content = diff_item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
                    
                    old_lines = len(old_content.splitlines())
                    new_lines = len(new_content.splitlines())
                    
                    # Simple approximation
                    if new_lines > old_lines:
                        return new_lines - old_lines, 0
                    elif old_lines > new_lines:
                        return 0, old_lines - new_lines
                    else:
                        # Lines count is same, assume some modifications
                        return max(1, old_lines // 10), max(1, old_lines // 10)
                
                return 0, 0
            
            else:
                return 0, 0
                
        except Exception:
            return 0, 0
    
    async def run_git_command(self, args: List[str]) -> Tuple[bool, str, str]:
        """Run a git command asynchronously."""
        try:
            # Prepare command
            cmd = ["git"] + args
            
            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            stdout_text = stdout.decode('utf-8', errors='ignore').strip()
            stderr_text = stderr.decode('utf-8', errors='ignore').strip()
            
            return success, stdout_text, stderr_text
            
        except Exception as e:
            return False, "", str(e)
    
    async def get_commit_stats(self, commit_hash: str) -> Dict[str, Any]:
        """Get statistics for a specific commit."""
        try:
            commit = self.repo.commit(commit_hash)
            
            # Get commit info
            stats = {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
                "files_changed": [],
                "total_additions": 0,
                "total_deletions": 0
            }
            
            # Get file changes
            if commit.parents:
                diffs = commit.diff(commit.parents[0])
                for diff in diffs:
                    file_info = {
                        "path": diff.a_path or diff.b_path,
                        "change_type": diff.change_type,
                        "additions": 0,
                        "deletions": 0
                    }
                    
                    # Calculate changes (simplified)
                    if not self._is_binary_change(diff):
                        additions, deletions = await self._calculate_line_changes(diff)
                        file_info["additions"] = additions
                        file_info["deletions"] = deletions
                        stats["total_additions"] += additions
                        stats["total_deletions"] += deletions
                    
                    stats["files_changed"].append(file_info)
            
            return stats
            
        except Exception as e:
            return {"error": f"Failed to get commit stats: {str(e)}"}