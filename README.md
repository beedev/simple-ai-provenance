# Simple AI Provenance Tracker

🎯 **Simple, effective AI conversation tracking with automatic commit provenance**

A lightweight MCP server that automatically tracks AI conversations from knowledge graph and enhances git commits with complete provenance information.

## ✨ Key Features

- **🔍 Auto-Detection**: Monitors knowledge graph for AI conversations
- **📊 PostgreSQL Storage**: Reuses existing `ai_commit.ai_commit_executions` schema
- **🤖 Commit Enhancement**: Automatically adds AI provenance to git commits
- **🛠️ Simple MCP**: Just 3 tools - no complexity
- **🔄 Background Monitoring**: Runs independently, no manual intervention

## 🚀 Quick Start

### 1. Installation

```bash
# Install the package
pip install -e .
```

### 2. Database Setup

The system reuses the existing PostgreSQL schema:
```bash
# Ensure PostgreSQL is running with the ai_commit schema
# Database: postgresql://postgres@localhost:5432/pconfig
# Schema: ai_commit.ai_commit_executions (already exists)
```

### 3. Start the System

```bash
# Start background monitoring
python start_simple_provenance.py
```

### 4. Configure Claude Code MCP

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "simple-ai-provenance": {
      "command": "python",
      "args": ["-m", "simple_provenance_tracker.mcp_server"],
      "cwd": "/path/to/mcp-ai-commit/src",
      "env": {
        "DATABASE_URL": "postgresql://postgres@localhost:5432/pconfig",
        "DATABASE_SCHEMA": "ai_commit"
      }
    }
  }
}
```

## 🛠️ MCP Tools

### `track_conversation`
Manually track an AI conversation:
```json
{
  "prompt_text": "Can you help me implement authentication?",
  "response_text": "I'll help you implement secure authentication...",
  "repo_path": "/path/to/repo",
  "context": {"source": "manual"}
}
```

### `enhance_commit_with_provenance`
Enhance a commit message with AI provenance:
```json
{
  "commit_message": "feat: add user authentication",
  "repo_path": "/path/to/repo"
}
```

Returns enhanced commit like:
```
feat: add user authentication

🤖 AI-Generated Content:
   Prompt: Can you help me implement authentication?
   Model: claude/sonnet-4
   ID: a1b2c3d4-e5f6-7890

📊 Full provenance available in ai_commit.ai_commit_executions
```

### `get_conversation_history`
Get conversation history for a repository:
```json
{
  "repo_path": "/path/to/repo",
  "limit": 10
}
```

## 🔄 How It Works

```
1. Knowledge Graph Watcher (Background)
   ↓ Detects AI conversations
2. Auto-Track to PostgreSQL 
   ↓ Stores in ai_commit.ai_commit_executions
3. Claude Code calls enhance_commit_with_provenance
   ↓ Before creating commits
4. Enhanced Commit Created
   ↓ With complete AI provenance
5. Conversations Marked as Committed
   ↓ commit_included = true
```

## 📊 Database Schema

Reuses existing `ai_commit.ai_commit_executions` table:

| Column | Type | Purpose |
|--------|------|---------|
| `exec_id` | UUID | Unique conversation ID |
| `prompt_text` | TEXT | AI prompt |
| `response_text` | TEXT | AI response |
| `repo_path` | VARCHAR | Git repository |
| `commit_included` | BOOLEAN | Used in commit? |
| `final_commit_hash` | VARCHAR | Git commit hash |
| `user_context` | JSON | Knowledge graph context |

## 🔧 Configuration

Environment variables:
```bash
DATABASE_URL=postgresql://postgres@localhost:5432/pconfig
DATABASE_SCHEMA=ai_commit
KG_POLL_INTERVAL=10  # Knowledge graph check interval (seconds)
AUTO_TRACK_ENABLED=true
```

## 📁 Project Structure

```
src/
├── simple_provenance_tracker/
│   ├── __init__.py
│   ├── mcp_server.py      # MCP server with 3 tools
│   ├── kg_watcher.py      # Knowledge graph monitor
│   └── config.py          # Simple configuration
├── start_simple_provenance.py  # Startup script
└── simple-provenance-mcp-config.json  # Claude Code config
```

## 🎯 Design Philosophy

- **Simple > Complex**: 3 MCP tools vs 20+ in old implementation
- **Reuse > Rebuild**: Leverage existing database schema
- **Auto > Manual**: Background monitoring vs manual calls
- **Direct > Abstracted**: Direct database operations vs complex layers

## 🔍 Monitoring

The background watcher logs activity:
```
🔍 Knowledge Graph Watcher started...
📝 Found AI conversation in entity: UserAuthDiscussion
✅ Auto-tracked AI conversation: a1b2c3d4-e5f6-7890
```

## ⚡ Performance

- **Lightweight**: Single background process
- **Efficient**: 10-second polling interval
- **Fast**: Direct database operations
- **Scalable**: PostgreSQL backend

## 🛡️ Security

- Uses existing database permissions
- No sensitive data in knowledge graph
- Local processing only
- Configurable file patterns

## 📝 License

MIT License