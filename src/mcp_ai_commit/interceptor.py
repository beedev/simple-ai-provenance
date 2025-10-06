"""Automatic prompt/response interception system for AI commit tracking."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import json
import os
from pathlib import Path

from .database import get_database
from .models import ExecutionRecord
from .model_detection import enhance_context_with_model_detection, get_claude_code_model_info


class PromptInterceptor:
    """Intercepts and logs all AI prompts/responses for commit generation."""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.active_prompts = {}  # Track ongoing prompts
        
    async def log_prompt(self, prompt_text: str, context: Dict[str, Any]) -> str:
        """Log an outgoing prompt to AI model."""
        exec_id = str(uuid.uuid4())
        
        # Enhance context with automatic model detection
        enhanced_context = enhance_context_with_model_detection(context.copy())
        
        # For Claude Code, use specific model info
        claude_model_info = get_claude_code_model_info()
        
        # Store prompt immediately when sent
        db = await get_database()
        
        # Create partial execution record (response will be added later)
        record = ExecutionRecord(
            exec_id=exec_id,
            timestamp=datetime.utcnow(),
            repo_path=enhanced_context.get('repo_path', os.getcwd()),
            branch_name=enhanced_context.get('branch_name', 'unknown'),
            commit_hash=None,  # Will be set when commit happens
            model_provider=claude_model_info['provider'],  # Use detected Claude model
            model_name=claude_model_info['model'],  # Use detected Claude model
            prompt_text=prompt_text,
            response_text="",  # Will be filled when response comes
            commit_message="",  # Will be filled when commit happens
            files_changed=[],
            execution_successful=False,
            user_context=enhanced_context,
            performance_metrics={'prompt_tokens': len(prompt_text.split())},
            ai_footer=""
        )
        
        await db.store_execution(record)
        
        # Track this prompt as active
        self.active_prompts[exec_id] = {
            'prompt_text': prompt_text,
            'context': context,
            'timestamp': datetime.utcnow()
        }
        
        print(f"🔍 Logged prompt with exec_id: {exec_id}")
        return exec_id
    
    async def log_response(self, exec_id: str, response_text: str, model_info: Dict[str, Any]):
        """Log AI response when it comes back."""
        if exec_id not in self.active_prompts:
            print(f"⚠️ Warning: Response for unknown exec_id: {exec_id}")
            return
        
        db = await get_database()
        
        # Get the existing record
        existing_record = await db.get_execution(exec_id)
        if not existing_record:
            print(f"❌ Could not find existing record for exec_id: {exec_id}")
            return
        
        # Update the existing record with response data
        # We need to update the database record directly
        from sqlalchemy import update
        from .database import AICommitExecution
        
        async with await db.get_session() as session:
            try:
                # Update the existing record
                stmt = update(AICommitExecution).where(
                    AICommitExecution.exec_id == uuid.UUID(exec_id)
                ).values(
                    response_text=response_text,
                    model_provider=model_info.get('provider', existing_record.model_provider),
                    model_name=model_info.get('model', existing_record.model_name),
                    execution_successful=True,
                    completion_tokens=len(response_text.split()),
                    execution_time_ms=int((datetime.utcnow() - existing_record.timestamp).total_seconds() * 1000),
                    ai_footer=f"🤖 AI-Generated (exec_id: {exec_id})"
                )
                
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
        
        # Remove from active tracking
        del self.active_prompts[exec_id]
        
        print(f"✅ Logged response for exec_id: {exec_id}")
    
    async def consolidate_for_commit(self, repo_path: str, commit_message: str) -> str:
        """Consolidate all uncommitted prompts/responses for this repo into commit footer."""
        db = await get_database()
        
        # Get all executions for this repo that haven't been included in a commit yet
        uncommitted_executions = await self._get_uncommitted_executions(db, repo_path)
        
        if not uncommitted_executions:
            return commit_message
        
        # Build consolidated footer
        footer_lines = ["\n"]
        
        for i, exec_record in enumerate(uncommitted_executions[:5]):  # Max 5 uncommitted
            footer_lines.append(f"🤖 AI-Generated Content (exec_id: {exec_record.exec_id})")
            footer_lines.append(f"   Model: {exec_record.model_provider}/{exec_record.model_name}")
            footer_lines.append(f"   Prompt: {exec_record.prompt_text[:100]}...")
            footer_lines.append(f"   Response: {exec_record.response_text[:100]}...")
            footer_lines.append(f"   Timestamp: {exec_record.timestamp.isoformat()}Z")
            footer_lines.append("")
        
        footer_lines.append("📊 Provenance: All AI interactions logged in database")
        
        final_message = commit_message + "\n".join(footer_lines)
        
        # Update the database records with the final commit message
        await self._update_commit_message_for_executions(db, repo_path, final_message)
        
        print(f"🔗 Consolidated {len(uncommitted_executions)} uncommitted AI interactions for commit")
        return final_message
    
    async def _get_uncommitted_executions(self, db, repo_path: str):
        """Get all executions for this repo that haven't been included in a commit yet."""
        from sqlalchemy import select, and_
        from .database import AICommitExecution
        
        async with await db.get_session() as session:
            try:
                # Query for executions that are successful, have responses, and haven't been committed
                query = select(AICommitExecution).where(
                    and_(
                        AICommitExecution.repo_path == repo_path,
                        AICommitExecution.execution_successful == True,
                        AICommitExecution.response_text != "",
                        AICommitExecution.commit_included == False  # Key: only uncommitted ones
                    )
                ).order_by(AICommitExecution.timestamp.desc())
                
                result = await session.execute(query)
                db_records = result.scalars().all()
                
                # Convert to ExecutionRecord objects
                from .models import ExecutionRecord
                executions = []
                for record in db_records:
                    executions.append(ExecutionRecord(
                        exec_id=str(record.exec_id),
                        timestamp=record.timestamp,
                        repo_path=record.repo_path,
                        branch_name=record.branch_name,
                        commit_hash=record.commit_hash,
                        model_provider=record.model_provider,
                        model_name=record.model_name,
                        prompt_text=record.prompt_text,
                        response_text=record.response_text,
                        commit_message=record.commit_message,
                        files_changed=record.files_changed,
                        execution_successful=record.execution_successful,
                        user_context=record.user_context or {},
                        performance_metrics={
                            'prompt_tokens': record.prompt_tokens,
                            'completion_tokens': record.completion_tokens,
                            'execution_time_ms': record.execution_time_ms
                        },
                        ai_footer=record.ai_footer,
                        commit_included=record.commit_included,
                        final_commit_hash=record.final_commit_hash
                    ))
                
                return executions
                
            except Exception as e:
                print(f"❌ Error getting uncommitted executions: {e}")
                return []
    
    async def _update_commit_message_for_executions(self, db, repo_path: str, commit_message: str):
        """Update uncommitted executions with the final commit message."""
        from sqlalchemy import update, and_
        from .database import AICommitExecution
        
        async with await db.get_session() as session:
            try:
                # Update all uncommitted executions for this repo with the final commit message
                stmt = update(AICommitExecution).where(
                    and_(
                        AICommitExecution.repo_path == repo_path,
                        AICommitExecution.execution_successful == True,
                        AICommitExecution.response_text != "",
                        AICommitExecution.commit_included == False
                    )
                ).values(
                    commit_message=commit_message
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                print(f"📝 Updated {result.rowcount} executions with final commit message")
                
            except Exception as e:
                await session.rollback()
                print(f"❌ Error updating commit message: {e}")
    
    async def mark_as_committed(self, repo_path: str, commit_hash: str):
        """Mark all uncommitted executions for this repo as included in the given commit."""
        db = await get_database()
        
        from sqlalchemy import update, and_
        from .database import AICommitExecution
        
        async with await db.get_session() as session:
            try:
                # Update all uncommitted executions for this repo
                stmt = update(AICommitExecution).where(
                    and_(
                        AICommitExecution.repo_path == repo_path,
                        AICommitExecution.execution_successful == True,
                        AICommitExecution.response_text != "",
                        AICommitExecution.commit_included == False
                    )
                ).values(
                    commit_included=True,
                    commit_hash=commit_hash,
                    final_commit_hash=commit_hash
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                updated_count = result.rowcount
                print(f"✅ Marked {updated_count} AI interactions as committed to {commit_hash[:8]}")
                
                return updated_count
                
            except Exception as e:
                await session.rollback()
                print(f"❌ Error marking executions as committed: {e}")
                return 0
    
    async def get_commit_history(self, repo_path: str, limit: int = 10):
        """Get AI commit history for a repository."""
        db = await get_database()
        
        from sqlalchemy import select
        from .database import AICommitExecution
        
        async with await db.get_session() as session:
            try:
                query = select(AICommitExecution).where(
                    AICommitExecution.repo_path == repo_path
                ).order_by(AICommitExecution.timestamp.desc()).limit(limit)
                
                result = await session.execute(query)
                db_records = result.scalars().all()
                
                # Convert to ExecutionRecord objects
                from .models import ExecutionRecord
                history = []
                for record in db_records:
                    history.append(ExecutionRecord(
                        exec_id=str(record.exec_id),
                        timestamp=record.timestamp,
                        repo_path=record.repo_path,
                        branch_name=record.branch_name,
                        commit_hash=record.commit_hash,
                        model_provider=record.model_provider,
                        model_name=record.model_name,
                        prompt_text=record.prompt_text,
                        response_text=record.response_text,
                        commit_message=record.commit_message,
                        files_changed=record.files_changed,
                        execution_successful=record.execution_successful,
                        user_context=record.user_context or {},
                        performance_metrics={
                            'prompt_tokens': record.prompt_tokens,
                            'completion_tokens': record.completion_tokens,
                            'execution_time_ms': record.execution_time_ms
                        },
                        ai_footer=record.ai_footer,
                        commit_included=record.commit_included,
                        final_commit_hash=record.final_commit_hash
                    ))
                
                return history
                
            except Exception as e:
                print(f"❌ Error getting commit history: {e}")
                return []


# Global interceptor instance
_interceptor: Optional[PromptInterceptor] = None


def get_interceptor() -> PromptInterceptor:
    """Get global prompt interceptor instance."""
    global _interceptor
    if _interceptor is None:
        _interceptor = PromptInterceptor()
    return _interceptor