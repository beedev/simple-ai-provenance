"""MCP server implementation for AI-powered commit generation."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, ToolsCapability
import mcp.server.stdio

from .config import get_config
from .database import get_database
from .validator import FileValidator
from .models import (
    CommitRequest, CommitResponse, ExecutionRecord, 
    ValidationLevel, ModelProvider, CommitStrategy
)
from .ai_client import AIClient
from .git_operations import GitOperations
from .interceptor import get_interceptor


app = Server("mcp-ai-commit")


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available AI commit tools."""
    return [
        types.Tool(
            name="ai_commit_generate",
            description="Generate AI-powered commit message from staged changes",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to git repository"
                    },
                    "model_provider": {
                        "type": "string",
                        "enum": ["openai", "anthropic", "local"],
                        "default": "openai",
                        "description": "AI model provider"
                    },
                    "model_name": {
                        "type": "string",
                        "default": "gpt-4",
                        "description": "Specific model name"
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["conventional", "semantic", "natural", "custom"],
                        "default": "conventional",
                        "description": "Commit message strategy"
                    },
                    "allowed_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allowed file path patterns"
                    },
                    "validation_level": {
                        "type": "string",
                        "enum": ["strict", "warn", "permissive"],
                        "default": "strict",
                        "description": "File validation strictness"
                    },
                    "temperature": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 2.0,
                        "default": 0.3,
                        "description": "AI model creativity"
                    },
                    "max_tokens": {
                        "type": "integer",
                        "minimum": 50,
                        "maximum": 1000,
                        "default": 200,
                        "description": "Maximum response tokens"
                    },
                    "include_body": {
                        "type": "boolean",
                        "default": true,
                        "description": "Include detailed commit body"
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Additional instructions for AI"
                    }
                },
                "required": ["repo_path"]
            }
        ),
        
        types.Tool(
            name="ai_prompt_log",
            description="Log AI prompt when sent to model (automatic interception)",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The prompt being sent to AI model"
                    },
                    "context": {
                        "type": "object",
                        "description": "Context information (repo_path, model, etc.)"
                    }
                },
                "required": ["prompt_text", "context"]
            }
        ),
        
        types.Tool(
            name="ai_response_log", 
            description="Log AI response when received (automatic interception)",
            inputSchema={
                "type": "object",
                "properties": {
                    "exec_id": {
                        "type": "string",
                        "description": "Execution ID from prompt log"
                    },
                    "response_text": {
                        "type": "string", 
                        "description": "The AI response text"
                    },
                    "model_info": {
                        "type": "object",
                        "description": "Model information (provider, model name, etc.)"
                    }
                },
                "required": ["exec_id", "response_text", "model_info"]
            }
        ),
        
        types.Tool(
            name="commit_consolidate",
            description="Consolidate AI interactions from DB into commit message",
            inputSchema={
                "type": "object", 
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Repository path"
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Original commit message to enhance"
                    }
                },
                "required": ["repo_path", "commit_message"]
            }
        ),
        
        types.Tool(
            name="ai_commit_execute",
            description="Execute AI-generated commit with provenance tracking",
            inputSchema={
                "type": "object",
                "properties": {
                    "exec_id": {
                        "type": "string",
                        "description": "Execution ID from ai_commit_generate"
                    },
                    "confirm": {
                        "type": "boolean",
                        "default": false,
                        "description": "Confirm execution of commit"
                    },
                    "append_footer": {
                        "type": "boolean",
                        "default": true,
                        "description": "Append AI execution footer to commit"
                    }
                },
                "required": ["exec_id", "confirm"]
            }
        ),
        
        types.Tool(
            name="ai_commit_history",
            description="Query AI commit execution history",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Filter by repository path"
                    },
                    "exec_id": {
                        "type": "string",
                        "description": "Get specific execution by ID"
                    },
                    "successful_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "Only return successful executions"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                        "description": "Maximum results to return"
                    },
                    "offset": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0,
                        "description": "Results offset for pagination"
                    }
                },
                "required": []
            }
        ),
        
        types.Tool(
            name="ai_commit_validate",
            description="Validate repository and file changes without generating commit",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {
                        "type": "string",
                        "description": "Path to git repository"
                    },
                    "allowed_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allowed file path patterns"
                    },
                    "validation_level": {
                        "type": "string",
                        "enum": ["strict", "warn", "permissive"],
                        "default": "strict",
                        "description": "File validation strictness"
                    }
                },
                "required": ["repo_path"]
            }
        ),
        
        types.Tool(
            name="ai_commit_config",
            description="Get or update AI commit configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "update"],
                        "default": "get",
                        "description": "Configuration action"
                    },
                    "config_data": {
                        "type": "object",
                        "description": "Configuration data for update action"
                    }
                },
                "required": []
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    
    if name == "ai_commit_generate":
        return await handle_generate_commit(arguments)
    elif name == "ai_commit_execute":
        return await handle_execute_commit(arguments)
    elif name == "ai_commit_history":
        return await handle_commit_history(arguments)
    elif name == "ai_commit_validate":
        return await handle_validate_repository(arguments)
    elif name == "ai_commit_config":
        return await handle_configuration(arguments)
    elif name == "ai_prompt_log":
        return await handle_prompt_log(arguments)
    elif name == "ai_response_log":
        return await handle_response_log(arguments)
    elif name == "commit_consolidate":
        return await handle_commit_consolidate(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_commit(arguments: dict) -> list[types.TextContent]:
    """Generate AI-powered commit message."""
    try:
        # Parse request
        request = CommitRequest(**arguments)
        
        # Initialize validator
        validator = FileValidator(request.repo_path, request.allowed_paths)
        
        # Validate execution context
        context_valid, context_errors = validator.validate_execution_context()
        if not context_valid:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "Repository validation failed",
                    "details": context_errors,
                    "can_execute": False
                }, indent=2)
            )]
        
        # Validate file changes
        file_changes = validator.validate_file_changes(request.validation_level)
        
        # Check file limits
        limits_valid, limit_errors = validator.check_file_limits(file_changes)
        
        # Determine if execution should be blocked
        validation_errors = []
        if request.validation_level == ValidationLevel.STRICT:
            # Strict mode: block on any validation failure
            for file_change in file_changes:
                if not file_change.is_allowed:
                    validation_errors.extend(file_change.validation_warnings)
        
        if not limits_valid:
            validation_errors.extend(limit_errors)
        
        can_execute = len(validation_errors) == 0
        
        # Generate commit message using AI
        ai_client = AIClient(request.model_provider, request.model_name)
        
        # Prepare context for AI
        repo_info = validator.get_repository_info()
        
        # Generate commit
        ai_response = await ai_client.generate_commit_message(
            file_changes=file_changes,
            repo_info=repo_info,
            strategy=request.strategy,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_body=request.include_body,
            custom_instructions=request.context_instructions
        )
        
        # Create response
        exec_id = str(uuid.uuid4())
        response = CommitResponse(
            exec_id=exec_id,
            commit_message=ai_response["commit_message"],
            commit_body=ai_response.get("commit_body"),
            detected_type=ai_response.get("detected_type", "unknown"),
            confidence_score=ai_response.get("confidence_score", 0.8),
            breaking_changes=ai_response.get("breaking_changes", []),
            analyzed_files=file_changes,
            total_additions=sum(f.additions for f in file_changes),
            total_deletions=sum(f.deletions for f in file_changes),
            validation_passed=can_execute,
            validation_errors=validation_errors,
            validation_warnings=[w for f in file_changes for w in f.validation_warnings if f.is_allowed],
            model_used=f"{request.model_provider}:{request.model_name}",
            prompt_tokens=ai_response.get("prompt_tokens", 0),
            completion_tokens=ai_response.get("completion_tokens", 0),
            can_execute=can_execute,
            execution_blocked_reason="; ".join(validation_errors) if validation_errors else None
        )
        
        # Store execution record for provenance
        db = await get_database()
        execution_record = ExecutionRecord(
            exec_id=exec_id,
            repo_path=request.repo_path,
            branch_name=repo_info.get("current_branch", "unknown"),
            model_provider=request.model_provider.value,
            model_name=request.model_name,
            prompt_text=ai_response.get("prompt_text", ""),
            response_text=ai_response.get("response_text", ""),
            commit_message=response.commit_message,
            files_changed=[f.path for f in file_changes],
            execution_successful=False,  # Not executed yet
            user_context={
                "validation_level": request.validation_level.value,
                "strategy": request.strategy.value,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            },
            performance_metrics={
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_files": len(file_changes),
                "total_additions": response.total_additions,
                "total_deletions": response.total_deletions
            }
        )
        
        await db.store_execution(execution_record)
        
        return [types.TextContent(
            type="text",
            text=json.dumps(response.dict(), indent=2, default=str)
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to generate commit",
                "details": str(e),
                "can_execute": False
            }, indent=2)
        )]


