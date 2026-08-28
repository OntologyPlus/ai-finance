"""
决策沙盘引擎 — v8.0 Module I-A
按 `经营分析方法论.md` §4.4 治理流程深化：
执行前模拟 + 5 域影响预测 + 可逆性评估 + 置信度计算

支持的模拟操作：
- budget_change: 预算变更（增/减/调拨）
- expense_overrun: 费用超支
- strategic_shift: 战略方向调整
- approval_decision: 审批决策（批准/驳回）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.impact_assessment import (
    DecisionSandbox, ImpactChain, ImpactNode,
)
from models.budget import BudgetItem
from models.expense import ExpenseReport
from models.strategic import StrategicInitiative
from engines.impact_assessment_engine import ImpactAssessmentEngine


# ─── 操作类型与域影响系数 ─────────────────────────────

_OPERATION_DOMAINS = {
    "budget_change": ["budget", "expense", "alert", "cashflow", "strategic"],
    "expense_overrun": ["expense", "budget", "alert", "cashflow"],
    "strategic_shift": ["strategic", "budget", "alert", "cashflow"],
    "approval_decision": ["approval", "expense", "budget"],
}

# 风险等级权重
_RISK_WEIGHT = {"低": 1, "中": 2, "高": 3}

# 不可逆操作类型
_IRREVERSIBLE_OPS = {"strategic_shift"}


class DecisionSandboxEngine:
    """决策沙盘：执行前模拟影响并提供决策支持"""

    def __init__(self):
        self.impact_engine = ImpactAssessmentEngine()

    async def simulate(
        self,
        scenario_name: str,
        operation_type: str,
        operation_params: Dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """模拟一次决策操作的影响"""
        if operation_type not in _OPERATION_DOMAINS:
            raise ValueError(
                f"Unsupported operation_type: {operation_type}. "
                f"Supported: {list(_OPERATION_DOMAINS.keys())}"
            )

        logger.info(
            f"[Sandbox] 模拟场景: {scenario_name}, op={operation_type}, "
            f"params={operation_params}"
        )

        # 1. 5 域影响预测
        prediction = await self._predict_5_domain_impact(
            operation_type, operation_params, db
        )

        # 2. 计算总体风险
        overall_risk = self._aggregate_risk(prediction)

        # 3. 可逆性评估
        reversibility = self._assess_reversibility(operation_type, operation_params)

        # 4. 预测置信度
        confidence = self._calculate_confidence(operation_type, prediction, db)

        # 5. 风险与建议
        recommendations = self._generate_recommendations(
            operation_type, prediction, overall_risk, reversibility
        )

        # 6. 存储
        sandbox_id = None
        if db:
            sb = DecisionSandbox(
                scenario_name=scenario_name,
                operation_type=operation_type,
                operation_params=operation_params,
                prediction=prediction,
                overall_risk=overall_risk,
                reversibility=reversibility,
                confidence=confidence,
                status="已模拟",
            )
            db.add(sb)
            await db.flush()
            sandbox_id = sb.id

        return {
            "sandbox_id": sandbox_id,
            "scenario_name": scenario_name,
            "operation_type": operation_type,
            "operation_params": operation_params,
            "prediction": prediction,
            "overall_risk": overall_risk,
            "reversibility": reversibility,
            "confidence": confidence,
            "recommendations": recommendations,
            "simulated_at": datetime.utcnow().isoformat(),
        }

    async def _predict_5_domain_impact(
        self,
        operation_type: str,
        params: Dict[str, Any],
        db: Optional[AsyncSession],
    ) -> Dict[str, Any]:
        """5 域影响预测"""
        domains = _OPERATION_DOMAINS[operation_type]
        prediction = {"domains": {}, "affected_count": 0, "high_risk_count": 0}

        if operation_type == "budget_change":
            for domain in domains:
                prediction["domains"][domain] = await self._predict_budget_domain(
                    domain, params, db
                )
        elif operation_type == "expense_overrun":
            for domain in domains:
                prediction["domains"][domain] = self._predict_expense_domain(
                    domain, params
                )
        elif operation_type == "strategic_shift":
            for domain in domains:
                prediction["domains"][domain] = self._predict_strategic_domain(
                    domain, params
                )
        elif operation_type == "approval_decision":
            for domain in domains:
                prediction["domains"][domain] = self._predict_approval_domain(
                    domain, params
                )

        # 统计
        prediction["affected_count"] = len(prediction["domains"])
        prediction["high_risk_count"] = sum(
            1 for d in prediction["domains"].values()
            if d["severity"] == "高"
        )
        return prediction

    async def _predict_budget_domain(
        self, domain: str, params: Dict[str, Any], db: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """预算变更对各域的预测"""
        amount = float(params.get("amount", 0))
        change_type = params.get("change_type", "decrease")
        budget_id = params.get("budget_id")

        # 查询实际预算项
        budget_item = None
        if db and budget_id:
            try:
                stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
                result = await db.execute(stmt)
                budget_item = result.scalar_one_or_none()
            except Exception:
                pass

        if domain == "budget":
            if budget_item:
                available = float(budget_item.available_amount or 0)
                annual = float(budget_item.annual_amount or 0)
                if change_type == "decrease":
                    ratio = amount / annual if annual > 0 else 0
                    if ratio > 0.3:
                        return {
                            "severity": "高",
                            "description": f"预算减少{ratio*100:.0f}%，将显著影响执行",
                            "magnitude": -amount,
                            "metrics": {
                                "before": annual,
                                "after": annual - amount,
                                "available_before": available,
                                "available_after": available - amount,
                            },
                        }
                    elif ratio > 0.1:
                        return {
                            "severity": "中",
                            "description": f"预算减少{ratio*100:.0f}%，需要关注执行",
                            "magnitude": -amount,
                            "metrics": {
                                "before": annual, "after": annual - amount,
                            },
                        }
                else:  # increase
                    return {
                        "severity": "低",
                        "description": f"预算增加{amount}元",
                        "magnitude": amount,
                        "metrics": {"before": annual, "after": annual + amount},
                    }
            return {
                "severity": "中",
                "description": f"预算{change_type}{amount}元（无具体预算项数据）",
                "magnitude": -amount if change_type == "decrease" else amount,
            }

        elif domain == "expense":
            if change_type == "decrease" and amount > 100000:
                return {
                    "severity": "中",
                    "description": "预算减少可能影响费用审批通过率",
                    "magnitude": -amount * 0.1,  # 估算影响 10% 费用
                }
            return {
                "severity": "低",
                "description": "对费用执行影响较小",
            }

        elif domain == "alert":
            if change_type == "decrease":
                return {
                    "severity": "中",
                    "description": "预算减少将推高执行率，可能触发黄色/橙色预警",
                    "triggered_alerts": ["执行率超标"],
                }
            return {"severity": "低", "description": "对预警阈值影响有限"}

        elif domain == "cashflow":
            if change_type == "decrease" and amount > 1000000:
                return {
                    "severity": "中",
                    "description": f"大额预算减少{amount}元，可能影响现金流计划",
                    "magnitude": -amount,
                }
            return {"severity": "低", "description": "对现金流影响较小"}

        elif domain == "strategic":
            if change_type == "decrease" and amount > 5000000:
                return {
                    "severity": "高",
                    "description": "大额预算减少可能影响战略举措覆盖率",
                    "mitigation": "建议评估战略对齐度",
                }
            return {"severity": "低", "description": "对战略执行影响较小"}

        return {"severity": "低", "description": "无显著影响"}

    def _predict_expense_domain(
        self, domain: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """费用超支对各域的预测"""
        overrun = float(params.get("overrun_amount", 0))
        if domain == "expense":
            if overrun > 100000:
                return {
                    "severity": "高",
                    "description": f"大额超支{overrun}元，需立即关注",
                    "magnitude": overrun,
                }
            elif overrun > 10000:
                return {"severity": "中", "description": f"中等超支{overrun}元"}
            return {"severity": "低", "description": f"小额超支{overrun}元"}
        elif domain == "budget":
            return {
                "severity": "中" if overrun > 50000 else "低",
                "description": f"超支将占用预算额度{overrun}元",
            }
        elif domain == "alert":
            return {
                "severity": "中",
                "description": "超支将触发执行率预警",
                "triggered_alerts": ["执行率超标", "费用异常"],
            }
        elif domain == "cashflow":
            return {
                "severity": "中" if overrun > 100000 else "低",
                "description": f"超支对现金流的短期影响约{overrun}元",
            }
        return {"severity": "低", "description": "无显著影响"}

    def _predict_strategic_domain(
        self, domain: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """战略方向调整对各域的预测"""
        new_direction = params.get("new_direction", "")
        if domain == "strategic":
            return {
                "severity": "高",
                "description": f"战略方向调整为「{new_direction}」，影响范围广",
                "warning": "战略调整需经管委会批准",
            }
        elif domain == "budget":
            return {
                "severity": "中",
                "description": "战略调整可能需要重新分配预算",
                "magnitude": "需重新评估",
            }
        elif domain == "alert":
            return {
                "severity": "中",
                "description": "战略调整可能引发预算/进度预警",
            }
        elif domain == "cashflow":
            return {
                "severity": "中",
                "description": "战略调整对现金流的影响需重新评估",
            }
        return {"severity": "低", "description": "影响有限"}

    def _predict_approval_domain(
        self, domain: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """审批决策对各域的预测"""
        decision = params.get("decision", "approve")
        amount = float(params.get("amount", 0))
        if domain == "approval":
            if decision == "reject":
                return {
                    "severity": "低",
                    "description": "驳回决策，流程终结",
                }
            return {
                "severity": "中" if amount > 100000 else "低",
                "description": f"批准金额{amount}元",
            }
        elif domain == "expense":
            return {
                "severity": "低",
                "description": f"审批后费用将执行{amount}元",
            }
        elif domain == "budget":
            return {
                "severity": "低" if amount < 50000 else "中",
                "description": f"将占用预算{amount}元",
            }
        return {"severity": "低", "description": "影响有限"}

    def _aggregate_risk(self, prediction: Dict[str, Any]) -> str:
        """聚合总体风险"""
        severities = [
            d.get("severity", "低") for d in prediction["domains"].values()
        ]
        if "高" in severities:
            high_count = severities.count("高")
            return "高" if high_count >= 2 else "中"
        if "中" in severities:
            return "中"
        return "低"

    def _assess_reversibility(
        self, operation_type: str, params: Dict[str, Any]
    ) -> str:
        """评估可逆性"""
        if operation_type in _IRREVERSIBLE_OPS:
            return "不可逆"
        if operation_type == "approval_decision":
            return "部分可逆"
        # 预算变更、费用超支：可逆（可通过反向操作）
        return "可逆"

    def _calculate_confidence(
        self,
        operation_type: str,
        prediction: Dict[str, Any],
        db: Optional[AsyncSession],
    ) -> float:
        """预测置信度（基于历史数据完备度）"""
        base_confidence = {
            "budget_change": 0.85,
            "expense_overrun": 0.75,
            "strategic_shift": 0.55,  # 战略调整难量化
            "approval_decision": 0.90,
        }
        conf = base_confidence.get(operation_type, 0.6)
        # 有 db 连接 + 域影响完整 = 高置信度
        if db and prediction["affected_count"] >= 4:
            conf += 0.1
        # 数据不足降低置信度
        if prediction["affected_count"] < 3:
            conf -= 0.15
        return round(max(0.0, min(1.0, conf)), 2)

    def _generate_recommendations(
        self,
        operation_type: str,
        prediction: Dict[str, Any],
        overall_risk: str,
        reversibility: str,
    ) -> List[str]:
        """生成决策建议"""
        recs: List[str] = []
        if overall_risk == "高":
            recs.append("⚠️ 高风险操作，建议先制定缓解方案再执行")
            recs.append("建议召开专项评审会议")
        elif overall_risk == "中":
            recs.append("中等风险，建议在监控下执行")
        else:
            recs.append("✅ 低风险操作，可正常执行")

        if reversibility == "不可逆":
            recs.append("🔒 不可逆操作，请确保决策审慎")
        elif reversibility == "部分可逆":
            recs.append("部分可逆，需准备回退方案")

        if prediction["high_risk_count"] >= 2:
            recs.append("多个高影响域，建议拆分执行或暂缓")

        # 操作类型专属建议
        if operation_type == "budget_change":
            if "alert" in prediction["domains"] and \
                    prediction["domains"]["alert"]["severity"] in ("中", "高"):
                recs.append("建议同步通知预警责任人")
        elif operation_type == "strategic_shift":
            recs.append("建议同步更新战略 OKR 和预算计划")
        elif operation_type == "approval_decision":
            recs.append("建议记录决策理由，便于后续追溯")
        return recs

    # ═══════════════════════════════════════════════════════════
    # 对比多个沙盘场景
    # ═══════════════════════════════════════════════════════════

    async def compare_scenarios(
        self,
        scenarios: List[Dict[str, Any]],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """对比多个场景的预测结果"""
        results = []
        for s in scenarios:
            sim = await self.simulate(
                scenario_name=s.get("name", "未命名场景"),
                operation_type=s["operation_type"],
                operation_params=s.get("params", {}),
                db=db,
            )
            results.append(sim)

        # 排序：风险低 → 高
        results_sorted = sorted(
            results, key=lambda x: _RISK_WEIGHT.get(x["overall_risk"], 0)
        )

        return {
            "scenarios": results_sorted,
            "best_scenario": results_sorted[0]["scenario_name"] if results_sorted else None,
            "comparison": [
                {
                    "name": r["scenario_name"],
                    "risk": r["overall_risk"],
                    "reversibility": r["reversibility"],
                    "confidence": r["confidence"],
                }
                for r in results_sorted
            ],
        }

    # ═══════════════════════════════════════════════════════════
    # 沙盘持久化与回放
    # ═══════════════════════════════════════════════════════════

    async def list_sandboxes(
        self, db: AsyncSession, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """列出历史沙盘场景"""
        stmt = select(DecisionSandbox).order_by(
            DecisionSandbox.created_at.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        sbs = result.scalars().all()
        return [
            {
                "id": sb.id,
                "scenario_name": sb.scenario_name,
                "operation_type": sb.operation_type,
                "overall_risk": sb.overall_risk,
                "reversibility": sb.reversibility,
                "confidence": sb.confidence,
                "status": sb.status,
                "created_at": sb.created_at.isoformat() if sb.created_at else None,
            }
            for sb in sbs
        ]

    async def get_sandbox(
        self, sandbox_id: int, db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """获取沙盘详情"""
        stmt = select(DecisionSandbox).where(DecisionSandbox.id == sandbox_id)
        result = await db.execute(stmt)
        sb = result.scalar_one_or_none()
        if not sb:
            return None
        return {
            "id": sb.id,
            "scenario_name": sb.scenario_name,
            "operation_type": sb.operation_type,
            "operation_params": sb.operation_params,
            "prediction": sb.prediction,
            "overall_risk": sb.overall_risk,
            "reversibility": sb.reversibility,
            "confidence": sb.confidence,
            "pareto_score": sb.pareto_score,
            "status": sb.status,
            "created_at": sb.created_at.isoformat() if sb.created_at else None,
        }
