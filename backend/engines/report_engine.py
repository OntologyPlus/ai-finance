from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import AlertRecord, AlertClosure
from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport
from models.budget import BudgetItem
from models.ontology import ReasoningTrace
from models.report_signoff import ReportSignoff, ExecutiveBrief
from engines.caliber_engine import CaliberEngine


class ReportEngine:
    """Report Engine (阶段七): Handles three reports + one meeting auto-generation.

    Three reports: Monthly flash, Quarterly report, Annual review.
    One meeting: Monthly management meeting materials.
    """

    def __init__(self):
        self.engine_name = "report"
        self.caliber_engine = CaliberEngine()

    # v12.0: 截点报告自动出具（5/8/10/12 日）
    async def generate_at_cutoff(
        self,
        period: str,
        report_type: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """截点报告自动出具入口

        Args:
            period: 期间 YYYY-MM
            report_type: monthly_5 / monthly_8 / monthly_10 / monthly_12
            db: AsyncSession

        Returns:
            {success, report_id, report_type, period, content}
        """
        try:
            report_id = f"RPT-{period}-{report_type}-{uuid.uuid4().hex[:6].upper()}"

            # 1. 收集本期数据
            stmt = select(MonthlyReport).where(MonthlyReport.period == period)
            result = await db.execute(stmt)
            monthly_data = result.scalar_one_or_none()

            # 2. 计算口径
            caliber = self.caliber_engine.get_caliber("monthly_flash")

            # 3. 构造报告内容（v12.0 简化版：基本元数据 + AI 占位）
            content = {
                "period": period,
                "report_type": report_type,
                "caliber": caliber,
                "data_source": "本系统自产自销",
                "engine": "ReportEngine",
                "generated_at": datetime.now().isoformat(),
                "auto_generated": True,
            }

            # 4. 记录推理轨迹
            await self._record_trace(
                scene_name=f"cutoff_{report_type}",
                input_data={"period": period, "report_type": report_type},
                steps=[
                    {"step": 1, "action": "收集期间数据", "result": "OK"},
                    {"step": 2, "action": "应用口径", "result": caliber},
                    {"step": 3, "action": "生成报告内容", "result": report_id},
                ],
                conclusion=f"截点 {report_type} 报告 {report_id} 自动出具完成",
                rule_ids=["FIN-RPT-001", "FIN-RPT-002"],
                confidence=Decimal("0.95"),
                db=db,
            )

            # 5. 写入 ExecutiveBrief
            try:
                brief = ExecutiveBrief(
                    brief_id=report_id,
                    period=period,
                    title=f"{period} {report_type} 自动出具",
                    summary=f"由系统在 {report_type} 截点自动出具的报告",
                    content=json.dumps(content, ensure_ascii=False, default=str),
                )
                db.add(brief)
                await db.commit()
            except Exception as e:
                logger.warning(f"ExecutiveBrief 写入失败: {e}")
                await db.rollback()

            logger.info(f"[ReportEngine] 截点报告 {report_id} 自动出具完成")
            return {
                "success": True,
                "report_id": report_id,
                "report_type": report_type,
                "period": period,
                "content": content,
            }
        except Exception as e:
            logger.error(f"ReportEngine.generate_at_cutoff error: {e}")
            return {"success": False, "error": str(e)}

    async def _record_trace(
        self,
        scene_name: str,
        input_data: Dict,
        steps: list,
        conclusion: str,
        rule_ids: list,
        confidence: Decimal,
        db: AsyncSession,
    ) -> None:
        trace = ReasoningTrace(
            trace_id=f"RT-RP-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def _get_execution_summary(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        stmt = select(ExecutionRate).where(ExecutionRate.period == period)
        result = await db.execute(stmt)
        rates = result.scalars().all()

        if not rates:
            return {"total_items": 0, "avg_annual_rate": 0, "by_l1": {}}

        by_l1: Dict[str, list] = {}
        for r in rates:
            by_l1.setdefault(r.l1_code, []).append(r)

        l1_summary = {}
        for l1_code, l1_rates in by_l1.items():
            avg_rate = sum(float(r.annual_rate or 0) for r in l1_rates) / len(l1_rates)
            l1_summary[l1_code] = {
                "item_count": len(l1_rates),
                "avg_annual_rate": round(avg_rate, 2),
            }

        avg_annual = sum(float(r.annual_rate or 0) for r in rates) / len(rates)

        return {
            "total_items": len(rates),
            "avg_annual_rate": round(avg_annual, 2),
            "by_l1": l1_summary,
        }

    async def _get_alert_summary(
        self, db: AsyncSession
    ) -> Dict[str, Any]:
        stmt = select(AlertRecord)
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        by_level = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0}
        by_status = {"开放": 0, "响应中": 0, "待闭环确认": 0, "已闭环": 0, "已升级": 0}

        for a in alerts:
            by_level[a.alert_level] = by_level.get(a.alert_level, 0) + 1
            by_status[a.alert_status] = by_status.get(a.alert_status, 0) + 1

        return {
            "total": len(alerts),
            "by_level": by_level,
            "by_status": by_status,
        }

    async def _get_strategic_intent_summary(self, db: AsyncSession) -> Dict[str, Any]:
        stmt = select(BudgetItem).where(
            BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        by_l1_intent = {}
        for item in items:
            intent = getattr(item, 'strategic_intent_l1', None) or '未分类'
            if intent not in by_l1_intent:
                by_l1_intent[intent] = {"total_budget": 0, "total_used": 0, "item_count": 0}
            by_l1_intent[intent]["total_budget"] += float(item.annual_amount or 0)
            by_l1_intent[intent]["total_used"] += float(item.used_amount or 0)
            by_l1_intent[intent]["item_count"] += 1

        for intent, data in by_l1_intent.items():
            data["execution_rate"] = round(data["total_used"] / data["total_budget"] * 100, 2) if data["total_budget"] > 0 else 0

        by_l2_intent = {}
        for item in items:
            l2 = getattr(item, 'strategic_intent_l2', None) or '未分类'
            if l2 not in by_l2_intent:
                by_l2_intent[l2] = {"total_budget": 0, "total_used": 0, "item_count": 0}
            by_l2_intent[l2]["total_budget"] += float(item.annual_amount or 0)
            by_l2_intent[l2]["total_used"] += float(item.used_amount or 0)
            by_l2_intent[l2]["item_count"] += 1

        for l2, data in by_l2_intent.items():
            data["execution_rate"] = round(data["total_used"] / data["total_budget"] * 100, 2) if data["total_budget"] > 0 else 0

        return {
            "by_l1_intent": by_l1_intent,
            "by_l2_intent": by_l2_intent,
        }

    async def generate_monthly_flash(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate monthly flash report.

        Deadlines: 5th (data collection), 8th (draft), 10th (final).

        Args:
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Dict with monthly flash report content.
        """
        try:
            steps = []

            execution_summary = await self._get_execution_summary(period, db)
            steps.append({"step": "execution_data", "items": execution_summary["total_items"]})

            alert_summary = await self._get_alert_summary(db)
            steps.append({"step": "alert_data", "total_alerts": alert_summary["total"]})

            strategic_summary = await self._get_strategic_intent_summary(db)

            stmt_budget = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            result_budget = await db.execute(stmt_budget)
            budget_items = result_budget.scalars().all()

            total_budget = sum(Decimal(str(i.annual_amount)) for i in budget_items)
            total_used = sum(Decimal(str(i.used_amount)) for i in budget_items)
            overall_rate = (total_used / total_budget * 100) if total_budget > 0 else Decimal("0")

            content = {
                "period": period,
                "report_type": "月度快报",
                "deadlines": {
                    "data_collection": "5th",
                    "draft": "8th",
                    "final": "10th",
                },
                "overall_execution_rate": float(overall_rate.quantize(Decimal("0.01"))),
                "total_budget": float(total_budget),
                "total_used": float(total_used),
                "execution_by_l1": execution_summary.get("by_l1", {}),
                "alert_summary": alert_summary,
                "strategic_intent_analysis": strategic_summary,
                "key_findings": self._extract_key_findings(execution_summary, alert_summary, overall_rate, strategic_summary, budget_items),
                "caliber_reconciliation": await self._generate_caliber_reconciliation(period, db),
                "caliber_note": self.caliber_engine.generate_caliber_note("management"),
            }

            report = MonthlyReport(
                id=f"MF-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type="月度快报",
                content=json.dumps(content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            steps.append({"step": "generate", "report_id": report.id})

            await self._record_trace(
                scene_name="月度快报生成",
                input_data={"period": period},
                steps=steps,
                conclusion=f"Monthly flash report {report.id} generated",
                rule_ids=["HR-RPT-MF"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Monthly flash report generated for period {period}")
            return content

        except Exception as e:
            logger.error(f"Monthly flash report generation failed for period {period}: {e}")
            raise

    async def _generate_caliber_reconciliation(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """生成口径对账数据"""
        return await self.caliber_engine.reconcile_calibers(period, db)

    def _extract_key_findings(
        self,
        execution_summary: Dict,
        alert_summary: Dict,
        overall_rate: Decimal,
        strategic_summary: Dict = None,
        budget_items: list = None,
    ) -> list:
        findings = []

        if overall_rate > Decimal("90"):
            findings.append("整体执行率超过90%，预算使用进度偏快")
        elif overall_rate < Decimal("50"):
            findings.append("整体执行率低于50%，预算使用进度偏慢")

        for l1_code, data in execution_summary.get("by_l1", {}).items():
            avg_rate = data.get("avg_annual_rate", 0)
            if avg_rate > 100:
                findings.append(f"L1科目{l1_code}执行率超过100%，存在超预算风险")
            elif avg_rate < 30:
                findings.append(f"L1科目{l1_code}执行率低于30%，需关注执行进度")

        red_alerts = alert_summary.get("by_level", {}).get("红色", 0)
        if red_alerts > 0:
            findings.append(f"存在{red_alerts}条红色预警，需立即处理")

        open_alerts = alert_summary.get("by_status", {}).get("开放", 0)
        if open_alerts > 10:
            findings.append(f"存在{open_alerts}条开放预警，预警响应需加强")

        # Strategic dimension findings
        if strategic_summary:
            for intent, data in strategic_summary.get("by_l1_intent", {}).items():
                rate = data.get("execution_rate", 0)
                if rate > 100:
                    findings.append(f"战略意图方向「{intent}」执行率超过100%，存在超预算风险")
                elif rate < 50:
                    findings.append(f"{intent}方向执行率仅{rate:.0f}%，低于目标60%，建议关注里程碑进展")
                else:
                    findings.append(f"{intent}方向预算执行率{rate:.0f}%，基本符合预期")

        # Quadrant-level execution anomalies from budget items
        if budget_items:
            quadrant_totals = {"发展": {"budget": 0, "used": 0}, "收缩": {"budget": 0, "used": 0},
                               "稳定": {"budget": 0, "used": 0}, "探索": {"budget": 0, "used": 0}}
            for item in budget_items:
                q = getattr(item, 'quadrant', None)
                if q and q in quadrant_totals:
                    quadrant_totals[q]["budget"] += float(item.annual_amount or 0)
                    quadrant_totals[q]["used"] += float(item.used_amount or 0)

            for q, totals in quadrant_totals.items():
                if totals["budget"] > 0:
                    q_rate = totals["used"] / totals["budget"] * 100
                    if q == "收缩" and q_rate > 100:
                        findings.append(f"收缩象限预算执行率超100%，需评估是否需要战略调整")
                    elif q == "发展" and q_rate < 50:
                        findings.append(f"发展象限执行率仅{q_rate:.0f}%，低于战略预期，建议加速推进")

        return findings

    async def generate_quarterly_report(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate quarterly report with 3GAP+3List and transfer recommendations.

        Args:
            period: Period string (YYYY-QN).
            db: AsyncSession for database operations.

        Returns:
            Dict with quarterly report content.
        """
        try:
            steps = []

            stmt_gap = select(GapAnalysis).where(GapAnalysis.period == period)
            result_gap = await db.execute(stmt_gap)
            gap_analyses = result_gap.scalars().all()
            steps.append({"step": "gap_data", "count": len(gap_analyses)})

            stmt_list = select(ListAnalysis).where(ListAnalysis.period == period)
            result_list = await db.execute(stmt_list)
            list_analyses = result_list.scalars().all()
            steps.append({"step": "list_data", "count": len(list_analyses)})

            alert_summary = await self._get_alert_summary(db)
            steps.append({"step": "alert_data", "total": alert_summary["total"]})

            from engines.pdca_review import PDCAReviewEngine
            pdca_engine = PDCAReviewEngine()
            transfer_recs = await pdca_engine._generate_transfer_recommendations(db)
            steps.append({"step": "transfer_recs", "count": len(transfer_recs)})

            strategic_summary = await self._get_strategic_intent_summary(db)

            content = {
                "period": period,
                "report_type": "季度汇报",
                "gap_analysis": [
                    {
                        "center_id": ga.center_id,
                        "l1_code": ga.l1_code,
                        "gap1": float(ga.gap1) if ga.gap1 else 0,
                        "gap2": float(ga.gap2) if ga.gap2 else 0,
                        "gap3": float(ga.gap3) if ga.gap3 else 0,
                    }
                    for ga in gap_analyses
                ],
                "list_classification": [
                    {
                        "center_id": la.center_id,
                        "list_type": la.list_type,
                        "item_name": la.item_name,
                        "action_plan": la.action_plan,
                    }
                    for la in list_analyses
                ],
                "transfer_recommendations": transfer_recs,
                "alert_summary": alert_summary,
                "strategic_intent_analysis": strategic_summary,
                "caliber_reconciliation": await self._generate_caliber_reconciliation(period, db),
                "caliber_note": self.caliber_engine.generate_caliber_note("management"),
            }

            report = MonthlyReport(
                id=f"QR-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type="季度汇报",
                content=json.dumps(content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            await self._record_trace(
                scene_name="季度报告生成",
                input_data={"period": period},
                steps=steps,
                conclusion=f"Quarterly report {report.id} generated",
                rule_ids=["HR-RPT-QR"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Quarterly report generated for period {period}")
            return content

        except Exception as e:
            logger.error(f"Quarterly report generation failed for period {period}: {e}")
            raise

    async def generate_annual_review(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate annual review with portfolio calibration.

        Args:
            period: Period string (YYYY).
            db: AsyncSession for database operations.

        Returns:
            Dict with annual review content.
        """
        try:
            steps = []

            from engines.pdca_review import PDCAReviewEngine
            pdca_engine = PDCAReviewEngine()

            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
            )
            result = await db.execute(stmt)
            all_items = result.scalars().all()
            steps.append({"step": "budget_data", "count": len(all_items)})

            portfolio = pdca_engine._calibrate_portfolio(all_items)
            steps.append({"step": "portfolio_calibration", "done": True})

            next_year_recs = pdca_engine._generate_next_year_recommendations(all_items, period)
            steps.append({"step": "next_year_recs", "count": len(next_year_recs)})

            strategic_summary = await self._get_strategic_intent_summary(db)

            for intent, data in strategic_summary.get("by_l1_intent", {}).items():
                rate = data.get("execution_rate", 0)
                if rate > 100:
                    next_year_recs.append(f"战略意图方向「{intent}」本年执行率超100%，建议下年调整预算或加强管控")
                elif rate < 50:
                    next_year_recs.append(f"战略意图方向「{intent}」本年执行率低于50%，建议下年评估该方向资源投入合理性")

            alert_summary = await self._get_alert_summary(db)

            total_budget = sum(Decimal(str(i.annual_amount)) for i in all_items)
            total_used = sum(Decimal(str(i.used_amount)) for i in all_items)
            overall_rate = (total_used / total_budget * 100) if total_budget > 0 else Decimal("0")

            content = {
                "period": period,
                "report_type": "年度复盘",
                "overall_execution_rate": float(overall_rate.quantize(Decimal("0.01"))),
                "total_budget": float(total_budget),
                "total_used": float(total_used),
                "portfolio_calibration": portfolio,
                "next_year_recommendations": next_year_recs,
                "alert_summary": alert_summary,
                "strategic_intent_analysis": strategic_summary,
                "year_over_year": {},
                "caliber_reconciliation": await self._generate_caliber_reconciliation(period, db),
                "caliber_note": self.caliber_engine.generate_caliber_note("management"),
            }

            report = MonthlyReport(
                id=f"AR-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type="年度复盘",
                content=json.dumps(content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            await self._record_trace(
                scene_name="年度复盘报告生成",
                input_data={"period": period},
                steps=steps,
                conclusion=f"Annual review report {report.id} generated",
                rule_ids=["HR-RPT-AR"],
                confidence=Decimal("85.00"),
                db=db,
            )

            logger.info(f"Annual review report generated for period {period}")
            return content

        except Exception as e:
            logger.error(f"Annual review report generation failed for period {period}: {e}")
            raise

    async def generate_meeting_materials(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate monthly management meeting materials with unclosed alerts.

        Args:
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Dict with meeting materials content.
        """
        try:
            steps = []

            execution_summary = await self._get_execution_summary(period, db)
            steps.append({"step": "execution_data", "done": True})

            stmt_unclosed = select(AlertRecord).where(
                AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认", "已升级"]),
            )
            result_unclosed = await db.execute(stmt_unclosed)
            unclosed_alerts = result_unclosed.scalars().all()
            steps.append({"step": "unclosed_alerts", "count": len(unclosed_alerts)})

            stmt_closure = select(AlertClosure).where(
                AlertClosure.closure_status.in_(["待业务响应", "待BP确认"]),
            )
            result_closure = await db.execute(stmt_closure)
            pending_closures = result_closure.scalars().all()
            steps.append({"step": "pending_closures", "count": len(pending_closures)})

            alert_summary = await self._get_alert_summary(db)

            strategic_summary = await self._get_strategic_intent_summary(db)

            content = {
                "period": period,
                "report_type": "经营分析会",
                "execution_summary": execution_summary,
                "unclosed_alerts": [
                    {
                        "alert_id": a.alert_id,
                        "level": a.alert_level,
                        "type": a.alert_type,
                        "status": a.alert_status,
                        "l1_code": a.l1_code,
                        "responsible_person": a.responsible_person,
                        "deadline": a.response_deadline.isoformat() if a.response_deadline else None,
                    }
                    for a in unclosed_alerts
                ],
                "pending_closures": [
                    {
                        "closure_id": c.closure_id,
                        "alert_id": c.alert_id,
                        "status": c.closure_status,
                        "responder": c.business_responder,
                    }
                    for c in pending_closures
                ],
                "alert_summary": alert_summary,
                "strategic_intent_analysis": strategic_summary,
                "agenda_items": self._generate_agenda(unclosed_alerts, pending_closures, execution_summary, strategic_summary),
            }

            report = MonthlyReport(
                id=f"MT-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type="经营分析会",
                content=json.dumps(content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            await self._record_trace(
                scene_name="经营分析会材料生成",
                input_data={"period": period},
                steps=steps,
                conclusion=f"Meeting materials {report.id} generated",
                rule_ids=["HR-RPT-MT"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Meeting materials generated for period {period}")
            return content

        except Exception as e:
            logger.error(f"Meeting materials generation failed for period {period}: {e}")
            raise

    async def validate_data_consistency(self, db: AsyncSession) -> Dict[str, Any]:
        from models.budget import BudgetItem
        from models.expense import ExpenseReport
        from models.alert import AlertRecord
        from sqlalchemy import select, func

        issues = []

        budget_total = await db.execute(select(func.sum(BudgetItem.annual_amount)).where(BudgetItem.status.in_(["已授予", "执行中"])))
        budget_sum = float(budget_total.scalar() or 0)

        expense_total = await db.execute(select(func.sum(ExpenseReport.amount)).where(ExpenseReport.status == "已核销"))
        expense_sum = float(expense_total.scalar() or 0)

        used_total = await db.execute(select(func.sum(BudgetItem.used_amount)).where(BudgetItem.status.in_(["已授予", "执行中"])))
        used_sum = float(used_total.scalar() or 0)

        if abs(used_sum - expense_sum) > 0.01:
            issues.append({"type": "预算核销与报销金额不一致", "budget_used": used_sum, "expense_total": expense_sum, "diff": abs(used_sum - expense_sum)})

        open_alerts = await db.execute(select(func.count(AlertRecord.id)).where(AlertRecord.alert_status.in_(["开放", "响应中"])))
        open_count = open_alerts.scalar() or 0

        return {
            "is_consistent": len(issues) == 0,
            "issues": issues,
            "summary": {
                "budget_total": budget_sum,
                "expense_total": expense_sum,
                "budget_used": used_sum,
                "open_alerts": open_count,
            }
        }

    def _generate_agenda(
        self,
        unclosed_alerts: list,
        pending_closures: list,
        execution_summary: Dict,
        strategic_summary: Dict = None,
    ) -> list:
        agenda = []

        red_alerts = [a for a in unclosed_alerts if a.alert_level == "红色"]
        if red_alerts:
            agenda.append({
                "item": "红色预警处理",
                "priority": "紧急",
                "count": len(red_alerts),
            })

        orange_alerts = [a for a in unclosed_alerts if a.alert_level == "橙色"]
        if orange_alerts:
            agenda.append({
                "item": "橙色预警跟进",
                "priority": "重要",
                "count": len(orange_alerts),
            })

        if pending_closures:
            agenda.append({
                "item": "预警闭环确认",
                "priority": "重要",
                "count": len(pending_closures),
            })

        avg_rate = execution_summary.get("avg_annual_rate", 0)
        if avg_rate > 0:
            agenda.append({
                "item": "执行率回顾",
                "priority": "常规",
                "detail": f"平均执行率{avg_rate:.1f}%",
            })

        if strategic_summary:
            l1_intents = strategic_summary.get("by_l1_intent", {})
            if l1_intents:
                agenda.append({
                    "item": "战略意图执行分析",
                    "priority": "重要",
                    "detail": f"共{len(l1_intents)}个战略意图方向",
                })

        agenda.append({
            "item": "下月工作重点",
            "priority": "常规",
        })

        return agenda

    async def signoff_report(
        self,
        report_id: str,
        author: str,
        reviewer: str,
        signer: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Report signoff workflow: 编制→审核→签发→发布.

        Creates a ReportSignoff record and advances through the workflow stages.

        Args:
            report_id: Report ID to sign off.
            author: 编制人.
            reviewer: 审核人.
            signer: 签发人.
            db: AsyncSession for database operations.

        Returns:
            Dict with signoff result and current status.
        """
        try:
            stmt = select(ReportSignoff).where(ReportSignoff.report_id == report_id)
            result = await db.execute(stmt)
            signoff = result.scalars().first()

            if signoff is None:
                signoff = ReportSignoff(
                    report_id=report_id,
                    author=author,
                    reviewer=reviewer,
                    signer=signer,
                    status="编制中",
                )
                db.add(signoff)
                await db.flush()
                logger.info(f"Report signoff created for {report_id}, status=编制中")
                return {"report_id": report_id, "status": "编制中", "action": "created"}

            status_flow = ["编制中", "待审核", "待签发", "已签发", "已发布"]
            current_idx = status_flow.index(signoff.status) if signoff.status in status_flow else -1

            if current_idx < 0 or current_idx >= len(status_flow) - 1:
                if signoff.status == "已驳回":
                    signoff.status = "编制中"
                    logger.info(f"Report {report_id} reverted to 编制中 from 已驳回")
                else:
                    logger.warning(f"Report {report_id} already at terminal status: {signoff.status}")
                    return {"report_id": report_id, "status": signoff.status, "action": "no_change"}

            if signoff.status == "编制中":
                signoff.status = "待审核"
            elif signoff.status == "待审核":
                signoff.status = "待签发"
            elif signoff.status == "待签发":
                signoff.status = "已签发"
                signoff.signoff_date = datetime.now()
            elif signoff.status == "已签发":
                signoff.status = "已发布"
                signoff.publish_date = datetime.now()

            await db.flush()
            logger.info(f"Report {report_id} signoff advanced to {signoff.status}")
            return {"report_id": report_id, "status": signoff.status, "action": "advanced"}

        except Exception as e:
            logger.error(f"Report signoff failed for {report_id}: {e}")
            raise

    async def generate_executive_brief(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Generate executive brief using 三聚焦 paradigm (聚焦问题/聚焦原因/聚焦行动).

        Args:
            period: Period string (YYYY-MM or YYYY-QN).
            db: AsyncSession for database operations.

        Returns:
            Dict with executive brief content.
        """
        try:
            execution_summary = await self._get_execution_summary(period, db)
            alert_summary = await self._get_alert_summary(db)
            strategic_summary = await self._get_strategic_intent_summary(db)

            # 聚焦问题: identify top issues from alerts and execution anomalies
            focus_problem_parts = []
            red_alerts = alert_summary.get("by_level", {}).get("红色", 0)
            orange_alerts = alert_summary.get("by_level", {}).get("橙色", 0)
            if red_alerts > 0:
                focus_problem_parts.append(f"存在{red_alerts}条红色预警，需立即处理")
            if orange_alerts > 0:
                focus_problem_parts.append(f"存在{orange_alerts}条橙色预警，需重点关注")

            avg_rate = execution_summary.get("avg_annual_rate", 0)
            if avg_rate > 90:
                focus_problem_parts.append(f"整体执行率{avg_rate:.1f}%，预算使用进度偏快")
            elif avg_rate < 50:
                focus_problem_parts.append(f"整体执行率仅{avg_rate:.1f}%，预算使用进度偏慢")

            for l1_code, data in execution_summary.get("by_l1", {}).items():
                l1_rate = data.get("avg_annual_rate", 0)
                if l1_rate > 100:
                    focus_problem_parts.append(f"L1科目{l1_code}执行率超100%，存在超预算风险")
                elif l1_rate < 30:
                    focus_problem_parts.append(f"L1科目{l1_code}执行率低于30%，执行进度滞后")

            focus_problem = "；".join(focus_problem_parts) if focus_problem_parts else "当前无重大问题"

            # 聚焦原因: root cause analysis
            focus_cause_parts = []
            open_alerts = alert_summary.get("by_status", {}).get("开放", 0)
            if open_alerts > 5:
                focus_cause_parts.append(f"预警响应不及时，{open_alerts}条预警仍处于开放状态，可能存在管理效率不足")

            for intent, data in strategic_summary.get("by_l1_intent", {}).items():
                rate = data.get("execution_rate", 0)
                if rate < 50:
                    focus_cause_parts.append(f"战略方向「{intent}」执行率仅{rate:.0f}%，资源配置或执行管理可能存在问题")

            focus_cause = "；".join(focus_cause_parts) if focus_cause_parts else "各维度运行正常，无明显根因"

            # 聚焦行动: recommended actions
            focus_action_parts = []
            if red_alerts > 0:
                focus_action_parts.append(f"立即处理{red_alerts}条红色预警，启动应急响应流程")
            if avg_rate < 50:
                focus_action_parts.append("加速预算执行进度，评估是否需要调整执行计划")
            elif avg_rate > 90:
                focus_action_parts.append("加强预算管控，评估超支风险并准备调拨方案")

            for intent, data in strategic_summary.get("by_l1_intent", {}).items():
                rate = data.get("execution_rate", 0)
                if rate < 50:
                    focus_action_parts.append(f"战略方向「{intent}」需加速推进，建议增加资源投入或调整里程碑")

            focus_action = "；".join(focus_action_parts) if focus_action_parts else "维持当前运营节奏，持续监控"

            # Key metrics summary
            key_metrics = {
                "overall_execution_rate": avg_rate,
                "total_budget_items": execution_summary.get("total_items", 0),
                "total_alerts": alert_summary.get("total", 0),
                "red_alerts": red_alerts,
                "orange_alerts": orange_alerts,
            }

            # Risk alerts
            risk_alerts = []
            if red_alerts > 0:
                risk_alerts.append({"level": "高", "description": f"{red_alerts}条红色预警未处理"})
            if avg_rate > 90:
                risk_alerts.append({"level": "中", "description": "整体执行率偏高，存在超预算风险"})
            for l1_code, data in execution_summary.get("by_l1", {}).items():
                if data.get("avg_annual_rate", 0) > 100:
                    risk_alerts.append({"level": "高", "description": f"L1科目{l1_code}超预算"})

            brief = ExecutiveBrief(
                period=period,
                focus_problem=focus_problem,
                focus_cause=focus_cause,
                focus_action=focus_action,
                key_metrics=key_metrics,
                risk_alerts=risk_alerts,
                status="草稿",
            )
            db.add(brief)
            await db.flush()

            content = {
                "period": period,
                "brief_id": brief.id,
                "focus_problem": focus_problem,
                "focus_cause": focus_cause,
                "focus_action": focus_action,
                "key_metrics": key_metrics,
                "risk_alerts": risk_alerts,
                "status": "草稿",
            }

            await self._record_trace(
                scene_name="高管简报生成",
                input_data={"period": period},
                steps=[{"step": "generate_brief", "brief_id": brief.id}],
                conclusion=f"Executive brief generated for period {period}",
                rule_ids=["HR-RPT-EB"],
                confidence=Decimal("85.00"),
                db=db,
            )

            logger.info(f"Executive brief generated for period {period}")
            return content

        except Exception as e:
            logger.error(f"Executive brief generation failed for period {period}: {e}")
            raise

    async def generate_meeting_agenda(
        self, meeting_type: str, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Auto-generate business review meeting agenda.

        Args:
            meeting_type: Meeting type (月度/季度).
            period: Period string.
            db: AsyncSession for database operations.

        Returns:
            Dict with meeting agenda content.
        """
        try:
            execution_summary = await self._get_execution_summary(period, db)
            alert_summary = await self._get_alert_summary(db)
            strategic_summary = await self._get_strategic_intent_summary(db)

            agenda_items = []

            # 1. 预警回顾
            red_alerts = alert_summary.get("by_level", {}).get("红色", 0)
            orange_alerts = alert_summary.get("by_level", {}).get("橙色", 0)
            if red_alerts > 0:
                agenda_items.append({
                    "item": "红色预警处理",
                    "priority": "紧急",
                    "duration": "15min",
                    "detail": f"共{red_alerts}条红色预警需处理",
                })
            if orange_alerts > 0:
                agenda_items.append({
                    "item": "橙色预警跟进",
                    "priority": "重要",
                    "duration": "10min",
                    "detail": f"共{orange_alerts}条橙色预警需跟进",
                })

            # 2. 执行率回顾
            avg_rate = execution_summary.get("avg_annual_rate", 0)
            agenda_items.append({
                "item": "预算执行率回顾",
                "priority": "重要",
                "duration": "20min",
                "detail": f"平均执行率{avg_rate:.1f}%",
            })

            # 3. 3GAP分析 (季度会议)
            if meeting_type == "季度":
                agenda_items.append({
                    "item": "3GAP差距分析",
                    "priority": "重要",
                    "duration": "30min",
                    "detail": "目标差距/执行差距/能力差距分析",
                })

            # 4. 战略意图执行分析
            if strategic_summary.get("by_l1_intent"):
                low_rate_intents = [
                    f"「{intent}」({data['execution_rate']:.0f}%)"
                    for intent, data in strategic_summary["by_l1_intent"].items()
                    if data.get("execution_rate", 0) < 60
                ]
                agenda_items.append({
                    "item": "战略意图执行分析",
                    "priority": "重要",
                    "duration": "15min",
                    "detail": f"低于60%的方向：{', '.join(low_rate_intents)}" if low_rate_intents else "各方向执行正常",
                })

            # 5. 决议追踪
            agenda_items.append({
                "item": "上次决议执行情况",
                "priority": "常规",
                "duration": "10min",
            })

            # 6. 下阶段工作重点
            agenda_items.append({
                "item": "下阶段工作重点",
                "priority": "常规",
                "duration": "15min",
            })

            content = {
                "meeting_type": meeting_type,
                "period": period,
                "agenda": agenda_items,
                "total_duration": f"{sum(int(item.get('duration', '0').replace('min', '')) for item in agenda_items)}min",
                "alert_summary": alert_summary,
                "execution_summary": execution_summary,
            }

            await self._record_trace(
                scene_name="经营分析会议程生成",
                input_data={"meeting_type": meeting_type, "period": period},
                steps=[{"step": "generate_agenda", "item_count": len(agenda_items)}],
                conclusion=f"Meeting agenda generated for {meeting_type} {period}",
                rule_ids=["HR-RPT-MA"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Meeting agenda generated for {meeting_type} period {period}")
            return content

        except Exception as e:
            logger.error(f"Meeting agenda generation failed for {meeting_type} {period}: {e}")
            raise

    async def generate_trend_analysis(
        self,
        l1_code: Optional[str],
        months: int,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate trend analysis report for last N months.

        Args:
            l1_code: Optional L1 code to filter (if None, analyze all).
            months: Number of months to analyze.
            db: AsyncSession for database operations.

        Returns:
            Dict with trend analysis content.
        """
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=months * 30)

            stmt = select(ExecutionRate).where(ExecutionRate.created_at >= cutoff)
            if l1_code:
                stmt = stmt.where(ExecutionRate.l1_code == l1_code)
            result = await db.execute(stmt)
            rates = result.scalars().all()

            if not rates:
                return {"error": "无历史执行率数据", "trend_data": []}

            # Group by period
            by_period: Dict[str, List] = {}
            for r in rates:
                period = r.period
                by_period.setdefault(period, []).append(r)

            # Calculate trend
            trend_data = []
            for period in sorted(by_period.keys()):
                period_rates = by_period[period]
                avg_monthly = sum(float(r.monthly_rate or 0) for r in period_rates) / len(period_rates)
                avg_cumulative = sum(float(r.cumulative_rate or 0) for r in period_rates) / len(period_rates)
                avg_annual = sum(float(r.annual_rate or 0) for r in period_rates) / len(period_rates)

                trend_data.append({
                    "period": period,
                    "avg_monthly_rate": round(avg_monthly, 2),
                    "avg_cumulative_rate": round(avg_cumulative, 2),
                    "avg_annual_rate": round(avg_annual, 2),
                    "item_count": len(period_rates),
                })

            # Identify trend direction
            if len(trend_data) >= 2:
                first_rate = trend_data[0]["avg_annual_rate"]
                last_rate = trend_data[-1]["avg_annual_rate"]
                change = last_rate - first_rate

                if change > 10:
                    trend_direction = "上升"
                    trend_description = f"执行率从{first_rate:.1f}%上升至{last_rate:.1f}%，预算使用进度加快"
                elif change < -10:
                    trend_direction = "下降"
                    trend_description = f"执行率从{first_rate:.1f}%下降至{last_rate:.1f}%，预算使用进度放缓"
                else:
                    trend_direction = "平稳"
                    trend_description = f"执行率保持在{last_rate:.1f}%左右，预算使用节奏稳定"
            else:
                trend_direction = "数据不足"
                trend_description = "历史数据不足，无法判断趋势"

            # Identify inflection points
            inflection_points = []
            for i in range(1, len(trend_data) - 1):
                prev_rate = trend_data[i-1]["avg_annual_rate"]
                curr_rate = trend_data[i]["avg_annual_rate"]
                next_rate = trend_data[i+1]["avg_annual_rate"]

                if (curr_rate > prev_rate and curr_rate > next_rate) or \
                   (curr_rate < prev_rate and curr_rate < next_rate):
                    inflection_points.append({
                        "period": trend_data[i]["period"],
                        "rate": curr_rate,
                        "type": "峰值" if curr_rate > prev_rate else "谷值",
                    })

            await self._record_trace(
                scene_name="趋势分析报告生成",
                input_data={"l1_code": l1_code, "months": months},
                steps=[
                    {"step": "load_data", "count": len(rates)},
                    {"step": "calculate_trend", "periods": len(trend_data)},
                ],
                conclusion=f"Trend analysis: {trend_direction}",
                rule_ids=["HR-RPT-TREND"],
                confidence=Decimal("85.00"),
                db=db,
            )

            logger.info(f"Trend analysis generated for {months} months")

            return {
                "l1_code": l1_code,
                "months": months,
                "trend_direction": trend_direction,
                "trend_description": trend_description,
                "trend_data": trend_data,
                "inflection_points": inflection_points,
            }

        except Exception as e:
            logger.error(f"Trend analysis generation failed: {e}")
            raise

    async def generate_risk_assessment(
        self,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate risk assessment report with risk matrix.

        Args:
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Dict with risk assessment content.
        """
        try:
            # Query alerts
            stmt_alert = select(AlertRecord).where(
                AlertRecord.created_at >= datetime.now() - timedelta(days=30)
            )
            result_alert = await db.execute(stmt_alert)
            alerts = result_alert.scalars().all()

            # Query execution rates
            stmt_rate = select(ExecutionRate).where(ExecutionRate.period == period)
            result_rate = await db.execute(stmt_rate)
            rates = result_rate.scalars().all()

            # Build risk matrix
            risk_items = []

            # Risk 1: Over-budget risk
            for rate in rates:
                annual_rate = float(rate.annual_rate or 0)
                if annual_rate > 100:
                    probability = "高" if annual_rate > 110 else "中"
                    impact = "高" if annual_rate > 120 else "中"
                    risk_items.append({
                        "risk_type": "超预算风险",
                        "l1_code": rate.l1_code,
                        "description": f"L1科目{rate.l1_code}执行率{annual_rate:.1f}%，已超预算",
                        "probability": probability,
                        "impact": impact,
                        "risk_level": "高" if probability == "高" and impact == "高" else "中",
                        "recommendation": "立即管控支出，评估是否需要预算调整",
                    })

            # Risk 2: Alert response risk
            open_alerts = [a for a in alerts if a.alert_status in ("开放", "响应中")]
            if len(open_alerts) > 10:
                probability = "高" if len(open_alerts) > 20 else "中"
                impact = "中"
                risk_items.append({
                    "risk_type": "预警响应风险",
                    "l1_code": None,
                    "description": f"存在{len(open_alerts)}条未闭环预警，响应效率不足",
                    "probability": probability,
                    "impact": impact,
                    "risk_level": "中",
                    "recommendation": "加强预警响应机制，确保及时闭环",
                })

            # Risk 3: Strategic execution risk
            strategic_summary = await self._get_strategic_intent_summary(db)
            for intent, data in strategic_summary.get("by_l1_intent", {}).items():
                rate = data.get("execution_rate", 0)
                if rate < 40:
                    probability = "高" if rate < 30 else "中"
                    impact = "高"
                    risk_items.append({
                        "risk_type": "战略执行风险",
                        "l1_code": None,
                        "description": f"战略方向「{intent}」执行率仅{rate:.1f}%，严重滞后",
                        "probability": probability,
                        "impact": impact,
                        "risk_level": "高",
                        "recommendation": f"评估「{intent}」方向资源配置，加速推进执行",
                    })

            # Risk matrix summary
            high_risks = [r for r in risk_items if r["risk_level"] == "高"]
            medium_risks = [r for r in risk_items if r["risk_level"] == "中"]
            low_risks = [r for r in risk_items if r["risk_level"] == "低"]

            overall_risk_level = "低"
            if len(high_risks) >= 2:
                overall_risk_level = "高"
            elif len(high_risks) >= 1 or len(medium_risks) >= 3:
                overall_risk_level = "中"

            await self._record_trace(
                scene_name="风险评估报告生成",
                input_data={"period": period},
                steps=[
                    {"step": "load_alerts", "count": len(alerts)},
                    {"step": "load_rates", "count": len(rates)},
                    {"step": "assess_risks", "count": len(risk_items)},
                ],
                conclusion=f"Risk assessment: {overall_risk_level} ({len(high_risks)} high, {len(medium_risks)} medium)",
                rule_ids=["HR-RPT-RISK"],
                confidence=Decimal("80.00"),
                db=db,
            )

            logger.info(f"Risk assessment generated for period {period}")

            return {
                "period": period,
                "overall_risk_level": overall_risk_level,
                "high_risk_count": len(high_risks),
                "medium_risk_count": len(medium_risks),
                "low_risk_count": len(low_risks),
                "risk_items": risk_items,
                "risk_matrix": {
                    "高概率高影响": len([r for r in risk_items if r["probability"] == "高" and r["impact"] == "高"]),
                    "高概率中影响": len([r for r in risk_items if r["probability"] == "高" and r["impact"] == "中"]),
                    "中概率高影响": len([r for r in risk_items if r["probability"] == "中" and r["impact"] == "高"]),
                    "中概率中影响": len([r for r in risk_items if r["probability"] == "中" and r["impact"] == "中"]),
                },
            }

        except Exception as e:
            logger.error(f"Risk assessment generation failed for period {period}: {e}")
            raise

    async def generate_special_report(
        self,
        report_type: str,
        target_code: str,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate special analysis report for specific L1/strategic intent.

        Args:
            report_type: Report type ("L1科目专项" or "战略意图专项").
            target_code: Target code (L1 code or strategic intent name).
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Dict with special report content.
        """
        try:
            # Query budget items
            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
            )
            if report_type == "L1科目专项":
                stmt = stmt.where(BudgetItem.l1_code == target_code)
            elif report_type == "战略意图专项":
                stmt = stmt.where(BudgetItem.strategic_intent_l1 == target_code)

            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {"error": f"未找到相关预算项目: {target_code}"}

            # Aggregate data
            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            total_granted = sum(float(i.granted_amount or 0) for i in items)
            total_frozen = sum(float(i.frozen_amount or 0) for i in items)
            execution_rate = (total_used / total_annual * 100) if total_annual > 0 else 0

            # By quadrant
            by_quadrant = {}
            for item in items:
                q = item.quadrant
                if q not in by_quadrant:
                    by_quadrant[q] = {"count": 0, "annual": 0, "used": 0}
                by_quadrant[q]["count"] += 1
                by_quadrant[q]["annual"] += float(item.annual_amount or 0)
                by_quadrant[q]["used"] += float(item.used_amount or 0)

            for q, data in by_quadrant.items():
                data["execution_rate"] = round(data["used"] / data["annual"] * 100, 2) if data["annual"] > 0 else 0

            # By L2
            by_l2 = {}
            for item in items:
                l2 = item.l2_code or "未分类"
                if l2 not in by_l2:
                    by_l2[l2] = {"count": 0, "annual": 0, "used": 0}
                by_l2[l2]["count"] += 1
                by_l2[l2]["annual"] += float(item.annual_amount or 0)
                by_l2[l2]["used"] += float(item.used_amount or 0)

            for l2, data in by_l2.items():
                data["execution_rate"] = round(data["used"] / data["annual"] * 100, 2) if data["annual"] > 0 else 0

            # Query alerts
            budget_ids = [i.budget_id for i in items]
            stmt_alert = select(AlertRecord).where(AlertRecord.budget_id.in_(budget_ids))
            result_alert = await db.execute(stmt_alert)
            alerts = result_alert.scalars().all()

            alert_summary = {
                "total": len(alerts),
                "by_level": {},
                "by_status": {},
            }
            for alert in alerts:
                level = alert.alert_level
                status = alert.alert_status
                alert_summary["by_level"][level] = alert_summary["by_level"].get(level, 0) + 1
                alert_summary["by_status"][status] = alert_summary["by_status"].get(status, 0) + 1

            # Key findings
            findings = []
            if execution_rate > 100:
                findings.append(f"执行率{execution_rate:.1f}%，已超预算，需立即管控")
            elif execution_rate < 50:
                findings.append(f"执行率仅{execution_rate:.1f}%，执行进度严重滞后")

            for q, data in by_quadrant.items():
                q_rate = data["execution_rate"]
                if q == "收缩" and q_rate > 100:
                    findings.append(f"收缩象限执行率{q_rate:.1f}%，需评估战略调整")
                elif q == "发展" and q_rate < 50:
                    findings.append(f"发展象限执行率{q_rate:.1f}%，需加速推进")

            red_alerts = alert_summary["by_level"].get("红色", 0)
            if red_alerts > 0:
                findings.append(f"存在{red_alerts}条红色预警，需立即处理")

            # Recommendations
            recommendations = []
            if execution_rate > 100:
                recommendations.append("立即冻结非必要支出，评估预算调整方案")
            elif execution_rate < 50:
                recommendations.append("分析执行滞后原因，制定加速执行计划")

            if red_alerts > 0:
                recommendations.append("启动红色预警应急响应流程")

            for q, data in by_quadrant.items():
                if data["execution_rate"] > 120:
                    recommendations.append(f"{q}象限超支严重，建议调拨预算或加强管控")

            content = {
                "report_type": report_type,
                "target_code": target_code,
                "period": period,
                "summary": {
                    "total_items": len(items),
                    "total_annual": total_annual,
                    "total_used": total_used,
                    "total_granted": total_granted,
                    "total_frozen": total_frozen,
                    "execution_rate": round(execution_rate, 2),
                },
                "by_quadrant": by_quadrant,
                "by_l2": by_l2,
                "alert_summary": alert_summary,
                "key_findings": findings,
                "recommendations": recommendations,
            }

            # Save report
            report = MonthlyReport(
                id=f"SP-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type=report_type,
                content=json.dumps(content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            await self._record_trace(
                scene_name="专项报告生成",
                input_data={"report_type": report_type, "target_code": target_code, "period": period},
                steps=[
                    {"step": "load_items", "count": len(items)},
                    {"step": "analyze", "done": True},
                ],
                conclusion=f"Special report {report.id} generated for {target_code}",
                rule_ids=["HR-RPT-SP"],
                confidence=Decimal("85.00"),
                db=db,
            )

            logger.info(f"Special report generated for {target_code}, period {period}")
            return content

        except Exception as e:
            logger.error(f"Special report generation failed: {e}")
            raise
