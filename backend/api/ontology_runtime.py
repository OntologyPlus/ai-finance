"""v11.0 本体运行仪表盘 API

从 ReasoningTrace、OntologyEvent、OntologyRule 等表聚合运行时数据。
用于前端"语义仪表盘"展示。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.ontology import (
    OntologyRule,
    OntologyScene,
    ReasoningTrace,
)
from models.schemas import APIResponse
from ontology.events import get_event_bus, OntologyEventType
from ontology.scenes import get_all_scenes

router = APIRouter()

# 5 分钟缓存（内存）
_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL: float = 300.0


def _cache_key(prefix: str, **kwargs) -> str:
    items = sorted(kwargs.items())
    return f"{prefix}:{':'.join(f'{k}={v}' for k, v in items)}"


def _is_cached(key: str) -> bool:
    if key not in _CACHE:
        return False
    age = (datetime.now() - _CACHE[key]["_time"]).total_seconds()
    return age < _CACHE_TTL


def _set_cache(key: str, data: Any) -> None:
    _CACHE[key] = {"data": data, "_time": datetime.now()}


def _get_cache(key: str) -> Any:
    return _CACHE[key]["data"]


# ─────────────────────────────────────────────────────────────
# 1. 场景命中 TOP（24h）
# ─────────────────────────────────────────────────────────────
@router.get("/ontology/runtime/scenes", response_model=APIResponse)
async def runtime_scenes(db: AsyncSession = Depends(get_db)):
    """24h 场景命中 TOP + 全部活跃场景"""
    key = _cache_key("scenes", window="24h")
    if _is_cached(key):
        return APIResponse(success=True, data=_get_cache(key))

    try:
        scenes = get_all_scenes()
        scene_ids = list(scenes.keys())

        # 24h 窗口
        cutoff = datetime.now() - timedelta(hours=24)

        # ReasoningTrace 表
        try:
            stmt = (
                select(ReasoningTrace.scene_name, func.count(ReasoningTrace.trace_id))
                .where(ReasoningTrace.created_at >= cutoff)
                .group_by(ReasoningTrace.scene_name)
            )
            result = await db.execute(stmt)
            hits = {row[0]: row[1] for row in result.all() if row[0]}
        except Exception:
            hits = {}

        # 事件总线历史
        try:
            bus = get_event_bus()
            events = await bus.get_event_history(limit=500)
            for e in events:
                if e.created_at and e.created_at >= cutoff:
                    # 尝试从 payload 推断场景
                    if e.payload and "scene" in e.payload:
                        sname = e.payload["scene"]
                        hits[sname] = hits.get(sname, 0) + 1
        except Exception:
            pass

        # 拼装
        scene_data = []
        for sid, sdef in scenes.items():
            hit_count = hits.get(sid, 0) + hits.get(sdef.name, 0)
            scene_data.append({
                "scene_id": sid,
                "name": sdef.name,
                "stage": sdef.stage,
                "description": sdef.description,
                "hit_count_24h": hit_count,
                "activated_objects_count": len(sdef.activated_objects or []),
                "activated_rules_count": len(sdef.activated_rules or []),
                "activated_behaviors_count": len(sdef.activated_behaviors or []),
            })

        scene_data.sort(key=lambda x: x["hit_count_24h"], reverse=True)
        active_count = sum(1 for s in scene_data if s["hit_count_24h"] > 0)
        total_hits = sum(s["hit_count_24h"] for s in scene_data)

        out = {
            "scenes": scene_data,
            "active_scenes": active_count,
            "total_scenes": len(scene_data),
            "total_hits_24h": total_hits,
            "window": "24h",
        }
        _set_cache(key, out)
        return APIResponse(success=True, data=out)
    except Exception as e:
        logger.error(f"runtime_scenes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# 2. 规则使用率
# ─────────────────────────────────────────────────────────────
@router.get("/ontology/runtime/rules", response_model=APIResponse)
async def runtime_rules(db: AsyncSession = Depends(get_db)):
    """规则使用率：哪些在用 / 哪些是死规则"""
    key = _cache_key("rules", window="all")
    if _is_cached(key):
        return APIResponse(success=True, data=_get_cache(key))

    try:
        # 全部规则
        stmt = select(OntologyRule).where(OntologyRule.is_active.is_(True))
        result = await db.execute(stmt)
        all_rules = result.scalars().all()

        # 推理轨迹中出现的 rule_id
        try:
            stmt2 = select(ReasoningTrace.steps)
            result2 = await db.execute(stmt2)
            all_steps_json = [row[0] for row in result2.all() if row[0]]
        except Exception:
            all_steps_json = []

        used_count = 0
        rule_usage: Dict[str, int] = defaultdict(int)
        for sjson in all_steps_json:
            try:
                steps_data = json.loads(sjson) if isinstance(sjson, str) else sjson
                if isinstance(steps_data, list):
                    for step in steps_data:
                        if isinstance(step, dict):
                            rid = step.get("rule_id") or step.get("rule")
                            if rid:
                                rule_usage[rid] += 1
                elif isinstance(steps_data, dict):
                    rid = steps_data.get("rule_id") or steps_data.get("rule")
                    if rid:
                        rule_usage[rid] += 1
            except Exception:
                pass

        # Scene 里激活的 rule_ids 也算"被使用过"
        scenes = get_all_scenes()
        for sdef in scenes.values():
            for rid in sdef.activated_rules or []:
                rule_usage[rid] += 1

        rule_list = []
        for r in all_rules:
            used = rule_usage.get(r.rule_id, 0)
            if used > 0:
                used_count += 1
            rule_list.append({
                "rule_id": r.rule_id,
                "name": r.rule_name,
                "rule_type": r.rule_type,
                "hit_count": used,
                "is_dead": used == 0,
            })

        rule_list.sort(key=lambda x: x["hit_count"], reverse=True)
        dead_rules = [r for r in rule_list if r["is_dead"]]

        out = {
            "rules": rule_list,
            "total": len(rule_list),
            "used": used_count,
            "dead_count": len(dead_rules),
            "dead_rules": dead_rules[:20],
            "top_used": [r for r in rule_list if r["hit_count"] > 0][:10],
        }
        _set_cache(key, out)
        return APIResponse(success=True, data=out)
    except Exception as e:
        logger.error(f"runtime_rules error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# 3. 覆盖度（业务事件 → 场景）
# ─────────────────────────────────────────────────────────────
@router.get("/ontology/runtime/coverage", response_model=APIResponse)
async def runtime_coverage(db: AsyncSession = Depends(get_db)):
    """业务事件 → 场景覆盖率"""
    key = _cache_key("coverage", window="7d")
    if _is_cached(key):
        return APIResponse(success=True, data=_get_cache(key))

    try:
        bus = get_event_bus()
        events = await bus.get_event_history(limit=1000)
        cutoff = datetime.now() - timedelta(days=7)
        recent_events = [e for e in events if e.created_at and e.created_at >= cutoff]

        total_events = len(recent_events)
        events_by_type: Dict[str, int] = Counter()
        events_with_scene = 0

        for e in recent_events:
            events_by_type[e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)] += 1
            if e.payload and ("scene" in e.payload or "scene_id" in e.payload):
                events_with_scene += 1

        # 已定义场景
        scenes = get_all_scenes()
        defined_scenes = len(scenes)

        # 事件类型映射到场景
        type_scene_map = {
            "BUDGET_GRANTED": "fin.budget_grant",
            "BUDGET_ADJUSTED": "fin.budget_adjustment",
            "BUDGET_WRITTEN_OFF": "fin.expense_reimbursement",
            "ALERT_TRIGGERED": "fin.alert_monitoring",
            "ALERT_CLOSED": "fin.alert_response",
            "ALERT_ESCALATED": "fin.alert_response",
        }

        covered_types = sum(1 for t in events_by_type if t in type_scene_map)
        coverage_rate = (covered_types / max(len(events_by_type), 1)) * 100

        out = {
            "total_events_7d": total_events,
            "events_by_type": dict(events_by_type),
            "events_with_scene_meta": events_with_scene,
            "defined_scenes": defined_scenes,
            "covered_event_types": covered_types,
            "coverage_rate": round(coverage_rate, 1),
            "window": "7d",
        }
        _set_cache(key, out)
        return APIResponse(success=True, data=out)
    except Exception as e:
        logger.error(f"runtime_coverage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# 4. 最近推理链路
# ─────────────────────────────────────────────────────────────
@router.get("/ontology/runtime/traces", response_model=APIResponse)
async def runtime_traces(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """最近 N 条推理 trace（来自 ReasoningTrace 表）"""
    try:
        stmt = select(ReasoningTrace).order_by(ReasoningTrace.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        traces = result.scalars().all()

        items = []
        for t in traces:
            steps = []
            try:
                steps = json.loads(t.steps) if t.steps else []
                if not isinstance(steps, list):
                    steps = [steps]
            except Exception:
                steps = []

            items.append({
                "trace_id": t.trace_id,
                "scene_id": t.scene_id,
                "scene_name": t.scene_name,
                "conclusion": t.conclusion,
                "rule_ids": json.loads(t.rule_ids) if isinstance(t.rule_ids, str) else (t.rule_ids or []),
                "step_count": len(steps) if isinstance(steps, list) else 0,
                "elapsed_ms": t.elapsed_ms,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        return APIResponse(success=True, data={"traces": items, "count": len(items)})
    except Exception as e:
        logger.error(f"runtime_traces error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# 5. 整体运行统计（KPI）
# ─────────────────────────────────────────────────────────────
@router.get("/ontology/runtime/stats", response_model=APIResponse)
async def runtime_stats(db: AsyncSession = Depends(get_db)):
    """整体运行统计：4 个 KPI 一站式"""
    key = _cache_key("stats", all="1")
    if _is_cached(key):
        return APIResponse(success=True, data=_get_cache(key))

    try:
        scenes_data = (await runtime_scenes(db)).data
        rules_data = (await runtime_rules(db)).data
        coverage_data = (await runtime_coverage(db)).data

        out = {
            "active_scenes": scenes_data.get("active_scenes", 0),
            "total_scenes": scenes_data.get("total_scenes", 0),
            "total_hits_24h": scenes_data.get("total_hits_24h", 0),
            "rules_total": rules_data.get("total", 0),
            "rules_used": rules_data.get("used", 0),
            "rules_dead": rules_data.get("dead_count", 0),
            "coverage_rate_7d": coverage_data.get("coverage_rate", 0),
            "total_events_7d": coverage_data.get("total_events_7d", 0),
            "updated_at": datetime.now().isoformat(),
        }
        _set_cache(key, out)
        return APIResponse(success=True, data=out)
    except Exception as e:
        logger.error(f"runtime_stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# 6. 清除缓存
# ─────────────────────────────────────────────────────────────
@router.post("/ontology/runtime/refresh", response_model=APIResponse)
async def refresh_cache():
    """清除缓存（开发用）"""
    _CACHE.clear()
    return APIResponse(success=True, message="Cache cleared")
