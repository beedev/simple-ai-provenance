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


class PromptInterceptor:
    """Intercepts and logs all AI prompts/responses for commit generation."""
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.active_prompts = {}  # Track ongoing prompts
        
    async def log_prompt(self, prompt_text: str, context: Dict[str, Any]) -> str:
        """Log an outgoing prompt to AI model."""
        exec_id = str(uuid.uuid4())
        
        # Store prompt immediately when sent
        db = await get_database()
        
        # Create partial execution record (response will be added later)
        record = ExecutionRecord(
            exec_id=exec_id,
            timestamp=datetime.utcnow(),
            repo_path=context.get('repo_path', os.getcwd()),
            branch_name=context.get('branch_name', 'unknown'),
            commit_hash=None,  # Will be set when commit happens
            model_provider=context.get('model_provider', 'unknown'),
            model_name=context.get('model_name', 'unknown'),
            prompt_text=prompt_text,
            response_text="",  # Will be filled when response comes
            commit_message="",  # Will be filled when commit happens
            files_changed=[],
            execution_successful=False,
            user_context=context,
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
                    commit_message=response_text,
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
        """Consolidate all recent prompts/responses for this repo into commit footer."""
        db = await get_database()
        
        # Get recent executions for this repo (last 10 minutes)
        from datetime import timedelta
        recent_time = datetime.utcnow() - timedelta(minutes=10)
        
        executions = await db.search_executions(
            repo_path=repo_path,
            successful_only=True,
            limit=10
        )
        
        # Filter to recent ones
        recent_executions = [
            exec for exec in executions 
            if exec.timestamp > recent_time and exec.response_text
        ]
        
        if not recent_executions:
            return commit_message
        
        # Build consolidated footer
        footer_lines = ["\n"]
        
        for i, exec_record in enumerate(recent_executions[:3]):  # Max 3 recent
            footer_lines.append(f"🤖 AI-Generated Content (exec_id: {exec_record.exec_id})")
            footer_lines.append(f"   Model: {exec_record.model_provider}/{exec_record.model_name}")
            footer_lines.append(f"   Prompt: {exec_record.prompt_text[:100]}...")
            footer_lines.append(f"   Response: {exec_record.response_text[:100]}...")
            footer_lines.append(f"   Timestamp: {exec_record.timestamp.isoformat()}Z")
            footer_lines.append("")
        
        footer_lines.append("📊 Provenance: All AI interactions logged in database")
        
        final_message = commit_message + "\n".join(footer_lines)
        
        # Update all records with final commit hash (will be set after commit)
        for exec_record in recent_executions:
            exec_record.commit_message = final_message
        
        print(f"🔗 Consolidated {len(recent_executions)} AI interactions for commit")
        return final_message


# Global interceptor instance
_interceptor: Optional[PromptInterceptor] = None


def get_interceptor() -> PromptInterceptor:
    """Get global prompt interceptor instance."""
    global _interceptor
    if _interceptor is None:
        _interceptor = PromptInterceptor()
    return _interceptor