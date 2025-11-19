# backend/create_tables.py
import asyncio
from app.db.session import engine
from app.db.models import Base

async def create():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create())
