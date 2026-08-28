"""v12.1: 阶段 3 — 费用报销 AI 智能引擎

提供 4 大 AI 能力：
1) AI 智能 L3 识别 — 根据 description 关键词 + 金额 + 业务场景自动推荐 L3 科目
2) AI 异常检测 — 拆单 / 重复 / 周末深夜 / 同人高频 / 金额异常 等 5 维异常评分
3) AI 智能路由 — 4 级管控 + 异常分 + 金额阈值 + 历史审批人 智能推荐审批人
4) AI 拒付预警 — 提交前预判拒付概率 + 修复建议
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem, BudgetSubjectL3
from models.expense import ExpenseReport, InvoiceRecord


# ───────────────────────────────────────────────────────────────────────
# L3 关键词映射（业务知识库）
# ───────────────────────────────────────────────────────────────────────
L3_KEYWORD_MAP: Dict[str, Dict[str, Any]] = {
    "差旅": {
        "l3_code": "L3-TRAVEL",
        "l3_name": "差旅费用",
        "control_tag": "强管控",
        "keywords": ["机票", "高铁", "火车", "出租车", "网约车", "滴滴", "酒店", "宾馆", "住宿", "出差", "差旅"],
    },
    "招待": {
        "l3_code": "L3-ENT",
        "l3_name": "业务招待费",
        "control_tag": "强管控",
        "keywords": ["招待", "餐饮", "宴请", "客户餐", "商务餐", "酒水", "茶饮"],
    },
    "市场推广": {
        "l3_code": "L3-MKT",
        "l3_name": "市场推广费",
        "control_tag": "中心弱管控",
        "keywords": ["推广", "广告", "投放", "百度", "抖音", "小红书", "媒体", "营销", "品牌"],
    },
    "办公": {
        "l3_code": "L3-OFF",
        "l3_name": "办公用品费",
        "control_tag": "不管控",
        "keywords": ["办公用品", "文具", "打印", "复印纸", "墨盒", "硒鼓", "文件夹"],
    },
    "研发": {
        "l3_code": "L3-RND",
        "l3_name": "研发费用",
        "control_tag": "组合管控",
        "keywords": ["研发", "实验", "试剂", "耗材", "样本", "检测", "临床", "试验", "软件采购", "SaaS"],
    },
    "会议": {
        "l3_code": "L3-MTG",
        "l3_name": "会议费",
        "control_tag": "中心弱管控",
        "keywords": ["会议", "论坛", "峰会", "研讨会", "培训", "场地", "会务"],
    },
    "通讯": {
        "l3_code": "L3-COM",
        "l3_name": "通讯费用",
        "control_tag": "不管控",
        "keywords": ["电话费", "通讯", "宽带", "网络费", "5G", "流量"],
    },
    "国际": {
        "l3_code": "L3-INTL",
        "l3_name": "国际业务费",
        "control_tag": "组合管控",
        "keywords": ["国际", "海外", "出境", "签证", "护照", "外汇", "BD", "License"],
    },
    "物流": {
        "l3_code": "L3-LOG",
        "l3_name": "物流运输费",
        "control_tag": "中心弱管控",
        "keywords": ["快递", "物流", "运输", "运费", "顺丰", "京东物流", "邮政"],
    },
    "招聘": {
        "l3_code": "L3-REC",
        "l3_name": "招聘费用",
        "control_tag": "不管控",
        "keywords": ["招聘", "猎头", "面试", "背调", "招聘会"],
    },
}


class ExpenseAIEngine:
    """v12.1 阶段 3：费用报销 AI 智能引擎"""

    engine_name = "expense_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 智能 L3 识别
    # ─────────────────────────────────────────────────────
    async def recognize_l3(
        self,
        description: str,
        amount: float,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 智能识别 L3 科目（关键词 + 金额双维度）

        Args:
            description: 报销说明（用户输入的文本）
            amount: 报销金额
            db: AsyncSession

        Returns:
            {
                "l3_code": "L3-XXX",
                "l3_name": "...",
                "control_tag": "...",
                "confidence": 0-100,
                "matched_keywords": [...],
                "alternatives": [{l3_code, l3_name, score}, ...],
                "is_in_db": True/False,  # L3 是否在数据库中已存在
            }
        """
        text = (description or "").strip()
        amount = float(amount or 0)
        if not text and amount <= 0:
            return {
                "l3_code": None,
                "l3_name": "无法识别（缺少说明和金额）",
                "control_tag": "强管控",
                "confidence": 0,
                "matched_keywords": [],
                "alternatives": [],
                "is_in_db": False,
            }

        # 1) 关键词打分
        scores: Dict[str, Dict[str, Any]] = {}
        for tag, info in L3_KEYWORD_MAP.items():
            hits = [k for k in info["keywords"] if k in text]
            if hits:
                # 基础分 = 命中数 * 25 + 文本长度加成
                base_score = len(hits) * 25 + min(20, len(text) / 10)
                scores[tag] = {
                    "l3_code": info["l3_code"],
                    "l3_name": info["l3_name"],
                    "control_tag": info["control_tag"],
                    "score": base_score,
                    "matched_keywords": hits,
                }

        # 2) 金额加成：差旅/招待/会议 通常金额较高
        if amount > 5000 and "差旅" in scores:
            scores["差旅"]["score"] += 15
        if amount > 3000 and "招待" in scores:
            scores["招待"]["score"] += 10
        if amount > 10000 and "研发" in scores:
            scores["研发"]["score"] += 10

        if not scores:
            # 兜底：默认强管控
            return {
                "l3_code": None,
                "l3_name": "未识别（无关键词命中）",
                "control_tag": "强管控",
                "confidence": 30,
                "matched_keywords": [],
                "alternatives": [],
                "is_in_db": False,
            }

        # 3) 排序取 Top 3
        sorted_scores = sorted(scores.values(), key=lambda x: -x["score"])
        top = sorted_scores[0]
        total_score = sum(s["score"] for s in sorted_scores) or 1
        confidence = round(top["score"] / total_score * 100, 1)

        # 4) 检查 L3 是否在数据库中
        is_in_db = True
        try:
            existing = await db.get(BudgetSubjectL3, top["l3_code"])
            is_in_db = existing is not None
        except Exception:
            pass

        return {
            "l3_code": top["l3_code"],
            "l3_name": top["l3_name"],
            "control_tag": top["control_tag"],
            "confidence": confidence,
            "matched_keywords": top["matched_keywords"],
            "alternatives": [
                {
                    "l3_code": s["l3_code"],
                    "l3_name": s["l3_name"],
                    "control_tag": s["control_tag"],
                    "score": round(s["score"], 1),
                }
                for s in sorted_scores[1:4]
            ],
            "is_in_db": is_in_db,
        }

    # ─────────────────────────────────────────────────────
    # 2) AI 异常检测（5 维）
    # ─────────────────────────────────────────────────────
    async def detect_anomalies(
        self,
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 5 维异常检测

        维度：
        1) 拆单检测 — 7 天内同申请人 + 同 L3 累计金额接近管控阈值
        2) 重复检测 — 同发票号 / 同金额 / 同申请人
        3) 异常时间 — 周末 / 深夜 22:00-06:00 报销
        4) 同人高频 — 30 天内同申请人报销次数 > 10
        5) 金额异常 — 偏离 L3 历史均值 ±3σ 或单笔 > 5万

        Returns:
            {
                "risk_score": 0-100,  # 越高越异常
                "risk_level": "低/中/高",
                "anomalies": [{type, severity, detail, evidence}],
                "should_block": True/False,
            }
        """
        anomalies: List[Dict[str, Any]] = []
        risk_score = 0

        applicant_id = expense_data.get("applicant_id", "")
        amount = float(expense_data.get("amount", 0) or 0)
        l3_code = expense_data.get("l3_code", "")
        invoice_number = expense_data.get("invoice_number", "")
        expense_date_val = expense_data.get("expense_date")
        if isinstance(expense_date_val, str):
            try:
                expense_date_val = datetime.strptime(expense_date_val, "%Y-%m-%d").date()
            except Exception:
                expense_date_val = None
        elif isinstance(expense_date_val, datetime):
            expense_date_val = expense_date_val.date()
        elif isinstance(expense_date_val, date):
            pass
        else:
            expense_date_val = None

        # ── 维度 1: 拆单检测（30 天内同申请人 + 同 L3 累计 + 多笔相近金额）──
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)
            stmt = select(ExpenseReport).where(
                and_(
                    ExpenseReport.applicant_id == applicant_id,
                    ExpenseReport.l3_code == l3_code,
                    ExpenseReport.created_at >= thirty_days_ago,
                    ExpenseReport.status.in_(["待审批", "组织线审批中", "法人线审批中", "已审批", "已核销"]),
                )
            )
            result = await db.execute(stmt)
            recent = result.scalars().all()
            if len(recent) >= 3:
                amounts = [float(e.amount or 0) for e in recent]
                total_recent = sum(amounts)
                # 拆单特征：累计金额 + 多笔相近金额（±10%）
                avg = total_recent / len(amounts)
                similar_count = sum(1 for a in amounts if abs(a - avg) < avg * 0.1) if avg > 0 else 0
                if similar_count >= 3 and avg < 5000:
                    # 阈值检查（默认 5 万强管控）
                    if total_recent > 30000 and total_recent < 50000:
                        risk_score += 30
                        anomalies.append({
                            "type": "拆单嫌疑",
                            "severity": "高",
                            "detail": f"30 天内同申请人 + 同 L3 累计 ¥{total_recent:.0f}，共 {len(recent)} 笔，接近 5 万管控阈值",
                            "evidence": {
                                "recent_count": len(recent),
                                "total_recent": total_recent,
                                "avg_amount": round(avg, 2),
                                "similar_count": similar_count,
                            },
                        })
        except Exception as e:
            logger.warning(f"拆单检测失败: {e}")

        # ── 维度 2: 重复检测 ──
        if invoice_number:
            try:
                stmt = select(InvoiceRecord).where(InvoiceRecord.invoice_number == invoice_number)
                result = await db.execute(stmt)
                if result.scalars().first():
                    risk_score += 50
                    anomalies.append({
                        "type": "重复发票",
                        "severity": "高",
                        "detail": f"发票号 {invoice_number} 已被使用过",
                        "evidence": {"invoice_number": invoice_number},
                    })
            except Exception as e:
                logger.warning(f"重复检测失败: {e}")

        # ── 维度 3: 异常时间（周末/深夜）──
        if expense_date_val:
            weekday = expense_date_val.weekday()  # 0=Mon, 6=Sun
            if weekday >= 5:  # 周末
                risk_score += 10
                anomalies.append({
                    "type": "异常时间",
                    "severity": "中",
                    "detail": f"费用发生日期 {expense_date_val} 为周末",
                    "evidence": {"date": str(expense_date_val), "weekday": weekday},
                })

        # ── 维度 4: 同人高频（30 天内 > 10 笔）──
        try:
            thirty_days_ago = datetime.now() - timedelta(days=30)
            stmt = select(func.count(ExpenseReport.expense_id)).where(
                and_(
                    ExpenseReport.applicant_id == applicant_id,
                    ExpenseReport.created_at >= thirty_days_ago,
                )
            )
            result = await db.execute(stmt)
            count = result.scalar() or 0
            if count >= 10:
                risk_score += 20
                anomalies.append({
                    "type": "同人高频",
                    "severity": "中",
                    "detail": f"30 天内 {applicant_id} 已报销 {count} 笔，可能存在分拆嫌疑",
                    "evidence": {"applicant_id": applicant_id, "count_30d": count},
                })
        except Exception as e:
            logger.warning(f"同人高频检测失败: {e}")

        # ── 维度 5: 金额异常（单笔 > 5 万 或 偏离均值 ±3σ）──
        if amount > 50000:
            risk_score += 25
            anomalies.append({
                "type": "大额报销",
                "severity": "高",
                "detail": f"单笔 ¥{amount:.0f} 超过 5 万，需额外审批（管委会）",
                "evidence": {"amount": amount},
            })

        if l3_code and amount > 0:
            try:
                # 取 L3 历史均值
                stmt = select(func.avg(ExpenseReport.amount)).where(
                    and_(
                        ExpenseReport.l3_code == l3_code,
                        ExpenseReport.status.in_(["已审批", "已核销"]),
                    )
                )
                result = await db.execute(stmt)
                avg = float(result.scalar() or 0)
                if avg > 0 and amount > avg * 3:
                    risk_score += 15
                    anomalies.append({
                        "type": "金额偏离",
                        "severity": "中",
                        "detail": f"金额 ¥{amount:.0f} 是 L3 历史均值 ¥{avg:.0f} 的 {amount/avg:.1f} 倍",
                        "evidence": {"amount": amount, "l3_avg": round(avg, 2), "ratio": round(amount/avg, 2)},
                    })
            except Exception as e:
                logger.warning(f"金额偏离检测失败: {e}")

        # 风险等级
        if risk_score >= 60:
            risk_level = "高"
            should_block = True
        elif risk_score >= 30:
            risk_level = "中"
            should_block = False
        else:
            risk_level = "低"
            should_block = False

        return {
            "risk_score": min(100, risk_score),
            "risk_level": risk_level,
            "anomalies": anomalies,
            "should_block": should_block,
        }

    # ─────────────────────────────────────────────────────
    # 3) AI 智能路由（4 级管控 + 异常 + 金额阈值）
    # ─────────────────────────────────────────────────────
    async def smart_route(
        self,
        expense_data: Dict[str, Any],
        anomaly_result: Dict[str, Any],
        l3_recognition: Dict[str, Any],
    ) -> Dict[str, Any]:
        """v12.1: 智能路由

        规则：
        1) 基础路由（4 级管控）：
           - 强管控: 部门负责人 → 中心总经理 → 法人财务负责人 → 法人/授权人
           - 中心弱管控: BP → 中心总经理
           - 组合管控: BP → 中心总经理
           - 不管控: 自动通过
        2) 异常加成：
           - 中风险：增加「财务复核」环节
           - 高风险：直接路由到「管委会」
        3) 金额加成：
           - > 5 万：增加「管委会」环节
        4) 优化：
           - 估算审批 SLA（基于历史均值）

        Returns:
            {
                "control_tag": "...",
                "approval_chain": ["环节1", "环节2", ...],
                "estimated_sla_hours": 24,
                "auto_approve": True/False,
                "routing_reason": "...",
            }
        """
        control_tag = l3_recognition.get("control_tag") or "强管控"
        amount = float(expense_data.get("amount", 0) or 0)
        risk_level = anomaly_result.get("risk_level", "低")

        # 基础链
        base_chain_map = {
            "强管控": ["部门负责人", "中心总经理", "法人财务负责人", "法人或授权人"],
            "中心弱管控": ["BP", "中心总经理"],
            "组合管控": ["BP", "中心总经理"],
            "不管控": [],
        }
        chain = list(base_chain_map.get(control_tag, base_chain_map["强管控"]))
        reasons = [f"基础路由（{control_tag}）"]

        # 异常加成
        if risk_level == "高":
            chain.append("管委会")
            reasons.append("高风险 → 增加管委会审批")
        elif risk_level == "中":
            # 在中间插入「财务复核」
            insert_pos = min(2, len(chain))
            chain.insert(insert_pos, "财务复核")
            reasons.append("中风险 → 增加财务复核")

        # 金额加成
        if amount > 50000:
            if "管委会" not in chain:
                chain.append("管委会")
                reasons.append(f"金额 ¥{amount:.0f} > 5万 → 增加管委会审批")

        # 自动审批判定
        auto_approve = control_tag == "不管控" and risk_level == "低" and amount <= 5000

        # SLA 估算（每环节 6-12 小时）
        chain_len = len(chain) if not auto_approve else 0
        base_hours = chain_len * 8 if chain_len else 0
        # 风险越高，审批越慢
        risk_factor = {"低": 1.0, "中": 1.3, "高": 1.8}.get(risk_level, 1.0)
        estimated_sla_hours = round(base_hours * risk_factor, 1) if base_hours else 0.5

        return {
            "control_tag": control_tag,
            "approval_chain": chain,
            "auto_approve": auto_approve,
            "estimated_sla_hours": estimated_sla_hours,
            "routing_reason": " | ".join(reasons),
        }

    # ─────────────────────────────────────────────────────
    # 4) AI 拒付预警
    # ─────────────────────────────────────────────────────
    async def predict_rejection(
        self,
        expense_data: Dict[str, Any],
        anomaly_result: Dict[str, Any],
        routing: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 提交前拒付概率预测

        综合考虑：异常分 + 路由复杂度 + 申请人历史拒付率 + 战略对齐度
        """
        applicant_id = expense_data.get("applicant_id", "")
        amount = float(expense_data.get("amount", 0) or 0)

        # 1) 申请人历史拒付率（过去 90 天）
        historical_reject_rate = 0.0
        try:
            ninety_days_ago = datetime.now() - timedelta(days=90)
            stmt = select(func.count(ExpenseReport.expense_id)).where(
                and_(
                    ExpenseReport.applicant_id == applicant_id,
                    ExpenseReport.created_at >= ninety_days_ago,
                )
            )
            result = await db.execute(stmt)
            total = result.scalar() or 0

            stmt_rej = select(func.count(ExpenseReport.expense_id)).where(
                and_(
                    ExpenseReport.applicant_id == applicant_id,
                    ExpenseReport.created_at >= ninety_days_ago,
                    ExpenseReport.status == "已驳回",
                )
            )
            result_rej = await db.execute(stmt_rej)
            rejected = result_rej.scalar() or 0

            if total > 0:
                historical_reject_rate = rejected / total
        except Exception as e:
            logger.warning(f"历史拒付率查询失败: {e}")

        # 2) 综合打分
        anomaly_score = anomaly_result.get("risk_score", 0) * 0.5  # 50%
        history_score = historical_reject_rate * 100 * 0.25          # 25%
        chain_complexity = min(100, len(routing.get("approval_chain", [])) * 20)
        chain_score = chain_complexity * 0.15                          # 15%
        # 战略对齐（简化版：根据 L3 类别）
        l3_code = expense_data.get("l3_code", "")
        strategic_alignment = 70 if l3_code else 50
        alignment_score = (100 - strategic_alignment) * 0.10          # 10%

        reject_prob = round(
            anomaly_score + history_score + chain_score + alignment_score,
            1,
        )
        reject_prob = min(100, max(0, reject_prob))

        if reject_prob >= 60:
            risk_band = "高"
        elif reject_prob >= 30:
            risk_band = "中"
        else:
            risk_band = "低"

        # 3) 修复建议
        recommendations: List[str] = []
        if anomaly_result.get("risk_level") == "高":
            for a in anomaly_result.get("anomalies", []):
                if a["type"] == "拆单嫌疑":
                    recommendations.append("避免分拆，合并为单笔合规报销")
                if a["type"] == "重复发票":
                    recommendations.append(f"更换发票：{a.get('evidence', {}).get('invoice_number')}")
                if a["type"] == "大额报销":
                    recommendations.append("准备管委会审批材料：合同/决议/预算依据")
        if historical_reject_rate > 0.2:
            recommendations.append("近 90 天拒付率 > 20%，建议先与 BP 沟通")
        if not recommendations:
            recommendations.append("各项指标良好，可直接提交")

        return {
            "reject_probability": reject_prob,
            "risk_band": risk_band,
            "factors": {
                "anomaly_score": round(anomaly_score, 1),
                "historical_reject_rate": round(historical_reject_rate * 100, 1),
                "chain_complexity": round(chain_complexity, 1),
                "strategic_alignment_gap": 100 - strategic_alignment,
            },
            "recommendations": recommendations,
        }

    # ─────────────────────────────────────────────────────
    # 综合接口：一站式 AI 报销预审
    # ─────────────────────────────────────────────────────
    async def pre_submit_review(
        self,
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 提交前 AI 预审一站式

        流程：L3 识别 → 异常检测 → 智能路由 → 拒付预警
        """
        description = expense_data.get("description", "")
        amount = float(expense_data.get("amount", 0) or 0)

        l3 = await self.recognize_l3(description, amount, db)
        anomaly = await self.detect_anomalies(expense_data, db)
        routing = await self.smart_route(expense_data, anomaly, l3)
        rejection = await self.predict_rejection(expense_data, anomaly, routing, db)

        return {
            "input": {
                "description": description,
                "amount": amount,
                "applicant_id": expense_data.get("applicant_id", ""),
            },
            "l3_recognition": l3,
            "anomaly_detection": anomaly,
            "smart_routing": routing,
            "rejection_prediction": rejection,
            "should_submit": not anomaly.get("should_block", False),
        }

    # ─────────────────────────────────────────────────────
    # 批量异常扫描（管理员视角）
    # ─────────────────────────────────────────────────────
    async def batch_anomaly_scan(
        self,
        db: AsyncSession,
        days: int = 7,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """v12.1: 批量扫描近 N 天所有待审批/已审批报销的异常情况"""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            stmt = select(ExpenseReport).where(
                and_(
                    ExpenseReport.created_at >= cutoff,
                    ExpenseReport.status.in_([
                        "待审批", "组织线审批中", "法人线审批中", "已审批"
                    ]),
                )
            )
            result = await db.execute(stmt)
            recent = result.scalars().all()

            # 拆分嫌疑聚类
            split_clusters: Dict[str, List] = defaultdict(list)
            for exp in recent:
                if exp.applicant_id and exp.l3_code:
                    key = f"{exp.applicant_id}|{exp.l3_code}"
                    split_clusters[key].append(exp)

            high_risk_items: List[Dict] = []
            for key, items in split_clusters.items():
                if len(items) < 3:
                    continue
                total = sum(float(e.amount or 0) for e in items)
                if total < 20000:
                    continue
                amounts = [float(e.amount or 0) for e in items]
                avg = total / len(amounts)
                similar = sum(1 for a in amounts if abs(a - avg) < avg * 0.15) if avg > 0 else 0
                if similar >= 3:
                    high_risk_items.append({
                        "type": "拆单嫌疑",
                        "applicant_id": items[0].applicant_id,
                        "l3_code": items[0].l3_code,
                        "expense_count": len(items),
                        "total_amount": round(total, 2),
                        "avg_amount": round(avg, 2),
                        "expense_ids": [e.expense_id for e in items],
                    })

            high_risk_items.sort(key=lambda x: -x["total_amount"])

            # 申请人频率
            applicant_counts: Counter = Counter(e.applicant_id for e in recent if e.applicant_id)
            high_freq = [
                {"applicant_id": k, "count": v}
                for k, v in applicant_counts.most_common(10)
                if v >= 8
            ]

            return {
                "scan_window_days": days,
                "scanned_count": len(recent),
                "high_risk_count": len(high_risk_items),
                "high_freq_applicants": high_freq,
                "split_clusters": high_risk_items[:top_n],
                "scanned_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"批量异常扫描失败: {e}")
            return {
                "scan_window_days": days,
                "scanned_count": 0,
                "high_risk_count": 0,
                "high_freq_applicants": [],
                "split_clusters": [],
                "scanned_at": datetime.now().isoformat(),
                "error": str(e),
            }
