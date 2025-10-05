# 🔄 Automatic AI Prompt Interception & Commit Consolidation

## ✅ **The CORRECT Workflow You Wanted**

This MCP server now implements **exactly** what you requested:

1. **Automatic Prompt Logging** → PostgreSQL as they happen
2. **Automatic Response Logging** → PostgreSQL when received  
3. **Database Consolidation** → When commit happens, pull from DB
4. **Enhanced Commit Message** → With complete AI provenance

## 🔧 **How It Actually Works**

### **Step 1: Claude Code Integration**
When Claude Code connects to this MCP server, it gets these tools:

- `ai_prompt_log` - Automatically called when Claude sends prompts to AI
- `ai_response_log` - Automatically called when AI responds
- `commit_consolidate` - Called during commit to pull from database

### **Step 2: Automatic Interception**
```
User: "Generate a commit message for these changes"
    ↓
Claude Code sends prompt to AI model
    ↓
MCP AUTOMATICALLY calls ai_prompt_log()
    ↓ 
Prompt stored in PostgreSQL with exec_id: abc123
    ↓
AI model responds with commit message
    ↓
MCP AUTOMATICALLY calls ai_response_log(exec_id: abc123)
    ↓
Response stored in PostgreSQL linked to prompt
```

### **Step 3: Database Storage**
```sql
-- PostgreSQL ai_commit.ai_commit_executions table now contains:
INSERT INTO ai_commit_executions (
    exec_id,
    timestamp,
    repo_path,
    prompt_text,
    response_text,
    model_provider,
    model_name,
    execution_successful
) VALUES (
    'abc123',
    '2025-10-05T17:00:00Z',
    '/Users/bharath/my-project',
    'Generate conventional commit for these staged files...',
    'feat: add user authentication system',
    'openai',
    'gpt-4',
    true
);
```

### **Step 4: Commit Consolidation**
```
User commits: git commit -m "feat: add user authentication"
    ↓
Git hook triggers (or Claude Code calls commit_consolidate)
    ↓
MCP queries PostgreSQL for recent AI interactions in this repo
    ↓
Consolidates all prompts/responses from last 10 minutes
    ↓
Enhanced commit message created with full provenance
```

### **Step 5: Final Enhanced Commit**
```
feat: add user authentication system

Implements OAuth2 authentication with JWT tokens
for secure user login and session management.

🤖 AI-Generated Content (exec_id: abc123)
   Model: openai/gpt-4
   Prompt: Generate conventional commit for these staged files...
   Response: feat: add user authentication system...
   Timestamp: 2025-10-05T17:00:00Z

📊 Provenance: All AI interactions logged in database
```

## 🎯 **Key MCP Tools for Automatic Operation**

### **1. ai_prompt_log**
```json
{
  "name": "ai_prompt_log",
  "prompt_text": "Generate a commit for these changes...", 
  "context": {
    "repo_path": "/Users/bharath/project",
    "model_provider": "openai",
    "model_name": "gpt-4"
  }
}
```
**Result**: Returns `exec_id` and stores prompt in DB immediately

### **2. ai_response_log**  
```json
{
  "name": "ai_response_log",
  "exec_id": "abc123",
  "response_text": "feat: add authentication system",
  "model_info": {"provider": "openai", "model": "gpt-4"}
}
```
**Result**: Links response to prompt in database

### **3. commit_consolidate**
```json
{
  "name": "commit_consolidate", 
  "repo_path": "/Users/bharath/project",
  "commit_message": "feat: add authentication"
}
```
**Result**: Queries DB for recent AI interactions, returns enhanced message

## 🔧 **Installation & Setup**

### **1. Install Git Hooks (Optional but Recommended)**
```bash
python -c "
from mcp_ai_commit.git_hooks import install_hooks
install_hooks('/path/to/your/project')
"
```

### **2. Claude Code Configuration**
Add to Claude Code MCP servers:
```json
{
  "mcp-ai-commit": {
    "command": "python",
    "args": ["-m", "mcp_ai_commit.server"],
    "env": {
      "DATABASE_URL": "postgresql://postgres@localhost:5432/pconfig"
    }
  }
}
```

### **3. Usage**
```bash
# Just use Claude Code normally:
cd /any/project
git add .

# Ask Claude Code: "Generate a commit message"
# - Prompt automatically logged to PostgreSQL  
# - Response automatically logged to PostgreSQL
# - Commit automatically enhanced with provenance
```

## 📊 **Database Schema for Provenance**

Every AI interaction stores:
```sql
CREATE TABLE ai_commit.ai_commit_executions (
    exec_id UUID PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    repo_path VARCHAR(500) NOT NULL,
    branch_name VARCHAR(100) NOT NULL,
    commit_hash VARCHAR(40),
    model_provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    prompt_text TEXT NOT NULL,           -- FULL PROMPT
    response_text TEXT NOT NULL,         -- FULL RESPONSE  
    commit_message TEXT NOT NULL,        -- FINAL COMMIT
    files_changed JSON NOT NULL,         -- FILES INVOLVED
    execution_successful BOOLEAN DEFAULT FALSE,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0
);
```

## 🎉 **Result: Complete Transparency**

**Every commit now has:**
- ✅ **Full prompt text** that generated it
- ✅ **Complete AI response** received  
- ✅ **Unique execution ID** for tracking
- ✅ **Model information** (provider/name)
- ✅ **Timestamp and performance metrics**
- ✅ **Database audit trail** for compliance

**Example Enhanced Commit:**
```
feat: implement user dashboard with analytics

Added comprehensive user dashboard displaying:
- Real-time usage statistics
- Performance metrics visualization  
- User engagement analytics

🤖 AI-Generated Content (exec_id: def456)
   Model: anthropic/claude-3-sonnet
   Prompt: Create a commit message for the new dashboard feature with analytics...
   Response: feat: implement user dashboard with analytics. Added comprehensive...
   Timestamp: 2025-10-05T17:15:30Z

🤖 AI-Generated Content (exec_id: ghi789)  
   Model: openai/gpt-4
   Prompt: Improve the commit body to be more detailed...
   Response: Added comprehensive user dashboard displaying: - Real-time usage...
   Timestamp: 2025-10-05T17:16:45Z

📊 Provenance: All AI interactions logged in database
```

## 🔍 **Query Your AI History**

```sql
-- See all AI prompts from last week
SELECT repo_path, prompt_text, response_text, timestamp 
FROM ai_commit.ai_commit_executions 
WHERE timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC;

-- Find specific commit's AI interactions
SELECT * FROM ai_commit.ai_commit_executions 
WHERE commit_hash = 'abc123def456';

-- Usage by model
SELECT model_provider, model_name, COUNT(*) 
FROM ai_commit.ai_commit_executions
GROUP BY model_provider, model_name;
```

This is **exactly** the automatic interception → database storage → commit consolidation workflow you wanted!