"""Simple database operations for AI provenance tracking."""

import asyncio
import uuid
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, JSON, 
    create_engine, MetaData, Table, select, update
)
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import asyncpg

from .config import get_config


Base = declarative_base()


class AICommitExecution(Base):
    """SQLAlchemy model for AI commit executions - reusing existing schema."""
    
    __tablename__ = "ai_commit_executions"
    __table_args__ = {'schema': 'ai_commit'}
    
    # Primary identification
    exec_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    
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
    
    # Commit tracking
    commit_included = Column(Boolean, default=False, nullable=False, index=True)
    final_commit_hash = Column(String(40), nullable=True, index=True)
    
    # Performance metrics
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    
    # Additional context
    user_context = Column(JSON, nullable=True)
    ai_footer = Column(Text, nullable=True)


class DatabaseManager:
    """Simple database manager for AI provenance tracking."""
    
    def __init__(self):
        config = get_config()
        self.database_url = config["database_url"]
        self.schema_name = config["database_schema"]
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        if self._initialized:
            return
        
        # Convert postgres:// to postgresql:// for asyncpg
        async_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        
        # Create async engine
        self.engine = create_async_engine(
            async_url,
            pool_size=5,
            max_overflow=10,
            echo=False  # Set to True for SQL debugging
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
            await conn.execute(text(f"SET search_path TO {self.schema_name}, public"))
            await conn.run_sync(Base.metadata.create_all)
        
        self._initialized = True
        print(f"✅ Database initialized: {self.database_url} (schema: {self.schema_name})")
    
    async def _ensure_schema_exists(self) -> None:
        """Ensure the schema exists in the database."""
        # Connect directly with asyncpg to create schema
        asyncpg_url = self.database_url.replace("postgresql://", "")
        conn = await asyncpg.connect(f"postgresql://{asyncpg_url}")
        try:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")
            print(f"✅ Schema ensured: {self.schema_name}")
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
        await session.execute(text(f"SET search_path TO {self.schema_name}, public"))
        
        return session
    
    async def store_execution(self, execution: AICommitExecution) -> str:
        """Store an execution record."""
        async with await self.get_session() as session:
            try:
                session.add(execution)
                await session.commit()
                print(f"✅ Stored execution: {execution.exec_id}")
                return str(execution.exec_id)
            except Exception as e:
                await session.rollback()
                print(f"❌ Error storing execution: {e}")
                raise e
    
    async def get_execution(self, exec_id: str) -> Optional[AICommitExecution]:
        """Get an execution by ID."""
        async with await self.get_session() as session:
            try:
                query = select(AICommitExecution).where(
                    AICommitExecution.exec_id == uuid.UUID(exec_id)
                )
                result = await session.execute(query)
                return result.scalar_one_or_none()
            except Exception as e:
                print(f"❌ Error getting execution: {e}")
                return None
    
    async def get_uncommitted_executions(self, repo_path: str) -> List[AICommitExecution]:
        """Get uncommitted executions for a repository."""
        async with await self.get_session() as session:
            try:
                from sqlalchemy import and_
                query = select(AICommitExecution).where(
                    and_(
                        AICommitExecution.repo_path == repo_path,
                        AICommitExecution.commit_included == False,
                        AICommitExecution.execution_successful == True
                    )
                ).order_by(AICommitExecution.timestamp.desc()).limit(5)
                
                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                print(f"❌ Error getting uncommitted executions: {e}")
                return []
    
    async def mark_executions_committed(self, exec_ids: List[str], commit_hash: str, commit_message: str) -> int:
        """Mark executions as committed."""
        async with await self.get_session() as session:
            try:
                stmt = update(AICommitExecution).where(
                    AICommitExecution.exec_id.in_([uuid.UUID(eid) for eid in exec_ids])
                ).values(
                    commit_included=True,
                    final_commit_hash=commit_hash,
                    commit_message=commit_message
                )
                
                result = await session.execute(stmt)
                await session.commit()
                
                updated_count = result.rowcount
                print(f"✅ Marked {updated_count} executions as committed to {commit_hash[:8]}")
                return updated_count
                
            except Exception as e:
                await session.rollback()
                print(f"❌ Error marking executions as committed: {e}")
                return 0


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager


async def close_database():
    """Close global database connection."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None