async def handle_execute_commit(arguments: dict) -> list[types.TextContent]:
    """Execute AI-generated commit with provenance tracking."""
    try:
        exec_id = arguments["exec_id"]
        confirm = arguments.get("confirm", False)
        append_footer = arguments.get("append_footer", True)
        
        if not confirm:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "Execution not confirmed",
                    "message": "Set confirm=true to execute the commit"
                }, indent=2)
            )]
        
        # Retrieve execution record
        db = await get_database()
        execution_record = await db.get_execution(exec_id)
        
        if not execution_record:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "Execution record not found",
                    "exec_id": exec_id
                }, indent=2)
            )]
        
        # Execute the commit
        git_ops = GitOperations(execution_record.repo_path)
        
        # Prepare commit message with optional AI footer
        commit_message = execution_record.commit_message
        if append_footer:
            footer = f"\n\n🤖 Generated with AI\nExecution ID: {exec_id}\nModel: {execution_record.model_name}\nTimestamp: {execution_record.timestamp.isoformat()}"
            commit_message += footer
            execution_record.ai_footer = footer
        
        # Execute the commit
        success, commit_hash, error_msg = await git_ops.create_commit(commit_message)
        
        # Update execution record
        execution_record.execution_successful = success
        execution_record.commit_hash = commit_hash
        
        # Store updated record
        await db.store_execution(execution_record)
        
        if success:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "exec_id": exec_id,
                    "commit_hash": commit_hash,
                    "commit_message": commit_message,
                    "repository": execution_record.repo_path,
                    "branch": execution_record.branch_name,
                    "files_changed": execution_record.files_changed
                }, indent=2)
            )]
        else:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "exec_id": exec_id,
                    "error": error_msg,
                    "commit_message": commit_message
                }, indent=2)
            )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to execute commit",
                "details": str(e)
            }, indent=2)
        )]


