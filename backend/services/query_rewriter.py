from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from loguru import logger


class QueryType(str, Enum):
    FACT_QUERY = "fact_query"
    RELATIONAL_QUERY = "relational_query"
    ATTRIBUTION_ANALYSIS = "attribution_analysis"
    ACTION_RECOMMENDATION = "action_recommendation"
    BUDGET_QUERY = "budget_query"
    EXPENSE_QUERY = "expense_query"
    ALERT_QUERY = "alert_query"
    ANALYSIS_QUERY = "analysis_query"
    REPORT_QUERY = "report_query"
    GENERAL = "general"


_BUDGET_KEYWORDS = ["预算", "额度", "授予", "编制", "调整", "调拨", "B转A", "B→A", "象限", "A类", "B类", "冻结", "释放"]
_EXPENSE_KEYWORDS = ["报销", "费用", "审批", "核销", "支出", "发票", "申请"]
_ALERT_KEYWORDS = ["预警", "蓝色", "黄色", "橙色", "红色", "闭环", "升级", "响应", "阈值"]
_ANALYSIS_KEYWORDS = ["分析", "3GAP", "3List", "差距", "清单", "归因", "执行率", "必赢", "改善", "资源"]
_REPORT_KEYWORDS = ["报表", "月报", "季报", "快报", "汇报", "复盘", "经营分析会"]

_FACT_PATTERNS = ["多少", "是什么", "有哪些", "当前", "总额", "数量", "状态"]
_RELATIONAL_PATTERNS = ["关系", "关联", "相关", "影响", "导致", "因为"]
_ATTRIBUTION_PATTERNS = ["为什么", "原因", "归因", "为什么超", "为什么低"]
_ACTION_PATTERNS = ["怎么办", "如何处理", "建议", "措施", "应该", "如何调整", "怎样"]

_SUBJECT_ALIASES: Dict[str, List[str]] = {
    "B1": ["差旅", "差旅费", "出差", "机票", "酒店", "交通"],
    "B2": ["招待", "招待费", "接待", "宴请"],
    "B3": ["培训", "培训费", "课程", "学习"],
    "B4": ["办公", "办公费", "办公用品", "设备租赁"],
    "B5": ["研发", "研发费", "开发", "技术", "外包", "专利"],
    "B6": ["市场", "市场费", "推广", "品牌", "广告", "营销"],
    "B7": ["渠道", "渠道费", "返利", "经销商", "代理"],
    "B8": ["税费", "税", "增值税", "所得税"],
    "B9": ["人力", "人力成本", "薪酬", "工资", "社保", "福利"],
}

_CENTER_ALIASES: Dict[str, List[str]] = {
    "C001": ["津康", "津康中心", "总部"],
    "C002": ["华北", "华北中心", "北方"],
    "C003": ["华东", "华东中心", "东部"],
    "C004": ["华南", "华南中心", "南方"],
}


@dataclass
class RewrittenQuery:
    original: str
    rewritten: str
    query_type: QueryType
    expanded_terms: List[str]
    subject_codes: List[str]
    center_ids: List[str]
    confidence: float


