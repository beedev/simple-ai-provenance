"""Configuration management for MCP AI Commit server."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv


class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="ai_commit", description="Database name")
    username: str = Field(default="postgres", description="Database username")
    password: str = Field(default="", description="Database password")
    
    # Connection pool settings
    min_connections: int = Field(default=1, description="Minimum connections in pool")
    max_connections: int = Field(default=10, description="Maximum connections in pool")
    
    # Schema configuration
    schema_name: str = Field(default="ai_commit", description="Schema name for tables")
    
    @property
    def connection_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def asyncpg_url(self) -> str:
        """Generate asyncpg connection URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class AIModelConfig(BaseModel):
    """AI model configuration."""
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_base_url: Optional[str] = Field(None, description="OpenAI base URL for custom endpoints")
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    
    # Default model settings
    default_provider: str = Field(default="openai", description="Default AI provider")
    default_model: str = Field(default="gpt-4", description="Default model name")
    default_temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Default temperature")
    default_max_tokens: int = Field(default=200, ge=50, le=2000, description="Default max tokens")
    
    # Rate limiting
    requests_per_minute: int = Field(default=60, description="API requests per minute limit")
    
    @validator('default_provider')
    def validate_provider(cls, v):
        """Validate AI provider."""
        allowed = ['openai', 'anthropic', 'local']
        if v not in allowed:
            raise ValueError(f"Provider must be one of: {allowed}")
        return v


class SecurityConfig(BaseModel):
    """Security and validation configuration."""
    
    # Default security level
    default_validation_level: str = Field(default="strict", description="Default validation level")
    
    # Global allowed paths (applied to all repos unless overridden)
    global_allowed_patterns: list[str] = Field(
        default_factory=lambda: [
            "src/**",
            "lib/**",
            "app/**",
            "components/**",
            "pages/**",
            "utils/**",
            "*.py",
            "*.js",
            "*.ts",
            "*.jsx",
            "*.tsx",
            "*.json",
            "*.md",
            "*.yml",
            "*.yaml"
        ],
        description="Global allowed file patterns"
    )
    
    # Blocked patterns (never allow)
    global_blocked_patterns: list[str] = Field(
        default_factory=lambda: [
            ".env*",
            "*.key",
            "*.pem",
            "*.p12",
            "secrets/**",
            "credentials/**",
            "private/**",
            "node_modules/**",
            ".git/**",
            "*.log"
        ],
        description="Global blocked file patterns"
    )
    
    # Execution limits
    max_files_per_commit: int = Field(default=50, description="Maximum files per commit")
    max_changes_per_file: int = Field(default=1000, description="Maximum changes per file")
    
    @validator('default_validation_level')
    def validate_level(cls, v):
        """Validate security level."""
        allowed = ['strict', 'warn', 'permissive']
        if v not in allowed:
            raise ValueError(f"Validation level must be one of: {allowed}")
        return v


class ServerConfig(BaseModel):
    """MCP server configuration."""
    
    # Server identification
    server_name: str = Field(default="mcp-ai-commit", description="Server name")
    server_version: str = Field(default="0.1.0", description="Server version")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(None, description="Log file path")
    
    # Performance
    max_concurrent_requests: int = Field(default=10, description="Max concurrent requests")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    
    # Storage
    data_directory: Path = Field(default=Path.home() / ".mcp-ai-commit", description="Data directory")
    
    # Features
    enable_provenance_tracking: bool = Field(default=True, description="Enable provenance tracking")
    enable_metrics: bool = Field(default=True, description="Enable performance metrics")
    enable_caching: bool = Field(default=True, description="Enable response caching")
    
    @validator('data_directory')
    def create_data_dir(cls, v):
        """Ensure data directory exists."""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v


class MCPAICommitConfig(BaseModel):
    """Complete MCP AI Commit configuration."""
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ai_models: AIModelConfig = Field(default_factory=AIModelConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "MCPAICommitConfig":
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            # Try common locations
            for env_path in [".env", "../.env", "../../.env"]:
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    break
        
        return cls(
            database=DatabaseConfig(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "ai_commit"),
                username=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
                schema_name=os.getenv("AI_COMMIT_SCHEMA", "ai_commit")
            ),
            ai_models=AIModelConfig(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                default_provider=os.getenv("AI_COMMIT_DEFAULT_PROVIDER", "openai"),
                default_model=os.getenv("AI_COMMIT_DEFAULT_MODEL", "gpt-4"),
                default_temperature=float(os.getenv("AI_COMMIT_TEMPERATURE", "0.3")),
                default_max_tokens=int(os.getenv("AI_COMMIT_MAX_TOKENS", "200"))
            ),
            security=SecurityConfig(
                default_validation_level=os.getenv("AI_COMMIT_VALIDATION_LEVEL", "strict"),
                max_files_per_commit=int(os.getenv("AI_COMMIT_MAX_FILES", "50")),
                max_changes_per_file=int(os.getenv("AI_COMMIT_MAX_CHANGES", "1000"))
            ),
            server=ServerConfig(
                log_level=os.getenv("AI_COMMIT_LOG_LEVEL", "INFO"),
                max_concurrent_requests=int(os.getenv("AI_COMMIT_MAX_CONCURRENT", "10")),
                data_directory=Path(os.getenv("AI_COMMIT_DATA_DIR", str(Path.home() / ".mcp-ai-commit")))
            )
        )
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MCPAICommitConfig":
        """Load configuration from dictionary."""
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration to dictionary."""
        return self.dict()
    
    def save_to_file(self, file_path: str) -> None:
        """Save configuration to JSON file."""
        import json
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    @classmethod
    def from_file(cls, file_path: str) -> "MCPAICommitConfig":
        """Load configuration from JSON file."""
        import json
        with open(file_path, 'r') as f:
            return cls.from_dict(json.load(f))


# Global configuration instance
_config: Optional[MCPAICommitConfig] = None


def get_config() -> MCPAICommitConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = MCPAICommitConfig.from_env()
    return _config


def set_config(config: MCPAICommitConfig) -> None:
    """Set global configuration instance."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset global configuration to reload from environment."""
    global _config
    _config = None