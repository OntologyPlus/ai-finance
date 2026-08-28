from __future__ import annotations

import json
import math
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport
from models.budget import BudgetItem, BudgetSubjectL1
from models.alert import AlertRecord, AlertClosure
from models.expense import ExpenseReport, BudgetWriteOff
from models.ontology import OntologyRule, ReasoningTrace

# 季度季节性权重因子：Q4通常使用量高
SEASONAL_WEIGHTS = {1: Decimal("0.9"), 2: Decimal("1.0"), 3: Decimal("1.0"), 4: Decimal("1.1")}


class DataLockError(Exception):
    pass


class BusinessAnalysisEngine:
    """Business Analysis Engine (阶段四): Handles execution rate calculation, quadrant compliance, 3GAP+3List analysis.

    Calculates monthly/cumulative/annual execution rates,
    checks quadrant compliance, performs 3GAP analysis (目标差距/执行差距/预测变动),
    and classifies items into 3List (确定类/风险类/机会类).
    """

    def __init__(self):
        self.engine_name = "business_analysis"

    def check_data_lock(self, period: str, db: AsyncSession = None) -> bool:
        from datetime import datetime
        now = datetime.now()
        try:
            year, month = period.split("-")
            year, month = int(year), int(month)
        except (ValueError, AttributeError):
            return False
        lock_date = datetime(year, month, 12, 23, 59, 59)
        if now > lock_date:
            return True
        return False

    async def lock_period_data(self, period: str, locked_by: str, db: AsyncSession) -> Dict:
        from models.analysis import ExecutionRate
        from sqlalchemy import update
        stmt = update(ExecutionRate).where(
            ExecutionRate.period == period,
            ExecutionRate.is_locked == False
        ).values(is_locked=True, locked_by=locked_by, locked_at=datetime.now())
        await db.execute(stmt)
        await db.commit()
        return {"period": period, "locked_by": locked_by, "status": "locked"}

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
            trace_id=f"RT-BA-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def calculate_execution_rates(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> List[ExecutionRate]:
        """Calculate execution rates for a center in a given period.

        Monthly rate = actual / monthly plan * 100%.
        Cumulative rate = cumulative actual / cumulative plan * 100%.
        Annual rate = cumulative actual / annual budget * 100%.

        Args:
            center_id: Center ID to calculate for.
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            List of ExecutionRate records.
        """
        try:
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            rates: List[ExecutionRate] = []

            for item in items:
                annual = Decimal(str(item.annual_amount))
                used = Decimal(str(item.used_amount))
                frozen = Decimal(str(item.frozen_amount))

                month_num = int(period.split("-")[1])
                monthly_plan = annual / 12 if annual > 0 else Decimal("0")
                cumulative_plan = monthly_plan * month_num

                monthly_actual = used / month_num if month_num > 0 else Decimal("0")

                monthly_rate = (monthly_actual / monthly_plan * 100) if monthly_plan > 0 else Decimal("0")
                cumulative_rate = (used / cumulative_plan * 100) if cumulative_plan > 0 else Decimal("0")
                annual_rate = (used / annual * 100) if annual > 0 else Decimal("0")

                rate_record = ExecutionRate(
                    id=f"ER-{uuid.uuid4().hex[:8].upper()}",
                    period=period,
                    l1_code=item.l1_code,
                    l2_code=item.l2_code,
                    l3_code=item.l3_code,
                    center_id=center_id,
                    monthly_plan=monthly_plan.quantize(Decimal("0.01")),
                    monthly_actual=monthly_actual.quantize(Decimal("0.01")),
                    cumulative_plan=cumulative_plan.quantize(Decimal("0.01")),
                    cumulative_actual=used.quantize(Decimal("0.01")),
                    annual_budget=annual.quantize(Decimal("0.01")),
                    monthly_rate=monthly_rate.quantize(Decimal("0.01")),
                    cumulative_rate=cumulative_rate.quantize(Decimal("0.01")),
                    annual_rate=annual_rate.quantize(Decimal("0.01")),
                )
                db.add(rate_record)
                rates.append(rate_record)

            await db.flush()

            logger.info(f"Execution rates calculated for center {center_id}, period {period}: {len(rates)} records")
            return rates

        except Exception as e:
            logger.error(f"Execution rate calculation failed for center {center_id}: {e}")
            raise

    async def check_quadrant_compliance(
        self, period: str, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Check quadrant compliance across all budget items.

        Verifies that budget execution follows quadrant strategy:
        - 发展: Should have high execution rate
        - 收缩: Should have low execution rate
        - 稳定: Should have moderate execution rate
        - 探索: Variable execution rate acceptable

        Args:
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            List of compliance check results per quadrant.
        """
        try:
            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            quadrant_data: Dict[str, Dict] = {
                "发展": {"items": [], "expected_rate": Decimal("80")},
                "收缩": {"items": [], "expected_rate": Decimal("40")},
                "稳定": {"items": [], "expected_rate": Decimal("60")},
                "探索": {"items": [], "expected_rate": Decimal("50")},
            }

            for item in items:
                quadrant_data[item.quadrant]["items"].append(item)

            compliance_results = []
            for quadrant, data in quadrant_data.items():
                items_list = data["items"]
                if not items_list:
                    compliance_results.append({
                        "quadrant": quadrant,
                        "compliant": True,
                        "actual_rate": 0,
                        "expected_rate": float(data["expected_rate"]),
                        "item_count": 0,
                        "deviation": 0,
                    })
                    continue

                total_annual = sum(Decimal(str(i.annual_amount)) for i in items_list)
                total_used = sum(Decimal(str(i.used_amount)) for i in items_list)
                actual_rate = (total_used / total_annual * 100) if total_annual > 0 else Decimal("0")

                expected = data["expected_rate"]
                deviation = actual_rate - expected
                compliant = abs(deviation) < Decimal("20")

                compliance_results.append({
                    "quadrant": quadrant,
                    "compliant": compliant,
                    "actual_rate": float(actual_rate.quantize(Decimal("0.01"))),
                    "expected_rate": float(expected),
                    "item_count": len(items_list),
                    "deviation": float(deviation.quantize(Decimal("0.01"))),
                })

            logger.info(f"Quadrant compliance check complete for period {period}")
            return compliance_results

        except Exception as e:
            logger.error(f"Quadrant compliance check failed: {e}")
            raise

    async def analyze_3gap(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> GapAnalysis:
        """Perform 3GAP analysis for a center.

        GAP1 (目标差距): Annual target vs current forecast.
        GAP2 (执行差距): Current forecast vs executed.
        GAP3 (预测变动): Current forecast vs previous forecast.

        Args:
            center_id: Center ID.
            period: Period string (YYYY-QN).
            db: AsyncSession for database operations.

        Returns:
            GapAnalysis record with three gap values.
        """
        try:
            if self.check_data_lock(period):
                logger.warning(f"Period {period} data lock date has passed, data should be finalized")

            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
            total_used = sum(Decimal(str(i.used_amount)) for i in items)
            total_frozen = sum(Decimal(str(i.frozen_amount)) for i in items)

            # 滚动预测：基于最近3个月核销金额计算月均使用量
            try:
                month_num = int(period.split("-")[-1].replace("Q", ""))
                months_elapsed = month_num * 3
            except (ValueError, IndexError):
                months_elapsed = 6  # default to mid-year

            # 查询最近3个月的核销金额
            monthly_avg_used = None
            try:
                budget_ids = [item.budget_id for item in items]
                if budget_ids:
                    stmt_wo = select(func.sum(BudgetWriteOff.write_off_amount)).where(
                        and_(
                            BudgetWriteOff.budget_id.in_(budget_ids),
                        )
                    )
                    wo_result = await db.execute(stmt_wo)
                    total_write_off = wo_result.scalar() or Decimal("0")

                    if total_write_off > 0:
                        monthly_avg_used = (total_write_off / 3).quantize(Decimal("0.01"))
            except Exception as e:
                logger.warning(f"Failed to query write-off data for rolling forecast: {e}")

            remaining_months = 12 - months_elapsed

            if monthly_avg_used is not None and monthly_avg_used > 0 and remaining_months > 0:
                # 滚动预测：已使用 + 月均使用量 * 剩余月数
                current_forecast = (total_used + monthly_avg_used * remaining_months).quantize(Decimal("0.01"))
            elif months_elapsed > 0 and total_used > 0:
                # 回退到简单线性外推
                current_forecast = (total_used * 12 / months_elapsed).quantize(Decimal("0.01"))
            else:
                current_forecast = total_frozen  # fallback to frozen if no usage data

            # 季节性因子调整
            try:
                quarter_num = int(period.split("-")[-1].replace("Q", ""))
                seasonal_weight = SEASONAL_WEIGHTS.get(quarter_num, Decimal("1.0"))
                current_forecast = (current_forecast * seasonal_weight).quantize(Decimal("0.01"))
            except (ValueError, IndexError):
                pass

            # Fix: previous_forecast uses previous period data if available, otherwise annual_amount
            previous_forecast = total_annual  # baseline
            try:
                year_str = period.split("-")[0]
                prev_year = str(int(year_str) - 1)
                prev_period = period.replace(year_str, prev_year)
                stmt_prev = select(GapAnalysis).where(
                    and_(
                        GapAnalysis.center_id == center_id,
                        GapAnalysis.period == prev_period,
                    )
                ).order_by(GapAnalysis.created_at.desc()).limit(1)
                prev_result = await db.execute(stmt_prev)
                prev_analysis = prev_result.scalars().first()
                if prev_analysis:
                    # Reconstruct previous annual_target from gap1_detail
                    prev_detail = {}
                    try:
                        if prev_analysis.gap1_detail:
                            prev_detail = json.loads(prev_analysis.gap1_detail)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    prev_annual = Decimal(str(prev_detail.get("annual_target", total_annual)))
                    # Use previous current_forecast: annual - gap1
                    prev_gap1 = Decimal(str(prev_analysis.gap1))
                    prev_forecast_from_prev = prev_annual - prev_gap1
                    if prev_forecast_from_prev > 0:
                        previous_forecast = prev_forecast_from_prev
            except Exception:
                pass

            gap1 = total_annual - current_forecast
            gap2 = current_forecast - total_used
            gap3 = current_forecast - previous_forecast

            gap1_detail = json.dumps({
                "annual_target": float(total_annual),
                "current_forecast": float(current_forecast),
                "gap": float(gap1),
            }, ensure_ascii=False)
            gap2_detail = json.dumps({
                "current_forecast": float(current_forecast),
                "executed": float(total_used),
                "gap": float(gap2),
            }, ensure_ascii=False)
            gap3_detail = json.dumps({
                "current_forecast": float(current_forecast),
                "previous_forecast": float(previous_forecast),
                "gap": float(gap3),
            }, ensure_ascii=False)

            l1_code = items[0].l1_code if items else "00"

            analysis = GapAnalysis(
                id=f"GA-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                center_id=center_id,
                l1_code=l1_code,
                gap1=gap1.quantize(Decimal("0.01")),
                gap2=gap2.quantize(Decimal("0.01")),
                gap3=gap3.quantize(Decimal("0.01")),
                gap1_detail=gap1_detail,
                gap2_detail=gap2_detail,
                gap3_detail=gap3_detail,
            )
            db.add(analysis)
            await db.flush()

            logger.info(f"3GAP analysis complete for center {center_id}, period {period}")
            return analysis

        except Exception as e:
            logger.error(f"3GAP analysis failed for center {center_id}: {e}")
            raise

    async def classify_3list(
        self,
        gap_analysis: GapAnalysis,
        db: AsyncSession,
    ) -> List[ListAnalysis]:
        """Classify items into 3List based on business semantics.

        必赢清单：战略核心科目（strategic_intent_l1非空）+ 执行率低于80%
        改善清单：非核心科目 + 执行率超100%（超支）
        观察清单：其余项目

        Args:
            gap_analysis: GapAnalysis record from analyze_3gap.
            db: AsyncSession for database operations.

        Returns:
            List of ListAnalysis records with per-item classification.
        """
        try:
            if self.check_data_lock(gap_analysis.period):
                logger.warning(f"Period {gap_analysis.period} data lock date has passed, data should be finalized")

            # Query individual budget items for this center
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == gap_analysis.center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                # Fallback: create a single record from aggregate gap analysis
                gap1 = Decimal(str(gap_analysis.gap1))
                gap2 = Decimal(str(gap_analysis.gap2))
                gap3 = Decimal(str(gap_analysis.gap3))
                abs_gap1, abs_gap2, abs_gap3 = abs(gap1), abs(gap2), abs(gap3)
                max_gap = max(abs_gap1, abs_gap2, abs_gap3)

                if max_gap == Decimal("0"):
                    list_type = "必赢清单"
                    item_name = f"中心{gap_analysis.center_id}-观察"
                    amount = Decimal("0")
                    description = "无显著差距，按计划执行"
                    action_plan = "维持当前执行节奏"
                elif abs_gap1 == max_gap:
                    list_type = "必赢清单"
                    item_name = f"中心{gap_analysis.center_id}-必赢(目标差距)"
                    amount = gap1
                    description = f"目标差距为主: 年度目标与预测差异={gap1}"
                    action_plan = "聚焦执行，确保目标达成"
                elif abs_gap2 == max_gap:
                    list_type = "改善清单"
                    item_name = f"中心{gap_analysis.center_id}-改善(执行差距)"
                    amount = gap2
                    description = f"执行差距为主: 预测与实际差异={gap2}"
                    action_plan = "识别执行风险，制定缓解措施"
                else:
                    list_type = "观察清单"
                    item_name = f"中心{gap_analysis.center_id}-观察(预测变动)"
                    amount = gap3
                    description = f"预测变动为主: 当期与上期预测差异={gap3}"
                    action_plan = "抓住预测改善机会，优化资源配置"

                analysis = ListAnalysis(
                    id=f"LA-{uuid.uuid4().hex[:8].upper()}",
                    period=gap_analysis.period,
                    center_id=gap_analysis.center_id,
                    list_type=list_type,
                    item_name=item_name,
                    l1_code=gap_analysis.l1_code,
                    amount=amount.quantize(Decimal("0.01")),
                    description=description,
                    action_plan=action_plan,
                )
                db.add(analysis)
                await db.flush()
                return [analysis]

            # Per-item classification with business semantics
            analyses: List[ListAnalysis] = []
            for item in items:
                annual = Decimal(str(item.annual_amount))
                used = Decimal(str(item.used_amount))
                frozen = Decimal(str(item.frozen_amount))

                # 计算执行率
                execution_rate = (used / annual * 100) if annual > 0 else Decimal("0")

                # 判断是否战略核心科目
                is_strategic_core = bool(item.strategic_intent_l1)

                # 业务语义分类逻辑
                if is_strategic_core and execution_rate < Decimal("80"):
                    # 必赢清单：战略核心科目 + 执行率低于80%
                    list_type = "必赢清单"
                    item_name = f"{item.budget_name}-必赢"
                    description = f"战略核心科目({item.strategic_intent_l1})执行率{execution_rate:.1f}%低于80%，需重点保障"
                    action_plan = "优先保障资源投入，加强执行监控，确保战略目标达成"
                elif not is_strategic_core and execution_rate > Decimal("100"):
                    # 改善清单：非核心科目 + 执行率超100%（超支）
                    list_type = "改善清单"
                    item_name = f"{item.budget_name}-改善"
                    description = f"非核心科目执行率{execution_rate:.1f}%超100%，存在超支风险"
                    action_plan = "分析超支原因，制定费用管控措施，评估是否需要预算调整"
                else:
                    # 观察清单：其余项目
                    list_type = "观察清单"
                    if is_strategic_core:
                        item_name = f"{item.budget_name}-观察(战略核心)"
                        description = f"战略核心科目({item.strategic_intent_l1})执行率{execution_rate:.1f}%，基本正常"
                    else:
                        item_name = f"{item.budget_name}-观察"
                        description = f"非核心科目执行率{execution_rate:.1f}%，持续关注"
                    action_plan = "维持当前执行节奏，定期检查"

                # 计算金额差异（用于amount字段）
                amount = annual - used if annual > used else used - annual

                analysis = ListAnalysis(
                    id=f"LA-{uuid.uuid4().hex[:8].upper()}",
                    period=gap_analysis.period,
                    center_id=gap_analysis.center_id,
                    list_type=list_type,
                    item_name=item_name,
                    l1_code=item.l1_code,
                    amount=amount.quantize(Decimal("0.01")),
                    description=description,
                    action_plan=action_plan,
                )
                db.add(analysis)
                analyses.append(analysis)

            await db.flush()

            logger.info(f"3List classification complete: {len(analyses)} items for center {gap_analysis.center_id}")
            return analyses

        except Exception as e:
            logger.error(f"3List classification failed: {e}")
            raise

    async def auto_identify_3gap_3list(
        self,
        period: str,
        db: AsyncSession,
        top_n_per_list: int = 5,
    ) -> Dict[str, Any]:
        """v12.0: 全中心自动跑 3GAP+3List

        流程：
        1) 找到所有有预算项目的中心
        2) 对每个中心跑 3GAP 分析
        3) 对每个 3GAP 结果跑 3List 分类
        4) 按 list_type 汇总 Top-N 项目

        Returns:
            {
              "period": "...",
              "centers_processed": int,
              "gap_summary": [...],
              "list_summary": {
                "必赢清单": [...],
                "改善清单": [...],
                "观察清单": [...],
              },
              "auto_generated": True
            }
        """
        try:
            # 1) 取所有有项目的中心
            stmt = select(BudgetItem.center_id).where(
                BudgetItem.status.in_(["已授予", "执行中"])
            ).distinct()
            result = await db.execute(stmt)
            center_ids = [r[0] for r in result.all() if r[0]]

            if not center_ids:
                return {
                    "period": period,
                    "centers_processed": 0,
                    "gap_summary": [],
                    "list_summary": {"必赢清单": [], "改善清单": [], "观察清单": []},
                    "auto_generated": True,
                    "message": "无任何已授予/执行中预算",
                }

            # 2) 每个中心跑 3GAP
            gap_records = []
            for cid in center_ids:
                try:
                    ga = await self.analyze_3gap(cid, period, db)
                    gap_records.append(ga)
                except Exception as e:
                    logger.warning(f"3GAP 跳过中心 {cid}: {e}")

            # 3) 每个 3GAP 跑 3List
            all_lists = {"必赢清单": [], "改善清单": [], "观察清单": []}
            for ga in gap_records:
                try:
                    items = await self.classify_3list(ga, db)
                    for it in items:
                        lst = it.list_type or "观察清单"
                        all_lists.setdefault(lst, []).append({
                            "list_id": it.id,
                            "item_name": it.item_name,
                            "center_id": it.center_id,
                            "l1_code": it.l1_code,
                            "amount": float(it.amount or 0),
                            "description": it.description,
                            "action_plan": it.action_plan,
                            "period": it.period,
                        })
                except Exception as e:
                    logger.warning(f"3List 跳过中心 {ga.center_id}: {e}")

            # 4) 每个 list 按金额降序取 Top-N
            list_summary = {}
            for lst_name, items in all_lists.items():
                items.sort(key=lambda x: abs(x.get("amount", 0)), reverse=True)
                list_summary[lst_name] = items[:top_n_per_list]

            # 5) 3GAP 摘要
            gap_summary = [
                {
                    "gap_id": g.id,
                    "center_id": g.center_id,
                    "l1_code": g.l1_code,
                    "gap1": float(g.gap1 or 0),
                    "gap2": float(g.gap2 or 0),
                    "gap3": float(g.gap3 or 0),
                    "max_gap_dim": (
                        "GAP1-目标差距" if abs(float(g.gap1 or 0)) >= max(abs(float(g.gap2 or 0)), abs(float(g.gap3 or 0))) else
                        "GAP2-执行差距" if abs(float(g.gap2 or 0)) >= abs(float(g.gap3 or 0)) else
                        "GAP3-预测变动"
                    ),
                }
                for g in gap_records
            ]

            steps = [
                {"step": "perceive", "detail": f"发现{len(center_ids)}个中心，跑3GAP+3List批处理"},
                {"step": "reason", "detail": "对每个中心计算3维度差距并按业务语义归类"},
                {"step": "execute", "detail": f"完成{len(gap_records)}个3GAP + {sum(len(v) for v in all_lists.values())}个3List项"},
                {"step": "reflect", "detail": "汇总Top-N清单供季度复盘使用"},
            ]
            await self._record_trace(
                scene_name="3GAP+3List自动批跑",
                input_data={"period": period, "center_count": len(center_ids)},
                steps=steps,
                conclusion=f"完成{len(gap_records)}个中心3GAP分析，{sum(len(v) for v in all_lists.values())}项3List归类",
                rule_ids=["HR-3GAP", "HR-3LIST"],
                confidence=Decimal("90.00"),
                db=db,
            )

            return {
                "period": period,
                "centers_processed": len(gap_records),
                "centers_total": len(center_ids),
                "gap_summary": gap_summary,
                "list_summary": list_summary,
                "auto_generated": True,
                "list_totals": {k: len(v) for k, v in all_lists.items()},
            }
        except Exception as e:
            logger.error(f"auto_identify_3gap_3list 失败: {e}")
            raise

    def get_center_responsibilities(self) -> Dict[str, Any]:
        return {
            "财经中心": {
                "data_domains": ["预算执行率", "费用率", "核销率", "预算偏差"],
                "collection_cycle": "每月5日前",
                "report_types": ["月度快报", "季度汇报"],
            },
            "运营中心": {
                "data_domains": ["项目进度", "里程碑达成", "3GAP分析", "3List分类"],
                "collection_cycle": "每月8日前",
                "report_types": ["经营分析会材料"],
            },
            "人力中心": {
                "data_domains": ["编制执行", "人力成本", "招聘进度", "培训费用"],
                "collection_cycle": "每月10日前",
                "report_types": ["人力成本专项报告"],
            },
        }

    async def collect_center_data(self, center: str, period: str, db: AsyncSession) -> Dict[str, Any]:
        """Collect real data for a center from budget items, expense reports, and alert records.

        Args:
            center: Center name or ID.
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Structured data package for the center.
        """
        responsibilities = self.get_center_responsibilities()
        if center not in responsibilities:
            return {"error": f"未知中心: {center}"}
        resp = responsibilities[center]

        # Query budget items for the center
        stmt_budget = select(BudgetItem).where(
            BudgetItem.center_id == center,
        )
        result_budget = await db.execute(stmt_budget)
        budget_items = result_budget.scalars().all()

        budget_ids = [item.budget_id for item in budget_items]

        # Query expense reports for those budget items
        expense_items = []
        if budget_ids:
            stmt_expense = select(ExpenseReport).where(
                ExpenseReport.budget_id.in_(budget_ids),
            )
            result_expense = await db.execute(stmt_expense)
            expense_items = result_expense.scalars().all()

        # Query alert records for those budget items
        alert_items = []
        if budget_ids:
            stmt_alert = select(AlertRecord).where(
                AlertRecord.budget_id.in_(budget_ids),
            )
            result_alert = await db.execute(stmt_alert)
            alert_items = result_alert.scalars().all()

        # Aggregate budget data
        total_annual = sum(float(item.annual_amount or 0) for item in budget_items)
        total_used = sum(float(item.used_amount or 0) for item in budget_items)
        total_frozen = sum(float(item.frozen_amount or 0) for item in budget_items)
        total_granted = sum(float(item.granted_amount or 0) for item in budget_items)

        # Aggregate expense data
        total_expense_amount = sum(float(exp.amount or 0) for exp in expense_items)
        expense_by_status: Dict[str, int] = {}
        for exp in expense_items:
            status = exp.status or "未知"
            expense_by_status[status] = expense_by_status.get(status, 0) + 1

        # Aggregate alert data
        alert_by_level: Dict[str, int] = {}
        alert_by_status: Dict[str, int] = {}
        for alert in alert_items:
            level = alert.alert_level or "未知"
            status = alert.alert_status or "未知"
            alert_by_level[level] = alert_by_level.get(level, 0) + 1
            alert_by_status[status] = alert_by_status.get(status, 0) + 1

        # Calculate execution rate
        execution_rate = (total_used / total_annual * 100) if total_annual > 0 else 0

        return {
            "center": center,
            "period": period,
            "status": "已采集",
            "domains": resp["data_domains"],
            "collection_deadline": resp["collection_cycle"],
            "budget_summary": {
                "total_items": len(budget_items),
                "total_annual": total_annual,
                "total_used": total_used,
                "total_frozen": total_frozen,
                "total_granted": total_granted,
                "execution_rate": round(execution_rate, 2),
                "by_quadrant": {
                    q: sum(1 for i in budget_items if i.quadrant == q)
                    for q in ["发展", "收缩", "稳定", "探索"]
                },
                "by_category": {
                    "A": sum(1 for i in budget_items if i.budget_category == "A"),
                    "B": sum(1 for i in budget_items if i.budget_category == "B"),
                },
            },
            "expense_summary": {
                "total_count": len(expense_items),
                "total_amount": total_expense_amount,
                "by_status": expense_by_status,
            },
            "alert_summary": {
                "total_count": len(alert_items),
                "by_level": alert_by_level,
                "by_status": alert_by_status,
            },
        }

    async def generate_monthly_report(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> MonthlyReport:
        """Generate monthly report including execution rates, quadrant compliance, alert tracking, 3GAP+3List.

        Args:
            center_id: Center ID.
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            MonthlyReport record.
        """
        try:
            steps = []

            execution_rates = await self.calculate_execution_rates(center_id, period, db)
            steps.append({"step": "execution_rates", "count": len(execution_rates)})

            quadrant_compliance = await self.check_quadrant_compliance(period, db)
            steps.append({"step": "quadrant_compliance", "results": len(quadrant_compliance)})

            quarter_period = period[:4] + "-Q" + str((int(period.split("-")[1]) - 1) // 3 + 1)
            gap_analysis = await self.analyze_3gap(center_id, quarter_period, db)
            steps.append({"step": "3gap_analysis", "id": gap_analysis.id})

            list_analyses = await self.classify_3list(gap_analysis, db)
            steps.append({"step": "3list_classification", "count": len(list_analyses), "types": [la.list_type for la in list_analyses]})

            stmt_alerts = select(AlertClosure).join(
                AlertRecord, AlertClosure.alert_id == AlertRecord.alert_id
            ).where(
                AlertRecord.l1_code.in_(
                    select(BudgetItem.l1_code).where(BudgetItem.center_id == center_id)
                )
            )
            result_alerts = await db.execute(stmt_alerts)
            alert_closures = result_alerts.scalars().all()

            report_content = {
                "period": period,
                "center_id": center_id,
                "execution_rates": [
                    {
                        "l1_code": r.l1_code,
                        "monthly_rate": float(r.monthly_rate) if r.monthly_rate else 0,
                        "cumulative_rate": float(r.cumulative_rate) if r.cumulative_rate else 0,
                        "annual_rate": float(r.annual_rate) if r.annual_rate else 0,
                    }
                    for r in execution_rates
                ],
                "quadrant_compliance": quadrant_compliance,
                "gap_analysis": {
                    "gap1": float(gap_analysis.gap1) if gap_analysis.gap1 else 0,
                    "gap2": float(gap_analysis.gap2) if gap_analysis.gap2 else 0,
                    "gap3": float(gap_analysis.gap3) if gap_analysis.gap3 else 0,
                },
                "list_classification": [
                    {
                        "type": la.list_type,
                        "item_name": la.item_name,
                        "l1_code": la.l1_code,
                        "amount": float(la.amount) if la.amount else 0,
                        "action_plan": la.action_plan,
                    }
                    for la in list_analyses
                ],
                "alert_closure_tracking": {
                    "total_closures": len(alert_closures),
                    "closed": sum(1 for c in alert_closures if c.closure_status == "已闭环"),
                    "pending": sum(1 for c in alert_closures if c.closure_status != "已闭环"),
                },
            }

            report = MonthlyReport(
                id=f"MR-{uuid.uuid4().hex[:8].upper()}",
                period=period,
                report_type="月度快报",
                center_id=center_id,
                content=json.dumps(report_content, ensure_ascii=False, default=str),
                status="编制中",
            )
            db.add(report)
            await db.flush()

            await self._record_trace(
                scene_name="月度报告生成",
                input_data={"center_id": center_id, "period": period},
                steps=steps,
                conclusion=f"Monthly report {report.id} generated for center {center_id}",
                rule_ids=["HR-RPT-001"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Monthly report generated for center {center_id}, period {period}")
            return report

        except Exception as e:
            logger.error(f"Monthly report generation failed for center {center_id}: {e}")
            raise

    async def predict_execution_trend(
        self,
        l1_code: str,
        db: AsyncSession,
        months_ahead: int = 6,
    ) -> Dict[str, Any]:
        """Predict execution trend for next N months using linear regression + moving average.

        Args:
            l1_code: L1 subject code to predict.
            db: AsyncSession for database operations.
            months_ahead: Number of months to predict (default 6).

        Returns:
            Dict with trend prediction, confidence intervals, and historical data.
        """
        try:
            # Query historical execution rates for this L1 code (last 12 months)
            stmt = (
                select(ExecutionRate)
                .where(ExecutionRate.l1_code == l1_code)
                .order_by(ExecutionRate.period.desc())
                .limit(12)
            )
            result = await db.execute(stmt)
            rates = result.scalars().all()

            if len(rates) < 3:
                return {
                    "l1_code": l1_code,
                    "error": "历史数据不足，至少需要3个月数据",
                    "historical_data": [],
                    "prediction": None,
                }

            # Sort by period ascending
            rates_sorted = sorted(rates, key=lambda r: r.period)

            # Extract monthly execution rates
            historical_data = []
            for r in rates_sorted:
                historical_data.append({
                    "period": r.period,
                    "monthly_rate": float(r.monthly_rate or 0),
                    "cumulative_rate": float(r.cumulative_rate or 0),
                    "annual_rate": float(r.annual_rate or 0),
                })

            # Linear regression on monthly rates
            n = len(historical_data)
            x_values = list(range(n))
            y_values = [d["monthly_rate"] for d in historical_data]

            # Calculate slope and intercept
            x_mean = sum(x_values) / n
            y_mean = sum(y_values) / n
            numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
            denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                slope = Decimal("0")
            else:
                slope = Decimal(str(numerator / denominator))

            intercept = Decimal(str(y_mean)) - slope * Decimal(str(x_mean))

            # Predict next N months
            predictions = []
            for i in range(months_ahead):
                x_pred = Decimal(str(n + i))
                y_pred = slope * x_pred + intercept
                predictions.append(float(y_pred.quantize(Decimal("0.01"))))

            # Calculate confidence interval (simple: ±10% of predicted value)
            confidence_intervals = []
            for pred in predictions:
                margin = abs(pred) * 0.1
                confidence_intervals.append({
                    "predicted": pred,
                    "lower": round(pred - margin, 2),
                    "upper": round(pred + margin, 2),
                })

            # Moving average (3-month)
            moving_avg = []
            for i in range(len(y_values)):
                if i < 2:
                    moving_avg.append(y_values[i])
                else:
                    avg = sum(y_values[i-2:i+1]) / 3
                    moving_avg.append(round(avg, 2))

            # Trend classification
            if slope > Decimal("2"):
                trend = "上升"
            elif slope < Decimal("-2"):
                trend = "下降"
            else:
                trend = "平稳"

            # Identify inflection points (where direction changes)
            inflection_points = []
            for i in range(1, len(moving_avg) - 1):
                if (moving_avg[i] > moving_avg[i-1] and moving_avg[i] > moving_avg[i+1]) or \
                   (moving_avg[i] < moving_avg[i-1] and moving_avg[i] < moving_avg[i+1]):
                    inflection_points.append({
                        "period": historical_data[i]["period"],
                        "rate": moving_avg[i],
                        "type": "峰值" if moving_avg[i] > moving_avg[i-1] else "谷值",
                    })

            await self._record_trace(
                scene_name="执行趋势预测",
                input_data={"l1_code": l1_code, "months_ahead": months_ahead},
                steps=[
                    {"step": "load_historical", "count": len(historical_data)},
                    {"step": "linear_regression", "slope": float(slope), "intercept": float(intercept)},
                    {"step": "predict", "months": months_ahead},
                ],
                conclusion=f"Trend prediction for L1 {l1_code}: {trend}",
                rule_ids=["HR-BA-TREND"],
                confidence=Decimal("85.00"),
                db=db,
            )

            logger.info(f"Execution trend prediction complete for L1 {l1_code}, trend={trend}")

            return {
                "l1_code": l1_code,
                "trend": trend,
                "slope": float(slope.quantize(Decimal("0.01"))),
                "historical_data": historical_data,
                "moving_average": moving_avg,
                "predictions": [
                    {"month_offset": i + 1, **confidence_intervals[i]}
                    for i in range(months_ahead)
                ],
                "inflection_points": inflection_points,
            }

        except Exception as e:
            logger.error(f"Execution trend prediction failed for L1 {l1_code}: {e}")
            raise

    async def detect_anomalies(
        self,
        period: str,
        db: AsyncSession,
        z_threshold: float = 2.0,
        iqr_multiplier: float = 1.5,
    ) -> Dict[str, Any]:
        """Detect anomalies in budget execution using Z-score and IQR methods.

        Args:
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.
            z_threshold: Z-score threshold for anomaly detection (default 2.0).
            iqr_multiplier: IQR multiplier for outlier detection (default 1.5).

        Returns:
            Dict with detected anomalies, categorized by type.
        """
        try:
            # Query all execution rates for this period
            stmt = select(ExecutionRate).where(ExecutionRate.period == period)
            result = await db.execute(stmt)
            rates = result.scalars().all()

            if len(rates) < 5:
                return {
                    "period": period,
                    "error": "数据量不足，至少需要5条记录",
                    "anomalies": [],
                }

            # Extract monthly rates
            monthly_rates = [float(r.monthly_rate or 0) for r in rates]

            # Calculate mean and standard deviation
            mean_rate = sum(monthly_rates) / len(monthly_rates)
            variance = sum((x - mean_rate) ** 2 for x in monthly_rates) / len(monthly_rates)
            std_dev = math.sqrt(variance) if variance > 0 else 0.01

            # Sort for IQR calculation
            sorted_rates = sorted(monthly_rates)
            n = len(sorted_rates)
            q1 = sorted_rates[n // 4]
            q3 = sorted_rates[(3 * n) // 4]
            iqr = q3 - q1

            # Detect anomalies
            anomalies = []
            for i, rate in enumerate(rates):
                monthly_rate = float(rate.monthly_rate or 0)
                anomaly_types = []

                # Z-score detection
                if std_dev > 0:
                    z_score = (monthly_rate - mean_rate) / std_dev
                    if abs(z_score) > z_threshold:
                        anomaly_types.append({
                            "type": "Z-score异常",
                            "z_score": round(z_score, 2),
                            "threshold": z_threshold,
                        })

                # IQR detection
                lower_bound = q1 - iqr_multiplier * iqr
                upper_bound = q3 + iqr_multiplier * iqr
                if monthly_rate < lower_bound or monthly_rate > upper_bound:
                    anomaly_types.append({
                        "type": "IQR异常",
                        "value": monthly_rate,
                        "bounds": [round(lower_bound, 2), round(upper_bound, 2)],
                    })

                # Sudden change detection (compare with previous period if available)
                if i > 0:
                    prev_rate = float(rates[i-1].monthly_rate or 0)
                    if prev_rate > 0:
                        change_pct = abs(monthly_rate - prev_rate) / prev_rate * 100
                        if change_pct > 50:
                            anomaly_types.append({
                                "type": "突增突降",
                                "change_pct": round(change_pct, 2),
                                "prev_rate": prev_rate,
                                "curr_rate": monthly_rate,
                            })

                if anomaly_types:
                    anomalies.append({
                        "budget_id": rate.id,
                        "l1_code": rate.l1_code,
                        "l2_code": rate.l2_code,
                        "period": rate.period,
                        "monthly_rate": monthly_rate,
                        "anomaly_types": anomaly_types,
                        "severity": "高" if len(anomaly_types) >= 2 else "中",
                    })

            # Categorize anomalies
            by_type = {}
            for anomaly in anomalies:
                for at in anomaly["anomaly_types"]:
                    type_name = at["type"]
                    if type_name not in by_type:
                        by_type[type_name] = []
                    by_type[type_name].append(anomaly)

            await self._record_trace(
                scene_name="异常检测",
                input_data={"period": period, "z_threshold": z_threshold, "iqr_multiplier": iqr_multiplier},
                steps=[
                    {"step": "load_data", "count": len(rates)},
                    {"step": "z_score_detection", "mean": mean_rate, "std": std_dev},
                    {"step": "iqr_detection", "q1": q1, "q3": q3, "iqr": iqr},
                    {"step": "classify", "anomaly_count": len(anomalies)},
                ],
                conclusion=f"Detected {len(anomalies)} anomalies in period {period}",
                rule_ids=["HR-BA-ANOMALY"],
                confidence=Decimal("80.00"),
                db=db,
            )

            logger.info(f"Anomaly detection complete for period {period}: {len(anomalies)} anomalies found")

            return {
                "period": period,
                "total_records": len(rates),
                "anomaly_count": len(anomalies),
                "anomalies": anomalies,
                "by_type": {k: len(v) for k, v in by_type.items()},
                "statistics": {
                    "mean": round(mean_rate, 2),
                    "std_dev": round(std_dev, 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2),
                },
            }

        except Exception as e:
            logger.error(f"Anomaly detection failed for period {period}: {e}")
            raise

    async def root_cause_analysis(
        self,
        issue_type: str,
        l1_code: Optional[str],
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Perform root cause analysis for over-budget or low-execution issues.

        Args:
            issue_type: Type of issue ("超支" or "低执行率").
            l1_code: Optional L1 code to analyze (if None, analyze all).
            period: Period string (YYYY-MM).
            db: AsyncSession for database operations.

        Returns:
            Dict with root cause breakdown by dimensions (L1/L2/quadrant/strategic intent).
        """
        try:
            # Query budget items
            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            if l1_code:
                stmt = stmt.where(BudgetItem.l1_code == l1_code)

            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "issue_type": issue_type,
                    "l1_code": l1_code,
                    "period": period,
                    "error": "未找到相关预算项目",
                    "root_causes": [],
                }

            # Calculate execution rates
            item_rates = []
            for item in items:
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                item_rates.append({
                    "budget_id": item.budget_id,
                    "budget_name": item.budget_name,
                    "l1_code": item.l1_code,
                    "l2_code": item.l2_code,
                    "quadrant": item.quadrant,
                    "strategic_intent_l1": item.strategic_intent_l1,
                    "annual": annual,
                    "used": used,
                    "rate": rate,
                })

            # Filter problematic items
            if issue_type == "超支":
                problematic = [i for i in item_rates if i["rate"] > 100]
            else:  # 低执行率
                problematic = [i for i in item_rates if i["rate"] < 50]

            if not problematic:
                return {
                    "issue_type": issue_type,
                    "l1_code": l1_code,
                    "period": period,
                    "message": f"未发现{issue_type}问题",
                    "root_causes": [],
                }

            # Root cause breakdown by dimensions
            by_l1 = {}
            by_l2 = {}
            by_quadrant = {}
            by_strategic = {}

            for item in problematic:
                # By L1
                l1 = item["l1_code"]
                if l1 not in by_l1:
                    by_l1[l1] = {"count": 0, "total_deviation": 0}
                by_l1[l1]["count"] += 1
                deviation = abs(item["rate"] - 100) if issue_type == "超支" else abs(item["rate"] - 50)
                by_l1[l1]["total_deviation"] += deviation

                # By L2
                l2 = item["l2_code"] or "未分类"
                if l2 not in by_l2:
                    by_l2[l2] = {"count": 0, "total_deviation": 0}
                by_l2[l2]["count"] += 1
                by_l2[l2]["total_deviation"] += deviation

                # By quadrant
                quadrant = item["quadrant"]
                if quadrant not in by_quadrant:
                    by_quadrant[quadrant] = {"count": 0, "total_deviation": 0}
                by_quadrant[quadrant]["count"] += 1
                by_quadrant[quadrant]["total_deviation"] += deviation

                # By strategic intent
                strategic = item["strategic_intent_l1"] or "非战略核心"
                if strategic not in by_strategic:
                    by_strategic[strategic] = {"count": 0, "total_deviation": 0}
                by_strategic[strategic]["count"] += 1
                by_strategic[strategic]["total_deviation"] += deviation

            # Rank root causes by impact
            root_causes = []

            # Top L1 contributors
            sorted_l1 = sorted(by_l1.items(), key=lambda x: x[1]["total_deviation"], reverse=True)
            for l1, data in sorted_l1[:3]:
                root_causes.append({
                    "dimension": "L1科目",
                    "value": l1,
                    "count": data["count"],
                    "impact": round(data["total_deviation"], 2),
                    "recommendation": f"重点管控L1科目{l1}的预算执行",
                })

            # Top quadrant contributors
            sorted_quadrant = sorted(by_quadrant.items(), key=lambda x: x[1]["total_deviation"], reverse=True)
            for quadrant, data in sorted_quadrant[:2]:
                root_causes.append({
                    "dimension": "象限",
                    "value": quadrant,
                    "count": data["count"],
                    "impact": round(data["total_deviation"], 2),
                    "recommendation": f"评估{quadrant}象限的预算策略是否合理",
                })

            # Top strategic intent contributors
            sorted_strategic = sorted(by_strategic.items(), key=lambda x: x[1]["total_deviation"], reverse=True)
            for strategic, data in sorted_strategic[:2]:
                root_causes.append({
                    "dimension": "战略意图",
                    "value": strategic,
                    "count": data["count"],
                    "impact": round(data["total_deviation"], 2),
                    "recommendation": f"检查{strategic}方向的资源配置和执行进度",
                })

            await self._record_trace(
                scene_name="根因分析",
                input_data={"issue_type": issue_type, "l1_code": l1_code, "period": period},
                steps=[
                    {"step": "load_items", "count": len(items)},
                    {"step": "filter_problematic", "count": len(problematic)},
                    {"step": "breakdown_by_dimension", "dimensions": 4},
                    {"step": "rank_root_causes", "count": len(root_causes)},
                ],
                conclusion=f"Root cause analysis for {issue_type}: {len(root_causes)} root causes identified",
                rule_ids=["HR-BA-RCA"],
                confidence=Decimal("80.00"),
                db=db,
            )

            logger.info(f"Root cause analysis complete for {issue_type}: {len(root_causes)} root causes")

            return {
                "issue_type": issue_type,
                "l1_code": l1_code,
                "period": period,
                "total_items": len(items),
                "problematic_count": len(problematic),
                "root_causes": root_causes,
                "breakdown": {
                    "by_l1": by_l1,
                    "by_l2": by_l2,
                    "by_quadrant": by_quadrant,
                    "by_strategic_intent": by_strategic,
                },
            }

        except Exception as e:
            logger.error(f"Root cause analysis failed: {e}")
            raise

    async def compare_periods(
        self,
        period1: str,
        period2: str,
        l1_code: Optional[str],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Compare execution metrics between two periods (YoY or QoQ).

        Args:
            period1: First period (YYYY-MM or YYYY-QN).
            period2: Second period (YYYY-MM or YYYY-QN).
            l1_code: Optional L1 code to compare (if None, compare all).
            db: AsyncSession for database operations.

        Returns:
            Dict with comparison metrics and variance attribution.
        """
        try:
            # Query execution rates for both periods
            stmt1 = select(ExecutionRate).where(ExecutionRate.period == period1)
            if l1_code:
                stmt1 = stmt1.where(ExecutionRate.l1_code == l1_code)
            result1 = await db.execute(stmt1)
            rates1 = result1.scalars().all()

            stmt2 = select(ExecutionRate).where(ExecutionRate.period == period2)
            if l1_code:
                stmt2 = stmt2.where(ExecutionRate.l1_code == l1_code)
            result2 = await db.execute(stmt2)
            rates2 = result2.scalars().all()

            if not rates1 or not rates2:
                return {
                    "period1": period1,
                    "period2": period2,
                    "error": "其中一个周期无数据",
                    "comparison": None,
                }

            # Aggregate metrics by L1
            def aggregate_by_l1(rates):
                by_l1 = {}
                for r in rates:
                    l1 = r.l1_code
                    if l1 not in by_l1:
                        by_l1[l1] = {
                            "monthly_rates": [],
                            "cumulative_rates": [],
                            "annual_rates": [],
                        }
                    by_l1[l1]["monthly_rates"].append(float(r.monthly_rate or 0))
                    by_l1[l1]["cumulative_rates"].append(float(r.cumulative_rate or 0))
                    by_l1[l1]["annual_rates"].append(float(r.annual_rate or 0))

                # Calculate averages
                for l1, data in by_l1.items():
                    data["avg_monthly"] = round(sum(data["monthly_rates"]) / len(data["monthly_rates"]), 2)
                    data["avg_cumulative"] = round(sum(data["cumulative_rates"]) / len(data["cumulative_rates"]), 2)
                    data["avg_annual"] = round(sum(data["annual_rates"]) / len(data["annual_rates"]), 2)

                return by_l1

            agg1 = aggregate_by_l1(rates1)
            agg2 = aggregate_by_l1(rates2)

            # Compare
            comparison = []
            all_l1_codes = set(agg1.keys()) | set(agg2.keys())

            for l1 in all_l1_codes:
                data1 = agg1.get(l1, {"avg_monthly": 0, "avg_cumulative": 0, "avg_annual": 0})
                data2 = agg2.get(l1, {"avg_monthly": 0, "avg_cumulative": 0, "avg_annual": 0})

                # Calculate variances
                monthly_var = data2["avg_monthly"] - data1["avg_monthly"]
                cumulative_var = data2["avg_cumulative"] - data1["avg_cumulative"]
                annual_var = data2["avg_annual"] - data1["avg_annual"]

                # Determine trend
                if annual_var > 5:
                    trend = "改善"
                elif annual_var < -5:
                    trend = "恶化"
                else:
                    trend = "持平"

                comparison.append({
                    "l1_code": l1,
                    "period1": {
                        "avg_monthly": data1["avg_monthly"],
                        "avg_cumulative": data1["avg_cumulative"],
                        "avg_annual": data1["avg_annual"],
                    },
                    "period2": {
                        "avg_monthly": data2["avg_monthly"],
                        "avg_cumulative": data2["avg_cumulative"],
                        "avg_annual": data2["avg_annual"],
                    },
                    "variance": {
                        "monthly": round(monthly_var, 2),
                        "cumulative": round(cumulative_var, 2),
                        "annual": round(annual_var, 2),
                    },
                    "trend": trend,
                })

            # Sort by annual variance (most significant changes first)
            comparison.sort(key=lambda x: abs(x["variance"]["annual"]), reverse=True)

            # Overall summary
            overall1 = {
                "avg_monthly": round(sum(d["avg_monthly"] for d in agg1.values()) / len(agg1), 2) if agg1 else 0,
                "avg_annual": round(sum(d["avg_annual"] for d in agg1.values()) / len(agg1), 2) if agg1 else 0,
            }
            overall2 = {
                "avg_monthly": round(sum(d["avg_monthly"] for d in agg2.values()) / len(agg2), 2) if agg2 else 0,
                "avg_annual": round(sum(d["avg_annual"] for d in agg2.values()) / len(agg2), 2) if agg2 else 0,
            }

            await self._record_trace(
                scene_name="周期对比分析",
                input_data={"period1": period1, "period2": period2, "l1_code": l1_code},
                steps=[
                    {"step": "load_period1", "count": len(rates1)},
                    {"step": "load_period2", "count": len(rates2)},
                    {"step": "aggregate_by_l1", "l1_count": len(all_l1_codes)},
                    {"step": "calculate_variance", "comparison_count": len(comparison)},
                ],
                conclusion=f"Period comparison complete: {len(comparison)} L1 subjects compared",
                rule_ids=["HR-BA-COMPARE"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Period comparison complete: {period1} vs {period2}")

            return {
                "period1": period1,
                "period2": period2,
                "l1_code": l1_code,
                "overall": {
                    "period1": overall1,
                    "period2": overall2,
                    "variance": {
                        "monthly": round(overall2["avg_monthly"] - overall1["avg_monthly"], 2),
                        "annual": round(overall2["avg_annual"] - overall1["avg_annual"], 2),
                    },
                },
                "comparison": comparison,
            }

        except Exception as e:
            logger.error(f"Period comparison failed: {e}")
            raise
