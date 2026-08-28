"""
槽位提取服务 — 从用户查询中提取结构化信息
按 v8.0 计划 §3.2 模块 G 实施：时间/类型/部门/金额/范围
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# ─── 槽位类型定义 ─────────────────────────────────

SLOT_TYPES = (
    "period",        # 期间
    "period_type",   # 期间类型（年/季/月/周/日）
    "subject",       # 科目（L1/L2/L3）
    "center",        # 中心
    "department",    # 部门
    "applicant",     # 申请人
    "amount_range",  # 金额范围
    "amount_min",    # 金额最小值
    "amount_max",    # 金额最大值
    "scope",         # 范围（超支/不足/达成/异常等）
    "object_type",   # 对象类型（预算/费用/预警/分析等）
    "metric",        # 指标
    "sort_by",       # 排序字段
    "limit",         # 数量限制
)


@dataclass
class Slot:
    """单个槽位"""
    name: str
    value: Any
    confidence: float = 1.0
    raw_text: str = ""  # 原文片段


@dataclass
class ExtractionResult:
    """槽位提取结果"""
    slots: Dict[str, Slot] = field(default_factory=dict)
    intent_hint: str = ""  # 意图提示（增强 IntentClassifier）
    missing_slots: List[str] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any:
        if name in self.slots:
            return self.slots[name].value
        return default

    def has(self, name: str) -> bool:
        return name in self.slots


# ─── 正则模式库 ───────────────────────────────────

_PERIOD_PATTERNS: List[Tuple[str, str, float]] = [
    # YYYY-MM or YYYYMM
    (r"(\d{4})[\s年-](\d{1,2})月?", "month", 1.0),
    (r"(\d{4})[\s年-](\d{1,2})[\s月-](\d{1,2})日?", "day", 1.0),
    # Q1-Q4
    (r"(20\d{2})\s*[Qq]([1-4])\s*季度?", "quarter", 1.0),
    (r"(20\d{2})\s*年第?([1-4])\s*季度", "quarter", 1.0),
    # 年度
    (r"(20\d{2})\s*年(度|全年)?", "year", 0.95),
    # 半年
    (r"(20\d{2})\s*[上下]半年", "half_year", 1.0),
]

_RELATIVE_PERIOD = {
    "上上": -2, "上": -1, "本": 0, "当前": 0, "这": 0,
    "今": 0, "去": -1, "去年": -1,
    "前年": -2,
}

_PERIOD_TYPE = {
    "月": "month", "月份": "month",
    "季度": "quarter", "季": "quarter",
    "年": "year", "年度": "year", "全年": "year",
    "周": "week", "星期": "week",
    "日": "day", "天": "day", "号": "day",
}

# 金额单位
_AMOUNT_UNITS = {
    "千": 1000, "k": 1000, "K": 1000,
    "万": 10000, "w": 10000, "W": 10000, "萬元": 10000,
    "百万": 1000000, "百万": 1000000, "M": 1000000,
    "千万": 10000000,
    "亿": 100000000, "y": 100000000, "Y": 100000000,
}

# 范围关键词
_SCOPE_KEYWORDS = {
    "超支": "overrun", "超额": "overrun", "超预算": "overrun",
    "结余": "underrun", "剩余": "underrun", "未达": "underrun",
    "达成": "achieved", "完成": "achieved",
    "异常": "anomaly", "波动": "anomaly",
    "高": "high", "低": "low",
    "上升": "increasing", "增长": "increasing",
    "下降": "decreasing", "降低": "decreasing",
}

# 排序关键词
_SORT_KEYWORDS = {
    "最大": "amount desc", "最高": "amount desc",
    "最小": "amount asc", "最低": "amount asc",
    "最近": "date desc", "最新": "date desc",
    "最早": "date asc",
    "最慢": "duration desc", "最快": "duration asc",
}

# 数量限制
_LIMIT_PATTERN = re.compile(r"(?:top|前|最[高低大小长短]?)\s*(\d{1,3})")


class SlotExtractor:
    """槽位提取器：基于规则（不依赖 LLM，保证 0 成本 + 高准确）"""

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """预编译正则"""
        self._period_res: List[Tuple[re.Pattern, str, float]] = []
        for pat, ptype, conf in _PERIOD_PATTERNS:
            self._period_res.append((re.compile(pat), ptype, conf))

        self._amount_re = re.compile(
            r"(\d+(?:\.\d+)?)\s*(千|万|百万|千万|亿|k|K|w|W|M|Y)?\s*[元円]?"
        )
        self._range_re = re.compile(
            r"(?:超过?|大于|多于|above|over|>|>=)\s*(\d+(?:\.\d+)?)\s*(千|万|百万|千万|亿|k|K|w|W|M|Y)?"
            r"|(?:少于?|小于|低于|under|below|<|<=)\s*(\d+(?:\.\d+)?)\s*(千|万|百万|千万|亿|k|K|w|W|M|Y)?"
        )

    # ─── 期间提取 ─────────────────────────────────────

    def _extract_period(self, query: str) -> Tuple[Optional[Slot], Optional[Slot], Optional[Slot]]:
        """提取期间
        Returns: (period_slot, period_type_slot, raw_slot)
        """
        # 1. 绝对期间
        for pattern, ptype, conf in self._period_res:
            m = pattern.search(query)
            if m:
                if ptype == "month":
                    year, month = int(m.group(1)), int(m.group(2))
                    period_str = f"{year:04d}-{month:02d}"
                    return (
                        Slot("period", period_str, conf, m.group()),
                        Slot("period_type", "month", conf, ptype),
                        None,
                    )
                elif ptype == "day":
                    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    period_str = f"{year:04d}-{month:02d}-{day:02d}"
                    return (
                        Slot("period", period_str, conf, m.group()),
                        Slot("period_type", "day", conf, ptype),
                        None,
                    )
                elif ptype == "quarter":
                    year, q = int(m.group(1)), int(m.group(2))
                    # Q1=1-3, Q2=4-6, Q3=7-9, Q4=10-12
                    start_month = (q - 1) * 3 + 1
                    period_str = f"{year:04d}-Q{q}"
                    return (
                        Slot("period", period_str, conf, m.group()),
                        Slot("period_type", "quarter", conf, ptype),
                        None,
                    )
                elif ptype == "year":
                    year = int(m.group(1))
                    return (
                        Slot("period", f"{year:04d}", conf, m.group()),
                        Slot("period_type", "year", conf, ptype),
                        None,
                    )
                elif ptype == "half_year":
                    year = int(m.group(1))
                    is_upper = "上" in m.group()
                    period_str = f"{year:04d}-{'H1' if is_upper else 'H2'}"
                    return (
                        Slot("period", period_str, conf, m.group()),
                        Slot("period_type", "half_year", conf, ptype),
                        None,
                    )

        # 2. 相对期间
        for keyword, offset in _RELATIVE_PERIOD.items():
            if keyword in query:
                for ptype_kw, ptype in _PERIOD_TYPE.items():
                    if ptype_kw in query:
                        now = datetime.now()
                        target_year = now.year
                        target_month = now.month

                        if ptype == "month":
                            d = target_year * 12 + (target_month - 1) + offset
                            target_year, target_month = divmod(d, 12)
                            target_month += 1
                            period_str = f"{target_year:04d}-{target_month:02d}"
                        elif ptype == "quarter":
                            cur_q = (target_month - 1) // 3 + 1
                            d = target_year * 4 + (cur_q - 1) + offset
                            target_year, cur_q = divmod(d, 4)
                            cur_q += 1
                            period_str = f"{target_year:04d}-Q{cur_q}"
                        elif ptype == "year":
                            period_str = f"{target_year + offset:04d}"
                        else:
                            period_str = "current"

                        return (
                            Slot("period", period_str, 0.85, keyword + ptype_kw),
                            Slot("period_type", ptype, 0.85, ptype_kw),
                            None,
                        )

        return (None, None, None)

    # ─── 金额提取 ─────────────────────────────────────

    def _extract_amount(self, query: str) -> Tuple[Optional[Slot], Optional[Slot], Optional[Slot]]:
        """提取金额范围"""
        # 范围模式
        m = self._range_re.search(query)
        if m:
            # 解析单位
            if m.group(2):
                unit = _AMOUNT_UNITS.get(m.group(2), 1)
            elif m.group(4):
                unit = _AMOUNT_UNITS.get(m.group(4), 1)
            else:
                unit = 1
            if m.group(1):  # > X
                return (
                    None,
                    Slot("amount_min", float(m.group(1)) * unit, 0.9, m.group()),
                    None,
                )
            elif m.group(3):  # < X
                return (
                    None,
                    None,
                    Slot("amount_max", float(m.group(3)) * unit, 0.9, m.group()),
                )

        return (None, None, None)

    # ─── 范围/排序/限制提取 ─────────────────────────

    def _extract_scope(self, query: str) -> Optional[Slot]:
        for keyword, scope in _SCOPE_KEYWORDS.items():
            if keyword in query:
                return Slot("scope", scope, 0.9, keyword)
        return None

    def _extract_sort(self, query: str) -> Optional[Slot]:
        for keyword, sort in _SORT_KEYWORDS.items():
            if keyword in query:
                return Slot("sort_by", sort, 0.9, keyword)
        return None

    def _extract_limit(self, query: str) -> Optional[Slot]:
        m = _LIMIT_PATTERN.search(query)
        if m:
            return Slot("limit", int(m.group(1)), 0.95, m.group())
        return None

    # ─── 中心/部门提取 ─────────────────────────────

    def _extract_org(self, query: str) -> Tuple[Optional[Slot], Optional[Slot]]:
        """提取中心/部门
        简化：识别 "XX中心" "XX部" 等关键词
        """
        center_m = re.search(r"([\u4e00-\u9fff]{2,8})中心", query)
        if center_m:
            return Slot("center", center_m.group(1), 0.85, center_m.group()), None

        dept_m = re.search(r"([\u4e00-\u9fff]{2,8})(部|部门|科室|组)", query)
        if dept_m:
            return None, Slot("department", dept_m.group(1), 0.85, dept_m.group())

        return (None, None)

    # ─── 意图提示 ───────────────────────────────────

    def _detect_intent_hint(self, query: str, slots: Dict[str, Slot]) -> str:
        """基于槽位推断意图提示（增强 IntentClassifier）"""
        if "period" not in slots:
            return ""
        scope = slots.get("scope")
        if scope:
            if scope.value == "overrun":
                return "alert_query"
            if scope.value == "anomaly":
                return "expense_query"

        if "amount" in str(slots) or "amount_min" in slots or "amount_max" in slots:
            return "expense_query"

        return ""

    # ─── 主入口 ─────────────────────────────────────

    def extract(self, query: str) -> ExtractionResult:
        """提取所有槽位"""
        result = ExtractionResult()

        # 1. 期间
        period, ptype, _ = self._extract_period(query)
        if period:
            result.slots["period"] = period
        if ptype:
            result.slots["period_type"] = ptype

        # 2. 金额范围
        _, amt_min, amt_max = self._extract_amount(query)
        if amt_min:
            result.slots["amount_min"] = amt_min
        if amt_max:
            result.slots["amount_max"] = amt_max

        # 3. 范围/排序/限制
        scope = self._extract_scope(query)
        if scope:
            result.slots["scope"] = scope
        sort_by = self._extract_sort(query)
        if sort_by:
            result.slots["sort_by"] = sort_by
        limit = self._extract_limit(query)
        if limit:
            result.slots["limit"] = limit

        # 4. 中心/部门
        center, dept = self._extract_org(query)
        if center:
            result.slots["center"] = center
        if dept:
            result.slots["department"] = dept

        # 5. 意图提示
        result.intent_hint = self._detect_intent_hint(query, result.slots)

        return result

    def to_dict(self, result: ExtractionResult) -> Dict[str, Any]:
        """转字典（用于传参）"""
        return {
            "slots": {
                k: {"value": v.value, "confidence": v.confidence, "raw_text": v.raw_text}
                for k, v in result.slots.items()
            },
            "intent_hint": result.intent_hint,
            "missing_slots": result.missing_slots,
        }
