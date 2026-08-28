---
name: cash-flow-monitor
description: 现金流双线监控技能，支持现金流预测、流动性缺口检查、利润现金流差异分析和收支匹配分析
intent: cash_flow_query
mode: branch
activated_rules:
  - HR-016
  - HR-017
  - HR-018
activated_objects:
  - obj_cash_flow_plan
  - obj_cash_pool
  - obj_payment_schedule
  - obj_receipt_forecast
activated_behaviors:
  - fin.cashflow.forecast
  - fin.cashflow.liquidity_alert
  - fin.cashflow.profit_cash_gap
  - fin.cashflow.receipt_payment_match
---

# 现金流双线监控

## 核心能力
- 现金流预测：基于收入预算+支出预算+历史付款模式，预测未来3/6/12个月现金流
- 流动性缺口检查：当预测现金流低于安全阈值时触发预警
- 利润vs现金流差异分析：分析利润与现金流的差异来源（应收/应付/折旧/摊销）
- 收支匹配分析：分析收入与支出的时间差，识别流动性风险窗口

## 硬规则
- HR-016: 现金流预测必须区分经营/投资/筹资三类活动
- HR-017: 当月经营性现金流预测为负时，必须触发资金缺口预警
- HR-018: 付款排期不得早于审批完成日期，不得晚于合同约定付款日

## 交互规范
1. 现金流数据需标注活动类型和期间
2. 流动性缺口需给出具体金额和建议
3. 利润现金流差异需分解差异来源
4. 收支匹配需按周/月展示时间差

## 方法论参考

| 方法论 | 引用原因 |
|--------|---------|
| CFO指标定义与数据口径标准 | 现金流监控需使用标准现金流指标口径（经营性现金流执行率、现金执行率、现金流偏差），确保与预算执行率口径一致 |
| CFO预警响应标准 | 流动性缺口和现金流异常需按预警分级标准触发预警，确保资金风险及时响应和升级 |
