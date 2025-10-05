# Test MCP Integration

## Test Commands for Claude Code

Once the MCP server is connected to Claude Code, you can test it:

### 1. Generate AI Commit
```
Use the mcp-ai-commit server to generate a commit message for the currently staged files in this repository using conventional commit format.
```

### 2. Validate Repository
```
Use the mcp-ai-commit server to validate the current repository state and check if it's ready for commits.
```

### 3. Query History
```
Use the mcp-ai-commit server to show the last 5 AI-generated commits for this repository.
```

### 4. Check Configuration
```
Use the mcp-ai-commit server to show the current configuration and test database connectivity.
```

## Expected Behavior

When working properly, Claude Code will:
- Automatically use the MCP server for commit generation
- Store full provenance (prompt + response) in PostgreSQL
- Append AI footer with execution ID to commits
- Validate file scope using allowed patterns
- Provide complete audit trail

## Verification

Check that the server is properly loaded:
- Claude Code should show "mcp-ai-commit" in available tools
- Database should receive execution records
- Commits should include AI footer with exec_id