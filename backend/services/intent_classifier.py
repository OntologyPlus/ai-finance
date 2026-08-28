from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from loguru import logger


_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "budget_query": ["预算", "额度", "授予", "A类", "B类", "象限", "编制", "冻结", "释放", "年度预算", "预算科目"],
    "expense_query": ["报销", "费用", "核销", "发票", "审批", "支出", "管控路由", "组织线", "法人线"],
    "alert_query": ["预警", "偏差", "执行率", "滚动预测", "里程碑", "蓝色", "黄色", "红色", "升级", "闭环"],
    "analysis_query": ["分析", "3GAP", "3List", "差距", "必赢", "改善", "资源清单", "执行率分析"],
    "report_query": ["报表", "快报", "月报", "季报", "年报", "报告", "汇报"],
    "pdca_query": ["PDCA", "复盘", "闭环率", "改进", "检查", "总结"],
    "ontology_query": ["本体", "对象", "关系", "行为", "规则", "场景", "定义"],
    "cash_flow_query": ["现金流", "资金", "流动性", "付款排期", "收款", "资金池", "收支"],
    "scenario_query": ["情景", "场景规划", "弹性预算", "压力测试", "紧急调拨", "乐观", "悲观", "基准"],
    "impact_query": ["影响评估", "全链路", "影响分析"],
    "zbb_query": ["零基", "零基预算", "零基审视", "决策包", "决策单元"],
    "cost_center_query": ["成本中心", "标准成本", "差异分析", "成本分摊", "内部结算"],
    "hcp_query": ["HCP", "医疗卫生专业人士", "合规审查", "学术推广", "讲课费"],
    "pipeline_query": ["管线", "研发管线", "临床试验", "CRO", "多中心", "Go/No-Go"],
    "meeting_query": ["经营分析会", "会议决议", "一报一会", "三聚焦", "决议追踪"],
}

_INTENT_LABELS = list(_INTENT_KEYWORDS.keys()) + ["general"]


class IntentClassifier:
    def __init__(self) -> None:
        self._idf: Dict[str, float] = {}
        self._doc_freq: Counter = Counter()
        self._doc_count = 0
        self._vocabulary: set[str] = set()
        self._trained = False
        self._train()

    def _train(self) -> None:
        docs: List[Tuple[str, str]] = []
        for intent, keywords in _INTENT_KEYWORDS.items():
            for keyword in keywords:
                docs.append((intent, keyword))

        self._doc_count = len(docs)
        self._doc_freq = Counter()
        for _, text in docs:
            tokens = self._tokenize(text)
            seen = set(tokens)
            for token in seen:
                self._doc_freq[token] += 1
            self._vocabulary.update(tokens)

        self._idf = {}
        for token in self._vocabulary:
            df = self._doc_freq.get(token, 0)
            self._idf[token] = math.log((self._doc_count + 1) / (df + 1)) + 1

        self._intent_vectors: Dict[str, Dict[str, float]] = {}
        for intent in _INTENT_KEYWORDS:
            vec: Dict[str, float] = {}
            for keyword in _INTENT_KEYWORDS[intent]:
                tokens = self._tokenize(keyword)
                for token in tokens:
                    vec[token] = vec.get(token, 0) + 1
            for token in vec:
                vec[token] *= self._idf.get(token, 1.0)
            norm = sum(v * v for v in vec.values()) ** 0.5
            if norm > 0:
                for token in vec:
                    vec[token] /= norm
            self._intent_vectors[intent] = vec

        self._trained = True

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)
        bigrams = [tokens[i] + tokens[i + 1] for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def _text_to_vector(self, text: str) -> Dict[str, float]:
        tokens = self._tokenize(text)
        vec: Dict[str, float] = {}
        for token in tokens:
            vec[token] = vec.get(token, 0) + 1
        for token in vec:
            vec[token] *= self._idf.get(token, 1.0)
        norm = sum(v * v for v in vec.values()) ** 0.5
        if norm > 0:
            for token in vec:
                vec[token] /= norm
        return vec

    def _cosine_sim(self, a: Dict[str, float], b: Dict[str, float]) -> float:
        common = set(a.keys()) & set(b.keys())
        if not common:
            return 0.0
        return sum(a[k] * b[k] for k in common)

    async def classify(self, text: str) -> Tuple[str, float]:
        rule_result = self._tfidf_classify(text)
        llm_result = await self._llm_classify(text)
        return self._resolve_conflict(rule_result, llm_result)

    def _tfidf_classify(self, text: str) -> Tuple[str, float]:
        if not self._trained or not text.strip():
            return ("general", 0.0)

        text_vec = self._text_to_vector(text)
        scores: Dict[str, float] = {}

        for intent, intent_vec in self._intent_vectors.items():
            scores[intent] = self._cosine_sim(text_vec, intent_vec)

        if not scores:
            return ("general", 0.0)

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        return (best_intent, min(best_score, 1.0))

    async def _llm_classify(self, text: str) -> Tuple[str, float]:
        direct_match = self._direct_keyword_match(text)
        if direct_match[1] > 0.5:
            return direct_match

        try:
            from utils.llm_client import get_llm_client
            llm = get_llm_client()

            categories = ", ".join(_INTENT_LABELS)
            prompt = (
                f"请将以下用户输入分类到最匹配的意图类别中。\n"
                f"可选类别：{categories}\n"
                f"用户输入：{text}\n"
                f"请只输出类别名称和置信度(0-1)，格式：类别|置信度"
            )

            messages = [{"role": "user", "content": prompt}]
            response = await llm.invoke(messages, temperature=0)
            content = response.content.strip()

            match = re.match(r"(\w+)\s*[|,，]\s*([\d.]+)", content)
            if match:
                intent = match.group(1)
                confidence = float(match.group(2))
                if intent in _INTENT_LABELS:
                    return (intent, confidence)
        except Exception as e:
            logger.debug(f"LLM classification fallback: {e}")

        return ("general", 0.3)

    def _direct_keyword_match(self, text: str) -> Tuple[str, float]:
        scores: Dict[str, float] = {}
        for intent, keywords in _INTENT_KEYWORDS.items():
            score = 0.0
            for keyword in keywords:
                if keyword in text:
                    score += 1.0
            if score > 0:
                scores[intent] = score / len(keywords)

        if not scores:
            return ("general", 0.0)

        best = max(scores, key=scores.get)
        return (best, min(scores[best] * 2, 1.0))

    def _resolve_conflict(
        self,
        rule_result: Tuple[str, float],
        llm_result: Tuple[str, float],
    ) -> Tuple[str, float]:
        rule_intent, rule_conf = rule_result
        llm_intent, llm_conf = llm_result

        if rule_intent == llm_intent:
            return (rule_intent, max(rule_conf, llm_conf))

        # 加权仲裁：TF-IDF 0.4, LLM 0.6
        rule_score = rule_conf * 0.4
        llm_score = llm_conf * 0.6

        return rule_result if rule_score > llm_score else llm_result
