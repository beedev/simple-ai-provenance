"""Command line interface for MCP AI Commit."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich.json import JSON

from .config import get_config, set_config, MCPAICommitConfig
from .database import get_database, close_database
from .validator import FileValidator
from .ai_client import AIClient
from .git_operations import GitOperations
from .models import CommitRequest, ValidationLevel, ModelProvider, CommitStrategy


app = typer.Typer(help="AI-powered commit generation with provenance tracking")
console = Console()


@app.command()
def generate(
    repo_path: str = typer.Argument(..., help="Path to git repository"),
    model: str = typer.Option("gpt-4", help="AI model to use"),
    provider: str = typer.Option("openai", help="AI provider (openai, anthropic)"),
    strategy: str = typer.Option("conventional", help="Commit strategy (conventional, semantic, natural)"),
    temperature: float = typer.Option(0.3, help="AI temperature (0.0-2.0)"),
    max_tokens: int = typer.Option(200, help="Maximum tokens"),
    validation_level: str = typer.Option("strict", help="Validation level (strict, warn, permissive)"),
    allowed_paths: Optional[List[str]] = typer.Option(None, help="Allowed file patterns"),
    no_body: bool = typer.Option(False, help="Don't include commit body"),
    custom_instructions: Optional[str] = typer.Option(None, help="Custom instructions for AI"),
    dry_run: bool = typer.Option(False, help="Generate commit message without creating execution record"),
    auto_execute: bool = typer.Option(False, help="Automatically execute the commit"),
):
    """Generate an AI-powered commit message."""
    asyncio.run(_generate_async(
        repo_path=repo_path,
        model=model,
        provider=provider,
        strategy=strategy,
        temperature=temperature,
        max_tokens=max_tokens,
        validation_level=validation_level,
        allowed_paths=allowed_paths,
        include_body=not no_body,
        custom_instructions=custom_instructions,
        dry_run=dry_run,
        auto_execute=auto_execute
    ))


async def _generate_async(
    repo_path: str,
    model: str,
    provider: str,
    strategy: str,
    temperature: float,
    max_tokens: int,
    validation_level: str,
    allowed_paths: Optional[List[str]],
    include_body: bool,
    custom_instructions: Optional[str],
    dry_run: bool,
    auto_execute: bool
):
    """Async implementation of generate command."""
    try:
        # Create request
        request = CommitRequest(
            repo_path=repo_path,
            model_provider=ModelProvider(provider),
            model_name=model,
            strategy=CommitStrategy(strategy),
            temperature=temperature,
            max_tokens=max_tokens,
            validation_level=ValidationLevel(validation_level),
            allowed_paths=allowed_paths,
            include_body=include_body,
            context_instructions=custom_instructions,
            track_provenance=not dry_run
        )
        
        # Initialize components
        validator = FileValidator(request.repo_path, request.allowed_paths)
        git_ops = GitOperations(request.repo_path)
        
        # Validate repository state
        console.print("🔍 Validating repository state...", style="blue")
        
        context_valid, context_errors = validator.validate_execution_context()
        if not context_valid:
            console.print("❌ Repository validation failed:", style="red")
            for error in context_errors:
                console.print(f"  • {error}", style="red")
            raise typer.Exit(1)
        
        # Validate file changes
        file_changes = validator.validate_file_changes(request.validation_level)
        
        if not file_changes:
            console.print("❌ No staged changes found", style="red")
            raise typer.Exit(1)
        
        # Display file changes
        _display_file_changes(file_changes)
        
        # Check validation errors
        validation_errors = []
        for file_change in file_changes:
            if not file_change.is_allowed:
                validation_errors.extend(file_change.validation_warnings)
        
        if validation_errors and request.validation_level == ValidationLevel.STRICT:
            console.print("❌ Validation errors:", style="red")
            for error in validation_errors:
                console.print(f"  • {error}", style="red")
            raise typer.Exit(1)
        
        # Generate commit message
        console.print("🤖 Generating commit message...", style="blue")
        
        ai_client = AIClient(request.model_provider, request.model_name)
        repo_info = validator.get_repository_info()
        
        ai_response = await ai_client.generate_commit_message(
            file_changes=file_changes,
            repo_info=repo_info,
            strategy=request.strategy,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_body=request.include_body,
            custom_instructions=request.context_instructions
        )
        
        # Display generated commit
        _display_generated_commit(ai_response)
        
        # Store execution record if not dry run
        exec_id = None
        if not dry_run:
            from .database import get_database
            from .models import ExecutionRecord
            import uuid
            
            exec_id = str(uuid.uuid4())
            db = await get_database()
            
            execution_record = ExecutionRecord(
                exec_id=exec_id,
                repo_path=request.repo_path,
                branch_name=repo_info.get("current_branch", "unknown"),
                model_provider=request.model_provider.value,
                model_name=request.model_name,
                prompt_text=ai_response.get("prompt_text", ""),
                response_text=ai_response.get("response_text", ""),
                commit_message=ai_response["commit_message"],
                files_changed=[f.path for f in file_changes],
                execution_successful=False,
                user_context={
                    "cli_invocation": True,
                    "validation_level": request.validation_level.value,
                    "strategy": request.strategy.value
                },
                performance_metrics=ai_response.get("performance_metrics", {})
            )
            
            await db.store_execution(execution_record)
            console.print(f"📝 Execution record saved: {exec_id}", style="green")
        
        # Auto-execute or prompt for execution
        if auto_execute or (not dry_run and Confirm.ask("Execute this commit?")):
            if dry_run:
                console.print("❌ Cannot execute in dry-run mode", style="red")
                raise typer.Exit(1)
            
            # Execute commit
            console.print("⚡ Executing commit...", style="blue")
            
            commit_message = ai_response["commit_message"]
            if ai_response.get("commit_body"):
                commit_message += "\n\n" + ai_response["commit_body"]
            
            # Add AI footer
            footer = f"\n\n🤖 Generated with AI\nExecution ID: {exec_id}\nModel: {request.model_name}"
            commit_message += footer
            
            success, commit_hash, error_msg = await git_ops.create_commit(commit_message)
            
            if success:
                console.print(f"✅ Commit created: {commit_hash[:8]}", style="green")
                
                # Update execution record
                if exec_id:
                    execution_record.execution_successful = True
                    execution_record.commit_hash = commit_hash
                    execution_record.ai_footer = footer
                    await db.store_execution(execution_record)
            else:
                console.print(f"❌ Commit failed: {error_msg}", style="red")
                raise typer.Exit(1)
        
        await close_database()
        
    except Exception as e:
        console.print(f"❌ Error: {str(e)}", style="red")
        raise typer.Exit(1)


@app.command()
def history(
    repo_path: Optional[str] = typer.Option(None, help="Filter by repository path"),
    exec_id: Optional[str] = typer.Option(None, help="Get specific execution"),
    successful_only: bool = typer.Option(False, help="Only show successful executions"),
    limit: int = typer.Option(20, help="Maximum results"),
    json_output: bool = typer.Option(False, help="Output as JSON")
):
    """View AI commit execution history."""
    asyncio.run(_history_async(repo_path, exec_id, successful_only, limit, json_output))


async def _history_async(
    repo_path: Optional[str],
    exec_id: Optional[str],
    successful_only: bool,
    limit: int,
    json_output: bool
):
    """Async implementation of history command."""
    try:
        db = await get_database()
        
        if exec_id:
            # Get specific execution
            record = await db.get_execution(exec_id)
            if record:
                if json_output:
                    console.print(JSON(record.dict()))
                else:
                    _display_execution_record(record)
            else:
                console.print(f"❌ Execution {exec_id} not found", style="red")
        else:
            # Search executions
            records = await db.search_executions(
                repo_path=repo_path,
                successful_only=successful_only,
                limit=limit
            )
            
            if json_output:
                console.print(JSON([r.dict() for r in records]))
            else:
                _display_execution_history(records)
        
        await close_database()
        
    except Exception as e:
        console.print(f"❌ Error: {str(e)}", style="red")
        raise typer.Exit(1)


@app.command()
def config(
    action: str = typer.Argument(..., help="Action: show, init, validate"),
    config_file: Optional[str] = typer.Option(None, help="Configuration file path"),
):
    """Manage AI commit configuration."""
    if action == "show":
        config_obj = get_config()
        console.print(JSON(config_obj.to_dict()))
    
    elif action == "init":
        # Create sample configuration
        config_path = config_file or ".env"
        if Path(config_path).exists():
            if not Confirm.ask(f"Configuration file {config_path} exists. Overwrite?"):
                raise typer.Exit(0)
        
        # Copy example config
        import shutil
        example_path = Path(__file__).parent.parent.parent / ".env.example"
        if example_path.exists():
            shutil.copy(example_path, config_path)
            console.print(f"✅ Configuration template created: {config_path}", style="green")
            console.print("📝 Please edit the configuration file with your settings", style="blue")
        else:
            console.print("❌ Configuration template not found", style="red")
    
    elif action == "validate":
        try:
            config_obj = get_config()
            console.print("✅ Configuration is valid", style="green")
            
            # Test database connection
            async def test_db():
                try:
                    db = await get_database()
                    console.print("✅ Database connection successful", style="green")
                    await close_database()
                except Exception as e:
                    console.print(f"❌ Database connection failed: {str(e)}", style="red")
            
            asyncio.run(test_db())
            
        except Exception as e:
            console.print(f"❌ Configuration error: {str(e)}", style="red")
            raise typer.Exit(1)
    
    else:
        console.print(f"❌ Unknown action: {action}", style="red")
        raise typer.Exit(1)


def _display_file_changes(file_changes):
    """Display file changes in a table."""
    table = Table(title="Staged Changes")
    table.add_column("Status", style="cyan")
    table.add_column("File", style="white")
    table.add_column("Changes", style="green")
    table.add_column("Valid", style="yellow")
    
    for file_change in file_changes:
        status = {
            'A': '➕ Added',
            'M': '📝 Modified',
            'D': '❌ Deleted',
            'R': '🔄 Renamed'
        }.get(file_change.status, file_change.status)
        
        changes = f"+{file_change.additions} -{file_change.deletions}"
        valid = "✅" if file_change.is_allowed else "❌"
        
        table.add_row(status, file_change.path, changes, valid)
    
    console.print(table)


def _display_generated_commit(ai_response):
    """Display the generated commit message."""
    commit_msg = ai_response["commit_message"]
    commit_body = ai_response.get("commit_body")
    
    # Create commit preview
    full_message = commit_msg
    if commit_body:
        full_message += "\n\n" + commit_body
    
    panel = Panel(
        full_message,
        title="Generated Commit Message",
        border_style="green"
    )
    console.print(panel)
    
    # Display metadata
    metadata_table = Table(title="Generation Metadata")
    metadata_table.add_column("Property", style="cyan")
    metadata_table.add_column("Value", style="white")
    
    metadata_table.add_row("Type", ai_response.get("detected_type", "unknown"))
    metadata_table.add_row("Confidence", f"{ai_response.get('confidence_score', 0):.2f}")
    metadata_table.add_row("Tokens", f"{ai_response.get('completion_tokens', 0)}")
    
    if ai_response.get("breaking_changes"):
        metadata_table.add_row("Breaking Changes", ", ".join(ai_response["breaking_changes"]))
    
    console.print(metadata_table)


def _display_execution_record(record):
    """Display a single execution record."""
    panel = Panel(
        f"[bold]Commit:[/bold] {record.commit_message}\n"
        f"[bold]Repository:[/bold] {record.repo_path}\n"
        f"[bold]Branch:[/bold] {record.branch_name}\n"
        f"[bold]Model:[/bold] {record.model_provider}:{record.model_name}\n"
        f"[bold]Success:[/bold] {'✅' if record.execution_successful else '❌'}\n"
        f"[bold]Timestamp:[/bold] {record.timestamp}\n"
        f"[bold]Files:[/bold] {len(record.files_changed)}",
        title=f"Execution {record.exec_id[:8]}",
        border_style="blue"
    )
    console.print(panel)


def _display_execution_history(records):
    """Display execution history in a table."""
    if not records:
        console.print("No execution records found", style="yellow")
        return
    
    table = Table(title="AI Commit History")
    table.add_column("ID", style="cyan")
    table.add_column("Timestamp", style="white")
    table.add_column("Repository", style="green")
    table.add_column("Message", style="white")
    table.add_column("Model", style="yellow")
    table.add_column("Success", style="red")
    
    for record in records:
        commit_msg = record.commit_message[:50] + "..." if len(record.commit_message) > 50 else record.commit_message
        success = "✅" if record.execution_successful else "❌"
        model = f"{record.model_provider}:{record.model_name}"
        
        table.add_row(
            record.exec_id[:8],
            record.timestamp.strftime("%Y-%m-%d %H:%M"),
            Path(record.repo_path).name,
            commit_msg,
            model,
            success
        )
    
    console.print(table)


if __name__ == "__main__":
    app()