from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings

# Get settings
settings = get_settings()

# Create async engine from the DATABASE_URL
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,  # Set to True to see SQL queries
)

# Create async session factory
async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

async def get_db() -> AsyncSession:
    """
    Dependency to get an async database session.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def create_tables():
    """
    Create all database tables.
    """
    from app.models.base import Base  # Import your Base model
    async with engine.begin() as conn:
        # This will create tables for all models that inherit from Base
        # Note: In a production environment, you should use Alembic for migrations.
        await conn.run_sync(Base.metadata.create_all)
