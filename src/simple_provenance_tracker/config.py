"""Simple configuration for provenance tracker."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration from .env
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "pconfig")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "root")

# Build database URL
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

DATABASE_SCHEMA = os.getenv("AI_COMMIT_SCHEMA", "ai_commit")

# Knowledge graph polling interval (seconds)
KG_POLL_INTERVAL = int(os.getenv("KG_POLL_INTERVAL", "10"))

# Default repository path
DEFAULT_REPO_PATH = os.getenv("DEFAULT_REPO_PATH", os.getcwd())

# Enable auto-tracking
AUTO_TRACK_ENABLED = os.getenv("AUTO_TRACK_ENABLED", "true").lower() == "true"

def get_config():
    """Get configuration dictionary."""
    return {
        "database_url": DATABASE_URL,
        "database_schema": DATABASE_SCHEMA,
        "kg_poll_interval": KG_POLL_INTERVAL,
        "default_repo_path": DEFAULT_REPO_PATH,
        "auto_track_enabled": AUTO_TRACK_ENABLED
    }