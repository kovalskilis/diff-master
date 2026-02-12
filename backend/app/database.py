from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings

# Convert postgresql:// to postgresql+asyncpg://

import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(database_url, echo=True, future=True)

async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def create_db_and_tables():
    """
    Create all database tables based on SQLAlchemy models.

    IMPORTANT: we must import models before calling Base.metadata.create_all,
    otherwise metadata will be empty and no tables will be created. This
    function is used both at app startup (lifespan) and from one-off scripts
    inside Docker, so the import has to be local to avoid circular imports.
    """
    import asyncio
    
    # Import models so that they are registered on Base.metadata
    try:
        # When running inside the app package
        from models import (  # type: ignore  # noqa: F401
            BaseDocument,
            Article,
            Snapshot,
            ArticleVersion,
            WorkspaceFile,
            EditTarget,
            PatchedFragment,
            ExcelReport,
            AuditLog,
            TaxUnit,
            TaxUnitVersion,
        )
    except Exception:
        # Fallback for different import contexts; it's enough to import the module
        import models  # type: ignore  # noqa: F401

    # Retry logic: wait for database to be ready (up to 30 seconds)
    max_retries = 30
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print(f"✅ Database tables created successfully")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️  Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(retry_delay)
            else:
                print(f"❌ Failed to create database tables after {max_retries} attempts: {e}")
                raise

