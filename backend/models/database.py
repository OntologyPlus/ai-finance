from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from loguru import logger
from typing import AsyncGenerator, Optional, Any

from models.config import settings

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
except ImportError:
    AsyncGraphDatabase = None
    AsyncDriver = None

try:
    from redis.asyncio import Redis
except ImportError:
    Redis = None

try:
    from elasticsearch import AsyncElasticsearch
except ImportError:
    AsyncElasticsearch = None


class Base(DeclarativeBase):
    pass


class DatabaseManager:
    def __init__(self):
        self.async_engine = None
        self.async_session_factory = None
        self.neo4j_driver: Optional[Any] = None
        self.redis_client: Optional[Any] = None
        self.es_client: Optional[Any] = None

    async def init_mysql(self):
        self.async_engine = create_async_engine(
            settings.MYSQL_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={"charset": "utf8mb4"},
        )
        async with self.async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Using MySQL")

        self.async_session_factory = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_neo4j(self):
        if AsyncGraphDatabase is None:
            logger.warning("neo4j package not installed, running without Neo4j")
            self.neo4j_driver = None
            return
        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URL,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            await self.neo4j_driver.verify_connectivity()
            logger.info("Neo4j connected")
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}, running without Neo4j")
            self.neo4j_driver = None

    async def init_redis(self):
        if Redis is None:
            logger.warning("redis package not installed, running without Redis")
            self.redis_client = None
            return
        try:
            redis_url = settings.REDIS_URL
            # If REDIS_PASSWORD is set and not already in URL, append it
            if settings.REDIS_PASSWORD and "@" not in redis_url:
                # redis://localhost:6379/0 → redis://:password@localhost:6379/0
                redis_url = redis_url.replace("redis://", f"redis://:{settings.REDIS_PASSWORD}@")
            self.redis_client = Redis.from_url(
                redis_url,
                decode_responses=True,
            )
            await self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, running without Redis")
            self.redis_client = None

    async def init_elasticsearch(self):
        if AsyncElasticsearch is None:
            logger.warning("elasticsearch package not installed, running without ES")
            self.es_client = None
            return
        try:
            self.es_client = AsyncElasticsearch(hosts=[settings.ELASTIC_URL])
            await self.es_client.ping()
            logger.info("Elasticsearch connected")
        except Exception as e:
            logger.warning(f"Elasticsearch connection failed: {e}, running without ES")
            self.es_client = None

    async def init_all(self):
        await self.init_mysql()
        await self.init_neo4j()
        await self.init_redis()
        await self.init_elasticsearch()

    async def close_all(self):
        if self.async_engine:
            await self.async_engine.dispose()
            logger.info("MySQL engine disposed")

        if self.neo4j_driver:
            await self.neo4j_driver.close()
            logger.info("Neo4j driver closed")

        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis client closed")

        if self.es_client:
            await self.es_client.close()
            logger.info("Elasticsearch client closed")

    async def create_tables(self):
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    # v12.2: 主动 import 所有 model，确保 Base.metadata 完整注册（create_all 只建已注册的表）
    from models import budget, expense, approval, alert, organization, analysis, ontology
    from models import caliber, transfer, form, user, strategic
    from models import cash_flow, cost_center, hcp_compliance, rnd_pipeline, scenario
    from models import impact_assessment, zero_based_budget, approval_config, archive
    from models import business_review, contract, milestone, budget_occupation
    from models import pending_item, report_signoff, trace_feedback, expense_effect, memory, decision
    from models import expense_ops, budget_version, rule_catalog
    await db_manager.init_all()
    await db_manager.create_tables()
