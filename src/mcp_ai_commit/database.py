"""Database management for AI commit provenance tracking."""

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, JSON, 
    create_engine, MetaData, Table
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import asyncpg

from .config import get_config
from .models import ExecutionRecord, CommitResponse


Base = declarative_base()


class AICommitExecution(Base):
    """SQLAlchemy model for AI commit executions."""
    
    __tablename__ = "ai_commit_executions"
    __table_args__ = {'schema': 'ai_commit'}
    
    # Primary identification
    exec_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Repository context
    repo_path = Column(String(500), nullable=False)
    branch_name = Column(String(100), nullable=False)
    commit_hash = Column(String(40), nullable=True, index=True)
    
    # AI interaction
    model_provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    
    # Results
    commit_message = Column(Text, nullable=False)
    commit_body = Column(Text, nullable=True)
    files_changed = Column(JSON, nullable=False)  # List of file paths
    
    # Execution status
    execution_successful = Column(Boolean, default=False, nullable=False)
    validation_passed = Column(Boolean, default=True, nullable=False)
    validation_errors = Column(JSON, nullable=True)  # List of error messages
    
    # Performance metrics
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    
    # Additional context
    user_context = Column(JSON, nullable=True)
    ai_footer = Column(Text, nullable=True)
    
class AICommitConfiguration(Base):
    """SQLAlchemy model for saved configurations."""
    
    __tablename__ = "ai_commit_configurations"
    __table_args__ = {'schema': 'ai_commit'}
    
    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Configuration data
    config_data = Column(JSON, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_default = Column(Boolean, default=False)


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self):
        self.config = get_config()
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        if self._initialized:
            return
        
        # Create async engine
        self.engine = create_async_engine(
            self.config.database.connection_url,
            pool_size=self.config.database.min_connections,
            max_overflow=self.config.database.max_connections - self.config.database.min_connections,
            echo=self.config.server.log_level == "DEBUG"
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Ensure schema exists
        await self._ensure_schema_exists()
        
        # Create tables
        async with self.engine.begin() as conn:
            # Set search path to include our schema
            from sqlalchemy import text
            await conn.execute(text(f"SET search_path TO {self.config.database.schema_name}, public"))
            await conn.run_sync(Base.metadata.create_all)
        
        self._initialized = True
    
    async def _ensure_schema_exists(self) -> None:
        """Ensure the schema exists in the database."""
        # Connect directly with asyncpg to create schema
        conn = await asyncpg.connect(self.config.database.asyncpg_url)
        try:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.database.schema_name}")
        finally:
            await conn.close()
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self._initialized = False
    
    async def get_session(self) -> AsyncSession:
        """Get an async database session."""
        if not self._initialized:
            await self.initialize()
        
        session = self.session_factory()
        # Set search path for this session
        from sqlalchemy import text
        await session.execute(text(f"SET search_path TO {self.config.database.schema_name}, public"))
        return session
    
    async def store_execution(self, record: ExecutionRecord) -> str:
        """Store an execution record in the database."""
        async with await self.get_session() as session:
            try:
                db_record = AICommitExecution(
                    exec_id=uuid.UUID(record.exec_id) if isinstance(record.exec_id, str) else record.exec_id,
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
                    user_context=record.user_context,
                    ai_footer=record.ai_footer,
                    # Map performance_metrics to database fields
                    prompt_tokens=record.performance_metrics.get('prompt_tokens', 0),
                    completion_tokens=record.performance_metrics.get('completion_tokens', 0),
                    execution_time_ms=record.performance_metrics.get('execution_time_ms', 0)
                )
                
                session.add(db_record)
                await session.commit()
                return str(db_record.exec_id)
                
            except Exception as e:
                await session.rollback()
                raise e
    
    async def get_execution(self, exec_id: str) -> Optional[ExecutionRecord]:
        """Retrieve an execution record by ID."""
        async with await self.get_session() as session:
            try:
                from sqlalchemy import select
                result = await session.execute(
                    select(AICommitExecution).where(AICommitExecution.exec_id == uuid.UUID(exec_id))
                )
                db_record = result.scalar_one_or_none()
                
                if not db_record:
                    return None
                
                return ExecutionRecord(
                    exec_id=str(db_record.exec_id),
                    timestamp=db_record.timestamp,
                    repo_path=db_record.repo_path,
                    branch_name=db_record.branch_name,
                    commit_hash=db_record.commit_hash,
                    model_provider=db_record.model_provider,
                    model_name=db_record.model_name,
                    prompt_text=db_record.prompt_text,
                    response_text=db_record.response_text,
                    commit_message=db_record.commit_message,
                    files_changed=db_record.files_changed,
                    execution_successful=db_record.execution_successful,
                    user_context=db_record.user_context or {},
                    performance_metrics={
                        'prompt_tokens': db_record.prompt_tokens,
                        'completion_tokens': db_record.completion_tokens,
                        'execution_time_ms': db_record.execution_time_ms
                    },
                    ai_footer=db_record.ai_footer
                )
                
            except Exception as e:
                raise e
    
    async def search_executions(
        self,
        repo_path: Optional[str] = None,
        branch_name: Optional[str] = None,
        successful_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[ExecutionRecord]:
        """Search execution records with filters."""
        async with await self.get_session() as session:
            try:
                from sqlalchemy import select, and_
                
                query = select(AICommitExecution)
                
                conditions = []
                if repo_path:
                    conditions.append(AICommitExecution.repo_path == repo_path)
                if branch_name:
                    conditions.append(AICommitExecution.branch_name == branch_name)
                if successful_only:
                    conditions.append(AICommitExecution.execution_successful == True)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                query = query.order_by(AICommitExecution.timestamp.desc()).limit(limit).offset(offset)
                
                result = await session.execute(query)
                db_records = result.scalars().all()
                
                return [
                    ExecutionRecord(
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
                        ai_footer=record.ai_footer
                    )
                    for record in db_records
                ]
                
            except Exception as e:
                raise e
    
    async def get_repository_stats(self, repo_path: str) -> Dict[str, Any]:
        """Get statistics for a specific repository."""
        async with await self.get_session() as session:
            try:
                from sqlalchemy import select, func
                
                # Total executions
                total_result = await session.execute(
                    select(func.count(AICommitExecution.exec_id))
                    .where(AICommitExecution.repo_path == repo_path)
                )
                total_executions = total_result.scalar()
                
                # Successful executions
                success_result = await session.execute(
                    select(func.count(AICommitExecution.exec_id))
                    .where(
                        and_(
                            AICommitExecution.repo_path == repo_path,
                            AICommitExecution.execution_successful == True
                        )
                    )
                )
                successful_executions = success_result.scalar()
                
                # Most recent execution
                recent_result = await session.execute(
                    select(AICommitExecution.timestamp)
                    .where(AICommitExecution.repo_path == repo_path)
                    .order_by(AICommitExecution.timestamp.desc())
                    .limit(1)
                )
                most_recent = recent_result.scalar()
                
                return {
                    "total_executions": total_executions,
                    "successful_executions": successful_executions,
                    "success_rate": successful_executions / total_executions if total_executions > 0 else 0.0,
                    "most_recent_execution": most_recent.isoformat() if most_recent else None
                }
                
            except Exception as e:
                raise e


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def close_database() -> None:
    """Close global database connections."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None