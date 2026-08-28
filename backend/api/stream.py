from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db


router = APIRouter()


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., description="对话消息列表")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")
    stream: bool = Field(True, description="是否流式输出")


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


@router.post("/stream/chat")
async def stream_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    if not request.stream:
        return {"success": True, "data": {"response": "Non-stream mode not available in demo"}}

    return StreamingResponse(
        _generate_stream(request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_stream(request: ChatRequest, db: AsyncSession):
    session_id = str(uuid.uuid4())[:8]

    try:
        yield _sse_event("thinking", {"session_id": session_id, "message": "正在分析您的请求..."})

        user_input = ""
        for m in reversed(request.messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break

        from services.intent_classifier import IntentClassifier
        classifier = IntentClassifier()
        intent, confidence = await classifier.classify(user_input)

        yield _sse_event("intent", {"intent": intent, "confidence": confidence})

        from services.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        routing = await orchestrator.route(request.messages, request.context, db)
        yield _sse_event("routing", {
            "agent": routing["agent_name"],
            "intent": intent,
            "confidence": confidence,
        })

        # v11.0: emit ontology meta (scene + rules) so frontend can show reasoning
        try:
            from ontology.scenes import get_scene
            from agents.base import match_scene
            ontology_meta = await _build_ontology_meta(user_input, routing["agent_name"], request.context)
            if ontology_meta:
                yield _sse_event("ontology", ontology_meta)
        except Exception as e:
            logger.debug(f"ontology meta emit failed: {e}")

        from utils.llm_client import get_llm_client
        llm = get_llm_client()

        agent = routing.get("agent")
        if agent and hasattr(agent, "system_prompt") and agent.system_prompt:
            full_messages = [{"role": "system", "content": agent.system_prompt}] + request.messages
        else:
            full_messages = request.messages

        tools = agent.get_default_tools() if agent and hasattr(agent, "get_default_tools") else []

        collected_content = ""
        tool_calls_found = False

        if tools:
            bound_llm = llm.bind_tools(tools)
            response = await bound_llm.invoke(full_messages, temperature=0.3)

            if response.tool_calls:
                tool_calls_found = True
                tool_names = [tc.get("function", {}).get("name", "") for tc in response.tool_calls]
                yield _sse_event("tools_used", {"tools": tool_names})

                result = await orchestrator.execute(request.messages, request.context, db)
                collected_content = result["response"]
            else:
                collected_content = response.content
        else:
            for chunk in llm.stream(full_messages, temperature=0.3):
                collected_content += chunk
                yield _sse_event("content", {"chunk": chunk, "session_id": session_id})

        if tool_calls_found and collected_content:
            yield _sse_event("content", {"chunk": collected_content, "session_id": session_id})

        suggestions = agent.get_suggestions() if agent and hasattr(agent, "get_suggestions") else []
        yield _sse_event("suggestions", {"suggestions": suggestions})

        yield _sse_event("done", {
            "session_id": session_id,
            "intent": intent,
            "agent": routing["agent_name"],
        })

    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        yield _sse_event("error", {"message": str(e), "session_id": session_id})


async def _build_ontology_meta(user_input: str, agent_name: str, context: dict) -> dict:
    """v11.0: Build ontology meta for chat reasoning transparency.

    Returns dict with scene_id, scene_name, activated_rules, activated_behaviors,
    matched_objects, confidence, elapsed_ms.
    """
    import time
    started = time.time()
    try:
        from ontology.scenes import match_scene_semantic
        matches = await match_scene_semantic(user_input, top_k=1, min_score=0.2)
        if not matches:
            return None
        scene_id, confidence, desc = matches[0]
        from ontology.scenes import get_scene
        from ontology.relations import get_relations_for_scene
        from ontology.behaviors import get_behaviors_for_scene
        scene = get_scene(scene_id)
        if scene is None:
            return {
                "scene_id": scene_id,
                "scene_name": scene_id,
                "confidence": round(confidence, 3),
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        # Collect activated rules and behaviors (from scene + reasoning)
        activated_rules = list(scene.activated_rules or [])
        activated_behaviors = list(scene.activated_behaviors or [])
        activated_objects = list(scene.activated_objects or [])
        return {
            "scene_id": scene_id,
            "scene_name": scene.name,
            "stage": scene.stage,
            "confidence": round(confidence, 3),
            "matched_objects": activated_objects[:6],
            "activated_rules": activated_rules,
            "activated_behaviors": activated_behaviors,
            "agent_name": agent_name,
            "elapsed_ms": int((time.time() - started) * 1000),
        }
    except Exception as e:
        logger.debug(f"_build_ontology_meta failed: {e}")
        return None
