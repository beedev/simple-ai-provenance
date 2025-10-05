# Claude Code Integration Guide

Complete guide for integrating MCP AI Commit as the default commit behavior in Claude Code.

## 🎯 Integration Objectives

1. **Automatic Provenance**: All Claude Code commits automatically include AI execution tracking
2. **Scope Validation**: File changes are validated against project-specific allowed patterns  
3. **Seamless Workflow**: No additional user action required - works transparently
4. **Quality Assurance**: AI-generated commits follow project conventions and best practices

## 🔧 Installation & Setup

### 1. Add MCP Server to Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "ai-commit": {
      "command": "python",
      "args": ["-m", "mcp_ai_commit.server"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432", 
        "POSTGRES_DB": "ai_commit",
        "POSTGRES_USER": "your_user",
        "POSTGRES_PASSWORD": "your_password",
        "OPENAI_API_KEY": "your_openai_key",
        "AI_COMMIT_VALIDATION_LEVEL": "strict",
        "AI_COMMIT_DEFAULT_PROVIDER": "openai",
        "AI_COMMIT_DEFAULT_MODEL": "gpt-4"
      }
    }
  }
}
```

### 2. Configure Project-Specific Settings

Create `.claude-ai-commit.json` in your project root:

```json
{
  "enabled": true,
  "strategy": "conventional",
  "validation_level": "strict",
  "allowed_paths": [
    "src/**",
    "lib/**", 
    "components/**",
    "*.py",
    "*.js", 
    "*.ts",
    "*.jsx",
    "*.tsx",
    "*.json",
    "*.md",
    "README*",
    "CHANGELOG*"
  ],
  "blocked_paths": [
    ".env*",
    "*.key",
    "*.pem",
    "secrets/**",
    "credentials/**",
    "node_modules/**",
    ".git/**"
  ],
  "model_settings": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.3,
    "max_tokens": 200
  },
  "commit_settings": {
    "include_body": true,
    "append_footer": true,
    "require_confirmation": false
  },
  "custom_instructions": "Follow the project's conventional commit format. Focus on business impact and user-facing changes."
}
```

### 3. Enable Auto-Commit Hooks

Configure Claude Code to automatically use AI commits:

```python
# claude_code_hooks.py - Add to your Claude Code project

async def on_commit_request(staged_files, commit_context):
    """Auto-generate AI commit when Claude Code creates commits."""
    
    # Check if AI commit is enabled for this project
    config = load_project_config()
    if not config.get("ai_commit_enabled", True):
        return None
    
    # Generate AI commit
    try:
        response = await mcp_call("ai_commit_generate", {
            "repo_path": commit_context["repo_path"],
            "model_provider": config["model_settings"]["provider"],
            "model_name": config["model_settings"]["model"],
            "strategy": config["strategy"],
            "allowed_paths": config["allowed_paths"],
            "validation_level": config["validation_level"],
            "temperature": config["model_settings"]["temperature"],
            "max_tokens": config["model_settings"]["max_tokens"],
            "include_body": config["commit_settings"]["include_body"],
            "custom_instructions": config.get("custom_instructions")
        })
        
        if response["can_execute"]:
            return {
                "exec_id": response["exec_id"],
                "commit_message": response["commit_message"],
                "commit_body": response.get("commit_body"),
                "ai_generated": True
            }
        else:
            # Log validation errors
            log_validation_errors(response["validation_errors"])
            return None
            
    except Exception as e:
        log_error(f"AI commit generation failed: {e}")
        return None

async def on_commit_execute(commit_data):
    """Execute AI-generated commit with provenance."""
    
    if commit_data.get("ai_generated") and commit_data.get("exec_id"):
        try:
            result = await mcp_call("ai_commit_execute", {
                "exec_id": commit_data["exec_id"],
                "confirm": True,
                "append_footer": True
            })
            
            if result["success"]:
                return {
                    "success": True,
                    "commit_hash": result["commit_hash"],
                    "provenance_id": commit_data["exec_id"]
                }
            else:
                log_error(f"AI commit execution failed: {result['error']}")
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            log_error(f"AI commit execution error: {e}")
            return {"success": False, "error": str(e)}
    
    return None

