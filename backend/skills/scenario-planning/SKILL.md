---
name: scenario-planning
description: 情景规划与弹性预算技能，支持多情景预算编制、弹性调整、压力测试和紧急调拨
intent: scenario_query
mode: branch
activated_rules:
  - HR-019
  - HR-020
  - HR-021
  - HR-022
activated_objects:
  - obj_scenario
  - obj_scenario_assumption
  - obj_elastic_budget
  - obj_budget_reserve
activated_behaviors:
  - fin.scenario.create
  - fin.scenario.compare
  - fin.scenario.elastic_adjust
  - fin.scenario.stress_test
  - fin.scenario.emergency_allocate
---

# 情景规划与弹性预算

## 核心能力
- 情景创建：定义乐观/基准/悲观/压力测试情景
- 情景对比：多情景预算对比分析
- 弹性调整：基于实际业务量自动调整预算额度（±30%上限）
- 压力测试：极端情景下的财务压力测试
- 紧急调拨：从预算储备金紧急调拨资金

## 硬规则
- HR-019: 每个预算周期必须至少编制基准+悲观两个情景
- HR-020: 弹性预算调整幅度不得超过基准预算的±30%
- HR-021: 紧急调拨须经管委会批准，5个工作日内补办正式手续
- HR-022: 压力测试必须覆盖收入下降30%+成本上升20%的极端情景

## 方法论参考

| 方法论 | 引用原因 |
|--------|---------|
| CFO分析问题定义标准 | 情景规划需从战略层视角定义情景假设，明确各情景的业务对象、时间粒度和分析维度 |
| CFO指标定义与数据口径标准 | 多情景预算对比需使用标准执行率口径和象限执行率预期值，确保不同情景间指标口径可比 |
