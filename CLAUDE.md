# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Simple AI Provenance Tracker is a lightweight MCP server that automatically tracks AI conversations from knowledge graph and enhances git commits with complete provenance information. It reuses existing PostgreSQL schema for efficiency.

## Development Commands

### Installation & Setup
```bash
# Install in development mode
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

### Code Quality & Testing
```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/

# Run tests
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with coverage
pytest --cov=src/simple_provenance_tracker
```

### Running the System
```bash
# Start background knowledge graph watcher
python start_simple_provenance.py

# Run MCP server directly (for testing)
python -m simple_provenance_tracker.mcp_server

# Run as module
python -c "from simple_provenance_tracker.mcp_server import main; import asyncio; asyncio.run(main())"
```

### Environment Configuration
```bash
# Required environment variables
DATABASE_URL=postgresql://postgres@localhost:5432/pconfig
DATABASE_SCHEMA=ai_commit
KG_POLL_INTERVAL=10
AUTO_TRACK_ENABLED=true
```

## Core Architecture

### Simple Design Philosophy
- **3 MCP Tools**: `track_conversation`, `enhance_commit_with_provenance`, `get_conversation_history`
- **Background Watcher**: Monitors knowledge graph for AI conversations
- **Direct Database**: Reuses existing `ai_commit.ai_commit_executions` table
- **Auto-Enhancement**: Enhances commits with AI provenance automatically

### Key Components

**MCP Server** (`mcp_server.py`):
- 3 simple tools with direct database operations
- Reuses existing database schema and connection logic
- No complex abstractions or multiple layers

**Knowledge Graph Watcher** (`kg_watcher.py`):
- Polls knowledge graph every 10 seconds
- Detects conversation patterns in entities/observations
- Auto-tracks conversations to PostgreSQL database
- Runs as independent background process

**Configuration** (`config.py`):
- Simple environment variable configuration
- Reuses existing database connection settings
- Minimal configuration surface

### Database Integration

**Existing Schema Reuse**:
The system leverages the existing `ai_commit.ai_commit_executions` table:

```sql
ai_commit.ai_commit_executions:
├── exec_id (UUID) - Conversation tracking ID
├── prompt_text (TEXT) - AI prompt from knowledge graph
├── response_text (TEXT) - AI response from knowledge graph  
├── repo_path (VARCHAR) - Git repository context
├── commit_included (BOOLEAN) - Used in commit yet?
├── final_commit_hash (VARCHAR) - Git commit reference
├── user_context (JSON) - Knowledge graph metadata
└── [other existing columns] - Maintained for compatibility
```

**Database Operations**:
- Insert: New conversations from knowledge graph
- Query: Uncommitted conversations for commit enhancement
- Update: Mark conversations as included in commits

### Integration Flow

```
1. Knowledge Graph Monitor
   ↓ Detects AI conversations
2. Auto-Track to Database
   ↓ INSERT into ai_commit_executions  
3. Claude Code MCP Call
   ↓ enhance_commit_with_provenance
4. Enhanced Commit
   ↓ With AI provenance footer
5. Mark as Committed
   ↓ UPDATE commit_included = true
```

## Claude Code Integration

### MCP Configuration
Add to Claude Code's MCP servers:
```json
{
  "mcpServers": {
    "simple-ai-provenance": {
      "command": "python",
      "args": ["-m", "simple_provenance_tracker.mcp_server"],
      "cwd": "/Users/bharath/mcp-ai-commit/src",
      "env": {
        "DATABASE_URL": "postgresql://postgres@localhost:5432/pconfig",
        "DATABASE_SCHEMA": "ai_commit"
      }
    }
  }
}
```

### Usage Workflow
1. **Background**: Knowledge graph watcher runs automatically
2. **Detection**: AI conversations auto-tracked to database
3. **Enhancement**: Call `enhance_commit_with_provenance` before commits
4. **Result**: Commits include complete AI provenance information

### MCP Tools Usage

**Track Conversation** (usually automatic):
```json
{
  "prompt_text": "Can you help implement authentication?",
  "response_text": "I'll implement secure authentication...",
  "repo_path": "/path/to/repo"
}
```

**Enhance Commit** (call before committing):
```json
{
  "commit_message": "feat: add user authentication",
  "repo_path": "/path/to/repo"  
}
```

**Get History** (for debugging/review):
```json
{
  "repo_path": "/path/to/repo",
  "limit": 10
}
```

## Development Guidelines

### Code Organization
- Keep it simple: Direct database operations, no complex abstractions
- Single responsibility: Each component does one thing well
- Reuse existing: Leverage proven database schema and connection logic

### Database Operations
- Use existing SQLAlchemy models from original implementation
- All database access is async using existing patterns
- Maintain compatibility with existing table structure

### Error Handling
- Simple error responses with clear messages
- Log errors for debugging but don't crash the system
- Graceful degradation when knowledge graph unavailable

### Testing Strategy
- Test MCP tools individually
- Mock database operations for unit tests
- Integration tests with real PostgreSQL (optional)
- Test knowledge graph watcher with mock conversations

### Performance Considerations
- 10-second polling interval (configurable)
- Direct database queries (no complex joins)
- Background processing doesn't block main operations
- Efficient conversation detection patterns

## Project Structure

```
src/
├── simple_provenance_tracker/
│   ├── __init__.py           # Package initialization
│   ├── mcp_server.py         # 3 MCP tools + server
│   ├── kg_watcher.py         # Knowledge graph monitor
│   └── config.py             # Simple configuration
├── start_simple_provenance.py   # Background startup script
└── simple-provenance-mcp-config.json  # Claude Code config
```

## Key Differences from Previous Implementation

**Removed Complexity**:
- No multiple interception mechanisms
- No complex bridge classes
- No automatic MCP calling (Claude Code doesn't support it)
- No 20+ MCP tools

**Simplified Design**:
- 3 MCP tools vs 20+
- Direct database operations vs complex ORM abstractions  
- Background watcher vs complex hooks
- Reuse existing schema vs creating new tables

**Working Integration**:
- Knowledge graph monitoring actually works
- MCP tools are simple and functional
- Database operations are direct and efficient
- Claude Code integration is straightforward