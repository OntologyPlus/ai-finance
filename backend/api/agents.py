from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from agents.base import get_all, get as get_agent_cls
from services.orchestrator import AgentOrchestrator


router = APIRouter()


class AgentExecuteRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., description="对话消息列表")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")


_orchestrator: AgentOrchestrator | None = None


def _get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


@router.get("/agents", response_model=APIResponse)
async def list_agents():
    registry = get_all()
    agents = []
    for name, cls in registry.items():
        agents.append({
            "name": name,
            "description": cls.description if hasattr(cls, "description") else "",
            "supported_intents": cls.supported_intents if hasattr(cls, "supported_intents") else [],
        })
    return APIResponse(success=True, data=agents)


@router.get("/agents/{name}", response_model=APIResponse)
async def get_agent_detail(name: str):
    cls = get_agent_cls(name)
    if cls is None:
        return APIResponse(success=False, message=f"Agent '{name}' not found")

    tools = []
    if hasattr(cls, "get_default_tools"):
        try:
            instance = cls()
            tools = instance.get_default_tools()
        except Exception:
            pass

    return APIResponse(success=True, data={
        "name": name,
        "description": cls.description if hasattr(cls, "description") else "",
        "supported_intents": cls.supported_intents if hasattr(cls, "supported_intents") else [],
        "system_prompt": cls.system_prompt if hasattr(cls, "system_prompt") else "",
        "tools": tools,
    })


@router.post("/agents/{name}/execute", response_model=APIResponse)
async def execute_agent(
    name: str,
    request: AgentExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    cls = get_agent_cls(name)
    if cls is None:
        return APIResponse(success=False, message=f"Agent '{name}' not found")

    try:
        instance = cls()
        result = await instance.execute(request.messages, request.context, db)
        return APIResponse(success=True, data={"response": result})
    except Exception as e:
        logger.error(f"Agent execution error [{name}]: {e}")
        return APIResponse(success=False, message=str(e))
