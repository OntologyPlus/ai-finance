from typing import Dict, List, Optional
import time

from loguru import logger
from pydantic import BaseModel, Field


class SceneDefinition(BaseModel):
    scene_id: str
    name: str
    description: str
    activation_condition: str
    stage: str
    activated_objects: List[str] = Field(default_factory=list)
    activated_relations: List[str] = Field(default_factory=list)
    activated_rules: List[str] = Field(default_factory=list)
    activated_behaviors: List[str] = Field(default_factory=list)


class SceneEmbedding(BaseModel):
    scene_id: str
    keywords: List[str]
    description: str = ""
    stage: str = ""
    embedding: Optional[List[float]] = None  # reserved for vector embedding


_SCENES: dict[str, SceneDefinition] = {}

_SCENE_KEYWORDS: dict[str, list[str]] = {
    "fin.budget_planning": ["预算编制", "预算规划", "年度预算", "预算申报", "战略对齐", "SP", "BP", "预算科目"],
    "fin.budget_grant": ["预算授予", "预算下达", "A类冻结", "B类授予", "额度分配", "预算启用"],
    "fin.expense_reimbursement": ["报销", "费用报销", "报销单", "审批", "核销", "费用申请", "支出"],
    "fin.business_analysis": ["经营分析", "3GAP", "3List", "差距分析", "行动清单", "必赢清单"],
    "fin.alert_monitoring": ["预警监控", "预警触发", "执行率", "偏差预警", "里程碑预警", "滚动预测"],
    "fin.alert_response": ["预警响应", "预警处理", "预警闭环", "预警升级", "双签"],
    "fin.b_class_management": ["B类管理", "B类预算", "B转A", "B→A", "弹性预算", "里程碑达标"],
    "fin.pdca_review": ["PDCA", "复盘", "月度复盘", "季度复盘", "年度复盘", "闭环检查"],
    "fin.report_issuance": ["报表", "月报", "季报", "快报", "汇报PPT", "出具报告"],
    "fin.next_cycle": ["下年度", "新周期", "年度规划", "改进计划", "下一年"],
    "fin.budget_adjustment": ["预算调整", "预算调拨", "跨象限", "预算转移", "追加预算"],
}

_SCENE_EMBEDDINGS: Dict[str, SceneEmbedding] = {
    "fin.budget_planning": SceneEmbedding(
        scene_id="fin.budget_planning",
        keywords=["预算", "编制", "规划", "年度预算", "预算申报", "科目", "战略意图", "SP", "BP", "预算项目", "预算科目"],
        description="预算编制与规划场景，包括年度预算申报、科目设置、战略意图关联",
        stage="一",
    ),
    "fin.budget_grant": SceneEmbedding(
        scene_id="fin.budget_grant",
        keywords=["授予", "冻结", "A类", "B类", "额度", "释放", "B转A", "里程碑", "转换"],
        description="预算授予与管控场景，包括A类冻结、B类授予、B→A转换",
        stage="二",
    ),
    "fin.expense_reimbursement": SceneEmbedding(
        scene_id="fin.expense_reimbursement",
        keywords=["报销", "费用", "发票", "审批", "核销", "提交", "差旅", "招待", "采购"],
        description="费用报销场景，包括报销提交、审批、核销全流程",
        stage="三",
    ),
    "fin.business_analysis": SceneEmbedding(
        scene_id="fin.business_analysis",
        keywords=["分析", "3GAP", "3List", "经营", "执行率", "偏差", "差距", "清单", "必赢"],
        description="经营分析场景，包括3GAP差距分析和3List行动清单",
        stage="四",
    ),
    "fin.alert_monitoring": SceneEmbedding(
        scene_id="fin.alert_monitoring",
        keywords=["预警", "监控", "超支", "偏差", "阈值", "蓝色", "黄色", "橙色", "红色", "月度", "季度"],
        description="预警监控场景，包括月度/季度/里程碑预警触发与监控",
        stage="五",
    ),
    "fin.alert_response": SceneEmbedding(
        scene_id="fin.alert_response",
        keywords=["响应", "闭环", "升级", "双签", "处理", "解决预警", "预警处理"],
        description="预警响应场景，包括预警响应、双签闭环、升级处理",
        stage="五",
    ),
    "fin.b_class_management": SceneEmbedding(
        scene_id="fin.b_class_management",
        keywords=["B类", "授予", "释放", "转换", "里程碑", "B类管理", "待定型"],
        description="B类预算管理场景，包括B类授予、释放、B→A转换",
        stage="二/五",
    ),
    "fin.pdca_review": SceneEmbedding(
        scene_id="fin.pdca_review",
        keywords=["PDCA", "复盘", "月度", "季度", "年度", "改进", "行动", "追踪"],
        description="PDCA复盘场景，包括月度/季度/年度复盘与行动追踪",
        stage="六",
    ),
    "fin.report_issuance": SceneEmbedding(
        scene_id="fin.report_issuance",
        keywords=["报表", "月报", "季报", "年报", "快报", "汇报", "PPT", "经营分析会"],
        description="报表出具场景，包括月度快报和季度汇报PPT出具",
        stage="七",
    ),
    "fin.next_cycle": SceneEmbedding(
        scene_id="fin.next_cycle",
        keywords=["下年度", "新循环", "启动", "跨年度", "待解决", "次年"],
        description="下年度启动场景，包括跨年度事项处理和新循环启动",
        stage="八",
    ),
    "fin.budget_adjustment": SceneEmbedding(
        scene_id="fin.budget_adjustment",
        keywords=["调整", "调拨", "追加", "削减", "跨象限", "预算变更"],
        description="预算调整场景，包括预算调拨、追加、削减",
        stage="六",
    ),
}

