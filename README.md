# MCP AI Commit

🤖 **AI-powered commit generation with automatic provenance tracking**

A Model Context Protocol (MCP) server that generates intelligent commit messages using AI while maintaining complete provenance tracking and file scope validation. Designed for integration with Claude Code and hostable for team use.

## ✨ Features

### 🎯 Core Capabilities
- **AI-Powered Commit Generation**: Uses OpenAI/Anthropic models to generate meaningful commit messages
- **Automatic Provenance Tracking**: Every commit includes execution ID and model information  
- **File Scope Validation**: `--allowed-paths` security prevents unauthorized file access
- **Multiple Commit Strategies**: Conventional, semantic, natural language, or custom formats
- **PostgreSQL Storage**: Configurable database for execution history and provenance
- **Claude Code Integration**: Built-in hooks for seamless Claude Code workflow

### 🛡️ Security Features
- **Path Validation**: Configurable allowed/blocked file patterns
- **Execution Limits**: Maximum files per commit and changes per file
- **Repository State Validation**: Ensures safe git operations
- **Permission Checking**: Validates write access before execution

### 📊 Provenance Tracking
- **Execution Records**: Complete prompt/response logging with unique exec_id
- **Performance Metrics**: Token usage, execution time, confidence scores
- **AI Footer**: Automatic append of AI execution details to commits
- **Search History**: Query executions by repository, success status, etc.

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the MCP server
git clone <repository-url>
cd mcp-ai-commit

# Install dependencies
pip install -e .
```

### 2. Configuration

```bash
# Create configuration from template
cp .env.example .env

# Edit configuration with your settings
vim .env
```

**Required Configuration:**
```env
# Database (uses your existing PostgreSQL)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=your_database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# AI API Keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Security Settings
AI_COMMIT_VALIDATION_LEVEL=strict
AI_COMMIT_MAX_FILES=50
```

### 3. Database Setup

The server automatically creates the required schema and tables:

```sql
-- Optional: Create dedicated database
CREATE DATABASE ai_commit;

-- Schema is created automatically on first run
-- Default schema name: ai_commit
```

### 4. Start MCP Server

```bash
# Run as MCP server
python -m mcp_ai_commit.server

# Or use CLI directly
mcp-ai-commit generate /path/to/repo
```

## 🔧 Usage

### MCP Server Functions

The server provides 5 main functions for Claude Code integration:

#### `ai_commit_generate`
Generate AI commit message from staged changes:

```json
{
  "repo_path": "/path/to/repository",
  "model_provider": "openai",
  "model_name": "gpt-4",
  "strategy": "conventional",
  "allowed_paths": ["src/**", "*.py", "*.js"],
  "validation_level": "strict",
  "temperature": 0.3,
  "include_body": true
}
```

#### `ai_commit_execute` 
Execute generated commit with provenance:

```json
{
  "exec_id": "uuid-from-generate",
  "confirm": true,
  "append_footer": true
}
```

#### `ai_commit_validate`
Validate repository without generating commit:

```json
{
  "repo_path": "/path/to/repository",
  "allowed_paths": ["src/**"],
  "validation_level": "strict"
}
```

#### `ai_commit_history`
Query execution history:

```json
{
  "repo_path": "/path/to/repository",
  "successful_only": true,
  "limit": 20
}
```

#### `ai_commit_config`
Get/update configuration:

```json
{
  "action": "get"
}
```

### CLI Interface

```bash
# Generate commit message
mcp-ai-commit generate /path/to/repo \
  --model gpt-4 \
  --strategy conventional \
  --allowed-paths "src/**" "*.py" \
  --validation-level strict

# Auto-execute commit
mcp-ai-commit generate /path/to/repo --auto-execute

# View history
mcp-ai-commit history --repo-path /path/to/repo

# Validate configuration
mcp-ai-commit config validate
```

### Example Workflow

```bash
# 1. Stage your changes
git add src/feature.py tests/test_feature.py

# 2. Generate AI commit
mcp-ai-commit generate . --strategy conventional

# Output:
# ✅ Generated: "feat: add user authentication feature"
# 📝 Execution ID: a1b2c3d4-e5f6-7890

# 3. Review and execute
# (CLI prompts for confirmation or use --auto-execute)

# 4. Commit created with AI footer:
# feat: add user authentication feature
# 
# Implements OAuth2 login with Google and GitHub providers
# 
# 🤖 Generated with AI
# Execution ID: a1b2c3d4-e5f6-7890
# Model: gpt-4
```

## 🔌 Claude Code Integration

### Automatic Integration

The MCP server automatically integrates with Claude Code when configured:

1. **Add to Claude Code MCP servers list**
2. **Configure environment variables**
3. **Enable auto-commit hooks** (optional)

### Manual Integration

Add to your Claude Code configuration:

```json
{
  "mcpServers": {
    "ai-commit": {
      "command": "python",
      "args": ["-m", "mcp_ai_commit.server"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "OPENAI_API_KEY": "your-key"
      }
    }
  }
}
```

### Claude Code Hooks

The server supports automatic integration with Claude Code's commit workflow:

```python
# In your Claude Code hooks
async def on_code_change(files_changed):
    if should_auto_commit(files_changed):
        await mcp_call("ai_commit_generate", {
            "repo_path": get_current_repo(),
            "allowed_paths": get_project_patterns(),
            "validation_level": "strict"
        })
