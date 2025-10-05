"""File validation and security for AI commit operations."""

import os
import stat
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import pathspec
import git

from .models import FileChange, ValidationLevel
from .config import get_config


class FileValidator:
    """Validates files against allowed patterns and security rules."""
    
    def __init__(self, repo_path: str, allowed_patterns: Optional[List[str]] = None):
        self.repo_path = Path(repo_path).resolve()
        self.config = get_config()
        
        # Build pattern specs
        self.allowed_spec = self._build_allowed_spec(allowed_patterns)
        self.blocked_spec = self._build_blocked_spec()
        
        # Git repository
        try:
            self.repo = git.Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a valid git repository: {repo_path}")
    
    def _build_allowed_spec(self, custom_patterns: Optional[List[str]] = None) -> pathspec.PathSpec:
        """Build pathspec for allowed file patterns."""
        patterns = []
        
        # Add global allowed patterns
        patterns.extend(self.config.security.global_allowed_patterns)
        
        # Add custom patterns if provided
        if custom_patterns:
            patterns.extend(custom_patterns)
        
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns)
    
    def _build_blocked_spec(self) -> pathspec.PathSpec:
        """Build pathspec for blocked file patterns."""
        return pathspec.PathSpec.from_lines('gitwildmatch', self.config.security.global_blocked_patterns)
    
    def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a single file against security rules.
        
        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []
        
        # Normalize path relative to repo root
        abs_path = Path(file_path)
        if abs_path.is_absolute():
            try:
                rel_path = abs_path.relative_to(self.repo_path)
            except ValueError:
                warnings.append(f"File outside repository: {file_path}")
                return False, warnings
        else:
            rel_path = Path(file_path)
        
        file_str = str(rel_path)
        
        # Check blocked patterns first (highest priority)
        if self.blocked_spec.match_file(file_str):
            warnings.append(f"File matches blocked pattern: {file_path}")
            return False, warnings
        
        # Check allowed patterns
        if not self.allowed_spec.match_file(file_str):
            warnings.append(f"File not in allowed patterns: {file_path}")
            return False, warnings
        
        # Check file permissions
        full_path = self.repo_path / rel_path
        if full_path.exists():
            file_stat = full_path.stat()
            
            # Check if file is readable
            if not os.access(full_path, os.R_OK):
                warnings.append(f"File not readable: {file_path}")
                return False, warnings
            
            # Check for suspicious permissions
            mode = file_stat.st_mode
            if mode & stat.S_ISUID or mode & stat.S_ISGID:
                warnings.append(f"File has setuid/setgid bit: {file_path}")
                return False, warnings
        
        return True, warnings
    
    def validate_file_changes(self, validation_level: ValidationLevel = ValidationLevel.STRICT) -> List[FileChange]:
        """
        Validate all staged file changes.
        
        Returns:
            List of FileChange objects with validation results
        """
        file_changes = []
        
        # Get staged files
        staged_files = []
        try:
            # Get staged changes
            staged_changes = self.repo.index.diff("HEAD", cached=True)
            for item in staged_changes:
                staged_files.append({
                    'path': item.a_path or item.b_path,
                    'change_type': item.change_type,
                    'a_blob': item.a_blob,
                    'b_blob': item.b_blob
                })
        except Exception as e:
            # Handle case where there's no HEAD (initial commit)
            staged_files = [{'path': item.path, 'change_type': 'A', 'a_blob': None, 'b_blob': None} 
                           for item in self.repo.index.entries.keys()]
        
        # Validate each file
        for file_info in staged_files:
            file_path = file_info['path']
            is_valid, warnings = self.validate_file(file_path)
            
            # Calculate file stats
            additions, deletions = self._calculate_file_changes(file_info)
            
            # Determine if file is binary
            is_binary = self._is_binary_file(file_path)
            
            file_change = FileChange(
                path=file_path,
                status=self._change_type_to_status(file_info['change_type']),
                additions=additions,
                deletions=deletions,
                is_binary=is_binary,
                is_allowed=is_valid,
                validation_warnings=warnings
            )
            
            file_changes.append(file_change)
        
        return file_changes
    
    def _calculate_file_changes(self, file_info: Dict) -> Tuple[int, int]:
        """Calculate additions and deletions for a file."""
        try:
            if file_info['change_type'] == 'A':  # Added
                return self._count_lines(file_info['b_blob']), 0
            elif file_info['change_type'] == 'D':  # Deleted
                return 0, self._count_lines(file_info['a_blob'])
            elif file_info['change_type'] == 'M':  # Modified
                # For simplicity, estimate changes
                # In a real implementation, you'd do a proper diff
                old_lines = self._count_lines(file_info['a_blob'])
                new_lines = self._count_lines(file_info['b_blob'])
                return max(0, new_lines - old_lines), max(0, old_lines - new_lines)
            else:
                return 0, 0
        except Exception:
            return 0, 0
    
    def _count_lines(self, blob) -> int:
        """Count lines in a git blob."""
        if blob is None:
            return 0
        try:
            return len(blob.data_stream.read().decode('utf-8', errors='ignore').splitlines())
        except Exception:
            return 0
    
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary."""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return False
        
        try:
            with open(full_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return False
    
    def _change_type_to_status(self, change_type) -> str:
        """Convert git change type to status string."""
        if hasattr(change_type, 'name'):
            return change_type.name
        else:
            return str(change_type)
    
    def check_file_limits(self, file_changes: List[FileChange]) -> Tuple[bool, List[str]]:
        """Check if file changes exceed configured limits."""
        errors = []
        
        # Check total file count
        if len(file_changes) > self.config.security.max_files_per_commit:
            errors.append(f"Too many files in commit: {len(file_changes)} > {self.config.security.max_files_per_commit}")
        
        # Check individual file changes
        for file_change in file_changes:
            total_changes = file_change.additions + file_change.deletions
            if total_changes > self.config.security.max_changes_per_file:
                errors.append(f"Too many changes in {file_change.path}: {total_changes} > {self.config.security.max_changes_per_file}")
        
        return len(errors) == 0, errors
    
    def validate_execution_context(self) -> Tuple[bool, List[str]]:
        """Validate the execution context (git state, permissions, etc.)."""
        errors = []
        
        # Check if repo is clean enough for commit
        if self.repo.is_dirty(untracked_files=False):
            # This is expected - we want staged changes
            pass
        
        # Check if we're in a detached HEAD state
        if self.repo.head.is_detached:
            errors.append("Repository is in detached HEAD state")
        
        # Check if we have permission to write to .git
        git_dir = self.repo_path / '.git'
        if not os.access(git_dir, os.W_OK):
            errors.append("No write permission to .git directory")
        
        # Check if there are any staged changes
        try:
            staged_changes = list(self.repo.index.diff("HEAD", cached=True))
            if not staged_changes:
                errors.append("No staged changes found")
        except Exception:
            # Might be initial commit
            if not list(self.repo.index.entries.keys()):
                errors.append("No staged changes found")
        
        return len(errors) == 0, errors
    
    def get_repository_info(self) -> Dict[str, str]:
        """Get repository information for context."""
        try:
            return {
                "repo_path": str(self.repo_path),
                "current_branch": self.repo.active_branch.name,
                "current_commit": self.repo.head.commit.hexsha,
                "remote_url": self.repo.remotes.origin.url if self.repo.remotes else "unknown"
            }
        except Exception as e:
            return {
                "repo_path": str(self.repo_path),
                "current_branch": "unknown",
                "current_commit": "unknown",
                "remote_url": "unknown",
                "error": str(e)
            }