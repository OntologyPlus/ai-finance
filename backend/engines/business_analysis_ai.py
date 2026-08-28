"""v12.1: 阶段 4 — 经营分析 AI 智能引擎

提供 5 大 AI 能力：
1) AI 根因下钻 — 在 root_cause_analysis 基础上做跨维度归因与影响度量
2) AI 智能归因 — 偏差自动归因到 L1/L2/L3/象限/战略意图/中心
3) AI 叙事生成 — 自动生成经营分析叙事报告（执行摘要 + 关键发现 + 建议）
4) AI 健康度预测 — 基于多维指标的预测性健康分（0-100）
5) AI 智能建议 — 基于规则+模式+历史数据生成可执行建议
"""
from __future__ import annotations

import json
import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport
from models.budget import BudgetItem
from models.alert import AlertRecord
from models.expense import ExpenseReport


class BusinessAnalysisAIEngine:
    """v12.1 阶段 4：经营分析 AI 智能引擎"""

    engine_name = "business_analysis_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 根因下钻（跨维度归因 + 影响度量）
    # ─────────────────────────────────────────────────────
    async def root_cause_drilldown(
        self,
        issue_type: str,        # "超支" / "低执行率" / "执行偏差"
        period: str,             # YYYY-MM
        l1_code: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: AI 根因下钻（v12.0 root_cause_analysis 升级版）

        在 4 维度下钻基础上增加：
        - 中心贡献度
        - 战略意图贡献度
        - 跨维度组合归因（如"发展象限+创新研发"是根因）
        - 异常事件关联（最近 30 天是否有相关告警/超支）
        - AI 修复建议（按优先级排序）

        Returns:
            {
                "issue_type": "...",
                "period": "...",
                "problematic_count": N,
                "total_impact_amount": ¥X,
                "dimension_contributions": {
                    "by_l1": [...],
                    "by_l2": [...],
                    "by_quadrant": [...],
                    "by_strategic_intent": [...],
                    "by_center": [...],
                },
                "cross_dimensional_patterns": [{...}],
                "recent_events": [...],
                "root_causes": [按impact排序的根因清单],
                "recommendations": [AI 建议],
            }
        """
        try:
            # 1) 拉取问题项目
            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            if l1_code:
                stmt = stmt.where(BudgetItem.l1_code == l1_code)
            result = await db.execute(stmt)
            items = result.scalars().all()

            # 2) 计算执行率
            problematic = []
            total_impact = 0.0
            for item in items:
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                if issue_type == "超支" and rate > 100:
                    deviation = used - annual
                    problematic.append({**item.__dict__, "rate": rate, "deviation": deviation})
                    total_impact += deviation
                elif issue_type == "低执行率" and rate < 50:
                    deviation = annual - used
                    problematic.append({**item.__dict__, "rate": rate, "deviation": deviation})
                    total_impact += deviation
                elif issue_type == "执行偏差" and abs(rate - 80) > 20:
                    deviation = abs(used - annual * 0.8)
                    problematic.append({**item.__dict__, "rate": rate, "deviation": deviation})
                    total_impact += deviation

            if not problematic:
                return {
                    "issue_type": issue_type,
                    "period": period,
                    "l1_code": l1_code,
                    "problematic_count": 0,
                    "total_impact_amount": 0,
                    "dimension_contributions": {},
                    "cross_dimensional_patterns": [],
                    "recent_events": [],
                    "root_causes": [],
                    "recommendations": [f"未发现{issue_type}问题，预算执行良好"],
                }

            # 3) 多维度贡献度计算
            def aggregate_by(field: str, label: str) -> List[Dict]:
                bucket: Dict[str, Dict] = {}
                for it in problematic:
                    key = getattr(it, field, None) or "未分类"
                    if key not in bucket:
                        bucket[key] = {"count": 0, "deviation": 0.0, "amount": 0.0}
                    bucket[key]["count"] += 1
                    bucket[key]["deviation"] += it["deviation"]
                    bucket[key]["amount"] += float(getattr(it, "annual_amount", 0) or 0)
                result = []
                for k, v in bucket.items():
                    result.append({
                        "value": k,
                        "dimension": label,
                        "count": v["count"],
                        "total_deviation": round(v["deviation"], 2),
                        "total_amount": round(v["amount"], 2),
                        "contribution_pct": round(v["deviation"] / total_impact * 100, 1) if total_impact > 0 else 0,
                    })
                result.sort(key=lambda x: -x["total_deviation"])
                return result

            by_l1 = aggregate_by("l1_code", "L1科目")
            by_l2 = aggregate_by("l2_code", "L2科目")
            by_quadrant = aggregate_by("quadrant", "象限")
            by_strategic = aggregate_by("strategic_intent_l1", "战略意图")
            by_center = aggregate_by("center_id", "中心")

            # 4) 跨维度组合模式（双维度叠加）
            cross_patterns: List[Dict] = []
            cross_keys = Counter()
            for it in problematic:
                key = f"{getattr(it, 'quadrant', 'N/A')}|{getattr(it, 'strategic_intent_l1', 'N/A')}"
                cross_keys[key] += 1
                cross_keys[f"{getattr(it, 'l1_code', 'N/A')}|{getattr(it, 'quadrant', 'N/A')}"] += 1
            for key, cnt in cross_keys.most_common(5):
                if cnt >= 2:
                    parts = key.split("|")
                    cross_patterns.append({
                        "pattern": " × ".join(parts),
                        "count": cnt,
                        "type": "跨维度聚集",
                    })

            # 5) 近期事件关联（最近 30 天告警/超支）
            recent_events: List[Dict] = []
            try:
                problem_budget_ids = [it["budget_id"] for it in problematic]
                thirty_days_ago = datetime.now() - timedelta(days=30)
                stmt_alert = select(AlertRecord).where(
                    and_(
                        AlertRecord.budget_id.in_(problem_budget_ids),
                        AlertRecord.created_at >= thirty_days_ago,
                    )
                )
                result_alert = await db.execute(stmt_alert)
                for a in result_alert.scalars().all():
                    recent_events.append({
                        "type": "预警",
                        "alert_id": a.alert_id,
                        "budget_id": a.budget_id,
                        "level": a.alert_level,
                        "message": a.alert_message,
                        "created_at": str(a.created_at),
                    })
            except Exception as e:
                logger.warning(f"近期事件关联失败: {e}")

            # 6) AI 根因清单（按 impact 排序，前 5）
            root_causes: List[Dict] = []
            for item in by_l1[:2]:
                root_causes.append({
                    "type": "L1科目贡献最大",
                    "value": item["value"],
                    "count": item["count"],
                    "impact": item["total_deviation"],
                    "contribution": item["contribution_pct"],
                    "description": f"L1 科目 {item['value']} 贡献了 {item['contribution_pct']}% 的偏差，涉及 {item['count']} 个项目",
                })
            for item in by_quadrant[:1]:
                root_causes.append({
                    "type": "象限异常",
                    "value": item["value"],
                    "count": item["count"],
                    "impact": item["total_deviation"],
                    "contribution": item["contribution_pct"],
                    "description": f"【{item['value']}象限】出现 {item['count']} 个问题项目",
                })
            for item in by_strategic[:1]:
                if item["value"] != "非战略核心":
                    root_causes.append({
                        "type": "战略意图偏离",
                        "value": item["value"],
                        "count": item["count"],
                        "impact": item["total_deviation"],
                        "contribution": item["contribution_pct"],
                        "description": f"战略意图【{item['value']}】方向出现 {item['count']} 个问题项目",
                    })
            for cp in cross_patterns[:2]:
                root_causes.append({
                    "type": "跨维度聚集",
                    "value": cp["pattern"],
                    "count": cp["count"],
                    "description": f"发现聚集模式：{cp['pattern']}（{cp['count']} 个项目）",
                })

            # 7) AI 修复建议
            recommendations: List[str] = []
            if by_quadrant and by_quadrant[0]["value"] == "发展":
                recommendations.append("发展象限超支 → 需追加预算申请或调整发展节奏")
            if by_quadrant and by_quadrant[0]["value"] == "稳定":
                recommendations.append("稳定象限超支 → 排查是否存在违规使用或预算编制偏差")
            if by_l1 and by_l1[0]["contribution_pct"] > 50:
                recommendations.append(f"重点关注 L1【{by_l1[0]['value']}】，单一科目贡献超 50% 偏差")
            if recent_events:
                recommendations.append(f"近 30 天有 {len(recent_events)} 条相关预警，建议优先处理高风险项")
            if issue_type == "低执行率":
                recommendations.append("执行率偏低 → 评估是预算编制过高还是执行能力不足")
            if not recommendations:
                recommendations.append("按维度优先级逐项推进，优先解决贡献度 >30% 的根因")

            return {
                "issue_type": issue_type,
                "period": period,
                "l1_code": l1_code,
                "problematic_count": len(problematic),
                "total_impact_amount": round(total_impact, 2),
                "dimension_contributions": {
                    "by_l1": by_l1[:5],
                    "by_l2": by_l2[:5],
                    "by_quadrant": by_quadrant,
                    "by_strategic_intent": by_strategic,
                    "by_center": by_center[:5],
                },
                "cross_dimensional_patterns": cross_patterns[:5],
                "recent_events": recent_events[:10],
                "root_causes": sorted(root_causes, key=lambda x: -x.get("impact", 0))[:5],
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"AI 根因下钻失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 2) AI 智能归因（偏差自动归因 + 责任主体）
    # ─────────────────────────────────────────────────────
    async def smart_attribution(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 智能归因 — 偏差自动归因到责任主体

        责任归因矩阵：
        - L1 偏差：财务 BP + 业务部门负责人
        - 战略意图偏离：战略管理部 + 业务负责人
        - 象限错位：战略 + 财务共同
        - 季节性偏差：业务部门
        - 单项目超支：项目负责人
        """
        try:
            # 1) 拉预算
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            attributions: List[Dict] = []
            for item in items:
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                if abs(rate - 80) <= 20:
                    continue  # 正常区间跳过

                # 偏差类型
                if rate > 100:
                    bias_type = "超支"
                elif rate < 50:
                    bias_type = "低执行"
                else:
                    bias_type = "执行偏差"

                # 责任主体（规则匹配）
                responsible = []
                confidence = 0
                if abs(rate - 100) > 30 and item.strategic_intent_l1:
                    responsible.append({"role": "战略管理部", "reason": f"战略意图【{item.strategic_intent_l1}】执行严重偏离"})
                    confidence += 30
                if item.l1_code in ["01", "02", "03"]:  # 商业化类
                    responsible.append({"role": "业务部门负责人", "reason": "L1 商业化类预算偏差"})
                    responsible.append({"role": "财务 BP", "reason": "需财务复核"})
                    confidence += 40
                elif item.l1_code in ["04", "05", "06"]:  # 研发类
                    responsible.append({"role": "研发负责人", "reason": "L1 研发类预算偏差"})
                    responsible.append({"role": "项目 PM", "reason": "项目级偏差"})
                    confidence += 40
                if item.quadrant == "发展" and bias_type == "超支":
                    responsible.append({"role": "战略管理部", "reason": "发展象限超支需战略复核"})
                if item.quadrant == "收缩" and bias_type == "低执行":
                    responsible.append({"role": "业务部门负责人", "reason": "收缩象限执行率仍偏低，未达降本目标"})

                if not responsible:
                    responsible.append({"role": "业务部门负责人", "reason": "默认归因"})
                    confidence = 50

                attributions.append({
                    "budget_id": item.budget_id,
                    "budget_name": item.budget_name,
                    "l1_code": item.l1_code,
                    "quadrant": item.quadrant,
                    "strategic_intent_l1": item.strategic_intent_l1,
                    "annual_amount": annual,
                    "used_amount": used,
                    "execution_rate": round(rate, 1),
                    "bias_type": bias_type,
                    "deviation_amount": round(used - annual, 2),
                    "responsible": responsible,
                    "confidence": min(100, confidence),
                })

            # 3) 归因汇总
            role_count: Counter = Counter()
            for a in attributions:
                for r in a["responsible"]:
                    role_count[r["role"]] += 1

            return {
                "center_id": center_id,
                "period": period,
                "scanned_count": len(items),
                "attribution_count": len(attributions),
                "role_summary": [{"role": k, "count": v} for k, v in role_count.most_common()],
                "attributions": attributions,
            }

        except Exception as e:
            logger.error(f"AI 智能归因失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 3) AI 叙事生成（自动经营分析报告）
    # ─────────────────────────────────────────────────────
    async def generate_narrative(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: AI 叙事生成 — 自动经营分析报告

        4 段式：
        1) 执行摘要（1-2 句话）
        2) 关键发现（数据支撑）
        3) 风险提示
        4) 行动建议
        """
        try:
            # 1) 收集数据
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "center_id": center_id,
                    "period": period,
                    "narrative": "无预算项目数据",
                    "key_findings": [],
                    "risks": [],
                    "recommendations": [],
                }

            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            total_frozen = sum(float(i.frozen_amount or 0) for i in items)
            overall_rate = (total_used / total_annual * 100) if total_annual > 0 else 0

            # 2) 象限分布
            quadrant_data = defaultdict(lambda: {"count": 0, "amount": 0, "used": 0})
            for i in items:
                q = i.quadrant or "未分类"
                quadrant_data[q]["count"] += 1
                quadrant_data[q]["amount"] += float(i.annual_amount or 0)
                quadrant_data[q]["used"] += float(i.used_amount or 0)

            # 3) 找出问题项
            issues = []
            for i in items:
                annual = float(i.annual_amount or 0)
                used = float(i.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                if rate > 100:
                    issues.append(f"{i.budget_name}超支{rate - 100:.0f}%（¥{used - annual:.0f}）")
                elif rate < 50:
                    issues.append(f"{i.budget_name}执行率仅{rate:.0f}%（预算¥{annual:.0f}）")

            # 4) 生成 4 段式叙事
            month_num = int(period.split("-")[1]) if "-" in period else 6
            expected_pace = month_num * 100 / 12  # 应执行进度

            if overall_rate > expected_pace + 10:
                pace_desc = "整体执行偏快"
            elif overall_rate < expected_pace - 10:
                pace_desc = "整体执行偏慢"
            else:
                pace_desc = "整体执行节奏良好"

            executive_summary = (
                f"中心 {center_id} 在 {period} 期间整体执行率 {overall_rate:.1f}%，"
                f"已使用 ¥{total_used:,.0f} / 年度预算 ¥{total_annual:,.0f}，{pace_desc}。"
                f"冻结金额 ¥{total_frozen:,.0f}，覆盖 {len(items)} 个预算项目。"
            )

            key_findings = [
                f"📊 整体执行率 {overall_rate:.1f}%，{'高于' if overall_rate > expected_pace else '低于'}预期进度 {abs(overall_rate - expected_pace):.1f}pp",
                f"📈 发展象限共 {quadrant_data.get('发展', {}).get('count', 0)} 个项目，金额 ¥{quadrant_data.get('发展', {}).get('amount', 0):,.0f}",
                f"⚖️ 稳定象限共 {quadrant_data.get('稳定', {}).get('count', 0)} 个项目，金额 ¥{quadrant_data.get('稳定', {}).get('amount', 0):,.0f}",
                f"🔬 探索象限共 {quadrant_data.get('探索', {}).get('count', 0)} 个项目，金额 ¥{quadrant_data.get('探索', {}).get('amount', 0):,.0f}",
            ]
            if quadrant_data.get("收缩", {}).get("count", 0) > 0:
                key_findings.append(f"📉 收缩象限 {quadrant_data['收缩']['count']} 个项目")

            risks = []
            if overall_rate < 40 and month_num >= 6:
                risks.append("⚠️ 中期执行率 < 40%，年末可能存在大量预算沉淀风险")
            if overall_rate > 100:
                risks.append("🚨 整体超支！需紧急召开预算调整评审会")
            overspend_count = sum(1 for i in items if float(i.used_amount or 0) > float(i.annual_amount or 0))
            if overspend_count >= 3:
                risks.append(f"🚨 {overspend_count} 个项目超支，建议系统性排查预算编制问题")

            recommendations = []
            if overall_rate < 60 and month_num >= 9:
                recommendations.append("年末临近，建议梳理 Q4 冲刺清单，重点投入高优先级项目")
            if overall_rate > 100:
                recommendations.append("整体超支 → 启动预算调整流程（调拨/追加/核减）")
            if len(issues) > 0:
                recommendations.append(f"优先处理 {len(issues)} 个问题项目：{'; '.join(issues[:3])}")
            if not recommendations:
                recommendations.append("维持当前执行节奏，定期回顾")

            # 风险等级
            if overall_rate > 100 or overall_rate < 30:
                risk_level = "高"
            elif overall_rate < 50 or overall_rate > 90:
                risk_level = "中"
            else:
                risk_level = "低"

            return {
                "center_id": center_id,
                "period": period,
                "executive_summary": executive_summary,
                "key_findings": key_findings,
                "risks": risks,
                "recommendations": recommendations,
                "risk_level": risk_level,
                "metrics": {
                    "overall_execution_rate": round(overall_rate, 1),
                    "total_annual": round(total_annual, 2),
                    "total_used": round(total_used, 2),
                    "total_frozen": round(total_frozen, 2),
                    "item_count": len(items),
                    "expected_pace": round(expected_pace, 1),
                },
                "quadrant_breakdown": {
                    k: {"count": v["count"], "amount": round(v["amount"], 2)} for k, v in quadrant_data.items()
                },
                "issue_count": len(issues),
            }

        except Exception as e:
            logger.error(f"AI 叙事生成失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 4) AI 健康度预测
    # ─────────────────────────────────────────────────────
    async def predict_health_score(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: AI 健康度预测 — 多维加权健康分

        5 维加权：
        1) 执行率合理性（25%）
        2) 战略对齐度（20%）
        3) 风险预警密度（20%）
        4) 预算调整频率（15%）
        5) 象限合规度（20%）
        """
        try:
            # 1) 拉取数据
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "center_id": center_id,
                    "period": period,
                    "health_score": 0,
                    "health_level": "未知",
                    "dimensions": {},
                    "recommendations": ["无预算项目数据"],
                }

            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            overall_rate = (total_used / total_annual * 100) if total_annual > 0 else 0

            # 维度 1: 执行率合理性
            month_num = int(period.split("-")[1]) if "-" in period else 6
            expected_pace = month_num * 100 / 12
            pace_dev = abs(overall_rate - expected_pace)
            if pace_dev <= 5:
                exec_score = 100
            elif pace_dev <= 15:
                exec_score = 85
            elif pace_dev <= 30:
                exec_score = 60
            else:
                exec_score = 30

            # 维度 2: 战略对齐度（战略核心科目执行率均值）
            strategic_items = [i for i in items if i.strategic_intent_l1]
            if strategic_items:
                strat_rates = []
                for i in strategic_items:
                    annual = float(i.annual_amount or 0)
                    used = float(i.used_amount or 0)
                    strat_rates.append((used / annual * 100) if annual > 0 else 0)
                strat_avg = sum(strat_rates) / len(strat_rates)
                # 越接近 80% 越好（既不超支也不欠执行）
                strat_score = max(0, 100 - abs(strat_avg - 80))
            else:
                strat_score = 50

            # 维度 3: 风险预警密度（近 30 天预警条数 / 项目数）
            try:
                thirty_days_ago = datetime.now() - timedelta(days=30)
                budget_ids = [i.budget_id for i in items]
                stmt_alert = select(func.count(AlertRecord.alert_id)).where(
                    and_(
                        AlertRecord.budget_id.in_(budget_ids),
                        AlertRecord.created_at >= thirty_days_ago,
                    )
                )
                result_alert = await db.execute(stmt_alert)
                alert_count = result_alert.scalar() or 0
                alert_ratio = alert_count / len(items) if items else 0
                if alert_ratio <= 0.2:
                    risk_score = 100
                elif alert_ratio <= 0.5:
                    risk_score = 75
                elif alert_ratio <= 1.0:
                    risk_score = 50
                else:
                    risk_score = 20
            except Exception:
                risk_score = 70

            # 维度 4: 预算调整频率（简化：从预算金额变化中估算）
            # 这里用 frozen/total 比例代替（frozen 比例高表示频繁调整）
            total_frozen = sum(float(i.frozen_amount or 0) for i in items)
            frozen_ratio = total_frozen / total_annual if total_annual > 0 else 0
            if frozen_ratio < 0.1:
                adjust_score = 100
            elif frozen_ratio < 0.3:
                adjust_score = 80
            elif frozen_ratio < 0.5:
                adjust_score = 50
            else:
                adjust_score = 20

            # 维度 5: 象限合规度
            quadrant_target = {"发展": 80, "稳定": 60, "收缩": 40, "探索": 50}
            quadrant_devs = []
            for i in items:
                annual = float(i.annual_amount or 0)
                used = float(i.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                target = quadrant_target.get(i.quadrant, 60)
                quadrant_devs.append(abs(rate - target))
            if quadrant_devs:
                avg_dev = sum(quadrant_devs) / len(quadrant_devs)
                quadrant_score = max(0, 100 - avg_dev)
            else:
                quadrant_score = 60

            # 加权汇总
            health_score = round(
                exec_score * 0.25
                + strat_score * 0.20
                + risk_score * 0.20
                + adjust_score * 0.15
                + quadrant_score * 0.20,
                1,
            )

            # 健康等级
            if health_score >= 85:
                health_level = "优秀"
                emoji = "🟢"
            elif health_score >= 70:
                health_level = "良好"
                emoji = "🔵"
            elif health_score >= 55:
                health_level = "关注"
                emoji = "🟡"
            elif health_score >= 40:
                health_level = "预警"
                emoji = "🟠"
            else:
                health_level = "高危"
                emoji = "🔴"

            # 建议
            recommendations = []
            if exec_score < 60:
                recommendations.append(f"执行率偏离预期 {pace_dev:.0f}pp，需调整执行节奏")
            if strat_score < 60:
                recommendations.append("战略核心科目执行偏离，需加强战略-预算联动")
            if risk_score < 50:
                recommendations.append(f"近 30 天预警 {alert_count} 条，密度偏高")
            if adjust_score < 50:
                recommendations.append(f"预算调整频繁（冻结比例 {frozen_ratio*100:.0f}%），建议复盘预算编制")
            if quadrant_score < 50:
                recommendations.append("象限执行偏差较大，建议复盘象限划分与执行策略")
            if not recommendations:
                recommendations.append("各项指标良好，继续保持")

            return {
                "center_id": center_id,
                "period": period,
                "health_score": health_score,
                "health_level": f"{emoji} {health_level}",
                "dimensions": {
                    "执行率合理性": round(exec_score, 1),
                    "战略对齐度": round(strat_score, 1),
                    "风险预警密度": round(risk_score, 1),
                    "预算调整频率": round(adjust_score, 1),
                    "象限合规度": round(quadrant_score, 1),
                },
                "metrics": {
                    "overall_execution_rate": round(overall_rate, 1),
                    "expected_pace": round(expected_pace, 1),
                    "frozen_ratio": round(frozen_ratio * 100, 1),
                    "alert_count_30d": alert_count,
                    "strategic_items": len(strategic_items),
                },
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"AI 健康度预测失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 5) AI 智能建议（基于规则 + 模式 + 历史）
    # ─────────────────────────────────────────────────────
    async def smart_recommendations(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        """v12.1: AI 智能建议 — 综合根因 + 归因 + 健康度生成行动清单"""
        try:
            root = await self.root_cause_drilldown("执行偏差", period, None, db)
            attr = await self.smart_attribution(center_id, period, db)
            health = await self.predict_health_score(center_id, period, db)

            recommendations: List[Dict] = []
            priority = 0

            # 来源 1: 根因（按 impact 排序）
            for rc in root.get("root_causes", [])[:3]:
                priority += 1
                recommendations.append({
                    "priority": priority,
                    "type": "根因",
                    "title": rc.get("type", ""),
                    "detail": rc.get("description", ""),
                    "value": rc.get("value", ""),
                    "impact": rc.get("impact", 0),
                    "source": "root_cause_drilldown",
                })

            # 来源 2: 归因（按置信度）
            sorted_attr = sorted(attr.get("attributions", []), key=lambda x: -x.get("confidence", 0))
            for a in sorted_attr[:2]:
                priority += 1
                resp = a["responsible"][0]["role"] if a["responsible"] else "业务部门"
                recommendations.append({
                    "priority": priority,
                    "type": "责任归因",
                    "title": f"{a['bias_type']}：{a['budget_name'][:30]}",
                    "detail": f"归因 {resp}（置信度 {a['confidence']}%）",
                    "value": resp,
                    "impact": abs(a["deviation_amount"]),
                    "source": "smart_attribution",
                })

            # 来源 3: 健康度（低分维度）
            for dim_name, dim_score in health.get("dimensions", {}).items():
                if dim_score < 60:
                    priority += 1
                    recommendations.append({
                        "priority": priority,
                        "type": "健康度",
                        "title": f"{dim_name}偏低（{dim_score}）",
                        "detail": f"需关注：{dim_name}",
                        "value": dim_name,
                        "impact": 100 - dim_score,
                        "source": "health_score",
                    })

            # 截取 Top N
            recommendations = recommendations[:top_n]

            return {
                "center_id": center_id,
                "period": period,
                "health_score": health.get("health_score", 0),
                "health_level": health.get("health_level", "未知"),
                "recommendations": recommendations,
                "summary": {
                    "total_recommendations": len(recommendations),
                    "root_cause_count": len(root.get("root_causes", [])),
                    "attribution_count": attr.get("attribution_count", 0),
                    "low_dim_count": sum(1 for v in health.get("dimensions", {}).values() if v < 60),
                },
            }

        except Exception as e:
            logger.error(f"AI 智能建议失败: {e}")
            raise
