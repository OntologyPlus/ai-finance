"""数据库自动初始化脚本，docker-compose启动时执行"""
from __future__ import annotations

import asyncio
from loguru import logger


async def init_db():
    from models.database import db_manager
    await db_manager.init_all()
    await db_manager.create_tables()

    from sqlalchemy.ext.asyncio import AsyncSession
    async with db_manager.async_session_factory() as session:
        try:
            from seed.budget import seed_budget
            await seed_budget(session)
            from seed.expense import seed_expense
            await seed_expense(session)
            from seed.alert import seed_alert
            await seed_alert(session)
            from seed.memory import seed_memory
            await seed_memory(session)
            await session.commit()
            logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            await session.rollback()
            raise
    await db_manager.close_all()


if __name__ == "__main__":
    asyncio.run(init_db())