async def handle_commit_history(arguments: dict) -> list[types.TextContent]:
    """Query AI commit execution history."""
    try:
        db = await get_database()
        
        exec_id = arguments.get("exec_id")
        if exec_id:
            # Get specific execution
            record = await db.get_execution(exec_id)
            if record:
                return [types.TextContent(
                    type="text",
                    text=json.dumps(record.dict(), indent=2, default=str)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Execution {exec_id} not found"}, indent=2)
                )]
        
        # Search executions
        records = await db.search_executions(
            repo_path=arguments.get("repo_path"),
            successful_only=arguments.get("successful_only", False),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0)
        )
        
        # Format for display
        formatted_records = []
        for record in records:
            formatted_records.append({
                "exec_id": record.exec_id,
                "timestamp": record.timestamp.isoformat(),
                "repo_path": record.repo_path,
                "branch": record.branch_name,
                "commit_hash": record.commit_hash,
                "commit_message": record.commit_message[:100] + "..." if len(record.commit_message) > 100 else record.commit_message,
                "model_used": f"{record.model_provider}:{record.model_name}",
                "successful": record.execution_successful,
                "files_count": len(record.files_changed)
            })
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "total_results": len(formatted_records),
                "executions": formatted_records
            }, indent=2)
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to query history",
                "details": str(e)
            }, indent=2)
        )]


