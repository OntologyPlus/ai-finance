from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger
import sys

from models.config import settings
from models.database import init_db, db_manager
from api import api_router
from websocket import router as ws_router, ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )
    logger.info("Starting system...")

    await init_db()
    logger.info("Database initialized")

    # ── v12.2: 可选启动 seed（开发环境 SEED_ON_START=True 时自动填充演示数据） ──
    if settings.SEED_ON_START:
        try:
            from seed.seed_all import seed_all
            if settings.SEED_FORCE_RELOAD:
                logger.warning("SEED_FORCE_RELOAD=True, clearing all data and re-seeding...")
            logger.info("Running seed_all (SEED_ON_START=True)...")
            await seed_all(force_reload=settings.SEED_FORCE_RELOAD)
            logger.info("Seed completed successfully")
        except Exception as e:
            logger.warning(f"Seed failed (non-fatal): {e}")

    # ── Ontology initialization ──
    try:
        from ontology.instances import get_instance_manager
        from ontology.events import get_event_bus, setup_default_subscribers
        from ontology.search import init_search_engine
        from ontology.consistency_check import OntologyConsistencyChecker
        from models.database import db_manager

        # Initialize instance manager with DB session
        inst_mgr = get_instance_manager()
        async with db_manager.async_session_factory() as session:
            await inst_mgr.load_from_db(session)
        logger.info(f"Ontology instances loaded: {len(inst_mgr._object_instances)} objects, {len(inst_mgr._relation_instances)} relations")

        # Initialize event bus (session will be injected per-request via API)
        event_bus = get_event_bus()
        setup_default_subscribers()
        logger.info("Ontology event bus initialized")

        # Initialize graph store (Memory + optional Neo4j dual-write) then hydrate
        from storage.runtime import init_graph_store
        from ontology.graph_query import OntologyGraphQuery, set_graph_query
        from ontology.graph_projection import hydrate_from_instances

        neo4j_driver = getattr(db_manager, "neo4j_driver", None)
        store = await init_graph_store(neo4j_driver=neo4j_driver, database=settings.NEO4J_DATABASE)
        await hydrate_from_instances(inst_mgr, store=store)
        gq = OntologyGraphQuery(inst_mgr, store=store)
        set_graph_query(gq)
        from ontology.decision_recorder import get_decision_recorder

        async with db_manager.async_session_factory() as session:
            loaded = await get_decision_recorder().hydrate_from_db(session, store=store)
        logger.info(
            f"Graph query initialized (store={type(store).__name__}, "
            f"Neo4j: {'connected' if neo4j_driver else 'not available'}, "
            f"decisions={loaded})"
        )

        # Initialize search engine with ES
        es_client = getattr(db_manager, 'es_client', None)
        init_search_engine(es_client)
        if es_client:
            from ontology.search import get_search_engine
            await get_search_engine().ensure_index()
        logger.info(f"Search engine initialized (ES: {'connected' if es_client else 'not available'})")

        # Run startup consistency check
        checker = OntologyConsistencyChecker()
        issues = checker.check_all()
        if issues:
            logger.warning(f"Ontology consistency check found {len(issues)} issues")
            for issue in issues[:5]:
                logger.warning(f"  [{issue.severity}] {issue.message}")
        else:
            logger.info("Ontology consistency check passed")
    except Exception as e:
        logger.warning(f"Ontology initialization partial failure: {e}")

    # ── Register scheduled tasks ──
    try:
        from services.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        from engines.alert_monitor import AlertMonitorEngine
        alert_engine = AlertMonitorEngine()

        # Daily scan at 08:00
        scheduler.schedule("daily_alert_scan", "0 8 * * *", lambda: None)
        # Auto-escalate every hour
        scheduler.schedule("auto_escalate", "0 * * * *", lambda: None)
        # Predictive scan every Monday
        scheduler.schedule("predictive_scan", "0 9 * * 1", lambda: None)

        await scheduler.start()
        logger.info("Scheduled tasks registered")
    except Exception as e:
        logger.warning(f"Failed to register scheduled tasks: {e}")

    logger.info("system started successfully")
    yield

    await db_manager.close_all()
    logger.info("system shutdown complete")


app = FastAPI(
    title="集团财经管理AI原生一体化系统",
    description="基于本体驱动的集团财经管理AI原生一体化系统，涵盖预算编制、费用报销、预警监控、经营分析、PDCA复盘、报表出具等全流程",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/api", include_in_schema=False)
async def api_root():
    return RedirectResponse(url="/docs")
