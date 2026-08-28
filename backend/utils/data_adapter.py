"""数据适配器 - 支持API模式和Mock模式的数据获取

参考 cfoclaw data_adapter.py 设计，为技能提供统一数据获取接口。
API模式：调用后端REST API
Mock模式：从内嵌JSON模拟数据读取
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# ── 环境变量 ──
FINANCE_API_BASE = os.environ.get("FINANCE_API_BASE", "")


# ── Mock 数据 ──

MOCK_BUDGET_ITEMS = [
    {"budget_id": "B-001", "budget_name": "创新研发-肿瘤管线", "l1_code": "B2", "annual_amount": 5000000, "used_amount": 3200000, "available_amount": 1800000, "status": "执行中", "quadrant": "发展", "strategic_intent_l1": "创新研发", "center_id": "C-RD"},
    {"budget_id": "B-002", "budget_name": "全渠道商业化-心血管", "l1_code": "B5", "annual_amount": 3000000, "used_amount": 2700000, "available_amount": 300000, "status": "执行中", "quadrant": "发展", "strategic_intent_l1": "全渠道商业化", "center_id": "C-MK"},
    {"budget_id": "B-003", "budget_name": "数字化转型-ERP升级", "l1_code": "B1", "annual_amount": 2000000, "used_amount": 800000, "available_amount": 1200000, "status": "执行中", "quadrant": "探索", "strategic_intent_l1": "数字化转型", "center_id": "C-IT"},
    {"budget_id": "B-004", "budget_name": "成本优化-供应链整合", "l1_code": "B7", "annual_amount": 1500000, "used_amount": 1200000, "available_amount": 300000, "status": "执行中", "quadrant": "稳定", "strategic_intent_l1": "成本优化", "center_id": "C-SC"},
    {"budget_id": "B-005", "budget_name": "国际化-东南亚拓展", "l1_code": "B5", "annual_amount": 1000000, "used_amount": 200000, "available_amount": 800000, "status": "执行中", "quadrant": "探索", "strategic_intent_l1": "国际化", "center_id": "C-INT"},
    {"budget_id": "B-006", "budget_name": "人力成本-研发中心", "l1_code": "B6", "annual_amount": 4000000, "used_amount": 3500000, "available_amount": 500000, "status": "执行中", "quadrant": "稳定", "strategic_intent_l1": "创新研发", "center_id": "C-RD"},
    {"budget_id": "B-007", "budget_name": "战略储备-应急基金", "l1_code": "B9", "annual_amount": 800000, "used_amount": 100000, "available_amount": 700000, "status": "已授予", "quadrant": "收缩", "strategic_intent_l1": "战略储备", "center_id": "C-FIN"},
    {"budget_id": "B-008", "budget_name": "临床III期-糖尿病", "l1_code": "B2", "annual_amount": 6000000, "used_amount": 5500000, "available_amount": 500000, "status": "执行中", "quadrant": "发展", "strategic_intent_l1": "创新研发", "center_id": "C-RD"},
]

MOCK_ALERTS = [
    {"alert_id": "ALT-001", "alert_level": "红色", "budget_id": "B-008", "description": "临床III期预算执行率92%，超预算风险", "status": "待响应", "created_at": "2024-06-01"},
    {"alert_id": "ALT-002", "alert_level": "橙色", "budget_id": "B-002", "description": "商业化预算执行率90%，接近上限", "status": "已响应", "created_at": "2024-06-02"},
    {"alert_id": "ALT-003", "alert_level": "黄色", "budget_id": "B-006", "description": "人力成本执行率88%，需关注", "status": "已闭环", "created_at": "2024-05-15"},
    {"alert_id": "ALT-004", "alert_level": "蓝色", "budget_id": "B-003", "description": "数字化转型执行率40%，进度偏慢", "status": "待响应", "created_at": "2024-06-05"},
    {"alert_id": "ALT-005", "alert_level": "红色", "budget_id": "B-001", "description": "肿瘤管线里程碑延期2个月", "status": "待响应", "created_at": "2024-06-03"},
]


def _is_api_mode() -> bool:
    """检查是否使用API模式"""
    return bool(FINANCE_API_BASE)


async def api_get(endpoint: str, params: Optional[Dict] = None) -> Any:
    """调用后端REST API"""
    import httpx
    url = f"{FINANCE_API_BASE}{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _calculate_execution_rate(used: float, annual: float) -> float:
    """计算执行率"""
    return round(used / annual * 100, 2) if annual > 0 else 0


def _calculate_closure_rate(alerts: List[Dict]) -> float:
    """计算闭环率"""
    if not alerts:
        return 0
    closed = sum(1 for a in alerts if a.get("status") == "已闭环")
    return round(closed / len(alerts) * 100, 2)


def _calculate_light_score(alerts: List[Dict]) -> float:
    """计算灯色评分"""
    if not alerts:
        return 0
    weights = {"红色": 4, "橙色": 3, "黄色": 2, "蓝色": 1}
    total = sum(weights.get(a.get("alert_level", ""), 0) for a in alerts)
    return round(total / len(alerts), 2)


async def fetch_executive_dashboard(period: str = "2024-06") -> Dict[str, Any]:
    """获取CFO一把手视图数据"""
    if _is_api_mode():
        try:
            data = await api_get("/api/dashboard/summary", {"period": period})
            return data.get("data", {})
        except Exception:
            pass

    # Mock模式
    items = MOCK_BUDGET_ITEMS
    alerts = MOCK_ALERTS
    total_annual = sum(i["annual_amount"] for i in items)
    total_used = sum(i["used_amount"] for i in items)
    execution_rate = _calculate_execution_rate(total_used, total_annual)
    closure_rate = _calculate_closure_rate(alerts)
    light_score = _calculate_light_score(alerts)

    # 象限分布
    quadrant_totals = {}
    for item in items:
        q = item.get("quadrant", "未分类")
        quadrant_totals[q] = quadrant_totals.get(q, 0) + item["annual_amount"]
    quadrant_ratios = {q: round(v / total_annual * 100, 1) for q, v in quadrant_totals.items()} if total_annual > 0 else {}

    # TOP-N关注清单
    overdue_alerts = [a for a in alerts if a["status"] == "待响应"]
    top_concerns = sorted(overdue_alerts, key=lambda a: {"红色": 0, "橙色": 1, "黄色": 2, "蓝色": 3}.get(a["alert_level"], 4))

    return {
        "period": period,
        "execution_rate": execution_rate,
        "closure_rate": closure_rate,
        "light_score": light_score,
        "total_annual": total_annual,
        "total_used": total_used,
        "overdue_alerts_count": len(overdue_alerts),
        "quadrant_ratios": quadrant_ratios,
        "top_concerns": top_concerns[:5],
        "items": items,
        "alerts": alerts,
    }


async def fetch_strategic_budget(period: str = "2024-06") -> Dict[str, Any]:
    """获取战略预算归因数据"""
    if _is_api_mode():
        try:
            data = await api_get("/api/strategic/budget-attribution", {"period": period})
            return data.get("data", {})
        except Exception:
            pass

    # Mock模式
    items = MOCK_BUDGET_ITEMS
    intent_summary = {}
    for item in items:
        intent = item.get("strategic_intent_l1", "未分类")
        if intent not in intent_summary:
            intent_summary[intent] = {"total": 0, "used": 0, "count": 0}
        intent_summary[intent]["total"] += item["annual_amount"]
        intent_summary[intent]["used"] += item["used_amount"]
        intent_summary[intent]["count"] += 1

    for intent, data in intent_summary.items():
        data["execution_rate"] = _calculate_execution_rate(data["used"], data["total"])

    return {
        "period": period,
        "intent_summary": intent_summary,
        "quadrant_distribution": {
            "发展": sum(1 for i in items if i.get("quadrant") == "发展"),
            "收缩": sum(1 for i in items if i.get("quadrant") == "收缩"),
            "稳定": sum(1 for i in items if i.get("quadrant") == "稳定"),
            "探索": sum(1 for i in items if i.get("quadrant") == "探索"),
        },
    }


async def fetch_pdca_review(period: str = "2024-Q2") -> Dict[str, Any]:
    """获取PDCA复盘数据"""
    if _is_api_mode():
        try:
            data = await api_get("/api/pdca/review", {"period": period})
            return data.get("data", {})
        except Exception:
            pass

    # Mock模式
    return {
        "period": period,
        "cycle_type": "季度",
        "closure_rate": 82.5,
        "gap1": -5.2,
        "gap2": -3.1,
        "gap3": 1.8,
        "three_lists": {
            "must_win": ["临床III期预算管控", "商业化费用优化"],
            "improve": ["数字化转型进度提升", "人力成本结构优化"],
            "resource": ["国际化资源追加评估", "战略储备释放可行性"],
        },
        "improvement_actions": [
            {"action": "加强临床III期里程碑管控", "owner": "研发中心", "deadline": "2024-07-31", "progress": 60},
            {"action": "优化商业化费用审批流程", "owner": "市场中心", "deadline": "2024-08-15", "progress": 30},
        ],
    }


def main():
    """命令行入口"""
    import asyncio
    import sys

    skill = sys.argv[1] if len(sys.argv) > 1 else "executive-dashboard"
    period = sys.argv[2] if len(sys.argv) > 2 else "2024-06"

    fetch_map = {
        "executive-dashboard": fetch_executive_dashboard,
        "strategic-budget": fetch_strategic_budget,
        "pdca-review": fetch_pdca_review,
    }

    fetch_fn = fetch_map.get(skill)
    if not fetch_fn:
        print(f"Unknown skill: {skill}")
        print(f"Available: {', '.join(fetch_map.keys())}")
        return

    result = asyncio.run(fetch_fn(period))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