async def handle_validate_repository(arguments: dict) -> list[types.TextContent]:
    """Validate repository and file changes without generating commit."""
    try:
        repo_path = arguments["repo_path"]
        allowed_paths = arguments.get("allowed_paths")
        validation_level = ValidationLevel(arguments.get("validation_level", "strict"))
        
        # Initialize validator
        validator = FileValidator(repo_path, allowed_paths)
        
        # Validate execution context
        context_valid, context_errors = validator.validate_execution_context()
        
        # Validate file changes
        file_changes = validator.validate_file_changes(validation_level)
        
        # Check file limits
        limits_valid, limit_errors = validator.check_file_limits(file_changes)
        
        # Get repository info
        repo_info = validator.get_repository_info()
        
        # Compile validation results
        all_errors = []
        all_warnings = []
        
        if not context_valid:
            all_errors.extend(context_errors)
        
        if not limits_valid:
            all_errors.extend(limit_errors)
        
        for file_change in file_changes:
            if not file_change.is_allowed and validation_level == ValidationLevel.STRICT:
                all_errors.extend(file_change.validation_warnings)
            elif file_change.validation_warnings:
                all_warnings.extend(file_change.validation_warnings)
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "repository": repo_info,
                "validation_passed": len(all_errors) == 0,
                "can_execute": len(all_errors) == 0,
                "errors": all_errors,
                "warnings": all_warnings,
                "file_changes": [f.dict() for f in file_changes],
                "summary": {
                    "total_files": len(file_changes),
                    "total_additions": sum(f.additions for f in file_changes),
                    "total_deletions": sum(f.deletions for f in file_changes),
                    "files_blocked": sum(1 for f in file_changes if not f.is_allowed)
                }
            }, indent=2, default=str)
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Failed to validate repository",
                "details": str(e)
            }, indent=2)
        )]


async def handle_configuration(arguments: dict) -> list[types.TextContent]:
    """Get or update AI commit configuration."""
    try:
        action = arguments.get("action", "get")
        
        if action == "get":
            config = get_config()
            return [types.TextContent(
                type="text",
                text=json.dumps(config.to_dict(), indent=2, default=str)
            )]
        
        elif action == "update":
            config_data = arguments.get("config_data", {})
            # In a real implementation, you'd update the configuration
            # For now, just return the current config
            config = get_config()
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "message": "Configuration update not yet implemented",
                    "current_config": config.to_dict()
                }, indent=2, default=str)
            )]
        
        else:
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Unknown action: {action}",
                    "supported_actions": ["get", "update"]
                }, indent=2)
            )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": "Configuration operation failed",
                "details": str(e)
            }, indent=2)
        )]


async def handle_prompt_log(arguments: dict) -> list[types.TextContent]:
    """Log AI prompt when sent to model (automatic interception)."""
    try:
        prompt_text = arguments["prompt_text"]
        context = arguments["context"]
        
        interceptor = get_interceptor()
        exec_id = await interceptor.log_prompt(prompt_text, context)
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "exec_id": exec_id,
                "message": "Prompt logged successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to log prompt: {str(e)}"
            })
        )]


async def handle_response_log(arguments: dict) -> list[types.TextContent]:
    """Log AI response when received (automatic interception)."""
    try:
        exec_id = arguments["exec_id"]
        response_text = arguments["response_text"]
        model_info = arguments["model_info"]
        
        interceptor = get_interceptor()
        await interceptor.log_response(exec_id, response_text, model_info)
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "exec_id": exec_id,
                "message": "Response logged successfully",
                "timestamp": datetime.utcnow().isoformat()
            })
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to log response: {str(e)}"
            })
        )]


async def handle_commit_consolidate(arguments: dict) -> list[types.TextContent]:
    """Consolidate AI interactions from DB into commit message."""
    try:
        repo_path = arguments["repo_path"]
        commit_message = arguments["commit_message"]
        
        interceptor = get_interceptor()
        enhanced_message = await interceptor.consolidate_for_commit(repo_path, commit_message)
        
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "original_message": commit_message,
                "enhanced_message": enhanced_message,
                "message": "Commit message enhanced with AI provenance"
            })
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Failed to consolidate commit: {str(e)}"
            })
        )]


async def create_server() -> Server:
    """Create and configure the MCP server."""
    return app


async def main():
    """Main entry point for the MCP server."""
    # Initialize database on startup
    await get_database()
    
    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream, 
            InitializationOptions(
                server_name="mcp-ai-commit",
                server_version="0.1.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability()
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())