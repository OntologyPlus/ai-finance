from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ontology.objects import get_object, get_all_objects
from ontology.relations import get_all_relations


class InjectionStrategy(str):
    OBJECT = "object"
    RELATION = "relation"
    PATH = "path"
    AGGREGATE = "aggregate"


class ContextBlock(BaseModel):
    source: str = Field(description="上下文来源(ObjectType#ID或RelationType#ID)")
    strategy: str = Field(description="注入策略")
    content: str = Field(description="注入内容")
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)


class OAGContext(BaseModel):
    query: str
    scene_id: Optional[str] = None
    blocks: List[ContextBlock] = Field(default_factory=list)
    total_tokens_estimate: int = 0
    max_tokens: int = 4000
    truncated_hard_rules: List[str] = Field(
        default_factory=list,
        description=(
            "被上下文窗口裁剪掉的硬规则(HR-*)的 rule_id 列表。"
            "硬规则按合约预留预算裁剪，剩余仍超出部分才会进入此列表。"
            "非空时由 hallucination_guard 的 context_sufficiency 策略标记为不通过，"
            "因为合规底线（HR-*）被静默漏检的风险必须显式化。"
        ),
    )


class OntologyContextInjector:
    def __init__(
        self,
        max_context_tokens: int = 4000,
        hard_rule_token_budget: int = 1500,
    ):
        self.max_tokens = max_context_tokens
        # 硬规则（strategy=="rule"）预留预算，不参与全局 score 竞争。
        # 超出本预算的硬规则才允许被裁，且必须记录到 truncated_hard_rules。
        self._hard_rule_token_budget = hard_rule_token_budget
        self._avg_token_per_char = 0.5
        self._rag_pipeline = None  # Lazy init to avoid circular import

    @property
    def rag_pipeline(self):
        if self._rag_pipeline is None:
            from services.rag import RAGPipeline
            self._rag_pipeline = RAGPipeline()
        return self._rag_pipeline

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text) * self._avg_token_per_char)

    async def inject_rag_context(self, query: str, existing_context: OAGContext, db: Any = None) -> OAGContext:
        """注入RAG检索结果作为额外上下文块，仅添加不与已有上下文重叠的结果"""
        try:
            rag_results = await self.rag_pipeline.retrieve(query, top_k=5)
        except Exception:
            return existing_context

        existing_contents = {block.content[:100] for block in existing_context.blocks}

        for result in rag_results:
            if result.content[:100] in existing_contents:
                continue
            block = ContextBlock(
                source=f"RAG#{result.source}",
                strategy="rag",
                content=f"【RAG检索】{result.content}",
                relevance_score=min(result.score / 10.0, 0.6) if result.score > 0 else 0.3,
            )
            existing_context.blocks.append(block)
            existing_context.total_tokens_estimate += self._estimate_tokens(block.content)

        return existing_context

    async def inject_object(
        self, object_id: str, context: OAGContext, db: Any = None
    ) -> OAGContext:
        obj = get_object(object_id)
        if obj is None:
            return context

        content_parts = [
            f"【对象】{obj.name} (ID: {obj.object_id})",
            f"类别: {obj.category}",
            f"定义: {obj.natural_language_definition}",
            f"关键属性: {', '.join(obj.key_attributes)}",
            f"参与关系: {', '.join(obj.participating_relations) if obj.participating_relations else '无'}",
        ]

        # Add numerical summary for budget-related objects if db session is available
        if db is not None:
            try:
                numerical_summary = await self._get_object_numerical_summary(obj.object_id, db)
                if numerical_summary:
                    content_parts.append(f"【数据摘要】{numerical_summary}")
            except Exception:
                pass

        content = "\n".join(content_parts)

        block = ContextBlock(
            source=f"Object#{obj.object_id}",
            strategy=InjectionStrategy.OBJECT,
            content=content,
            relevance_score=1.0,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def inject_relation(
        self, relation_name: str, context: OAGContext
    ) -> OAGContext:
        all_relations = get_all_relations()
        rel = None
        for r in all_relations.values():
            if r.name == relation_name or r.relation_id == relation_name:
                rel = r
                break

        if rel is None:
            return context

        content_parts = [
            f"【关系】{rel.name} (ID: {rel.relation_id})",
            f"源对象: {rel.source_object}",
            f"目标对象: {rel.target_object}",
            f"语义描述: {rel.semantic_description}",
            f"场景条件: {rel.scene_condition}",
        ]
        content = "\n".join(content_parts)

        block = ContextBlock(
            source=f"Relation#{rel.relation_id}",
            strategy=InjectionStrategy.RELATION,
            content=content,
            relevance_score=0.9,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def inject_path(
        self, from_object_id: str, to_object_id: str, context: OAGContext
    ) -> OAGContext:
        all_relations = get_all_relations()
        path = []
        visited = set()
        current = from_object_id

        while current and current not in visited and len(path) < 5:
            visited.add(current)
            found = False
            for rel in all_relations.values():
                if rel.source_object == current:
                    path.append(f"{rel.name}→{rel.target_object}")
                    if rel.target_object == to_object_id:
                        found = True
                        break
                    current = rel.target_object
                    found = True
                    break
            if not found:
                break

        if not path:
            return context

        content = f"【关系路径】{from_object_id} → {' → '.join(path)}"
        block = ContextBlock(
            source=f"Path#{from_object_id}→{to_object_id}",
            strategy=InjectionStrategy.PATH,
            content=content,
            relevance_score=0.8,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def inject_aggregate(
        self, object_id: str, context: OAGContext
    ) -> OAGContext:
        all_relations = get_all_relations()
        related_objects = []
        for rel in all_relations.values():
            if rel.source_object == object_id:
                related_objects.append(f"{rel.name}→{rel.target_object}")
            elif rel.target_object == object_id:
                related_objects.append(f"{rel.source_object}→{rel.name}")

        if not related_objects:
            return context

        content = f"【聚合关系】{object_id} 的关联对象: {', '.join(related_objects)}"
        block = ContextBlock(
            source=f"Aggregate#{object_id}",
            strategy=InjectionStrategy.AGGREGATE,
            content=content,
            relevance_score=0.7,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def optimize_window(self, context: OAGContext) -> OAGContext:
        """上下文窗口裁剪。

        关键合约：
        1. 硬规则块（strategy=="rule"）从全局 score 竞争中隔离，先按 score 排序并优先保留。
           在 self._hard_rule_token_budget 内的硬规则块**永不裁剪**——这是合规底线。
        2. 超出硬规则预算的硬规则块按 score 降序裁掉，被裁的 rule_id 记入
           context.truncated_hard_rules，由 hallucination_guard 检查到后拒答。
        3. 剩余的 object/relation/behavior/path/aggregate/methodology 块按 score 降序
           竞争剩余 token 预算（max_tokens - 已用硬规则预算）。
        """
        if context.total_tokens_estimate <= self.max_tokens:
            # 仍有必要清空 truncated_hard_rules（避免上一轮污染）
            context.truncated_hard_rules = []
            return context

        # ── 第一阶段：硬规则隔离裁剪 ──
        rule_blocks = [b for b in context.blocks if b.strategy == "rule"]
        non_rule_blocks = [b for b in context.blocks if b.strategy != "rule"]

        rule_blocks_sorted = sorted(rule_blocks, key=lambda b: b.relevance_score, reverse=True)

        kept_rules: List[ContextBlock] = []
        rule_tokens = 0
        truncated_rule_ids: List[str] = []
        for block in rule_blocks_sorted:
            block_tokens = self._estimate_tokens(block.content)
            if rule_tokens + block_tokens <= self._hard_rule_token_budget:
                kept_rules.append(block)
                rule_tokens += block_tokens
            else:
                # 从 source 形如 "Rule#HR-001" 中提取 rule_id
                rid = block.source.split("#", 1)[1] if "#" in block.source else block.source
                truncated_rule_ids.append(rid)

        # ── 第二阶段：非硬规则块按 score 排序竞争剩余 token ──
        non_rule_sorted = sorted(non_rule_blocks, key=lambda b: b.relevance_score, reverse=True)
        remaining_budget = self.max_tokens - rule_tokens

        kept_non_rules: List[ContextBlock] = []
        non_rule_tokens = 0
        for block in non_rule_sorted:
            block_tokens = self._estimate_tokens(block.content)
            if non_rule_tokens + block_tokens <= remaining_budget:
                kept_non_rules.append(block)
                non_rule_tokens += block_tokens
            # 超出预算的块直接丢弃（不写 truncated_hard_rules——那只是合规字段）

        # ── 合并：按原 block 列表顺序拼接（保持注入顺序）──
        kept_set = {(b.source, b.strategy) for b in kept_rules + kept_non_rules}
        context.blocks = [b for b in context.blocks if (b.source, b.strategy) in kept_set]
        context.total_tokens_estimate = rule_tokens + non_rule_tokens
        context.truncated_hard_rules = truncated_rule_ids

        return context

    def inject_rule(
        self, rule_id: str, context: OAGContext
    ) -> OAGContext:
        """注入规则定义到上下文"""
        from ontology.rules import get_rule
        rule = get_rule(rule_id)
        if rule is None:
            return context

        content_parts = [
            f"【规则】{rule.name} (ID: {rule.rule_id})",
            f"类型: {rule.rule_type}",
            f"定义: {rule.natural_language_definition}",
        ]
        if hasattr(rule, 'conditions') and rule.conditions:
            content_parts.append(f"条件: {', '.join(str(c) for c in rule.conditions)}")
        content = "\n".join(content_parts)

        block = ContextBlock(
            source=f"Rule#{rule.rule_id}",
            strategy="rule",
            content=content,
            relevance_score=0.95,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def inject_behavior(
        self, behavior_id: str, context: OAGContext
    ) -> OAGContext:
        """注入行为定义到上下文"""
        from ontology.behaviors import get_behavior
        behavior = get_behavior(behavior_id)
        if behavior is None:
            return context

        content_parts = [
            f"【行为】{behavior.name} (ID: {behavior.behavior_id})",
            f"定义: {behavior.natural_language_definition}",
        ]
        if hasattr(behavior, 'preconditions') and behavior.preconditions:
            content_parts.append(f"前置条件: {behavior.preconditions}")
        if hasattr(behavior, 'side_effects') and behavior.side_effects:
            content_parts.append(f"副作用: {behavior.side_effects}")
        content = "\n".join(content_parts)

        block = ContextBlock(
            source=f"Behavior#{behavior.behavior_id}",
            strategy="behavior",
            content=content,
            relevance_score=0.9,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    def inject_methodology(
        self, methodology_name: str, context: OAGContext
    ) -> OAGContext:
        """注入方法论文档到上下文"""
        import os
        methodology_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ontology", "references", "methodology")
        file_map = {
            "CFO交互标准与沟通范式": "CFO交互标准与沟通范式.md",
            "CFO分析问题定义标准": "CFO分析问题定义标准.md",
            "CFO指标定义与数据口径标准": "CFO指标定义与数据口径标准.md",
            "CFO报告撰写与呈现标准": "CFO报告撰写与呈现标准.md",
            "CFO预警响应标准": "CFO预警响应标准.md",
        }
        filename = file_map.get(methodology_name)
        if not filename:
            return context
        filepath = os.path.join(methodology_dir, filename)
        if not os.path.exists(filepath):
            return context
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content_raw = f.read()
        except Exception:
            return context
        # Truncate to max 2000 chars to fit context window
        if len(content_raw) > 2000:
            content_raw = content_raw[:2000] + "\n...(截断，完整内容请参考方法论文档)"
        content = f"【方法论】{methodology_name}\n{content_raw}"
        block = ContextBlock(
            source=f"Methodology#{methodology_name}",
            strategy="methodology",
            content=content,
            relevance_score=0.85,
        )
        context.blocks.append(block)
        context.total_tokens_estimate += self._estimate_tokens(content)
        return context

    async def _get_object_numerical_summary(
        self, object_id: str, db: Any
    ) -> str:
        """Query instance statistics for core business objects and return numerical summary."""
        oid_lower = object_id.lower()

        # ── 预算相关对象 ──
        budget_related_ids = {
            "obj_budget_item", "obj_budget_quadrant",
            "obj_budget_subject_l1", "obj_budget_subject_l2", "obj_budget_subject_l3",
        }
        if object_id in budget_related_ids:
            return await self._summary_budget(db)

        # ── 报销对象 ──
        if "expense" in oid_lower or "报销" in object_id:
            return await self._summary_expense(db)

        # ── 预警对象 ──
        if "alert" in oid_lower or "预警" in object_id:
            return await self._summary_alert(db)

        # ── 审批对象 ──
        if "approval" in oid_lower or "审批" in object_id:
            return await self._summary_approval(db)

        # ── 战略对象 ──
        if "strategic" in oid_lower or "战略" in object_id:
            return await self._summary_strategic(db)

        return ""

    async def _summary_budget(self, db: Any) -> str:
        """预算对象数值摘要"""
        try:
            from sqlalchemy import select, func
            from models.budget import BudgetItem

            stmt_count = select(func.count()).select_from(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            stmt_total = select(func.sum(BudgetItem.annual_amount)).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            stmt_used = select(func.sum(BudgetItem.used_amount)).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )

            count_result = await db.execute(stmt_count)
            total_result = await db.execute(stmt_total)
            used_result = await db.execute(stmt_used)

            count = count_result.scalar() or 0
            total = float(total_result.scalar() or 0)
            used = float(used_result.scalar() or 0)
            avg_rate = round(used / total * 100, 2) if total > 0 else 0

            return f"共{count}条实例，总金额{total:.2f}元，平均执行率{avg_rate}%"
        except Exception:
            return ""

    async def _summary_expense(self, db: Any) -> str:
        """报销对象数值摘要：总报销金额、平均报销额、合规率"""
        try:
            from sqlalchemy import select, func, case
            from models.expense import ExpenseReport

            stmt_total = select(func.sum(ExpenseReport.amount))
            stmt_count = select(func.count()).select_from(ExpenseReport)
            stmt_compliant = select(
                func.count().select_from(ExpenseReport)
            ).where(ExpenseReport.status != "已驳回")

            total_result = await db.execute(stmt_total)
            count_result = await db.execute(stmt_count)
            compliant_result = await db.execute(stmt_compliant)

            total = float(total_result.scalar() or 0)
            count = count_result.scalar() or 0
            compliant = compliant_result.scalar() or 0
            avg_amount = round(total / count, 2) if count > 0 else 0
            compliance_rate = round(compliant / count * 100, 2) if count > 0 else 0

            return f"共{count}条报销，总金额{total:.2f}元，平均报销额{avg_amount:.2f}元，合规率{compliance_rate}%"
        except Exception:
            return ""

    async def _summary_alert(self, db: Any) -> str:
        """预警对象数值摘要：预警总数、各颜色分布、闭环率"""
        try:
            from sqlalchemy import select, func
            from models.alert import AlertRecord

            stmt_total = select(func.count()).select_from(AlertRecord)
            stmt_by_level = select(AlertRecord.alert_level, func.count()).group_by(AlertRecord.alert_level)
            stmt_closed = select(func.count().select_from(AlertRecord)).where(
                AlertRecord.alert_status == "已闭环"
            )

            total_result = await db.execute(stmt_total)
            level_result = await db.execute(stmt_by_level)
            closed_result = await db.execute(stmt_closed)

            total = total_result.scalar() or 0
            closed = closed_result.scalar() or 0
            closure_rate = round(closed / total * 100, 2) if total > 0 else 0

            level_dist = ", ".join(
                f"{row[0]}{row[1]}条" for row in level_result.all()
            )

            parts = [f"共{total}条预警"]
            if level_dist:
                parts.append(f"分布: {level_dist}")
            parts.append(f"闭环率{closure_rate}%")
            return "，".join(parts)
        except Exception:
            return ""

    async def _summary_approval(self, db: Any) -> str:
        """审批对象数值摘要：审批通过率、平均审批时长"""
        try:
            from sqlalchemy import select, func
            from models.approval import ApprovalRecord
            from models.expense import ExpenseReport

            # 审批通过率
            stmt_total = select(func.count()).select_from(ApprovalRecord)
            stmt_approved = select(func.count().select_from(ApprovalRecord)).where(
                ApprovalRecord.approval_action == "通过"
            )

            total_result = await db.execute(stmt_total)
            approved_result = await db.execute(stmt_approved)

            total = total_result.scalar() or 0
            approved = approved_result.scalar() or 0
            approval_rate = round(approved / total * 100, 2) if total > 0 else 0

            # 平均审批时长：从报销单created_at到最新审批时间
            stmt_avg_days = select(
                func.avg(
                    func.extract("epoch", ApprovalRecord.approved_at) -
                    func.extract("epoch", ExpenseReport.created_at)
                ) / 86400.0
            ).join(
                ExpenseReport, ExpenseReport.expense_id == ApprovalRecord.expense_id
            ).where(
                ApprovalRecord.approved_at.isnot(None)
            )

            avg_days_result = await db.execute(stmt_avg_days)
            avg_days = avg_days_result.scalar()
            avg_days_str = f"{float(avg_days):.1f}" if avg_days is not None else "N/A"

            return f"审批通过率{approval_rate}%，平均审批时长{avg_days_str}天"
        except Exception:
            return ""

    async def _summary_strategic(self, db: Any) -> str:
        """战略对象数值摘要：各战略意图预算占比、执行率"""
        try:
            from sqlalchemy import select, func
            from models.budget import BudgetItem

            stmt = select(
                BudgetItem.strategic_intent_l1,
                func.sum(BudgetItem.annual_amount),
                func.sum(BudgetItem.used_amount),
            ).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
                BudgetItem.strategic_intent_l1.isnot(None),
            ).group_by(BudgetItem.strategic_intent_l1)

            result = await db.execute(stmt)
            rows = result.all()

            if not rows:
                return ""

            grand_total = sum(float(r[1] or 0) for r in rows)
            parts = []
            for intent, total, used in rows:
                total_f = float(total or 0)
                used_f = float(used or 0)
                pct = round(total_f / grand_total * 100, 1) if grand_total > 0 else 0
                exec_rate = round(used_f / total_f * 100, 1) if total_f > 0 else 0
                intent_name = intent or "未分类"
                parts.append(f"{intent_name}: 占比{pct}%，执行率{exec_rate}%")

            return "战略意图分布 — " + "；".join(parts)
        except Exception:
            return ""

    async def inject_instance_summary(
        self, object_id: str, context: OAGContext, db: Any, top_n: int = 5
    ) -> OAGContext:
        """Inject key instances (top N by amount) with their numerical attributes."""
        budget_related_ids = {
            "obj_budget_item", "obj_budget_quadrant",
        }
        if object_id not in budget_related_ids:
            return context

        try:
            from sqlalchemy import select
            from models.budget import BudgetItem

            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            ).order_by(BudgetItem.annual_amount.desc()).limit(top_n)
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return context

            lines = []
            for item in items:
                annual = float(item.annual_amount or 0) / 10000  # Convert to 万元
                used = float(item.used_amount or 0) / 10000
                rate = round(used / annual * 100, 2) if annual > 0 else 0
                intent_l1 = item.strategic_intent_l1 or "未分类"
                lines.append(
                    f"- {item.budget_name}: 年度{annual:.1f}万，已用{used:.1f}万，执行率{rate}%，{intent_l1}"
                )

            content = "【关键实例摘要】\n" + "\n".join(lines)
            block = ContextBlock(
                source=f"InstanceSummary#{object_id}",
                strategy="instance_summary",
                content=content,
                relevance_score=0.85,
            )
            context.blocks.append(block)
            context.total_tokens_estimate += self._estimate_tokens(content)
        except Exception:
            pass

        return context

    async def build_context(
        self,
        query: str = "",
        target_object_ids: Optional[List[str]] = None,
        target_relation_names: Optional[List[str]] = None,
        activated_rules: Optional[List[str]] = None,
        activated_behaviors: Optional[List[str]] = None,
        methodology_refs: Optional[List[str]] = None,
        scene_id: Optional[str] = None,
        db: Any = None,
    ) -> OAGContext:
        context = OAGContext(query=query, scene_id=scene_id)

        if target_object_ids:
            for obj_id in target_object_ids:
                context = await self.inject_object(obj_id, context, db=db)

        if target_relation_names:
            for rel_name in target_relation_names:
                context = self.inject_relation(rel_name, context)

        if activated_rules:
            for rule_id in activated_rules:
                context = self.inject_rule(rule_id, context)

        if activated_behaviors:
            for behavior_id in activated_behaviors:
                context = self.inject_behavior(behavior_id, context)

        if methodology_refs:
            for meth_name in methodology_refs:
                context = self.inject_methodology(meth_name, context)

        if target_object_ids and len(target_object_ids) >= 2:
            for i in range(len(target_object_ids)):
                for j in range(i + 1, len(target_object_ids)):
                    context = self.inject_path(
                        target_object_ids[i], target_object_ids[j], context
                    )

        if target_object_ids:
            for obj_id in target_object_ids:
                context = self.inject_aggregate(obj_id, context)

        # Inject instance summaries for budget-related objects
        if target_object_ids and db is not None:
            for obj_id in target_object_ids:
                context = await self.inject_instance_summary(obj_id, context, db)

        # RAG augmentation: if context blocks are insufficient, inject RAG results
        if len(context.blocks) < 3 and query:
            context = await self.inject_rag_context(query, context, db=db)

        context = self.optimize_window(context)
        return context

    def format_for_prompt(self, context: OAGContext) -> str:
        if not context.blocks:
            return ""

        parts = ["[Ontology上下文注入]"]
        for block in context.blocks:
            parts.append(block.content)
        parts.append("[/Ontology上下文注入]")

        return "\n\n".join(parts)
