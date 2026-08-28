from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import get_db, db_manager
from models.schemas import APIResponse

router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check():
    checks = {
        "database": "unknown",
        "neo4j": "unknown",
        "redis": "unknown",
        "elasticsearch": "unknown",
    }

    try:
        async with db_manager.async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"

    checks["neo4j"] = "ok" if db_manager.neo4j_driver else "disabled"
    checks["redis"] = "ok" if db_manager.redis_client else "disabled"
    checks["elasticsearch"] = "ok" if db_manager.es_client else "disabled"

    all_ok = all(
        v in ("ok", "disabled", "unknown") for v in checks.values()
    )

    return APIResponse(
        success=all_ok,
        message="healthy" if all_ok else "degraded",
        data=checks,
    )


@router.get("/health/ping", response_model=APIResponse)
async def ping():
    return APIResponse(success=True, message="pong")
