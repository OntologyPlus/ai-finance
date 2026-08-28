from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_memory(db: AsyncSession) -> None:
    """初始化记忆表种子数据"""
    from models.memory import UserProfile

    # 检查是否已有数据
    from sqlalchemy import select
    result = await db.execute(select(UserProfile).limit(1))
    if result.scalar_one_or_none():
        logger.info("Memory seed data already exists, skipping")
        return

    # 创建默认用户画像
    default_profiles = [
        UserProfile(
            user_id="admin",
            role="管理员",
            department="集团财经部",
            preferences={"language": "zh", "detail_level": "high"},
            behavior_patterns=[],
        ),
        UserProfile(
            user_id="demo_user",
            role="财经BP",
            department="战略规划中心",
            preferences={"language": "zh", "detail_level": "medium"},
            behavior_patterns=[{"pattern": "每周一查预算执行率", "frequency": "weekly"}],
        ),
    ]

    for profile in default_profiles:
        db.add(profile)

    await db.flush()
    logger.info(f"Memory seed data created: {len(default_profiles)} profiles")