```

## 📁 Configuration Options

### Database Configuration

```env
# PostgreSQL settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ai_commit
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
AI_COMMIT_SCHEMA=ai_commit
```

### AI Model Configuration

```env
# Provider settings
AI_COMMIT_DEFAULT_PROVIDER=openai
AI_COMMIT_DEFAULT_MODEL=gpt-4
AI_COMMIT_TEMPERATURE=0.3
AI_COMMIT_MAX_TOKENS=200

# API Keys
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Security Configuration

```env
# Validation level: strict, warn, permissive
AI_COMMIT_VALIDATION_LEVEL=strict

# File limits
AI_COMMIT_MAX_FILES=50
AI_COMMIT_MAX_CHANGES=1000
```

### Default File Patterns

**Allowed patterns:**
```
src/**, lib/**, app/**, components/**, pages/**, utils/**
*.py, *.js, *.ts, *.jsx, *.tsx, *.json, *.md, *.yml, *.yaml
```

**Blocked patterns:**
```
.env*, *.key, *.pem, *.p12, secrets/**, credentials/**
private/**, node_modules/**, .git/**, *.log
```

## 🏗️ Architecture

### Components

```
mcp-ai-commit/
├── src/mcp_ai_commit/
│   ├── server.py          # MCP server implementation
│   ├── ai_client.py       # AI model interactions
│   ├── database.py        # PostgreSQL provenance storage
│   ├── validator.py       # File scope validation
│   ├── git_operations.py  # Git command execution
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models
│   └── cli.py             # Command line interface
├── .env.example           # Configuration template
└── README.md
```

### Data Flow

```
1. Code Changes → Staged Files
2. File Validation → Security Check
3. AI Generation → Commit Message
4. Provenance Storage → Execution Record
5. Git Execution → Commit with Footer
6. History Tracking → Searchable Records
```

### Database Schema

```sql
-- Execution tracking
CREATE TABLE ai_commit_executions (
    exec_id UUID PRIMARY KEY,
    timestamp TIMESTAMP,
    repo_path VARCHAR(500),
    branch_name VARCHAR(100),
    commit_hash VARCHAR(40),
    model_provider VARCHAR(50),
    model_name VARCHAR(100),
    prompt_text TEXT,
    response_text TEXT,
    commit_message TEXT,
    files_changed JSON,
    execution_successful BOOLEAN,
    validation_passed BOOLEAN,
    user_context JSON,
    performance_metrics JSON
);

-- Configuration storage
CREATE TABLE ai_commit_configurations (
    config_id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    description TEXT,
    config_data JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    is_default BOOLEAN
);
```

## 🚀 Deployment

### Local Development

```bash
# Install in development mode
pip install -e .

# Run with auto-reload
python -m mcp_ai_commit.server
```

### Production Deployment

```bash
# Install from package
pip install mcp-ai-commit

# Run as service (systemd example)
[Unit]
Description=MCP AI Commit Server
After=postgresql.service

[Service]
Type=simple
User=mcp-user
WorkingDirectory=/opt/mcp-ai-commit
Environment=POSTGRES_HOST=localhost
Environment=OPENAI_API_KEY=your-key
ExecStart=/opt/mcp-ai-commit/venv/bin/python -m mcp_ai_commit.server
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

COPY . /app
WORKDIR /app

RUN pip install -e .

EXPOSE 8000
CMD ["python", "-m", "mcp_ai_commit.server"]
```

### Hosting for Teams

```bash
# Set up shared database
createdb ai_commit_shared

# Configure team environment
export POSTGRES_DB=ai_commit_shared
export AI_COMMIT_SCHEMA=team_commits

# Deploy with nginx proxy
# Enable multi-user access
```

## 🔒 Security Considerations

### File Access Control
- **Allowed Patterns**: Only specified patterns can be committed
- **Blocked Patterns**: Sensitive files are automatically excluded
- **Path Traversal**: Prevention of directory traversal attacks
- **Permission Validation**: Write access verification before execution

### Data Protection
- **API Key Security**: Secure environment variable storage
- **Database Encryption**: Connection encryption with PostgreSQL
- **Audit Trail**: Complete provenance tracking for compliance
- **User Context**: Isolation between different users/projects

### Git Safety
- **Repository Validation**: Ensures clean git state before operations
- **Staging Verification**: Only staged changes are considered
- **Rollback Support**: Failed commits don't affect repository state
- **Branch Protection**: Detached HEAD and merge conflict detection

## 📊 Monitoring & Analytics

### Execution Metrics
- **Success Rate**: Percentage of successful AI commit generations
- **Performance**: Average response time and token usage
- **Usage Patterns**: Most common commit strategies and models
- **Error Analysis**: Failed execution reasons and frequencies

### Repository Insights
- **Commit Frequency**: AI-generated vs manual commits
- **File Patterns**: Most commonly changed file types
- **Team Usage**: Individual developer adoption rates
- **Quality Metrics**: Commit message quality scores

## 🤝 Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd mcp-ai-commit

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```

### Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires database)
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

### Common Issues

**Database Connection Failed**
- Verify PostgreSQL is running
- Check connection credentials in .env
- Ensure database exists and user has permissions

**AI Generation Failed**
- Verify API keys are correct
- Check model availability and rate limits
- Review custom instructions for validity

**File Validation Errors**
- Review allowed_paths patterns
- Check file permissions
- Verify repository state

### Getting Help

- **Documentation**: See inline code documentation
- **Issues**: Create GitHub issue with error details
- **Discussions**: Join community discussions for questions
- **Email**: Contact maintainers for urgent issues

---

**🤖 Built for intelligent, traceable, and secure AI-powered development workflows**