# ── 同义词映射：默认值 + 动态缓存 ──
_DEFAULT_SYNONYM_MAP: Dict[str, List[str]] = {
    "花钱": ["费用报销", "报销"],
    "超了": ["预算预警", "超预算"],
    "不够": ["预算不足", "额度"],
    "调预算": ["预算调整", "预算调拨"],
    "审批": ["审批路由", "审批链"],
    "复盘": ["PDCA复盘", "经营复盘"],
    "报表": ["报表出具", "月度快报"],
    "战略": ["战略意图", "战略对齐"],
    "预警": ["预警监控", "预警响应"],
}

_SYNONYM_CACHE: Optional[Dict[str, List[str]]] = None
_SYNONYM_CACHE_TIME: float = 0.0
_SYNONYM_CACHE_TTL: float = 300.0  # 5分钟过期


async def get_synonym_map() -> Dict[str, List[str]]:
    """获取同义词映射，优先从DB加载，5分钟缓存，回退到默认值"""
    global _SYNONYM_CACHE, _SYNONYM_CACHE_TIME

    now = time.time()
    if _SYNONYM_CACHE is not None and (now - _SYNONYM_CACHE_TIME) < _SYNONYM_CACHE_TTL:
        return _SYNONYM_CACHE

    try:
        from sqlalchemy import select
        from models.ontology import OntologyRule
        from models.database import db_manager

        async with db_manager.async_session_factory() as db:
            stmt = select(OntologyRule).where(
                OntologyRule.rule_type == "synonym_mapping",
                OntologyRule.is_active.is_(True),
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()

            if rule is not None:
                import json
                config = json.loads(rule.condition) if isinstance(rule.condition, str) else rule.condition
                if isinstance(config, dict):
                    validated = {}
                    for k, v in config.items():
                        if isinstance(v, list):
                            validated[k] = v
                        elif isinstance(v, str):
                            validated[k] = [v]
                    if validated:
                        _SYNONYM_CACHE = validated
                        _SYNONYM_CACHE_TIME = now
                        return _SYNONYM_CACHE
    except Exception as e:
        logger.debug(f"Failed to load synonym map from DB, using default: {e}")

    _SYNONYM_CACHE = _DEFAULT_SYNONYM_MAP.copy()
    _SYNONYM_CACHE_TIME = now
    return _SYNONYM_CACHE


def invalidate_synonym_cache() -> None:
    """手动失效同义词缓存"""
    global _SYNONYM_CACHE, _SYNONYM_CACHE_TIME
    _SYNONYM_CACHE = None
    _SYNONYM_CACHE_TIME = 0.0


def _init_scenes() -> None:
    global _SCENES
    if _SCENES:
        return

    definitions = [
        SceneDefinition(
            scene_id="fin.budget_planning",
            name="预算编制",
            description="年度预算编制场景，从SP/BP战略目标出发，驱动预算项目编制，确保每个预算项目对标战略举措并归属象限",
            activation_condition="年度预算编制期启动，或战略目标调整触发预算重新编制",
            stage="阶段一",
            activated_objects=[
                "obj_strategic_sp", "obj_strategic_bp", "obj_strategic_initiative",
                "obj_budget_item", "obj_budget_quadrant",
                "obj_budget_subject_l1", "obj_budget_subject_l2", "obj_budget_subject_l3",
                "obj_role_committee", "obj_role_budget_dept",
            ],
            activated_relations=["驱动", "对标", "归属"],
            activated_rules=[
                "HR-001", "HR-007", "HR-008",
                "SR-007", "SR-011",
            ],
            activated_behaviors=[
                "fin.budget.a_class_freeze",
                "fin.budget.b_class_grant",
            ],
        ),
        SceneDefinition(
            scene_id="fin.budget_grant",
            name="预算授予",
            description="预算审批通过后的授予场景，A类预算冻结额度，B类预算按比例授予，支持B→A转换和额度释放",
            activation_condition="预算项目审批通过，进入授予执行阶段",
            stage="阶段二",
            activated_objects=[
                "obj_budget_item", "obj_budget_subject_l3",
                "obj_role_committee", "obj_role_budget_dept",
            ],
            activated_relations=["冻结", "释放", "B→A转换"],
            activated_rules=[
                "HR-004", "HR-007",
                "SR-007",
            ],
            activated_behaviors=[
                "fin.budget.a_class_freeze",
                "fin.budget.b_class_grant",
                "fin.budget.b2a_convert",
                "fin.budget.release",
            ],
        ),
        SceneDefinition(
            scene_id="fin.expense_reimbursement",
            name="费用报销",
            description="员工费用报销场景，报销单挂载预算项目，经组织线+法人线双线审批后核销，管控路由根据L3科目级别确定审批路径",
            activation_condition="员工提交报销单或预算使用申请",
            stage="阶段三",
            activated_objects=[
                "obj_expense_report", "obj_budget_usage_request",
                "obj_budget_item", "obj_budget_subject_l3",
                "obj_role_center_bp", "obj_role_budget_dept",
            ],
            activated_relations=["挂载", "审批组织线", "审批法人线"],
            activated_rules=[
                "HR-001", "HR-002", "HR-005",
                "SR-009", "SR-010",
            ],
            activated_behaviors=[
                "fin.expense.submit",
                "fin.control.route",
                "fin.approval.org_line",
                "fin.approval.legal_line",
                "fin.budget.write_off",
            ],
        ),
        SceneDefinition(
            scene_id="fin.business_analysis",
            name="经营分析",
            description="基于3GAP+3List工具的经营分析场景，定位目标差距、执行差距、能力差距，制定必赢清单、改善清单、资源清单",
            activation_condition="月度/季度经营分析会召开，或预警汇总触发深度分析",
            stage="阶段四",
            activated_objects=[
                "obj_tool_3gap_3list", "obj_budget_item",
                "obj_alert_record", "obj_role_ops_dept",
            ],
            activated_relations=["驱动", "对标"],
            activated_rules=[
                "HR-012",
                "RR-004",
            ],
            activated_behaviors=[
                "fin.analysis.3gap",
                "fin.analysis.3list",
            ],
        ),
        SceneDefinition(
            scene_id="fin.alert_monitoring",
            name="预警监控",
            description="预算执行预警监控场景，根据月度执行进度和季度滚动预测自动触发预警，包含蓝色/黄色/红色三级预警",
            activation_condition="月度/季度数据更新后自动检测阈值，或里程碑延期触发",
            stage="阶段五",
            activated_objects=[
                "obj_alert_record", "obj_budget_item",
                "obj_role_budget_dept",
            ],
            activated_relations=["触发"],
            activated_rules=[
                "HR-003", "HR-009", "HR-010", "HR-011",
                "SR-001", "SR-002", "SR-003", "SR-004", "SR-005", "SR-006", "SR-008",
            ],
            activated_behaviors=[
                "fin.alert.create_monthly",
                "fin.alert.create_quarterly",
                "fin.alert.create_milestone",
            ],
        ),
        SceneDefinition(
            scene_id="fin.alert_response",
            name="预警响应",
            description="预警响应与闭环场景，财经BP响应预警，预算管理部确认方案，超时或红色预警升级至上级，最终实现闭环",
            activation_condition="预警记录生成后触发响应流程",
            stage="阶段五",
            activated_objects=[
                "obj_alert_record",
                "obj_role_center_bp", "obj_role_budget_dept",
                "obj_role_committee",
            ],
            activated_relations=["响应", "确认", "升级"],
            activated_rules=[
                "HR-003", "HR-005", "HR-011", "HR-012",
            ],
            activated_behaviors=[
                "fin.alert.escalate",
                "fin.alert.close",
            ],
        ),
        SceneDefinition(
            scene_id="fin.b_class_management",
            name="B类预算管理",
            description="B类弹性预算的全生命周期管理，包括按比例授予、里程碑达标后B→A转换、未使用额度释放",
            activation_condition="B类预算项目需要授予、转换或释放操作",
            stage="阶段二/五",
            activated_objects=[
                "obj_budget_item",
                "obj_role_committee", "obj_role_budget_dept",
            ],
            activated_relations=["B→A转换", "冻结", "释放"],
            activated_rules=[
                "HR-004", "HR-009", "HR-010",
                "SR-007",
            ],
            activated_behaviors=[
                "fin.budget.b_class_grant",
                "fin.budget.b2a_convert",
                "fin.budget.release",
            ],
        ),
        SceneDefinition(
            scene_id="fin.pdca_review",
            name="PDCA复盘",
            description="PDCA闭环复盘场景，月度检查预警闭环率，季度评估战略执行进展，年度总结并输出改进计划",
            activation_condition="月度/季度/年度复盘周期到达",
            stage="阶段六",
            activated_objects=[
                "obj_alert_record", "obj_budget_item",
                "obj_strategic_initiative", "obj_role_ops_dept",
            ],
            activated_relations=["对标", "驱动"],
            activated_rules=[
                "HR-012",
            ],
            activated_behaviors=[
                "fin.pdca.monthly",
                "fin.pdca.quarterly",
                "fin.pdca.yearly",
            ],
        ),
        SceneDefinition(
            scene_id="fin.report_issuance",
            name="报表出具",
            description="定期报表出具场景，月度出具执行快报，季度出具汇报PPT，为管理层决策提供数据支撑",
            activation_condition="月度/季度报表出具周期到达",
            stage="阶段七",
            activated_objects=[
                "obj_report_monthly", "obj_report_quarterly",
                "obj_tool_3gap_3list", "obj_budget_item",
            ],
            activated_relations=[],
            activated_rules=[],
            activated_behaviors=[
                "fin.report.monthly",
                "fin.report.quarterly",
            ],
        ),
        SceneDefinition(
            scene_id="fin.next_cycle",
            name="下年度启动",
            description="下年度预算编制启动场景，基于年度PDCA复盘的改进计划，启动新一轮SP/BP更新和预算编制",
            activation_condition="年度复盘完成，下年度预算编制期启动",
            stage="阶段八",
            activated_objects=[
                "obj_strategic_sp", "obj_strategic_bp",
                "obj_report_yearly",
                "obj_role_committee", "obj_role_budget_dept",
            ],
            activated_relations=["驱动", "对标", "归属"],
            activated_rules=[
                "HR-007",
            ],
            activated_behaviors=[
                "fin.pdca.yearly",
            ],
        ),
        SceneDefinition(
            scene_id="fin.budget_adjustment",
            name="预算调整",
            description="预算调整与调拨场景，同象限内调拨经财经中心审批，跨象限调拨须管委会批准，支持额度释放和重新分配",
            activation_condition="预算执行过程中需要调整额度分配",
            stage="阶段六",
            activated_objects=[
                "obj_budget_item", "obj_budget_quadrant",
                "obj_role_committee", "obj_role_budget_dept",
            ],
            activated_relations=["冻结", "释放", "裁决"],
            activated_rules=[
                "HR-008",
            ],
            activated_behaviors=[
                "fin.adjustment.transfer",
                "fin.budget.release",
            ],
        ),
    ]

    _SCENES = {s.scene_id: s for s in definitions}


def get_all_scenes() -> dict[str, SceneDefinition]:
    _init_scenes()
    return _SCENES.copy()


def get_scene(scene_id: str) -> Optional[SceneDefinition]:
    _init_scenes()
    return _SCENES.get(scene_id)


def match_scene(user_input: str, context: dict | None = None) -> Optional[SceneDefinition]:
    _init_scenes()

    input_lower = user_input.lower()
    scores: dict[str, float] = {}

    for scene_id, keywords in _SCENE_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if keyword in input_lower:
                score += 1.0
        scores[scene_id] = score

    if context:
        ctx_stage = context.get("stage", "")
        ctx_objects = context.get("activated_objects", [])
        for scene_id, scene in _SCENES.items():
            if ctx_stage and ctx_stage in scene.stage:
                scores[scene_id] = scores.get(scene_id, 0) + 0.5
            for obj_id in ctx_objects:
                if obj_id in scene.activated_objects:
                    scores[scene_id] = scores.get(scene_id, 0) + 0.2

    best_scene_id = max(scores, key=scores.get) if scores else None
    if best_scene_id and scores[best_scene_id] > 0:
        return _SCENES.get(best_scene_id)

    return None


async def match_scene_semantic(query: str, top_k: int = 3, min_score: float = 0.3) -> List[tuple]:
    """语义场景匹配：基于TF-IDF关键词权重+阶段加权+动态阈值，支持同义词扩展和LLM回退"""

    # Load synonym map dynamically from DB (with cache)
    SYNONYM_MAP = await get_synonym_map()

    # Expand query with synonyms
    expanded_terms = set()
    for term, synonyms in SYNONYM_MAP.items():
        if term in query:
            expanded_terms.update(synonyms)
    expanded_query = query + "".join(expanded_terms)

    query_chars = set(expanded_query)

    # ── P5-4.1: TF-IDF 权重计算 ──
    import math

    total_scenes = len(_SCENE_EMBEDDINGS)
    # 统计每个关键词在多少个场景中出现
    kw_scene_count: Dict[str, int] = {}
    for embedding in _SCENE_EMBEDDINGS.values():
        for kw in embedding.keywords:
            kw_scene_count[kw] = kw_scene_count.get(kw, 0) + 1

    # 计算 IDF
    idf_map: Dict[str, float] = {}
    for kw, cnt in kw_scene_count.items():
        idf_map[kw] = math.log(total_scenes / cnt) if cnt > 0 else 0.0

    # ── P5-4.2: 阶段加权（中文+英文+业务关键词映射） ──
    stage_map_cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
    stage_map_en = {"Q1": "一", "Q2": "二", "Q3": "三", "Q4": "四"}
    stage_map_biz = {"编制": "一", "审批": "二", "执行": "三", "分析": "四", "预警": "五", "复盘": "六", "报表": "七", "规划": "八"}

    # 将query映射到中文阶段字符
    query_stages = set()
    for char, stage in stage_map_cn.items():
        if char in query:
            query_stages.add(stage)
    for en, cn_stage in stage_map_en.items():
        if en.lower() in query.lower():
            query_stages.add(stage_map_cn[cn_stage])
    for biz_kw, cn_stage_char in stage_map_biz.items():
        if biz_kw in query:
            query_stages.add(stage_map_cn[cn_stage_char])

    results = []

    for scene_id, embedding in _SCENE_EMBEDDINGS.items():
        # ── TF-IDF 关键词匹配分数 ──
        matched_idf_sum = 0.0
        total_idf_sum = 0.0
        for kw in embedding.keywords:
            kw_idf = idf_map.get(kw, 0.0)
            total_idf_sum += kw_idf
            if any(c in expanded_query for c in kw):
                matched_idf_sum += kw_idf

        keyword_score = matched_idf_sum / max(total_idf_sum, 1e-9)

        # ── 阶段匹配 ──
        stage_score = 0.0
        embedding_stage_nums = set()
        for char, num in stage_map_cn.items():
            if char in embedding.stage:
                embedding_stage_nums.add(num)
        if query_stages & embedding_stage_nums:
            stage_score = 0.2

        # Description overlap
        desc_chars = set(embedding.description)
        desc_overlap = len(query_chars & desc_chars) / max(len(desc_chars), 1)

        total_score = keyword_score * 0.6 + stage_score * 0.2 + desc_overlap * 0.2

        if total_score >= min_score:
            results.append((scene_id, total_score, embedding.description))

    results.sort(key=lambda x: x[1], reverse=True)

    # ── P5-4.3: 动态阈值 ──
    # 如果最佳分数与次佳分数差距>0.2，降低阈值到0.2以捕获明显的最佳匹配
    if not results and min_score > 0.2:
        # 重新用低阈值扫描
        for scene_id, embedding in _SCENE_EMBEDDINGS.items():
            matched_idf_sum = 0.0
            total_idf_sum = 0.0
            for kw in embedding.keywords:
                kw_idf = idf_map.get(kw, 0.0)
                total_idf_sum += kw_idf
                if any(c in expanded_query for c in kw):
                    matched_idf_sum += kw_idf
            keyword_score = matched_idf_sum / max(total_idf_sum, 1e-9)

            embedding_stage_nums = set()
            for char, num in stage_map_cn.items():
                if char in embedding.stage:
                    embedding_stage_nums.add(num)
            stage_score_val = 0.2 if (query_stages & embedding_stage_nums) else 0.0

            desc_chars = set(embedding.description)
            desc_overlap = len(query_chars & desc_chars) / max(len(desc_chars), 1)

            total_score = keyword_score * 0.6 + stage_score_val * 0.2 + desc_overlap * 0.2

            if total_score >= 0.2:
                results.append((scene_id, total_score, embedding.description))

        results.sort(key=lambda x: x[1], reverse=True)
    elif len(results) >= 2 and (results[0][1] - results[1][1]) > 0.2:
        # 差距大，说明最佳匹配明显，可以接受更低阈值的结果
        pass  # 已有结果，保持

    # If keyword match score is too low, try LLM-based semantic matching
    if not results or results[0][1] < 0.3:
        try:
            llm_result = await _llm_semantic_match(query, list(_SCENE_EMBEDDINGS.keys()))
            if llm_result:
                # Merge LLM results with existing results
                existing_ids = {r[0] for r in results}
                for scene_id, score in llm_result:
                    if scene_id not in existing_ids and scene_id in _SCENE_EMBEDDINGS:
                        results.append((scene_id, score, _SCENE_EMBEDDINGS[scene_id].description))
                results.sort(key=lambda x: x[1], reverse=True)
        except Exception as e:
            logger.warning(f"LLM semantic matching failed: {e}")

    return results[:top_k]


async def _llm_semantic_match(query: str, scene_ids: List[str]) -> List[tuple]:
    """Use LLM to match user query to scenes when keyword score is low.

    Now fully async-compatible: uses await instead of run_until_complete.
    """
    try:
        from utils.llm_client import get_llm_client

        scene_names = []
        for sid in scene_ids:
            emb = _SCENE_EMBEDDINGS.get(sid)
            if emb:
                scene_names.append(f"{sid}: {emb.description}")

        prompt = (
            f"用户意图'{query}'最匹配以下哪个场景？请返回最匹配的1-3个场景ID及匹配度(0-1)。\n"
            f"场景列表：\n" + "\n".join(scene_names) + "\n\n"
            f"请以JSON格式返回，例如：[{{\"scene_id\": \"fin.xxx\", \"score\": 0.8}}]"
        )

        llm = get_llm_client()
        response = await llm.ainvoke([{"role": "user", "content": prompt}], temperature=0.1)

        content = response.content if hasattr(response, 'content') else str(response)

        import json
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
            return [(item["scene_id"], float(item.get("score", 0.5))) for item in parsed if "scene_id" in item]
    except Exception as e:
        logger.debug(f"LLM semantic match failed (non-critical): {e}")

    return []
