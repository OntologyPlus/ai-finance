"""v12.1: 阶段 5 — 实时预警 AI 智能引擎

提供 5 大 AI 能力：
1) AI 预警疲劳检测 — 同规则高频推送时识别疲劳，智能降频
2) AI 告警聚类 — 按 budget/center/l1 聚类，识别系统性风险
3) AI 智能升级 — 基于历史解决时长推荐最优升级路径
4) AI 优先级打分 — 多维度综合优先级评分
5) AI 重复去重 — 同 budget+rule 窗口内去重
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import AlertRecord, AlertClosure
from models.budget import BudgetItem


class AlertAIEngine:
    """v12.1 阶段 5：实时预警 AI 智能引擎"""

    engine_name = "alert_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 预警疲劳检测
    # ─────────────────────────────────────────────────────
    async def detect_fatigue(
        self,
        days: int = 7,
        threshold: int = 10,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 预警疲劳检测

        规则：
        - 同 rule_id + 7 天内 > threshold 条 → 疲劳预警
        - 建议降频 / 合并 / 关闭
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = select(AlertRecord).where(AlertRecord.created_at >= cutoff)
            result = await db.execute(stmt)
            records = result.scalars().all()

            # 按 rule_id 聚合
            rule_counter: Counter = Counter()
            rule_samples: Dict[str, List] = defaultdict(list)
            for r in records:
                if r.rule_id:
                    rule_counter[r.rule_id] += 1
                    if len(rule_samples[r.rule_id]) < 3:
                        rule_samples[r.rule_id].append({
                            "alert_id": r.alert_id,
                            "budget_id": r.budget_id,
                            "level": r.alert_level,
                            "created_at": str(r.created_at),
                            "message": r.alert_message,
                        })

            fatigue_rules: List[Dict] = []
            for rule_id, count in rule_counter.most_common():
                if count >= threshold:
                    fatigue_rules.append({
                        "rule_id": rule_id,
                        "alert_count": count,
                        "period_days": days,
                        "avg_per_day": round(count / days, 1),
                        "fatigue_level": "严重" if count >= threshold * 3 else "中度" if count >= threshold * 2 else "轻度",
                        "samples": rule_samples[rule_id],
                        "recommendation": "建议降低触发频率 / 合并相似规则 / 关闭无效规则",
                    })

            return {
                "period_days": days,
                "total_alerts": len(records),
                "fatigue_rule_count": len(fatigue_rules),
                "fatigue_rules": fatigue_rules,
                "recommendation": (
                    f"发现 {len(fatigue_rules)} 个疲劳规则，建议：① 合并相似规则 ② 调整触发阈值 ③ 启用聚合通知"
                    if fatigue_rules else "当前无疲劳规则"
                ),
            }
        except Exception as e:
            logger.error(f"AI 疲劳检测失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 2) AI 告警聚类（系统性风险识别）
    # ─────────────────────────────────────────────────────
    async def cluster_alerts(
        self,
        days: int = 7,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 告警聚类

        按 budget_id 聚类，识别同一项目的高频告警（系统性风险信号）
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = select(AlertRecord).where(AlertRecord.created_at >= cutoff)
            result = await db.execute(stmt)
            records = result.scalars().all()

            # 按 budget_id 聚类
            budget_cluster: Dict[str, List] = defaultdict(list)
            for r in records:
                if r.budget_id:
                    budget_cluster[r.budget_id].append(r)

            clusters: List[Dict] = []
            for budget_id, items in budget_cluster.items():
                if len(items) < 3:
                    continue
                level_counter = Counter(i.alert_level for i in items)
                rules = list(set(i.rule_id for i in items if i.rule_id))
                clusters.append({
                    "budget_id": budget_id,
                    "alert_count": len(items),
                    "level_breakdown": dict(level_counter),
                    "rule_count": len(rules),
                    "rules": rules,
                    "is_systemic": len(items) >= 5 or level_counter.get("红色", 0) >= 2,
                })

            clusters.sort(key=lambda x: -x["alert_count"])
            systemic_count = sum(1 for c in clusters if c["is_systemic"])

            return {
                "period_days": days,
                "total_alerts": len(records),
                "cluster_count": len(clusters),
                "systemic_risk_count": systemic_count,
                "clusters": clusters[:20],
                "recommendation": (
                    f"识别 {systemic_count} 个系统性风险项目（高密度告警），需立即介入"
                    if systemic_count else "未识别系统性风险"
                ),
            }
        except Exception as e:
            logger.error(f"AI 告警聚类失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 3) AI 智能升级（最优升级路径）
    # ─────────────────────────────────────────────────────
    async def smart_escalation(
        self,
        alert_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 智能升级路径

        基于同规则历史告警的平均解决时长，推荐最优升级目标
        """
        try:
            alert = await db.get(AlertRecord, alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")

            # 查同 rule_id 历史告警的解决时长
            stmt = select(AlertRecord).where(
                and_(
                    AlertRecord.rule_id == alert.rule_id,
                    AlertRecord.status.in_(["已处理", "已升级", "已关闭"]),
                )
            )
            result = await db.execute(stmt)
            history = result.scalars().all()

            if history:
                # 计算平均解决时长（小时）
                resolve_hours: List[float] = []
                for h in history:
                    if h.resolved_at and h.created_at:
                        diff = (h.resolved_at - h.created_at).total_seconds() / 3600
                        resolve_hours.append(diff)
                avg_hours = sum(resolve_hours) / len(resolve_hours) if resolve_hours else 24
                max_hours = max(resolve_hours) if resolve_hours else 72
            else:
                avg_hours = 24
                max_hours = 72

            # 升级路径建议
            escalation_chain = []
            if alert.alert_level == "蓝色":
                escalation_chain = [{"level": "黄色", "role": "部门负责人", "sla_hours": 24}]
            elif alert.alert_level == "黄色":
                escalation_chain = [
                    {"level": "橙色", "role": "中心 BP", "sla_hours": 12},
                    {"level": "红色", "role": "中心总经理", "sla_hours": 6},
                ]
            else:  # 红色
                escalation_chain = [
                    {"level": "红色+", "role": "管委会", "sla_hours": 4},
                    {"level": "红色++", "role": "法人财务负责人", "sla_hours": 2},
                ]

            # 智能调整 SLA（基于历史）
            adjusted_chain = []
            for step in escalation_chain:
                adjusted_chain.append({
                    **step,
                    "sla_hours": max(2, round(min(avg_hours / 2, step["sla_hours"]), 1)),
                    "ai_suggested": True,
                })

            return {
                "alert_id": alert_id,
                "rule_id": alert.rule_id,
                "current_level": alert.alert_level,
                "historical_avg_hours": round(avg_hours, 1),
                "historical_max_hours": round(max_hours, 1),
                "historical_resolved_count": len(history),
                "escalation_chain": adjusted_chain,
                "recommendation": f"建议按 {len(adjusted_chain)} 级升级，首级 SLA {adjusted_chain[0]['sla_hours']}h（基于历史均值 {avg_hours:.1f}h）",
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"AI 智能升级失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 4) AI 优先级打分
    # ─────────────────────────────────────────────────────
    async def priority_score(
        self,
        alert_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 告警优先级智能打分（5 维加权）"""
        try:
            alert = await db.get(AlertRecord, alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")

            # 维度 1: 告警级别（30%）
            level_score = {"红色": 100, "橙色": 75, "黄色": 50, "蓝色": 25}.get(alert.alert_level, 50)

            # 维度 2: 金额影响（25%）
            impact_score = 50
            try:
                if alert.budget_id:
                    item = await db.get(BudgetItem, alert.budget_id)
                    if item:
                        annual = float(item.annual_amount or 0)
                        used = float(item.used_amount or 0)
                        rate = (used / annual * 100) if annual > 0 else 0
                        if rate > 100:
                            impact_score = min(100, 80 + (rate - 100))
                        elif rate < 50:
                            impact_score = max(0, 30 - (50 - rate))
                        else:
                            impact_score = 60
            except Exception:
                pass

            # 维度 3: 战略对齐（20%）
            strategic_score = 70
            try:
                if alert.budget_id:
                    item = await db.get(BudgetItem, alert.budget_id)
                    if item and item.strategic_intent_l1:
                        strategic_score = 100 if item.quadrant == "发展" else 80
            except Exception:
                pass

            # 维度 4: 频率（15%）
            freq_score = 50
            try:
                seven_days_ago = datetime.now() - timedelta(days=7)
                stmt = select(func.count(AlertRecord.alert_id)).where(
                    and_(
                        AlertRecord.budget_id == alert.budget_id,
                        AlertRecord.created_at >= seven_days_ago,
                    )
                )
                result = await db.execute(stmt)
                freq = result.scalar() or 0
                freq_score = min(100, 30 + freq * 10)
            except Exception:
                pass

            # 维度 5: 紧急度（10%）
            urgency_score = 50
            try:
                if alert.created_at:
                    age_hours = (datetime.now() - alert.created_at).total_seconds() / 3600
                    if age_hours > 48:
                        urgency_score = 100
                    elif age_hours > 24:
                        urgency_score = 75
                    elif age_hours > 6:
                        urgency_score = 50
                    else:
                        urgency_score = 25
            except Exception:
                pass

            total = round(
                level_score * 0.30 +
                impact_score * 0.25 +
                strategic_score * 0.20 +
                freq_score * 0.15 +
                urgency_score * 0.10,
                1,
            )

            if total >= 80:
                priority = "P0 立即处理"
            elif total >= 60:
                priority = "P1 4 小时内"
            elif total >= 40:
                priority = "P2 24 小时内"
            else:
                priority = "P3 72 小时内"

            return {
                "alert_id": alert_id,
                "priority_score": total,
                "priority": priority,
                "dimensions": {
                    "告警级别": level_score,
                    "金额影响": round(impact_score, 1),
                    "战略对齐": strategic_score,
                    "频率": round(freq_score, 1),
                    "紧急度": round(urgency_score, 1),
                },
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"AI 优先级打分失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 5) AI 重复去重
    # ─────────────────────────────────────────────────────
    async def dedup(
        self,
        window_hours: int = 24,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 重复告警去重（同 budget+rule 窗口内）"""
        try:
            cutoff = datetime.now() - timedelta(hours=window_hours)
            stmt = select(AlertRecord).where(AlertRecord.created_at >= cutoff)
            result = await db.execute(stmt)
            records = result.scalars().all()

            # 按 (budget_id, rule_id) 分组
            groups: Dict[tuple, List] = defaultdict(list)
            for r in records:
                key = (r.budget_id, r.rule_id)
                groups[key].append(r)

            dup_groups: List[Dict] = []
            total_dup = 0
            for (budget_id, rule_id), items in groups.items():
                if len(items) > 1:
                    total_dup += len(items) - 1
                    dup_groups.append({
                        "budget_id": budget_id,
                        "rule_id": rule_id,
                        "count": len(items),
                        "dup_count": len(items) - 1,
                        "keep_alert_id": max(items, key=lambda x: x.created_at).alert_id,
                        "dup_alert_ids": [i.alert_id for i in sorted(items, key=lambda x: x.created_at)[:-1]],
                    })

            return {
                "window_hours": window_hours,
                "total_alerts": len(records),
                "dedup_groups": len(dup_groups),
                "deduplicated_count": total_dup,
                "groups": dup_groups,
                "recommendation": f"可去重 {total_dup} 条告警，保留每组最新一条",
            }
        except Exception as e:
            logger.error(f"AI 重复去重失败: {e}")
            raise
