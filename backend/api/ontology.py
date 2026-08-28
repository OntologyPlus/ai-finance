import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.ontology import OntologyObject, OntologyRelation, OntologyBehavior, OntologyRule, OntologyScene, ReasoningTrace
from ontology.objects import get_all_objects, get_object
from ontology.relations import get_all_relations, get_relations_for_scene
from ontology.behaviors import get_all_behaviors, get_behaviors_for_scene
from ontology.scenes import get_all_scenes, get_scene, get_synonym_map, invalidate_synonym_cache


router = APIRouter()


@router.get("/ontology/objects", response_model=APIResponse)
async def list_ontology_objects(
    category: Optional[str] = Query(None, description="对象类别"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if category:
            from ontology.objects import get_objects_by_category
            objects = get_objects_by_category(category)
            data = [obj.model_dump() for obj in objects]
        else:
            stmt = select(OntologyObject).where(OntologyObject.is_active.is_(True))
            result = await db.execute(stmt)
            db_objects = result.scalars().all()
            data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in db_objects]

        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/relations", response_model=APIResponse)
async def list_ontology_relations(
    scene_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        if scene_id:
            relations = get_relations_for_scene(scene_id)
            data = [rel.model_dump() for rel in relations]
        else:
            stmt = select(OntologyRelation).where(OntologyRelation.is_active.is_(True))
            result = await db.execute(stmt)
            db_relations = result.scalars().all()
            data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in db_relations]

        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/behaviors", response_model=APIResponse)
async def list_ontology_behaviors(
    scene_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        if scene_id:
            behaviors = get_behaviors_for_scene(scene_id)
            data = [b.model_dump() for b in behaviors]
        else:
            stmt = select(OntologyBehavior).where(OntologyBehavior.is_active.is_(True))
            result = await db.execute(stmt)
            db_behaviors = result.scalars().all()
            data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in db_behaviors]

        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/rules", response_model=APIResponse)
async def list_ontology_rules(
    rule_type: Optional[str] = Query(None, description="硬规则/软规则/推理规则"),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = [OntologyRule.is_active.is_(True)]
        if rule_type:
            conditions.append(OntologyRule.rule_type == rule_type)

        stmt = select(OntologyRule).where(*conditions)
        result = await db.execute(stmt)
        rules = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in rules]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/scenes", response_model=APIResponse)
async def list_ontology_scenes(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(OntologyScene).where(OntologyScene.is_active.is_(True))
        result = await db.execute(stmt)
        scenes = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in scenes]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/scenes/{scene_id}", response_model=APIResponse)
async def get_ontology_scene(
    scene_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        scene = await db.get(OntologyScene, scene_id)
        if scene is None:
            in_memory_scene = get_scene(scene_id)
            if in_memory_scene is None:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            return APIResponse(success=True, data=in_memory_scene.model_dump())

        data = {c: getattr(scene, c) for c in scene.__table__.columns.keys()}

        activated_objects = []
        activated_rules = []
        activated_behaviors = []

        if scene.activated_objects:
            try:
                obj_ids = json.loads(scene.activated_objects) if isinstance(scene.activated_objects, str) else scene.activated_objects
                for obj_id in obj_ids:
                    obj = await db.get(OntologyObject, obj_id)
                    if obj:
                        activated_objects.append({c: getattr(obj, c) for c in obj.__table__.columns.keys()})
            except (json.JSONDecodeError, TypeError):
                pass

        if scene.activated_rules:
            try:
                rule_ids = json.loads(scene.activated_rules) if isinstance(scene.activated_rules, str) else scene.activated_rules
                for rule_id in rule_ids:
                    rule = await db.get(OntologyRule, rule_id)
                    if rule:
                        activated_rules.append({c: getattr(rule, c) for c in rule.__table__.columns.keys()})
            except (json.JSONDecodeError, TypeError):
                pass

        if scene.activated_behaviors:
            try:
                behavior_ids = json.loads(scene.activated_behaviors) if isinstance(scene.activated_behaviors, str) else scene.activated_behaviors
                for bid in behavior_ids:
                    behavior = await db.get(OntologyBehavior, bid)
                    if behavior:
                        activated_behaviors.append({c: getattr(behavior, c) for c in behavior.__table__.columns.keys()})
            except (json.JSONDecodeError, TypeError):
                pass

        data["activated_objects_detail"] = activated_objects
        data["activated_rules_detail"] = activated_rules
        data["activated_behaviors_detail"] = activated_behaviors

        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/domains", response_model=APIResponse)
async def list_domains():
    from ontology.domains import OntologyDomainManager
    dm = OntologyDomainManager()
    domains = dm.get_all_domains()
    data = [d.model_dump() for d in domains.values()]
    return APIResponse(success=True, data=data)


@router.get("/ontology/domains/{domain_id}/cohesion", response_model=APIResponse)
async def check_domain_cohesion(domain_id: str):
    from ontology.domains import OntologyDomainManager, DomainId
    dm = OntologyDomainManager()
    try:
        did = DomainId(domain_id)
        result = dm.check_cohesion(did)
        return APIResponse(success=True, data=result)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid domain_id: {domain_id}")


@router.get("/ontology/domains/cohesion-report", response_model=APIResponse)
async def get_all_cohesion_reports():
    from ontology.domains import OntologyDomainManager
    dm = OntologyDomainManager()
    reports = dm.get_all_cohesion_reports()
    return APIResponse(success=True, data=reports)


@router.get("/ontology/tech-debt", response_model=APIResponse)
async def scan_tech_debt():
    from ontology.tech_debt import OntologyTechDebtScanner
    scanner = OntologyTechDebtScanner()
    report = scanner.scan_all()
    return APIResponse(success=True, data=report.model_dump())


@router.get("/ontology/maturity", response_model=APIResponse)
async def assess_maturity():
    from ontology.maturity import OntologyMaturityAssessor
    assessor = OntologyMaturityAssessor()
    assessment = assessor.assess()
    return APIResponse(success=True, data=assessment.model_dump())


@router.get("/ontology/write-back/stats", response_model=APIResponse)
async def get_write_back_stats():
    from ontology.write_back import get_write_back_engine
    engine = get_write_back_engine()
    return APIResponse(success=True, data=engine.get_stats())


@router.get("/ontology/write-back/dead-letters", response_model=APIResponse)
async def list_dead_letters():
    from ontology.write_back import get_write_back_engine
    engine = get_write_back_engine()
    dead_letters = engine.get_dead_letters()
    data = [dl.model_dump() for dl in dead_letters.values()]
    return APIResponse(success=True, data=data)


@router.post("/ontology/write-back/dead-letters/{dead_letter_id}/retry", response_model=APIResponse)
async def retry_dead_letter(dead_letter_id: str):
    from ontology.write_back import get_write_back_engine
    engine = get_write_back_engine()
    result = engine.retry_dead_letter(dead_letter_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Dead letter {dead_letter_id} not found")
    return APIResponse(success=True, data=result.model_dump())


@router.get("/ontology/cache/consistency", response_model=APIResponse)
async def check_cache_consistency(db: AsyncSession = Depends(get_db)):
    from ontology.cache_manager import get_cache_manager
    manager = get_cache_manager()
    report = await manager.run_consistency_check(db)
    return APIResponse(success=True, data=report.model_dump())


@router.get("/ontology/health-score", response_model=APIResponse)
async def get_health_score(
    db: AsyncSession = Depends(get_db),
):
    from ontology.health_score import OntologyHealthScorer
    scorer = OntologyHealthScorer()

    alert_closure_rate = 0.0
    alert_response_timeliness = 0.0
    budget_binding_rate = 0.0
    ab_classification_rate = 0.0
    report_on_time_rate = 0.0
    avg_approval_days = 14.0
    ai_adoption_rate = 0.0

    try:
        from models.alert import AlertRecord, AlertClosure
        from models.expense import ExpenseReport

        stmt_alerts = select(AlertRecord)
        result = await db.execute(stmt_alerts)
        all_alerts = result.scalars().all()
        if all_alerts:
            closed = sum(1 for a in all_alerts if a.alert_status == "已闭环")
            alert_closure_rate = closed / len(all_alerts) * 100

        stmt_expenses = select(ExpenseReport)
        result = await db.execute(stmt_expenses)
        all_expenses = result.scalars().all()
        if all_expenses:
            bound = sum(1 for e in all_expenses if e.budget_id)
            budget_binding_rate = bound / len(all_expenses) * 100
    except Exception:
        pass

    card = scorer.calculate(
        alert_closure_rate=alert_closure_rate,
        alert_response_timeliness=alert_response_timeliness,
        budget_binding_rate=budget_binding_rate,
        ab_classification_rate=ab_classification_rate,
        report_on_time_rate=report_on_time_rate,
        avg_approval_days=avg_approval_days,
        ai_adoption_rate=ai_adoption_rate,
    )

    return APIResponse(success=True, data=card.model_dump())


@router.post("/ontology/changes", response_model=APIResponse)
async def submit_ontology_change(body: dict):
    from ontology.change_management import OntologyChangeManager, ChangeRequest, ChangePriority
    cm = OntologyChangeManager()

    priority = ChangePriority(body.get("priority", "P2-中"))
    change = ChangeRequest(
        change_id=body.get("change_id", f"CHG-{id(body):08x}"),
        title=body.get("title", ""),
        description=body.get("description", ""),
        priority=priority,
        change_type=body.get("change_type", "object_add"),
        target_id=body.get("target_id", ""),
        proposed_change=body.get("proposed_change", {}),
        submitter=body.get("submitter", "system"),
    )

    try:
        cm.submit_change(change)
        return APIResponse(success=True, message="Change submitted", data=change.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/changes/{change_id}/impact", response_model=APIResponse)
async def get_change_impact(change_id: str):
    from ontology.change_management import OntologyChangeManager
    cm = OntologyChangeManager()
    change = cm.get_change(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    return APIResponse(success=True, data=change.impact_analysis)


@router.post("/ontology/changes/{change_id}/approve", response_model=APIResponse)
async def approve_ontology_change(change_id: str, body: dict):
    from ontology.change_management import OntologyChangeManager
    cm = OntologyChangeManager()
    try:
        change = cm.approve_change(change_id, body.get("approver", "admin"))
        return APIResponse(success=True, message="Change approved", data=change.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ontology/versions/{version_id}/rollback", response_model=APIResponse)
async def rollback_ontology_version(version_id: str):
    from ontology.change_management import OntologyChangeManager
    cm = OntologyChangeManager()
    try:
        version = cm.rollback_version(version_id)
        return APIResponse(success=True, message="Version rolled back", data=version.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ontology/rules/soft/{rule_id}/params", response_model=APIResponse)
async def update_soft_rule_params(
    rule_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        rule = await db.get(OntologyRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

        if rule.rule_type != "软规则":
            raise HTTPException(status_code=400, detail=f"Rule {rule_id} is not a soft rule (type: {rule.rule_type})")

        params = body.get("params")
        if params is None:
            raise HTTPException(status_code=400, detail="params is required")

        try:
            condition = json.loads(rule.condition) if isinstance(rule.condition, str) else rule.condition
        except (json.JSONDecodeError, TypeError):
            condition = {}

        condition.update(params)
        rule.condition = json.dumps(condition, ensure_ascii=False)
        await db.flush()

        data = {c: getattr(rule, c) for c in rule.__table__.columns.keys()}
        return APIResponse(success=True, message="Soft rule parameters updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/traces", response_model=APIResponse)
async def list_reasoning_traces(
    scene_name: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if scene_name:
            conditions.append(ReasoningTrace.scene_name == scene_name)

        stmt = select(ReasoningTrace).where(*conditions).order_by(ReasoningTrace.created_at.desc()).limit(limit) if conditions else select(ReasoningTrace).order_by(ReasoningTrace.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        traces = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in traces]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/traces/{trace_id}", response_model=APIResponse)
async def get_reasoning_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        trace = await db.get(ReasoningTrace, trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

        data = {c: getattr(trace, c) for c in trace.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# v12.0: 推理审计员 — 评测驱动进化
@router.get("/ontology/traces-with-feedback", response_model=APIResponse)
async def list_traces_with_feedback_summary(
    scene_name: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """v12.0: 列出推理轨迹并附带反馈汇总（评测驱动进化）

    返回每条 trace 的：
    - 基础信息（场景/输入/步骤/结论/置信度）
    - 反馈统计：反馈数/平均分/有帮助率
    - 校准差：实际置信度 vs 期望置信度
    """
    try:
        from models.trace_feedback import TraceFeedback
        from sqlalchemy import func as sql_func

        # 1) 拉取 traces
        conditions = []
        if scene_name:
            conditions.append(ReasoningTrace.scene_name == scene_name)
        if min_confidence is not None:
            conditions.append(ReasoningTrace.confidence >= min_confidence)

        stmt = select(ReasoningTrace)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(ReasoningTrace.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        traces = result.scalars().all()

        if not traces:
            return APIResponse(success=True, data={"traces": [], "feedback_map": {}, "scene_stats": {}})

        trace_ids = [t.trace_id for t in traces]

        # 2) 拉取反馈（按 trace_id 聚合）
        fb_stmt = select(
            TraceFeedback.trace_id,
            sql_func.count(TraceFeedback.feedback_id).label("count"),
            sql_func.avg(TraceFeedback.accuracy_score).label("avg_score"),
            sql_func.sum(TraceFeedback.helpful).label("helpful_count"),
            sql_func.avg(TraceFeedback.confidence_calibration).label("avg_calibration"),
        ).where(TraceFeedback.trace_id.in_(trace_ids)).group_by(TraceFeedback.trace_id)
        fb_result = await db.execute(fb_stmt)
        feedback_map = {
            row.trace_id: {
                "feedback_count": int(row.count or 0),
                "avg_accuracy": float(row.avg_score or 0),
                "helpful_count": int(row.helpful_count or 0),
                "avg_calibration": float(row.avg_calibration or 0) if row.avg_calibration is not None else None,
            }
            for row in fb_result
        }

        # 3) 场景级统计
        scene_stats = {}
        for t in traces:
            sn = t.scene_name or "未分类"
            if sn not in scene_stats:
                scene_stats[sn] = {"count": 0, "avg_confidence": 0.0, "total_confidence": 0.0}
            scene_stats[sn]["count"] += 1
            scene_stats[sn]["total_confidence"] += float(t.confidence or 0)
        for sn, s in scene_stats.items():
            s["avg_confidence"] = round(s["total_confidence"] / s["count"], 2) if s["count"] > 0 else 0
            del s["total_confidence"]

        # 4) 拼装
        trace_list = []
        for t in traces:
            fb = feedback_map.get(t.trace_id, {})
            confidence = float(t.confidence or 0)
            calibration = fb.get("avg_calibration")
            data = {c: getattr(t, c) for c in t.__table__.columns.keys()}
            data["feedback_summary"] = fb
            data["calibration_gap"] = (
                round(confidence - calibration, 2)
                if calibration is not None else None
            )
            trace_list.append(data)

        return APIResponse(
            success=True,
            data={
                "traces": trace_list,
                "feedback_map": feedback_map,
                "scene_stats": scene_stats,
                "total": len(trace_list),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ontology/traces/{trace_id}/feedback", response_model=APIResponse)
async def submit_trace_feedback(
    trace_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.0: 提交推理轨迹反馈（评测驱动进化）"""
    try:
        from models.trace_feedback import TraceFeedback
        import uuid

        trace = await db.get(ReasoningTrace, trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

        feedback = TraceFeedback(
            feedback_id=f"FB-{uuid.uuid4().hex[:10].upper()}",
            trace_id=trace_id,
            scene_name=trace.scene_name,
            accuracy_score=int(body.get("accuracy_score", 3)),
            helpful=1 if body.get("helpful", True) else 0,
            comment=body.get("comment", ""),
            reviewer_id=body.get("reviewer_id", "anonymous"),
            reviewer_role=body.get("reviewer_role", "财经BP"),
            rule_adjust_suggestion=body.get("rule_adjust_suggestion"),
            confidence_calibration=body.get("confidence_calibration"),
        )
        db.add(feedback)
        await db.flush()

        return APIResponse(
            success=True,
            message="反馈已提交，将用于规则库迭代与置信度校准",
            data={
                "feedback_id": feedback.feedback_id,
                "trace_id": trace_id,
                "scene_name": trace.scene_name,
                "accuracy_score": feedback.accuracy_score,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ontology/eval-summary", response_model=APIResponse)
async def get_eval_summary(
    db: AsyncSession = Depends(get_db),
):
    """v12.0: 评测汇总 — 整体 AI 推理质量监控

    返回：
    - 反馈总数 / 平均准确性 / 整体校准差
    - 按场景的评测分布
    - 规则命中率 / 低置信度trace数
    """
    try:
        from models.trace_feedback import TraceFeedback
        from sqlalchemy import func as sql_func

        # 反馈汇总
        fb_stmt = select(
            sql_func.count(TraceFeedback.feedback_id).label("total"),
            sql_func.avg(TraceFeedback.accuracy_score).label("avg_accuracy"),
            sql_func.avg(TraceFeedback.confidence_calibration).label("avg_calibration"),
            sql_func.sum(TraceFeedback.helpful).label("helpful_total"),
        )
        fb_result = await db.execute(fb_stmt)
        fb_row = fb_result.first()
        feedback_total = int(fb_row.total or 0)
        avg_accuracy = float(fb_row.avg_accuracy or 0)
        avg_calibration = float(fb_row.avg_calibration or 0) if fb_row.avg_calibration is not None else None
        helpful_total = int(fb_row.helpful_total or 0)

        # Trace 数量
        trace_total_stmt = select(sql_func.count(ReasoningTrace.trace_id))
        trace_total = (await db.execute(trace_total_stmt)).scalar() or 0

        # 低置信度 trace
        low_conf_stmt = select(sql_func.count(ReasoningTrace.trace_id)).where(ReasoningTrace.confidence < 60)
        low_conf_count = (await db.execute(low_conf_stmt)).scalar() or 0

        # 按场景统计
        scene_stmt = select(
            ReasoningTrace.scene_name,
            sql_func.count(ReasoningTrace.trace_id).label("count"),
            sql_func.avg(ReasoningTrace.confidence).label("avg_conf"),
        ).group_by(ReasoningTrace.scene_name)
        scene_rows = (await db.execute(scene_stmt)).all()
        scene_breakdown = [
            {
                "scene_name": r.scene_name or "未分类",
                "trace_count": int(r.count or 0),
                "avg_confidence": round(float(r.avg_conf or 0), 2),
            }
            for r in scene_rows
        ]

        # 校准差（AI 自信度 vs 审计员期望）
        calibration_gap = None
        if avg_calibration is not None:
            avg_trace_conf_stmt = select(sql_func.avg(ReasoningTrace.confidence))
            avg_trace_conf = (await db.execute(avg_trace_conf_stmt)).scalar() or 0
            calibration_gap = round(float(avg_trace_conf) - avg_calibration, 2)

        return APIResponse(
            success=True,
            data={
                "trace_total": int(trace_total),
                "feedback_total": feedback_total,
                "feedback_coverage": round(feedback_total / trace_total * 100, 1) if trace_total > 0 else 0,
                "avg_accuracy": round(avg_accuracy, 2),
                "helpful_rate": round(helpful_total / feedback_total * 100, 1) if feedback_total > 0 else 0,
                "low_confidence_count": int(low_conf_count),
                "calibration_gap": calibration_gap,
                "scene_breakdown": scene_breakdown,
                "evaluation_health": (
                    "良好" if (avg_accuracy >= 4.0 and feedback_total >= 5)
                    else "样本不足" if feedback_total < 5
                    else "需改进"
                ),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────── Instance APIs ────────────────

@router.post("/ontology/instances", response_model=APIResponse)
async def create_object_instance(body: dict, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    try:
        inst = await mgr.create_object_instance(
            type_id=body.get("type_id", ""),
            instance_id=body.get("instance_id"),
            attributes=body.get("attributes", {}),
            status=body.get("status", "active"),
            tenant_id=body.get("tenant_id"),
        )
        await db.commit()
        return APIResponse(success=True, data=inst.model_dump())
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ontology/instances/{instance_id}", response_model=APIResponse)
async def get_object_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    inst = await mgr.get_object_instance(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    return APIResponse(success=True, data=inst.model_dump())


@router.put("/ontology/instances/{instance_id}", response_model=APIResponse)
async def update_object_instance(instance_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    inst = await mgr.update_object_instance(
        instance_id, attributes=body.get("attributes"), status=body.get("status")
    )
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    await db.commit()
    return APIResponse(success=True, data=inst.model_dump())


@router.delete("/ontology/instances/{instance_id}", response_model=APIResponse)
async def delete_object_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    try:
        inst = await mgr.delete_object_instance(instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Instance {instance_id} not found")
    await db.commit()
    return APIResponse(success=True, data=inst.model_dump(), message=f"Instance {instance_id} deleted")


@router.post("/ontology/instances/query", response_model=APIResponse)
async def query_object_instances(body: dict, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    results = await mgr.query_objects(
        type_id=body.get("type_id") or None,
        filters=body.get("filters"),
    )
    return APIResponse(success=True, data=[r.model_dump() for r in results])


@router.post("/ontology/relations", response_model=APIResponse)
async def create_relation_instance(body: dict, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    try:
        inst = await mgr.create_relation_instance(
            type_id=body.get("type_id", ""),
            source_id=body.get("source_instance_id", ""),
            target_id=body.get("target_instance_id", ""),
            attributes=body.get("attributes", {}),
        )
        await db.commit()
        return APIResponse(success=True, data=inst.model_dump())
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ontology/relations/{instance_id}", response_model=APIResponse)
async def get_relation_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    inst = await mgr.get_relation_instance(instance_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Relation instance {instance_id} not found")
    return APIResponse(success=True, data=inst.model_dump())


@router.delete("/ontology/relations/{instance_id}", response_model=APIResponse)
async def delete_relation_instance(instance_id: str, db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    try:
        inst = await mgr.delete_relation_instance(instance_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Relation instance {instance_id} not found")
    await db.commit()
    return APIResponse(success=True, data=inst.model_dump(), message=f"Relation instance {instance_id} deleted")


@router.get("/ontology/instances/{instance_id}/relations", response_model=APIResponse)
async def get_instance_relations(instance_id: str, direction: str = Query("both"), db: AsyncSession = Depends(get_db)):
    from ontology.instances import get_instance_manager
    mgr = get_instance_manager()
    mgr.set_db(db)
    relations = await mgr.get_relations_for_object(instance_id, direction=direction)
    return APIResponse(success=True, data=[r.model_dump() for r in relations])


# ──────────────── Search APIs ────────────────

@router.post("/ontology/instances/search", response_model=APIResponse)
async def search_instances(body: dict):
    from ontology.search import get_search_engine
    engine = get_search_engine()
    result = await engine.search(
        query=body.get("query", ""),
        type_id=body.get("type_id"),
        filters=body.get("filters"),
        from_=body.get("from", 0),
        size=body.get("size", 20),
    )
    return APIResponse(success=True, data=result)


# ──────────────── Graph APIs ────────────────

@router.post("/ontology/graph/path", response_model=APIResponse)
async def find_graph_path(body: dict):
    from ontology.graph_query import get_graph_query
    gq = get_graph_query()
    paths = await gq.find_path(
        source_id=body.get("source_id", ""),
        target_id=body.get("target_id", ""),
        max_depth=body.get("max_depth", 5),
    )
    return APIResponse(success=True, data={"paths": paths})


@router.post("/ontology/graph/related", response_model=APIResponse)
async def find_related_instances(body: dict):
    from ontology.graph_query import get_graph_query
    gq = get_graph_query()
    result = await gq.find_related(
        instance_id=body.get("instance_id", ""),
        relation_type_id=body.get("relation_type_id"),
        direction=body.get("direction", "both"),
        max_depth=body.get("max_depth", 1),
    )
    return APIResponse(success=True, data=result.model_dump())


# ──────────────── Event APIs ────────────────

@router.get("/ontology/events", response_model=APIResponse)
async def list_ontology_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    from ontology.events import get_event_bus, OntologyEventType
    bus = get_event_bus()
    et = OntologyEventType(event_type) if event_type else None
    events = await bus.get_event_history(event_type=et, limit=limit)
    return APIResponse(success=True, data=[e.model_dump() for e in events])


# ──────────────── Consistency APIs ────────────────

@router.get("/ontology/consistency", response_model=APIResponse)
async def check_ontology_consistency(db: AsyncSession = Depends(get_db)):
    from ontology.consistency_check import OntologyConsistencyChecker
    from models.ontology import OntologyConsistencyIssue as DBIssue
    checker = OntologyConsistencyChecker()
    issues = checker.check_all()
    # Persist issues
    for issue in issues:
        db.add(DBIssue(
            severity=issue.severity,
            category=issue.category,
            message=issue.message,
            target_id=issue.target_id,
            suggestion=issue.suggestion,
        ))
    await db.commit()
    return APIResponse(success=True, data=[i.model_dump() for i in issues])


# ──────────────── Sync APIs ────────────────

@router.post("/ontology/sync/neo4j", response_model=APIResponse)
async def sync_to_neo4j():
    from ontology.graph_query import get_graph_query
    gq = get_graph_query()
    count = await gq.sync_to_neo4j()
    return APIResponse(
        success=True,
        message=f"Incrementally upserted {count} records to graph store (no full wipe)",
        data={"upserted": count},
    )


@router.post("/ontology/sync/es", response_model=APIResponse)
async def sync_to_elasticsearch(db: AsyncSession = Depends(get_db)):
    from ontology.search import get_search_engine
    from sqlalchemy import select
    from models.ontology import OntologyObjectInstance
    stmt = select(OntologyObjectInstance)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    instances = [
        {
            "instance_id": r.instance_id,
            "type_id": r.type_id,
            "attributes": r.attributes or {},
            "status": r.status,
            "tenant_id": r.tenant_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    engine = get_search_engine()
    count = await engine.bulk_sync(instances)
    return APIResponse(success=True, message=f"Synced {count} records to Elasticsearch")


# ──────────────── Synonym APIs ────────────────

@router.get("/ontology/synonyms", response_model=APIResponse)
async def get_synonyms():
    """获取当前同义词配置"""
    synonym_map = await get_synonym_map()
    return APIResponse(success=True, data=synonym_map)


@router.put("/ontology/synonyms", response_model=APIResponse)
async def update_synonyms(body: dict, db: AsyncSession = Depends(get_db)):
    """更新同义词配置（写入OntologyRule表）"""
    synonym_data = body.get("synonyms")
    if synonym_data is None or not isinstance(synonym_data, dict):
        raise HTTPException(status_code=400, detail="synonyms field is required and must be a dict")

    # Validate structure: key -> list of strings
    validated = {}
    for k, v in synonym_data.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, list):
            validated[k] = [str(item) for item in v]
        elif isinstance(v, str):
            validated[k] = [v]

    if not validated:
        raise HTTPException(status_code=400, detail="synonyms must contain at least one valid mapping")

    try:
        # Upsert: find existing synonym_mapping rule or create one
        stmt = select(OntologyRule).where(
            OntologyRule.rule_type == "synonym_mapping",
            OntologyRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        rule = result.scalars().first()

        config_json = json.dumps(validated, ensure_ascii=False)

        if rule is None:
            rule = OntologyRule(
                rule_id="SYNONYM-001",
                rule_name="同义词映射配置",
                rule_type="synonym_mapping",
                condition=config_json,
                result="同义词扩展查询",
                is_active=True,
            )
            db.add(rule)
        else:
            rule.condition = config_json

        await db.flush()

        # Invalidate cache so next call picks up new data
        invalidate_synonym_cache()

        return APIResponse(success=True, message="Synonym mapping updated", data=validated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