class QueryRewriter:
    def __init__(self) -> None:
        self._subject_patterns = {
            code: re.compile("|".join(aliases), re.IGNORECASE)
            for code, aliases in _SUBJECT_ALIASES.items()
        }
        self._center_patterns = {
            code: re.compile("|".join(aliases), re.IGNORECASE)
            for code, aliases in _CENTER_ALIASES.items()
        }

    def rewrite(self, query: str) -> RewrittenQuery:
        query_type = self._detect_query_type(query)
        expanded_terms = self._expand_terms(query)
        subject_codes = self._extract_subject_codes(query)
        center_ids = self._extract_center_ids(query)

        rewritten = self._build_rewritten_query(query, query_type, expanded_terms, subject_codes, center_ids)

        confidence = self._estimate_confidence(query_type, subject_codes, center_ids)

        return RewrittenQuery(
            original=query,
            rewritten=rewritten,
            query_type=query_type,
            expanded_terms=expanded_terms,
            subject_codes=subject_codes,
            center_ids=center_ids,
            confidence=confidence,
        )

    def _detect_query_type(self, query: str) -> QueryType:
        domain = self._detect_domain(query)
        level = self._detect_level(query)

        if domain != QueryType.GENERAL:
            if level == "fact":
                return domain
            elif level == "relational":
                return QueryType.RELATIONAL_QUERY
            elif level == "attribution":
                return QueryType.ATTRIBUTION_ANALYSIS
            elif level == "action":
                return QueryType.ACTION_RECOMMENDATION
            return domain

        if level == "fact":
            return QueryType.FACT_QUERY
        elif level == "relational":
            return QueryType.RELATIONAL_QUERY
        elif level == "attribution":
            return QueryType.ATTRIBUTION_ANALYSIS
        elif level == "action":
            return QueryType.ACTION_RECOMMENDATION

        return QueryType.GENERAL

    def _detect_domain(self, query: str) -> QueryType:
        scores: Dict[QueryType, float] = {
            QueryType.BUDGET_QUERY: 0.0,
            QueryType.EXPENSE_QUERY: 0.0,
            QueryType.ALERT_QUERY: 0.0,
            QueryType.ANALYSIS_QUERY: 0.0,
            QueryType.REPORT_QUERY: 0.0,
        }

        for kw in _BUDGET_KEYWORDS:
            if kw in query:
                scores[QueryType.BUDGET_QUERY] += 1.0
        for kw in _EXPENSE_KEYWORDS:
            if kw in query:
                scores[QueryType.EXPENSE_QUERY] += 1.0
        for kw in _ALERT_KEYWORDS:
            if kw in query:
                scores[QueryType.ALERT_QUERY] += 1.0
        for kw in _ANALYSIS_KEYWORDS:
            if kw in query:
                scores[QueryType.ANALYSIS_QUERY] += 1.0
        for kw in _REPORT_KEYWORDS:
            if kw in query:
                scores[QueryType.REPORT_QUERY] += 1.0

        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
        return QueryType.GENERAL

    def _detect_level(self, query: str) -> str:
        for pattern in _ACTION_PATTERNS:
            if pattern in query:
                return "action"
        for pattern in _ATTRIBUTION_PATTERNS:
            if pattern in query:
                return "attribution"
        for pattern in _RELATIONAL_PATTERNS:
            if pattern in query:
                return "relational"
        for pattern in _FACT_PATTERNS:
            if pattern in query:
                return "fact"
        return "fact"

    def _expand_terms(self, query: str) -> List[str]:
        expanded = []
        for code, aliases in _SUBJECT_ALIASES.items():
            for alias in aliases:
                if alias in query:
                    for other_alias in aliases:
                        if other_alias not in query and other_alias not in expanded:
                            expanded.append(other_alias)
                    break

        for code, aliases in _CENTER_ALIASES.items():
            for alias in aliases:
                if alias in query:
                    for other_alias in aliases:
                        if other_alias not in query and other_alias not in expanded:
                            expanded.append(other_alias)
                    break

        return expanded

    def _extract_subject_codes(self, query: str) -> List[str]:
        codes = []
        for code, pattern in self._subject_patterns.items():
            if pattern.search(query):
                codes.append(code)
        return codes

    def _extract_center_ids(self, query: str) -> List[str]:
        ids = []
        for code, pattern in self._center_patterns.items():
            if pattern.search(query):
                ids.append(code)
        return ids

    def _build_rewritten_query(
        self,
        query: str,
        query_type: QueryType,
        expanded_terms: List[str],
        subject_codes: List[str],
        center_ids: List[str],
    ) -> str:
        parts = [query]

        if expanded_terms:
            parts.append(f"(相关词: {', '.join(expanded_terms)})")

        if subject_codes:
            parts.append(f"[科目: {', '.join(subject_codes)}]")

        if center_ids:
            center_names = []
            for cid in center_ids:
                aliases = _CENTER_ALIASES.get(cid, [])
                center_names.append(aliases[0] if aliases else cid)
            parts.append(f"[中心: {', '.join(center_names)}]")

        type_labels = {
            QueryType.FACT_QUERY: "事实查询",
            QueryType.RELATIONAL_QUERY: "关系查询",
            QueryType.ATTRIBUTION_ANALYSIS: "归因分析",
            QueryType.ACTION_RECOMMENDATION: "行动建议",
            QueryType.BUDGET_QUERY: "预算查询",
            QueryType.EXPENSE_QUERY: "费用查询",
            QueryType.ALERT_QUERY: "预警查询",
            QueryType.ANALYSIS_QUERY: "分析查询",
            QueryType.REPORT_QUERY: "报表查询",
        }
        type_label = type_labels.get(query_type, "通用")
        parts.append(f"[类型: {type_label}]")

        return " ".join(parts)

    def _estimate_confidence(self, query_type: QueryType, subject_codes: List[str], center_ids: List[str]) -> float:
        confidence = 0.5
        if query_type != QueryType.GENERAL:
            confidence += 0.2
        if subject_codes:
            confidence += 0.15
        if center_ids:
            confidence += 0.1
        return min(confidence, 1.0)
