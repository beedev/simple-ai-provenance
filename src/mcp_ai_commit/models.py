"""Data models for AI commit generation."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator


class ModelProvider(str, Enum):
    """Supported AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class CommitStrategy(str, Enum):
    """Commit generation strategies."""
    CONVENTIONAL = "conventional"  # Conventional commits format
    SEMANTIC = "semantic"         # Semantic commit messages
    NATURAL = "natural"           # Natural language
    CUSTOM = "custom"             # User-defined template


class ValidationLevel(str, Enum):
    """File validation security levels."""
    STRICT = "strict"       # Only allowed paths, reject on violation
    WARN = "warn"          # Allow but warn on violations
    PERMISSIVE = "permissive"  # Log violations but allow


class CommitRequest(BaseModel):
    """Request for AI commit generation."""
    
    # Git context
    repo_path: str = Field(..., description="Path to git repository")
    staged_files: Optional[List[str]] = Field(None, description="Specific staged files")
    
    # AI model configuration
    model_provider: ModelProvider = Field(ModelProvider.OPENAI, description="AI model provider")
    model_name: str = Field("gpt-4", description="Specific model name")
    temperature: float = Field(0.3, ge=0.0, le=2.0, description="Model creativity")
    max_tokens: int = Field(200, ge=50, le=1000, description="Max response tokens")
    
    # Commit configuration
    strategy: CommitStrategy = Field(CommitStrategy.CONVENTIONAL, description="Commit message strategy")
    include_body: bool = Field(True, description="Include commit body")
    include_breaking_changes: bool = Field(True, description="Detect breaking changes")
    
    # Security and validation
    allowed_paths: Optional[List[str]] = Field(None, description="Allowed file paths patterns")
    validation_level: ValidationLevel = Field(ValidationLevel.STRICT, description="Validation strictness")
    
    # Provenance options
    track_provenance: bool = Field(True, description="Enable provenance tracking")
    append_ai_footer: bool = Field(True, description="Append AI execution footer")
    
    # Custom configuration
    custom_template: Optional[str] = Field(None, description="Custom commit template")
    context_instructions: Optional[str] = Field(None, description="Additional instructions")
    
    @validator('repo_path')
    def validate_repo_path(cls, v):
        """Validate repository path exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Repository path does not exist: {v}")
        if not (path / ".git").exists():
            raise ValueError(f"Not a git repository: {v}")
        return str(path.absolute())
    
    @validator('allowed_paths')
    def validate_allowed_paths(cls, v):
        """Validate allowed paths patterns."""
        if v is None:
            return v
        # Ensure patterns are valid
        import pathspec
        try:
            pathspec.PathSpec.from_lines('gitwildmatch', v)
        except Exception as e:
            raise ValueError(f"Invalid path patterns: {e}")
        return v


class FileChange(BaseModel):
    """Represents a file change."""
    
    path: str = Field(..., description="File path")
    status: str = Field(..., description="Change status (A/M/D/R)")
    additions: int = Field(0, description="Lines added")
    deletions: int = Field(0, description="Lines deleted")
    is_binary: bool = Field(False, description="Is binary file")
    
    # Validation results
    is_allowed: bool = Field(True, description="File is within allowed paths")
    validation_warnings: List[str] = Field(default_factory=list, description="Validation warnings")


class CommitResponse(BaseModel):
    """Response from AI commit generation."""
    
    # Execution tracking
    exec_id: str = Field(..., description="Unique execution ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    
    # Generated content
    commit_message: str = Field(..., description="Generated commit message")
    commit_body: Optional[str] = Field(None, description="Generated commit body")
    
    # Analysis results
    detected_type: str = Field(..., description="Detected change type")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="AI confidence")
    breaking_changes: List[str] = Field(default_factory=list, description="Detected breaking changes")
    
    # File analysis
    analyzed_files: List[FileChange] = Field(default_factory=list, description="Analyzed files")
    total_additions: int = Field(0, description="Total lines added")
    total_deletions: int = Field(0, description="Total lines deleted")
    
    # Validation results
    validation_passed: bool = Field(True, description="All validations passed")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    validation_warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    
    # Provenance
    model_used: str = Field(..., description="Model used for generation")
    prompt_tokens: int = Field(0, description="Tokens in prompt")
    completion_tokens: int = Field(0, description="Tokens in completion")
    
    # Execution state
    can_execute: bool = Field(True, description="Safe to execute commit")
    execution_blocked_reason: Optional[str] = Field(None, description="Why execution is blocked")


class ExecutionRecord(BaseModel):
    """Complete execution record for provenance."""
    
    # Identification
    exec_id: str = Field(..., description="Unique execution ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Execution timestamp")
    
    # Request context
    repo_path: str = Field(..., description="Repository path")
    branch_name: str = Field(..., description="Git branch")
    commit_hash: Optional[str] = Field(None, description="Resulting commit hash")
    
    # AI interaction
    model_provider: str = Field(..., description="AI model provider")
    model_name: str = Field(..., description="Model used")
    prompt_text: str = Field(..., description="Full prompt sent to AI")
    response_text: str = Field(..., description="Full AI response")
    
    # Execution results
    commit_message: str = Field(..., description="Final commit message")
    files_changed: List[str] = Field(default_factory=list, description="Files in commit")
    execution_successful: bool = Field(False, description="Commit executed successfully")
    
    # Metadata
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User/environment context")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance data")
    
    # AI footer appended to commit
    ai_footer: Optional[str] = Field(None, description="AI execution footer text")


class ConfigurationProfile(BaseModel):
    """Saved configuration profile."""
    
    name: str = Field(..., description="Profile name")
    description: Optional[str] = Field(None, description="Profile description")
    
    # Model defaults
    default_model_provider: ModelProvider = Field(ModelProvider.OPENAI)
    default_model_name: str = Field("gpt-4")
    default_temperature: float = Field(0.3)
    
    # Commit defaults
    default_strategy: CommitStrategy = Field(CommitStrategy.CONVENTIONAL)
    default_template: Optional[str] = Field(None)
    
    # Security defaults
    global_allowed_paths: List[str] = Field(default_factory=list)
    default_validation_level: ValidationLevel = Field(ValidationLevel.STRICT)
    
    # Feature flags
    auto_stage_files: bool = Field(False, description="Auto-stage changed files")
    require_confirmation: bool = Field(True, description="Require user confirmation")
    auto_push: bool = Field(False, description="Auto-push after commit")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)