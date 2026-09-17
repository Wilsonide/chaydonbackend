import time

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

start = time.perf_counter()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

print(f"[DB] engine creation: {time.perf_counter() - start:.3f}s")

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