def load_project_config():
    """Load project-specific AI commit configuration."""
    config_path = Path(".claude-ai-commit.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    
    # Default configuration
    return {
        "ai_commit_enabled": True,
        "strategy": "conventional",
        "validation_level": "strict",
        "allowed_paths": ["src/**", "*.py", "*.js", "*.ts", "*.md"],
        "model_settings": {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 200
        },
        "commit_settings": {
            "include_body": True,
            "append_footer": True,
            "require_confirmation": False
        }
    }
```

## ⚙️ Default Behavior Configuration

### Automatic Commit Generation

When Claude Code wants to create a commit:

1. **Pre-Commit Hook**: Automatically calls `ai_commit_generate`
2. **Validation**: Checks file scope and repository state
3. **Generation**: AI creates commit message based on changes
4. **Review** (Optional): User can review before execution
5. **Execution**: Commit created with AI footer and provenance ID
6. **Tracking**: Execution recorded in database for auditing

### Validation Levels

**Strict Mode** (Recommended):
- Blocks commits if any files outside allowed patterns
- Requires all validation checks to pass
- Fails fast on security violations

**Warn Mode**:
- Allows commits but logs warnings
- Useful for gradual adoption
- Maintains audit trail of violations

**Permissive Mode**:
- Allows all commits
- Logs everything for monitoring
- Use only in development environments

### File Scope Patterns

**Default Allowed Patterns**:
```json
[
  "src/**", "lib/**", "app/**", "components/**", "pages/**", "utils/**",
  "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue", 
  "*.json", "*.yaml", "*.yml", "*.md", "*.txt",
  "README*", "CHANGELOG*", "LICENSE*"
]
```

**Default Blocked Patterns**:
```json
[
  ".env*", "*.key", "*.pem", "*.p12", "*.crt", "*.der",
  "secrets/**", "credentials/**", "private/**",
  "node_modules/**", ".git/**", "*.log", "*.cache"
]
```

## 🔄 Workflow Integration

### Standard Claude Code Workflow

```
1. User: "Implement user authentication"
2. Claude: Writes code, creates files, makes changes
3. Claude: Calls git add to stage changes
4. Claude: Triggers commit creation
   → Auto-calls ai_commit_generate
   → Validates files against allowed patterns
   → Generates: "feat: implement user authentication with OAuth2"
   → Creates commit with AI footer
5. User: Sees completed commit with provenance
```

### Error Handling Workflow

```
1. Claude: Attempts to create commit
2. AI Commit: Validates files
3. Validation Fails: Files outside allowed patterns
4. AI Commit: Returns validation errors
5. Claude: Reports to user with specific issues
6. User: Can either:
   - Adjust allowed patterns
   - Remove problematic files
   - Override with manual commit
```

### Rollback Workflow

```
1. User: "That commit message is wrong"
2. Claude: Queries ai_commit_history for recent commits
3. Claude: Finds commit by exec_id
4. Claude: Performs git reset --soft HEAD~1
5. Claude: Re-generates with different instructions
6. Claude: Creates new commit with updated message
```

## 🛠️ Customization Options

### Per-Project Configuration

Override global settings for specific projects:

```json
{
  "project_overrides": {
    "/path/to/secure-project": {
      "validation_level": "strict",
      "allowed_paths": ["src/**"],
      "model_settings": {
        "temperature": 0.1,
        "custom_instructions": "Use security-focused commit messages"
      }
    },
    "/path/to/documentation-project": {
      "strategy": "natural",
      "allowed_paths": ["**/*.md", "**/*.rst"],
      "model_settings": {
        "temperature": 0.7,
        "custom_instructions": "Focus on clarity and documentation value"
      }
    }
  }
}
```

### Custom Commit Strategies

Define custom strategies for different project types:

```python
# Custom strategy definitions
CUSTOM_STRATEGIES = {
    "api_changes": {
        "prompt_template": """
        Generate a commit message for API changes.
        Focus on:
        - Backward compatibility
        - API version impacts
        - Breaking changes
        - Consumer impact
        
        Use format: "api: <description> [breaking|compatible]"
        """,
        "validation_rules": ["check_api_compatibility", "verify_version_bump"]
    },
    
    "security_updates": {
        "prompt_template": """
        Generate a commit message for security updates.
        Focus on:
        - Security impact level
        - Vulnerability details (if public)
        - Affected components
        
        Use format: "security: <description> [CVE-XXXX-XXXX if applicable]"
        """,
        "validation_rules": ["require_security_review", "check_cve_references"]
    }
}
```

### Model Selection Logic

Automatically choose models based on context:

```python
async def select_optimal_model(file_changes, project_config):
    """Choose the best model for the current context."""
    
    # Complex changes → more powerful model
    total_changes = sum(f.additions + f.deletions for f in file_changes)
    if total_changes > 500:
        return "gpt-4"
    
    # Security-related files → security-focused model
    security_files = any("security" in f.path or "auth" in f.path for f in file_changes)
    if security_files:
        return "gpt-4"  # Use most capable model for security
    
    # Documentation changes → fast model
    doc_files = all(f.path.endswith(('.md', '.rst', '.txt')) for f in file_changes)
    if doc_files:
        return "gpt-3.5-turbo"
    
    # Default model from config
    return project_config["model_settings"]["model"]
```

## 📊 Monitoring & Analytics

### Execution Tracking

All AI commits are tracked with:

```sql
-- Example execution record
{
  "exec_id": "a1b2c3d4-e5f6-7890-abcd",
  "timestamp": "2024-01-15T10:30:00Z",
  "repo_path": "/Users/dev/my-project",
  "branch_name": "feature/auth",
  "model_provider": "openai",
  "model_name": "gpt-4",
  "commit_message": "feat: implement OAuth2 authentication",
  "files_changed": ["src/auth.py", "tests/test_auth.py"],
  "execution_successful": true,
  "user_context": {
    "claude_code_session": true,
    "strategy": "conventional",
    "validation_level": "strict"
  },
  "performance_metrics": {
    "prompt_tokens": 892,
    "completion_tokens": 45,
    "execution_time_ms": 1250
  }
}
```

### Usage Analytics

Query execution patterns:

```python
# Most used models
SELECT model_name, COUNT(*) as usage_count 
FROM ai_commit_executions 
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY model_name;

# Success rate by project
SELECT repo_path, 
       COUNT(*) as total_commits,
       SUM(CASE WHEN execution_successful THEN 1 ELSE 0 END) as successful_commits,
       ROUND(AVG(CASE WHEN execution_successful THEN 1.0 ELSE 0.0 END) * 100, 2) as success_rate
FROM ai_commit_executions
GROUP BY repo_path;

# Average commit message quality (by length and conventional format compliance)
SELECT strategy,
       AVG(LENGTH(commit_message)) as avg_message_length,
       COUNT(*) as total_commits
FROM ai_commit_executions
WHERE execution_successful = true
GROUP BY strategy;
```

## 🔒 Security & Compliance

### Audit Trail

Every AI commit includes:

- **Execution ID**: Unique identifier for traceability
- **Model Information**: Which AI model generated the commit
- **Prompt Data**: Complete prompt sent to AI (for compliance)
- **Validation Results**: Security check outcomes
- **User Context**: Environment and configuration used

### Access Control

```python
# Role-based AI commit permissions
ROLE_PERMISSIONS = {
    "developer": {
        "can_generate": True,
        "can_execute": True,
        "allowed_strategies": ["conventional", "semantic"],
        "max_files_per_commit": 20,
        "validation_level": "strict"
    },
    "senior_developer": {
        "can_generate": True,
        "can_execute": True,
        "allowed_strategies": ["conventional", "semantic", "natural", "custom"],
        "max_files_per_commit": 50,
        "validation_level": "warn"
    },
    "admin": {
        "can_generate": True,
        "can_execute": True,
        "allowed_strategies": ["*"],
        "max_files_per_commit": 100,
        "validation_level": "permissive",
        "can_override_patterns": True
    }
}
```

### Data Privacy

- **No Code Storage**: Only commit messages and file paths stored
- **API Key Security**: Encrypted environment variables
- **Local Processing**: Sensitive files never sent to AI
- **Audit Retention**: Configurable data retention policies

## 🚀 Deployment Examples

### Development Team Setup

```bash
# 1. Set up shared database
createdb ai_commit_team
psql ai_commit_team -c "CREATE SCHEMA team_commits;"

# 2. Configure team environment
export POSTGRES_DB=ai_commit_team
export AI_COMMIT_SCHEMA=team_commits
export AI_COMMIT_VALIDATION_LEVEL=strict

# 3. Deploy team-wide configuration
cat > .claude-ai-commit-team.json << EOF
{
  "validation_level": "strict",
  "allowed_paths": ["src/**", "tests/**", "docs/**", "*.py", "*.js", "*.md"],
  "blocked_paths": [".env*", "secrets/**", "credentials/**"],
  "model_settings": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.3
  },
  "commit_settings": {
    "strategy": "conventional",
    "include_body": true,
    "append_footer": true
  }
}
EOF
```

### Enterprise Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  ai-commit-server:
    build: .
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_DB=ai_commit_enterprise
      - AI_COMMIT_VALIDATION_LEVEL=strict
      - AI_COMMIT_MAX_FILES=50
    depends_on:
      - postgres
    ports:
      - "8080:8080"
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_commit_enterprise
      POSTGRES_USER: ai_commit
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

This integration makes AI commit generation completely transparent to Claude Code users while maintaining security, traceability, and quality standards.