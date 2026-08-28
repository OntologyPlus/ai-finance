# 集团财经管理体系：AI原生一体化系统设计

---

## 一、引言与设计哲学

### 1.1 为什么需要AI原生一体化系统

集团财经管理体系已建立从战略制定到次年采集的八阶段端到端流程，但在实际运行中，每个阶段都存在"人推动系统"的痛点。更深层的问题是：现有系统分散在多个独立平台，数据孤岛、流程断裂、口径不一致成为常态，导致财经管理体系的八阶段流程无法形成真正的闭环。

**八阶段痛点诊断**：

| 阶段 | 现状痛点 | AI原生一体化解法 |
|------|---------|----------------|
| 阶段一：SP+BP | 战略解码依赖人工对齐，预算与战略意图的映射关系靠经验判断 | AI自动匹配战略举措与预算项目，象限归属智能推荐 |
| 阶段二：预算授予 | A/B分类判定靠人工，B→A转换追踪靠Excel | AI自动分类+里程碑追踪+自动提醒转换 |
| 阶段三：费用报销 | 四级管控路由靠人记忆，双线审批靠流程引擎硬编码 | AI自动识别L3管控标签→路由审批→额度校验 |
| 阶段四：经营分析 | 数据汇总靠手工，3GAP+3List分析靠经验 | AI自动汇总+3GAP归因+3List归类+一报一会编制 |
| 阶段五：实时预警 | 三种通用规则+L1专项规则靠人工巡检，闭环靠催办 | AI自动扫描+四色分级推送+双签闭环+超时升级 |
| 阶段六：PDCA | 3GAP+3List工具使用不充分，调拨建议靠经验 | AI辅助3GAP分析+调拨建议+象限内/跨象限自动判断 |
| 阶段七：报表出具 | 三报一会编制耗时，数据口径靠人工核对 | AI自动编制+数据唯一性校验+5/8/10日截点提醒 |
| 阶段八：次年采集 | 未关闭预警梳理靠人工，复盘结论落地靠记忆 | AI自动梳理+反向输入+新循环启动 |

**系统分散导致的深层痛点**：

| 问题 | 具体表现 | 一体化系统解法 |
|------|---------|--------------|
| 数据孤岛 | 预算数据在预算管理系统、报销数据在ERP、报表数据在帆软，三套数据口径需人工对齐 | 本系统统一数据模型，数据天然同源，不存在口径对齐问题 |
| 流程断裂 | 报销审批在ERP完成，预算核销需调用预算管理系统，两步操作跨系统拼接 | 本系统内报销审批→预算核销一条链完成，流程天然连贯 |
| 响应延迟 | 从外部系统同步数据存在延迟，预警扫描依赖定时任务 | 本系统数据实时更新，事件驱动即时响应 |
| 新场景受限 | 新增预警规则需外部系统配合开发，响应周期长 | 本系统内AI组装原子规则，新场景分钟级响应 |

### 1.2 设计哲学：为大模型服务的本体

**核心原则一：本体只管"定义"，大模型负责"推理"**

本体只管"定义"——用清晰、无歧义、带业务语义的方式，说清楚有哪些对象、它们在什么场景下有什么关系、能发生哪些行为、规则是什么。大模型负责"推理"——面对一个具体情境时，由它去匹配场景、挑出相关的对象/关系/规则、把它们灵活组装成推理链、套用、给出结论。

**核心原则二：评判标准从"可判定"变为"可评测"，用"可追溯"替代"可判定"**

放弃确定性推理机，意味着不再有逻辑保证。"本体好不好"就不能靠逻辑一致性来证明了，只能靠经验——靠一套"场景→期望结论"的评测集，看大模型在关心的那些场景上表现稳不稳。评测集从一开始就是一等公民，而不是事后补丁。同时，要求大模型把推理过程显式吐出来——它匹配了哪个场景、激活了哪几条规则、按什么顺序套、每步的中间结论是什么——这样哪怕结果有波动，整个过程也是看得见、查得到、能复盘的。

**核心原则三：规则原子化，推理组装化**

传统规则引擎将复合逻辑写在单条规则中，大模型在长链推理中容易丢条件。AI原生体系下，每条规则只管一跳、只做一个最小判断；复合效果由大模型把多条原子规则一条条串起来产生。推理链是"组装"出来的，不是藏在单条规则里的。

以费用报销为例，传统方式是一条大规则"报销提交→校验预算ID→判断管控级别→路由审批→核销额度"，AI原生方式是拆成5条原子规则由大模型组装：

```
① [fin.budget.no_id_reject / HR-001] 无预算ID → 系统拦截
② [fin.control.route] L3管控标签 → 路由到对应审批模式
③ [fin.budget.balance_check / HR-002] 额度校验 → 是否超预算
④ [fin.approval.dual_line] 双线审批 → 先组织线后法人线
⑤ [fin.budget.write_off] 审批完成 → 核销额度
```

**核心原则四：确定性引擎只做门闩与审计，不替代大模型组装推理**

硬规则（HR-*）和 SoD 在**写路径**上由 `HardRuleEngine` / `SoDEnforcer` 强制执行，不把合规底线交给 LLM 临场判断。这与原则一不矛盾：复合场景（诊断、调拨建议、根因）仍由大模型按原子规则组装；引擎只保证「无预算不得提交」这类红线。每次改变世界状态（或被门闩拦住）写入 `DecisionRecord`——事后审计对象，不是 `DecisionSandbox` 那种事前试运行。评测集与推理轨迹（ReasoningTrace）仍是一等公民；Decision 补的是「谁批的、挂了哪条预算、命中哪些 HR」。

MySQL 是业务事实的 system of record。图（Memory + 可选 Neo4j）是投影：实例增量 upsert / tombstone，禁止全量删图。FinanceAgent 不持有图数据库连接。

---

## 二、系统数据模型

本章定义AI原生一体化系统的核心数据结构。所有业务引擎共享同一套数据模型，不存在数据孤岛。

### 2.1 核心数据实体与关系

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌──────────┐     驱动      ┌──────────┐     解码     ┌──────────┐  │
│  │ SP战略规划 │ ──────────→ │ BP年度计划 │ ──────────→ │ 战略举措  │  │
│  └──────────┘              └──────────┘              └────┬─────┘  │
│                                                           │        │
│                                                    对标   │        │
│                                                           ▼        │
│  ┌──────────┐     归属     ┌──────────┐     包含     ┌──────────┐  │
│  │   象限    │ ←────────── │ 预算项目  │ ←────────── │ L1科目   │  │
│  └──────────┘              └────┬─────┘              │ (B1-B9)  │  │
│                                 │                     └────┬─────┘  │
│                      挂载       │  冻结/释放               │包含    │
│                                 │                          ▼        │
│  ┌──────────┐              ┌────▼─────┐              ┌──────────┐  │
│  │ 预算额度  │ ←────────── │ 预算额度  │              │ L2科目   │  │
│  │ (A/B分类) │              │ 记录表   │              └────┬─────┘  │
│  └──────────┘              └──────────┘                    │包含    │
│                                                           ▼        │
│  ┌──────────┐     关联     ┌──────────┐              ┌──────────┐  │
│  │  报销单   │ ──────────→ │ 预算项目  │              │ L3科目   │  │
│  └────┬─────┘              └──────────┘              └────┬─────┘  │
│       │                                                   │        │
│  触发 │                                              管控  │        │
│       ▼                                                   ▼        │
│  ┌──────────┐     响应     ┌──────────┐     路由     ┌──────────┐  │
│  │ 预警记录  │ ──────────→ │   角色    │ ←────────── │管控标签  │  │
│  └────┬─────┘              └──────────┘              └──────────┘  │
│       │                                                             │
│  升级 │     确认                                                    │
│       ▼                                                             │
│  ┌──────────┐     双签     ┌──────────┐                            │
│  │预警升级   │             │闭环档案   │                            │
│  │记录表     │             │          │                            │
│  └──────────┘              └──────────┘                            │
│                                                                      │
│  ┌──────────┐     审批     ┌──────────┐                            │
│  │ 审批记录  │ ←────────── │  报销单   │                            │
│  │ (双线)   │              └──────────┘                            │
│  └──────────┘                                                       │
│                                                                      │
│  ┌──────────┐     B→A     ┌──────────┐                            │
│  │B→A转换   │ ──────────→ │ 预算项目  │                            │
│  │记录表    │              │(A/B类别)  │                            │
│  └──────────┘              └──────────┘                            │
│                                                                      │
│  ┌──────────┐     来源     ┌──────────┐                            │
│  │  报表    │ ←────────── │ 经营分析  │                            │
│  │(三报一会) │              │ 数据     │                            │
│  └──────────┘              └──────────┘                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

另有 `decision_record` 表记录改变世界状态的决策（提交/审批/核销/授予/调拨/预警闭环，以及被硬规则拦住的尝试）。图侧投影为 `:Decision` 节点，不替代上图业务实体。

### 2.2 预算科目体系（B1-B9 + L2 + L3）

**关键约束：预算管控到L3，报销管控到L2。**

#### 2.2.1 九个L1科目完整数据表结构

```yaml
budget_subject_l1:
  table: budget_subject_l1
  description: "一级预算科目大类，共9个"
  fields:
    - name: l1_code
      type: string(2)
      description: "L1科目编码"
      constraints: [primary_key, enum(B1,B2,B3,B4,B5,B6,B7,B8,B9)]
    - name: l1_name
      type: string(50)
      description: "L1科目名称"
    - name: management_mode
      type: enum(项目化管理, 通用管控, 合规导向)
      description: "管控模式"
    - name: alert_rule_type
      type: enum(通用规则, 通用+专项)
      description: "预警规则类型"
    - name: has_l2
      type: boolean
      description: "是否含L2子类"
    - name: description
      type: text
      description: "自然语言定义"
```

| L1编码 | L1名称 | 管控模式 | 预警规则 | 含L2子类 | 自然语言定义 |
|--------|--------|---------|---------|---------|------------|
| B1 | 资本支出 | 项目化管理 | 通用+里程碑专项+B1专项 | 是(3个L2) | 固定资产购置、基建等资本性支出，绑定项目ID，按里程碑阶段管控 |
| B2 | 研发支出 | 项目化管理 | 通用+里程碑专项+研发阶段专项 | 否 | 药品研发全周期支出，按IND/NDA/III期临床/上市后研究分阶段管控 |
| B3 | 维持性支出 | 通用管控 | 通用规则 | 否 | 日常运营维持性支出，按月度/季度执行进度管控 |
| B4 | 税务支出 | 合规导向 | 通用+税务合规专项 | 否 | 法定税务支出，合规优先不控费用，月度申报缴纳延迟预警 |
| B5 | 市场推广支出 | 通用管控 | 通用+ROI专项 | 是(6个L2) | 市场推广全链条支出，按L2分类ROI预警，单场活动费用预警 |
| B6 | 人力成本支出 | 通用管控 | 通用+编制联动专项 | 否 | 人力成本全口径支出，编制预警与工资预算联动 |
| B7 | 货物支出 | 通用管控 | 通用+供应商专项 | 是(3个L2) | 货物采购及加工支出，通用管控，供应商维度预警 |
| B8 | 股权投资支出 | 项目化管理 | 通用+投资阶段专项 | 否 | 股权投资全周期支出，单笔超500万红色预警，投资阶段专用阈值 |
| B9 | 财务费用 | 通用管控 | 通用规则 | 否 | 利息、汇兑等财务费用，通用管控 |

#### 2.2.2 L2子类数据结构

B1资本支出含3个L2子类：

| L2编码 | L2名称 | 归属L1 | 特殊规则 |
|--------|--------|--------|---------|
| B1-01 | 无形资产支出 | B1 | 单笔超年度预算×110%黄色、×130%红色；专利/软件License续期须提前60天预算确认 |
| B1-02 | 工程支出 | B1 | 预付款不超合同×30%；工程变更超原合同×10%须重新审批；超年度预算×120%黄色、×150%红色；竣工后60天内须完成结算审计 |
| B1-03 | 固定资产支出 | B1 | 单台设备超年度预算×120%黄色、×150%红色；进口设备须提前90天完成关税汇率评估 |

B5市场推广支出含6个L2子类：

| L2编码 | L2名称 | 归属L1 | ROI预警阈值 | 特殊规则 |
|--------|--------|--------|-----------|---------|
| B5-01 | 销售驱动类 | B5 | ROI实际值＜目标值×80%→蓝色 | 活动结束后15个工作日内提交效果评估报告 |
| B5-02 | 市场驱动类 | B5 | ROI实际值＜目标值×70%→蓝色 | 须提交专项分析报告 |
| B5-03 | 医学驱动类 | B5 | 费用人均超会议预算×115%→黄色；单次KOL维护费用超年度预算×150%→红色 | 参会人数低于确认人数×70%→蓝色 |
| B5-04 | 患者驱动类 | B5 | 实际入组患者人数超项目预算×110%→黄色；超×130%→红色 | — |
| B5-05 | 政策驱动类 | B5 | 单项政策研究费用超课题预算×120%→黄色 | 季度汇报缺席→蓝色 |
| B5-06 | 开发驱动类 | B5 | 单笔开发费用超课题预算×130%→黄色；超×160%→红色 | — |

B7货物支出含3个L2子类：

| L2编码 | L2名称 | 归属L1 | 特殊规则 |
|--------|--------|--------|---------|
| B7-01 | 成品采购 | B7 | 供应商维度预警 |
| B7-02 | 委托加工 | B7 | 供应商维度预警 |
| B7-03 | 自主生产 | B7 | 通用管控 |

B6人力成本支出不含L2子类，工资类/社保公积金/奖金及可变薪酬为专项预警规则中的分类，非L2子类：

| L2编码 | L2名称 | 归属L1 | 特殊规则 |
|--------|--------|--------|---------|
| B6-01 | 工资类（固定薪酬） | B6 | 每月实际发放不得超出月度预算×105% |
| B6-02 | 社保公积金 | B6 | 实际缴费基数超申报基数×105%→蓝色 |
| B6-03 | 奖金及可变薪酬 | B6 | 年终奖金须在12月15日前锁定预算 |

#### 2.2.3 L3最小管控单元

```yaml
budget_subject_l3:
  table: budget_subject_l3
  description: "三级最小管控单元，独立编号，携带管控标签"
  fields:
    - name: l3_code
      type: string(10)
      description: "L3科目编码"
      constraints: [primary_key]
    - name: l3_name
      type: string(100)
      description: "L3科目名称"
    - name: l2_code
      type: string(5)
      description: "归属L2编码"
      constraints: [foreign_key → budget_subject_l2.l2_code]
    - name: l1_code
      type: string(2)
      description: "归属L1编码"
      constraints: [foreign_key → budget_subject_l1.l1_code]
    - name: control_tag
      type: enum(强管控, 中心弱管控, 组合管控, 不管控)
      description: "管控级别标签，决定审批路由"
    - name: variety_group
      type: string(20)
      description: "品种组编码，四级管控的品种组维度"
    - name: is_project_managed
      type: boolean
      description: "是否项目化管理（绑定项目ID）"
    - name: alert_rules
      type: json
      description: "适用的预警规则ID列表"
```

**L3科目归属说明**：L3科目按业务属性归属L1，一级预算科目类别划分不等同于三级预算科目的固定从属关系。同一L1下的L3科目可具有不同的管控标签和业务属性，L3科目的归属由其业务实质决定而非简单的层级包含关系。

### 2.3 A/B两类预算数据模型

#### 2.3.1 A类预算：立项即全额授予

```yaml
budget_item:
  table: budget_item
  description: "预算项目主表"
  fields:
    - name: budget_id
      type: string(20)
      description: "预算项目唯一标识"
      constraints: [primary_key]
    - name: budget_name
      type: string(200)
      description: "预算项目名称"
    - name: budget_category
      type: enum(A, B)
      description: "A/B类别"
    - name: l1_code
      type: string(2)
      description: "归属L1科目"
    - name: l2_code
      type: string(5)
      description: "归属L2科目"
    - name: l3_code
      type: string(10)
      description: "归属L3科目"
    - name: quadrant
      type: enum(发展, 收缩, 稳定, 探索)
      description: "象限归属"
    - name: strategy_initiative_id
      type: string(20)
      description: "对标战略举措编号"
    - name: annual_amount
      type: decimal(15,2)
      description: "年度预算总额"
    - name: granted_amount
      type: decimal(15,2)
      description: "已授予额度"
    - name: frozen_amount
      type: decimal(15,2)
      description: "已冻结额度"
    - name: used_amount
      type: decimal(15,2)
      description: "已使用（核销）额度"
    - name: available_amount
      type: decimal(15,2)
      description: "可用额度 = granted_amount - frozen_amount - used_amount"
    - name: grant_percentage
      type: decimal(5,2)
      description: "授予比例（A类=100%，B类=0%）"
    - name: status
      type: enum(编制中, 待审批, 已授予, 执行中, 已冻结, 已核销, 已取消)
      description: "预算项目状态"
    - name: center_id
      type: string(10)
      description: "归属中心"
    - name: department_id
      type: string(10)
      description: "归属部门"
    - name: project_id
      type: string(20)
      description: "关联项目ID（项目化管理科目）"
    - name: pending_project_budget_id
      type: string(20)
      description: "暂存项目预算ID（B类预算专用，B→A转换后转为正式预算ID）"
    - name: created_at
      type: timestamp
      description: "创建时间"
    - name: updated_at
      type: timestamp
      description: "更新时间"
```

**A类预算关键约束**：

- 立项审批通过后，`grant_percentage` = 100%，`granted_amount` = `annual_amount`
- `frozen_amount` = `granted_amount`，额度全额锁定
- 不可超支，超预算须申请增补
- 状态流转：编制中 → 待审批 → 已授予（全额冻结）→ 执行中 → 已核销

#### 2.3.2 B类预算：年初授予0%，按进展B→A转换

**B类预算关键约束**：

- 年初判定为B类后，`grant_percentage` = 0%，`granted_amount` = 0
- B类额度不可用于报销，须完成B→A转换后方可使用
- 季度里程碑验证达标后，可申请B→A转换
- 转换后`grant_percentage` = 100%，`frozen_amount` = `annual_amount`
- B类冻结额度＞A类执行额30%时触发蓝色预警（膨胀监控）
- B类预算须关联暂存项目预算ID（`pending_project_budget_id`），用于标识B类预算所暂存的项目，B→A转换后该ID转为正式预算ID

#### 2.3.3 B→A转换记录表

```yaml
b2a_conversion:
  table: b2a_conversion
  description: "B类预算转A类的转换记录"
  fields:
    - name: conversion_id
      type: string(20)
      description: "转换记录编号"
      constraints: [primary_key]
    - name: budget_id
      type: string(20)
      description: "预算项目ID"
      constraints: [foreign_key → budget_item.budget_id]
    - name: conversion_date
      type: date
      description: "转换日期"
    - name: milestone_evidence
      type: text
      description: "里程碑达标证据"
    - name: milestone_period
      type: enum(Q1, Q2, Q3, Q4)
      description: "里程碑验证季度"
    - name: approver
      type: string(50)
      description: "审批人"
    - name: approval_status
      type: enum(待审批, 已通过, 已驳回)
      description: "审批状态"
    - name: pre_category
      type: enum(B)
      description: "转换前类别（固定为B）"
    - name: post_category
      type: enum(A)
      description: "转换后类别（固定为A）"
    - name: frozen_amount
      type: decimal(15,2)
      description: "转换后冻结额度"
    - name: report_to_committee
      type: boolean
      description: "是否已向管委会提交专项报告"
    - name: created_at
      type: timestamp
      description: "创建时间"
```

### 2.4 四级管控模式数据模型

#### 2.4.1 管控模式定义

```yaml
control_mode:
  table: control_mode
  description: "四级管控模式定义"
  records:
    - mode: 强管控
      code: STRONG
      cross_dept_allowed: false
      cross_category_allowed: false
      cross_variety_group_allowed: false
      over_budget_action: "须申请增补预算"
      description: "不可跨部门、不可跨费用类别、不可跨品种组，超预算须增补"
    - mode: 中心弱管控
      code: WEAK_CENTER
      cross_dept_allowed: true
      cross_category_allowed: false
      cross_variety_group_allowed: false
      over_budget_action: "须财经BP+中心GM审批"
      description: "中心内可跨部门，不可跨费用类别、不可跨品种组"
    - mode: 组合管控
      code: COMBINED
      cross_dept_allowed: true
      cross_category_allowed: true
      cross_variety_group_allowed: false
      over_budget_action: "须财经BP+中心GM审批"
      description: "中心内可跨部门+费用类别，不可跨品种组"
    - mode: 不管控
      code: NONE
      cross_dept_allowed: true
      cross_category_allowed: true
      cross_variety_group_allowed: true
      over_budget_action: "无需预算即可使用"
      description: "无限制"
```

#### 2.4.2 管控模式约束规则

| 管控模式 | 可否跨部门 | 可否跨费用类别 | 可否跨品种组 | 超预算处理 | 审批要求 |
|---------|----------|-------------|------------|----------|---------|
| 强管控 | ✗ | ✗ | ✗ | 须申请增补预算 | 标准双线审批 |
| 中心弱管控 | ✓（中心内） | ✗ | ✗ | 须财经BP+中心GM审批 | BP+中心GM审批 |
| 组合管控 | ✓（中心内） | ✓（中心内） | ✗ | 须财经BP+中心GM审批 | BP+中心GM审批 |
| 不管控 | ✓ | ✓ | ✓ | 无需预算即可使用 | 无需审批 |

#### 2.4.3 L3科目与管控标签映射

```yaml
l3_control_mapping:
  description: "L3科目与管控标签的映射关系"
  examples:
    - l3_code: "B3-01-001"
      l3_name: "招待费"
      control_tag: "强管控"
    - l3_code: "B3-01-002"
      l3_name: "培训费"
      control_tag: "中心弱管控"
    - l3_code: "B3-01-003"
      l3_name: "综合管理费"
      control_tag: "组合管控"
    - l3_code: "B3-01-004"
      l3_name: "折旧费"
      control_tag: "不管控"
```

### 2.5 双线审批数据模型

#### 2.5.1 审批线路定义

**组织管理线**：申请人 → 部门负责人 → 中心总经理

**法人架构线**：法人组织财务负责人 → 法人或授权人

**关键规则**：先走组织管理线，后走法人架构线。双线审批全部通过后方可核销预算。

#### 2.5.2 审批记录表

```yaml
approval_record:
  table: approval_record
  description: "双线审批记录表"
  fields:
    - name: approval_id
      type: string(20)
      description: "审批记录编号"
      constraints: [primary_key]
    - name: expense_id
      type: string(20)
      description: "报销单号"
      constraints: [foreign_key → expense_report.expense_id]
    - name: approval_line
      type: enum(组织管理线, 法人架构线)
      description: "审批线路"
    - name: approval_step
      type: integer
      description: "审批步骤序号"
    - name: approver_id
      type: string(20)
      description: "审批人ID"
    - name: approver_role
      type: enum(部门负责人, 中心总经理, 法人财务负责人, 法人或授权人)
      description: "审批人角色"
    - name: approval_action
      type: enum(通过, 驳回, 待审批)
      description: "审批动作"
    - name: approval_comment
      type: text
      description: "审批意见"
    - name: approved_at
      type: timestamp
      description: "审批时间"
    - name: deadline
      type: timestamp
      description: "审批截止时间"
    - name: is_overdue
      type: boolean
      description: "是否超时"
```

#### 2.5.3 审批流程状态机

```
报销单提交
    │
    ▼
┌─────────────────┐
│ 组织管理线-步骤1 │  申请人 → 部门负责人
│ 部门负责人审批   │
└────────┬────────┘
         │ 通过
         ▼
┌─────────────────┐
│ 组织管理线-步骤2 │  部门负责人 → 中心总经理
│ 中心总经理审批   │
└────────┬────────┘
         │ 通过
         ▼
┌─────────────────┐
│ 法人架构线-步骤1 │  法人组织财务负责人
│ 法人财务负责人   │
└────────┬────────┘
         │ 通过
         ▼
┌─────────────────┐
│ 法人架构线-步骤2 │  法人或授权人
│ 法人或授权人审批 │
└────────┬────────┘
         │ 通过
         ▼
┌─────────────────┐
│ 双线审批完成     │  → 触发预算核销
└─────────────────┘
```

### 2.6 预警数据模型

#### 2.6.1 预警记录表

```yaml
alert_record:
  table: alert_record
  description: "预警记录主表"
  fields:
    - name: alert_id
      type: string(20)
      description: "预警编号"
      constraints: [primary_key]
    - name: alert_level
      type: enum(蓝色, 黄色, 橙色, 红色)
      description: "预警级别"
    - name: alert_type
      type: enum(月度执行进度, 季度滚动预测, 里程碑, L1专项)
      description: "预警类型"
    - name: alert_status
      type: enum(开放, 响应中, 待闭环确认, 已闭环, 已升级)
      description: "预警状态"
    - name: l1_code
      type: string(2)
      description: "关联L1科目"
    - name: l2_code
      type: string(5)
      description: "关联L2科目"
    - name: l3_code
      type: string(10)
      description: "关联L3科目"
    - name: budget_id
      type: string(20)
      description: "关联预算ID"
    - name: project_id
      type: string(20)
      description: "关联项目ID（里程碑预警）"
    - name: trigger_value
      type: decimal(15,2)
      description: "触发值"
    - name: threshold_value
      type: decimal(15,2)
      description: "阈值"
    - name: deviation_rate
      type: decimal(5,2)
      description: "偏离率(%)"
    - name: responsible_person
      type: string(50)
      description: "责任人"
    - name: response_deadline
      type: timestamp
      description: "响应截止时间"
    - name: response_hours
      type: integer
      description: "响应时限（小时）"
    - name: notification_targets
      type: json
      description: "通知对象列表"
    - name: created_at
      type: timestamp
      description: "预警创建时间"
    - name: updated_at
      type: timestamp
      description: "最后更新时间"
```

#### 2.6.2 预警闭环档案

```yaml
alert_closure:
  table: alert_closure
  description: "预警闭环档案"
  fields:
    - name: closure_id
      type: string(20)
      description: "闭环档案编号"
      constraints: [primary_key]
    - name: alert_id
      type: string(20)
      description: "预警编号"
      constraints: [foreign_key → alert_record.alert_id]
    - name: business_response
      type: text
      description: "业务单元整改方案（含原因分析、已采取措施、预期关闭时间）"
    - name: business_responder
      type: string(50)
      description: "业务响应人"
    - name: business_response_at
      type: timestamp
      description: "业务响应时间"
    - name: bp_confirmation
      type: text
      description: "财经BP确认意见"
    - name: bp_confirmer
      type: string(50)
      description: "财经BP确认人"
    - name: bp_confirmation_at
      type: timestamp
      description: "BP确认时间"
    - name: closure_status
      type: enum(待业务响应, 待BP确认, 已闭环, 已驳回)
      description: "闭环状态"
    - name: retention_period
      type: integer
      description: "存档年限（≥3年）"
    - name: created_at
      type: timestamp
      description: "创建时间"
```

#### 2.6.3 预警升级记录

```yaml
alert_escalation:
  table: alert_escalation
  description: "预警升级记录"
  fields:
    - name: escalation_id
      type: string(20)
      description: "升级记录编号"
      constraints: [primary_key]
    - name: alert_id
      type: string(20)
      description: "预警编号"
      constraints: [foreign_key → alert_record.alert_id]
    - name: escalation_reason
      type: enum(超时未响应, 超时未闭环)
      description: "升级原因"
    - name: escalation_level
      type: string(50)
      description: "升级通知对象级别"
    - name: escalation_target
      type: string(50)
      description: "升级通知目标人"
    - name: original_deadline
      type: timestamp
      description: "原响应截止时间"
    - name: escalation_at
      type: timestamp
      description: "升级时间"
    - name: is_performance_impact
      type: boolean
      description: "是否纳入月度绩效考核"
```

---

## 三、业务语义本体设计

### 3.1 本体五层结构总览

```
┌──────────────────────────────────────────────────────────────┐
│                  业务语义本体五层结构                           │
│                                                              │
│  第五层：场景层（Scene Layer）                                │
│  ──────────────────────────                                  │
│  显式定义"场景"，声明每个场景下哪些对象、关系、规则被激活      │
│  大模型拿到情境→先匹配场景→再取出激活子集去推理               │
│  11个核心场景对齐八阶段业务流程                               │
│                                                              │
│  第四层：规则层（Rule Layer）                                 │
│  ──────────────────────────                                  │
│  显式的"条件→结果"，原子化（一条一跳）                        │
│  带标签（属于哪个场景、引用了哪些对象和关系）                  │
│  自带一个解好的示例                                          │
│  三层规则：硬规则/软规则/推理规则                             │
│                                                              │
│  第三层：行为层（Behavior Layer）                             │
│  ──────────────────────────                                  │
│  声明前置条件、效果、参数                                     │
│  自然语言和结构化都写                                         │
│  大模型要套用的动作模板                                      │
│                                                              │
│  第二层：关系层（Relation Layer）                             │
│  ──────────────────────────                                  │
│  除了类型和方向，关键是带上"在什么场景下成立"                 │
│                                                              │
│  第一层：对象层（Object Layer）                               │
│  ──────────────────────────                                  │
│  除了属性，必须有一句自然语言定义                             │
│  说清它参与哪些关系                                          │
│  "定义写清楚"比"形式正确"重要得多                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 对象层

**设计原则**：每个对象必须带上让大模型不用猜的信息——属性+自然语言定义+参与的关系。

#### 3.2.1 战略与预算对象

| 对象类别 | 核心对象 | 自然语言定义 | 关键属性 | 参与的关系 |
|---------|---------|------------|---------|----------|
| 战略 | SP战略规划 | 集团3-5年战略规划，决定资源配置方向 | 规划周期、三大战略方向（全渠道商业化/创新研发/国际化）、资源配置权重 | 驱动→BP、解码→战略举措 |
| 战略 | BP年度业务计划 | 将SP意图转化为年度经营目标和行动计划 | 年度、收入目标、费用目标、KPI/PBC | 对标→象限、输入→预算项目 |
| 战略 | 战略举措 | SP/BP解码后的可执行项目清单 | 举措编号(如G-2.3)、名称、战略方向 | 对标→象限、驱动→预算项目 |
| 预算 | 预算项目 | 经审批的年度预算额度分配单元，是费用发生的必要前提 | 预算ID、A/B类别、额度、冻结状态、象限归属 | 挂载→支出、对标→战略举措、受约束→象限 |
| 预算 | 象限 | 战略意图维度的分类框架，决定预算投向 | 象限名称（发展/收缩/稳定/探索）、资源配置权重 | 包含→预算项目、约束→额度 |
| 预算 | 预算科目(L1) | 一级预算科目大类，共9个 | 科目编码(B1-B9)、名称、通用预警规则 | 包含→L2科目、约束→预算项目 |
| 预算 | 预算科目(L2) | 二级预算科目子类 | 科目编码、名称、专项预警阈值 | 包含→L3科目 |
| 预算 | 预算科目(L3) | 三级最小管控单元，独立编号 | 科目编码、管控级别标签(强管控/中心弱管控/组合管控/不管控)、是否项目化管理 | 管控→报销单、约束→审批路由 |

#### 3.2.2 费用科目体系（9个L1预算科目）

**关键约束：预算管控到L3，报销管控到L2。**

| L1编码 | L1名称 | L2子类 | 管控特点 |
|--------|--------|--------|---------|
| B1 | 资本支出 | — | 项目化管理，绑定项目ID，里程碑预警 |
| B2 | 研发支出 | — | 项目化管理，IND/NDA/III期临床分阶段阈值，里程碑预警 |
| B3 | 维持性支出 | — | 通用管控，月度/季度预警 |
| B4 | 税务支出 | — | 合规导向不控费用，月度申报缴纳延迟预警 |
| B5 | 市场推广支出 | 销售驱动/市场驱动/医学驱动/患者驱动/政策驱动/开发驱动（6个L2） | 按L2分类ROI预警，单场活动费用预警 |
| B6 | 人力成本支出 | 工资类/社保公积金/奖金及可变薪酬 | 编制预警与工资预算联动 |
| B7 | 货物支出 | 成品采购/委托加工/自主生产（3个L2） | 通用管控，供应商维度预警 |
| B8 | 股权投资支出 | — | 单笔超500万红色预警（不受比例限制），投资阶段专用阈值 |
| B9 | 财务费用 | — | 通用管控 |

#### 3.2.3 支出、预警、角色、报表对象

| 对象类别 | 核心对象 | 自然语言定义 | 关键属性 | 参与的关系 |
|---------|---------|------------|---------|----------|
| 支出 | 报销单 | 员工费用报销的电子记录，须关联有效预算ID | 报销单号、金额、L2费用类别、预算ID、审批状态 | 关联→预算ID、触发→预警 |
| 支出 | 预算使用申请 | 报销前的额度确认 | 申请书编号、预算编号、申请金额、额度确认状态 | 关联→预算项目 |
| 预警 | 预警记录 | 系统检测到偏离阈值后生成的预警信号 | 预警编号、级别(蓝/黄/橙/红)、类型(月度/季度/里程碑/L1专项)、状态(开放/闭环) | 分发→角色、响应→处置、升级→上级 |
| 角色 | 管委会 | 集团最高经营决策机构 | — | 批准→战略方向、终审→年度预算、裁决→跨象限调拨 |
| 角色 | 财经中心预算管理部 | 汇总PK、预算库维护 | — | 审核→预算编制、维护→预算库 |
| 角色 | 各中心财经BP | 数据填报审核、预警确认 | 中心归属 | 确认→预警闭环、审核→数据 |
| 角色 | 运营中心经营管理部 | 收入/品种/推广费分析 | — | 编制→经营分析 |
| 角色 | 人力中心 | 人力成本分析 | — | 编制→人力成本分析 |
| 报表 | 月度快报 | 含执行率/象限执行/预警闭环追踪 | 报告期、编制中心、数据定稿日(12日) | 来源→本系统数据、分发→角色 |
| 报表 | 季度汇报PPT | 含趋势分析/调拨建议/滚动预测 | 季度、象限执行、3GAP+3List | 来源→经营分析 |
| 报表 | 年度复盘报告 | 含组合校准/次年建议 | 年度、战略意图执行率 | 来源→PDCA-C |
| 工具 | 3GAP+3List | 滚动预测分析工具 | GAP1(目标差距)/GAP2(执行差距)/GAP3(预测变动)、List1(确定类)/List2(风险类)/List3(机会类) | 应用于→季度复盘 |

### 3.3 关系层

**设计原则**：除了类型和方向，关键是带上"在什么场景下成立"。

| 关系名称 | 源对象 | 目标对象 | 场景条件 | 语义说明 |
|---------|-------|---------|---------|---------|
| 挂载 | 报销单 | 预算项目 | 费用报销场景：报销提交时必须选择有效预算ID | 每笔支出必须关联一个预算项目，无ID系统拦截 |
| 对标 | 预算项目 | 战略举措 | 预算编制场景：预算申报须对标SP/BP目标 | 预算项目须有战略依据，无依据不予审批 |
| 归属 | 预算项目 | 象限 | 预算编制场景：每个预算项目须归属一个象限 | 决定预算投向和管控方式 |
| 管控 | 预算科目(L3) | 报销单 | 费用报销场景：L3管控标签决定审批路由 | 四级管控模式决定可否跨部门/跨费用类别 |
| 触发 | 支出/数据变更 | 预警记录 | 预警监控场景：指标偏离阈值时自动触发 | 月度/季度/里程碑三种通用规则+L1专项 |
| 响应 | 角色(业务) | 预警记录 | 预警响应场景：业务单元须在四色时限内响应 | 蓝色3天/黄色2天/橙色1天/红色即时 |
| 确认 | 角色(财务BP) | 预警记录 | 预警闭环场景：财务BP确认整改方案后闭环 | 双签方可关闭预警 |
| 升级 | 预警记录 | 角色(上级) | 超时未响应场景：责任人超时未响应 | 系统自动升级通知上级 |
| 冻结 | 预算项目 | 预算额度 | A类立项/B→A转换场景：审批通过后系统锁定 | A类全额锁定，B类0%授予 |
| 释放 | 预算项目 | 预算额度 | 项目取消/结项场景：取消或核销后释放冻结额度 | 释放后额度可用于其他项目 |
| B→A转换 | B类预算 | A类预算 | B→A转换场景：季度里程碑验证达标 | B→A转换后全额锁定 |
| 审批(组织线) | 报销单 | 角色(部门负责人→中心总经理) | 费用报销场景：先组织管理线 | 申请人→部门负责人→中心总经理 |
| 审批(法人线) | 报销单 | 角色(法人财务负责人→法人/授权人) | 费用报销场景：后法人架构线 | 法人组织财务负责人→法人或授权人 |
| 裁决 | 角色(管委会) | 分歧事项 | 分歧裁决场景：跨象限调拨须管委会批准 | AI可建议，不可裁决 |
| 驱动 | 战略目标 | 预算项目 | 战略解码场景：SP/BP驱动预算编制 | 先定方向再配资源 |

### 3.4 行为层

**设计原则**：声明前置条件、效果、参数，自然语言和结构化都写。所有行为均为本系统内部操作。

| 行为ID | 行为名称 | 前置条件 | 效果 | 参数 | 所属阶段 |
|--------|---------|---------|------|------|---------|
| fin.budget.a_class_freeze | A类额度冻结 | 预算ID存在且有效；A类立项审批通过 | A类额度全额锁定；通知业务部门 | budget_id, amount | 阶段二 |
| fin.budget.b_class_grant | B类额度授予(0%) | 预算ID存在；B类判定完成 | B类额度授予0%，待里程碑验证后方可转换 | budget_id | 阶段二 |
| fin.budget.b2a_convert | B→A转换 | B类预算有明确进展；季度里程碑验证达标 | B类额度全额锁定；更新预算类别为A | budget_id, milestone_evidence | 阶段二 |
| fin.budget.release | 释放预算额度 | 预算ID存在且有冻结额度 | 冻结额度释放；预算余额增加；通知业务部门 | budget_id, amount, reason | 各阶段 |
| fin.control.route | 四级管控路由 | 报销单已关联有效预算ID；L3管控标签已识别 | 按管控级别路由到对应审批模式 | expense_id, l3_control_tag | 阶段三 |
| fin.expense.submit | 提交报销申请 | 预算ID有效且额度充足；发票合规 | 报销单进入审批流；系统自动校验 | expense_id, budget_id, amount, l2_category | 阶段三 |
| fin.approval.org_line | 组织管理线审批 | 报销单已提交 | 申请人→部门负责人→中心总经理 | expense_id, approver_chain | 阶段三 |
| fin.approval.legal_line | 法人架构线审批 | 组织管理线审批完成 | 法人组织财务负责人→法人或授权人 | expense_id, approver_chain | 阶段三 |
| fin.budget.write_off | 预算核销 | 双线审批完成 | 核销预算额度；更新执行率 | expense_id, budget_id, amount | 阶段三 |
| fin.alert.create_monthly | 生成月度执行进度预警 | 月末触发；累计执行偏离阈值 | 按四色分级推送至责任人；启动响应计时 | alert_type, level, l1_code | 阶段五 |
| fin.alert.create_quarterly | 生成季度滚动预测预警 | 季度末触发；滚动预测偏离 | 按四色分级推送至责任人；启动响应计时 | alert_type, level, l1_code | 阶段五 |
| fin.alert.create_milestone | 生成里程碑预警 | 里程碑偏离；三维度独立判断取最高级别 | 按四色分级推送；三维同时触发升级红色 | alert_type, level, project_id | 阶段五 |
| fin.alert.escalate | 预警升级 | 责任人超时未响应 | 通知上级；更新预警状态 | alert_id, timeout_hours | 阶段五 |
| fin.alert.close | 预警闭环 | 业务响应+财经BP确认双签完成 | 预警状态变为闭环；写入闭环档案 | alert_id, response, bp_confirmation | 阶段五 |
| fin.analysis.3gap | 3GAP分析 | 季度数据定稿完成 | 生成GAP1/GAP2/GAP3分析结果 | period, center | 阶段四/六 |
| fin.analysis.3list | 3List归类 | 3GAP分析完成 | 将偏差归入List1/List2/List3 | gap_results | 阶段四/六 |
| fin.report.monthly | 月度快报编制 | 每月12日数据定稿 | 生成月度快报；分发至相关角色 | period, center | 阶段七 |
| fin.report.quarterly | 季度汇报编制 | 季度数据汇总完成 | 生成季度汇报PPT（含3GAP+3List+调拨建议） | period | 阶段七 |
| fin.pdca.monthly | PDCA-A月度闭环 | 每月末 | 月度预警闭环检查 | period | 阶段六 |
| fin.pdca.quarterly | PDCA-B季度复盘 | 每季度末 | 季度复盘→3GAP+3List→象限内调拨建议 | period | 阶段六 |
| fin.pdca.yearly | PDCA-C年度校准 | 年度结束 | 年度复盘→组合校准→次年建议 | period | 阶段六 |
| fin.adjustment.transfer | 预算调拨 | 调拨申请提交 | 象限内→财经中心批；跨象限→管委会批 | from_id, to_id, amount, same_quadrant | 阶段六 |

### 3.5 规则层

**设计原则**：写成显式的"条件→结果"，满足三条——原子（只管一跳）、带标签（属于哪个场景、引用了哪些对象和关系）、自带一个解好的示例。

#### 3.5.1 费用报销规则

| 规则ID | 规则名称 | 条件 | 结果 | 场景标签 | 引用对象 | 示例 |
|--------|---------|------|------|---------|---------|------|
| fin.budget.no_id_reject | 无预算ID拦截 | 报销提交时无有效预算ID | HardRuleEngine HR-001 拦截，记 Decision.outcome=blocked | 费用报销 | 报销单、预算项目 | 员工提交报销未选预算ID→拦截 |
| fin.control.strong | 强管控路由 | L3管控标签为"强管控" | 不可跨部门跨费用类别，超预算须增补 | 费用报销 | L3科目、报销单 | 招待费(强管控)跨部门报销→拦截 |
| fin.control.weak | 中心弱管控路由 | L3管控标签为"中心弱管控" | 中心内可跨部门，须BP+中心GM审批 | 费用报销 | L3科目、报销单 | 培训费(弱管控)中心内跨部门→BP+GM审批 |
| fin.control.combo | 组合管控路由 | L3管控标签为"组合管控" | 中心内可跨部门跨费用类别 | 费用报销 | L3科目、报销单 | 综合管理费(组合管控)→中心内自由 |
| fin.control.none | 不管控路由 | L3管控标签为"不管控" | 无需预算即可使用 | 费用报销 | L3科目、报销单 | 折旧费(不管控)→直接通过 |
| fin.approval.org_first | 组织线优先 | 报销单进入审批流 | 先走组织管理线：申请人→部门负责人→中心总经理 | 费用报销 | 报销单、角色 | 报销单提交→先部门负责人审批 |
| fin.approval.legal_second | 法人线后置 | 组织管理线审批完成 | 后走法人架构线：法人财务负责人→法人/授权人 | 费用报销 | 报销单、角色 | 组织线通过→法人财务负责人审批 |

#### 3.5.2 预警规则（三种通用规则）

| 规则ID | 规则名称 | 条件 | 结果 | 场景标签 | 示例 |
|--------|---------|------|------|---------|------|
| fin.alert.monthly.blue | 月度执行蓝色 | ①当月实际>当月分期计划×105% 或 ②累计执行>累计分期计划×105% | 蓝色预警，5工作日内提交偏差说明 | 月度执行进度 | B2当月实际106%或累计执行106%→蓝色 |
| fin.alert.monthly.yellow | 月度执行黄色 | ①当月实际>当月分期计划×110% 或 ②累计执行>累计分期计划×110% | 黄色预警，冻结新增，5工作日内偏差分析+滚动预测 | 月度执行进度 | B5当月实际112%或累计执行112%→黄色 |
| fin.alert.monthly.red | 月度执行红色 | ①实际已超年度预算 或 ②预计全年>年度预算 | 红色预警，立即冻结，提交调增申请 | 月度执行进度 | B3实际已超年度预算→红色 |
| fin.alert.monthly.red_single | 月度单项目红色 | 单项目/单供应商偏差超50万 | 红色预警（不受比例限制） | 月度执行进度 | 某供应商偏差52万→红色 |
| fin.alert.quarterly.blue | 季度滚动蓝色 | 滚动预测>年度预算×105% | 蓝色预警，10工作日内提交调整说明 | 季度滚动预测 | B6滚动预测106%→蓝色 |
| fin.alert.quarterly.yellow | 季度滚动黄色 | 滚动预测>年度预算×110% | 黄色预警，冻结新增，10工作日内调增或调减方案 | 季度滚动预测 | B7滚动预测112%→黄色 |
| fin.alert.quarterly.red | 季度滚动红色 | 滚动预测>年度预算×115% | 红色预警，立即冻结，财经中心上报管委会 | 季度滚动预测 | B8滚动预测116%→红色 |
| fin.alert.milestone.time_blue | 里程碑时间蓝色 | 大里程碑延期21-30天 | 蓝色预警，5工作日内提交进展说明 | 里程碑预警 | III期临床延期25天→蓝色 |
| fin.alert.milestone.time_yellow | 里程碑时间黄色 | 大里程碑延期31-60天 | 黄色预警，冻结该项目L3新增付款 | 里程碑预警 | III期临床延期45天→黄色 |
| fin.alert.milestone.time_red | 里程碑时间红色 | 大里程碑延期>60天或取消 | 红色预警，冻结该项目L3所有新增支出 | 里程碑预警 | III期临床延期65天→红色 |
| fin.alert.milestone.cost_blue | 里程碑费用蓝色 | 里程碑费用>计划×110% | 蓝色预警 | 里程碑预警 | 里程碑费用112%→蓝色 |
| fin.alert.milestone.cost_yellow | 里程碑费用黄色 | 里程碑费用>计划×120% | 黄色预警，冻结该项目L3新增付款 | 里程碑预警 | 里程碑费用125%→黄色 |
| fin.alert.milestone.cumulative_blue | 累计进度蓝色 | 累计实际>累计分期计划×105% | 蓝色预警 | 里程碑预警 | 累计执行107%→蓝色 |
| fin.alert.milestone.max_level | 三维度取最高 | 多维度同时触发 | 取最高级别；三维同时→红色+启动调增 | 里程碑预警 | 时间黄色+费用蓝色→黄色 |
| fin.alert.dual_close | 双签闭环 | 预警关闭须业务+财经BP双签 | 未经双签不得关闭 | 预警响应 | 业务提交整改但BP未确认→仍开放 |
| fin.alert.escalate | 超时升级 | 责任人超时未响应 | 自动升级通知上级 | 预警响应 | 黄色2天未响应→通知上级 |
| fin.alert.b1.intangible_yellow | B1.1无形资产黄色 | 单笔超年度预算×110% | 黄色预警，须提交超支说明 | B1专项 | 无形资产单笔112%→黄色 |
| fin.alert.b1.intangible_red | B1.1无形资产红色 | 单笔超年度预算×130% | 红色预警，冻结新增，提交调增申请 | B1专项 | 无形资产单笔135%→红色 |
| fin.alert.b1.intangible_renewal | B1.1无形资产续期 | 专利/软件License续期 | 须提前60天预算确认 | B1专项 | License到期前60天→确认预算 |
| fin.alert.b1.engineering_prepaid | B1.2工程预付款 | 预付款超合同×30% | 系统拦截，须重新审批 | B1专项 | 预付款35%→拦截 |
| fin.alert.b1.engineering_change | B1.2工程变更 | 工程变更超原合同×10% | 须重新审批 | B1专项 | 变更超12%→重新审批 |
| fin.alert.b1.engineering_yellow | B1.2工程支出黄色 | 超年度预算×120% | 黄色预警 | B1专项 | 工程支出125%→黄色 |
| fin.alert.b1.engineering_red | B1.2工程支出红色 | 超年度预算×150% | 红色预警，冻结新增 | B1专项 | 工程支出155%→红色 |
| fin.alert.b1.engineering_settle | B1.2工程结算 | 竣工后60天 | 须完成结算审计 | B1专项 | 竣工55天→提醒结算审计 |
| fin.alert.b1.fixed_yellow | B1.3固定资产黄色 | 单台设备超年度预算×120% | 黄色预警 | B1专项 | 设备采购125%→黄色 |
| fin.alert.b1.fixed_red | B1.3固定资产红色 | 单台设备超年度预算×150% | 红色预警，冻结新增 | B1专项 | 设备采购160%→红色 |
| fin.alert.b1.fixed_import | B1.3进口设备 | 进口设备采购 | 须提前90天完成关税汇率评估 | B1专项 | 进口设备→提前90天评估 |

#### 3.5.3 A/B类预算管理规则

| 规则ID | 规则名称 | 条件 | 结果 | 场景标签 | 示例 |
|--------|---------|------|------|---------|------|
| fin.budget.a_class_lock | A类全额锁定 | A类立项审批通过 | 额度全额冻结，不可超支 | 预算授予 | A类项目审批→45万全额锁定 |
| fin.budget.b_class_zero | B类0%授予 | B类判定完成 | 年初授予0%，不可支出 | 预算授予 | B类项目→0%授予 |
| fin.b2a.convert | B→A转换 | 里程碑验证达标 | 全额锁定，更新类别为A | B类管理 | Q2里程碑达标→B转A |
| fin.b2a.freeze | B类未达标 | 里程碑验证未达标 | 冻结剩余额度 | B类管理 | Q2里程碑未达标→冻结 |
| fin.b2a.inflate | B类膨胀监控 | B类冻结额度>A类执行额30% | 触发蓝色预警 | B类管理 | B类占比32%→蓝色 |

#### 3.5.4 预算调整规则

| 规则ID | 规则名称 | 条件 | 结果 | 场景标签 | 示例 |
|--------|---------|------|------|---------|------|
| fin.adjustment.same_quadrant | 象限内调拨 | 调拨双方属同一象限 | 财经中心审批即可 | 预算调整 | 发展象限内调拨→财经中心批 |
| fin.adjustment.cross_quadrant | 跨象限调拨 | 调拨双方属不同象限 | 须管委会批准 | 预算调整 | 发展→收缩象限→管委会批 |
| fin.tax.compliance | 税务合规优先 | 税务支出超年度预算 | 不触发红色预警(强制支出)，滚动预测中单独列示 | 税务管理 | 增值税超预算→不冻结，须说明 |

### 3.6 场景层

**设计原则**：显式地定义"场景"，并声明每个场景下哪些对象、关系、规则是被激活的。大模型拿到一个具体情境，先匹配到场景，再从这层取出被激活的那一小片去推理。

**场景定义规范**：

```yaml
scene_id: "fin.expense_reimbursement"
name: "费用报销场景"
description: "员工因公发生费用后提交报销申请，系统校验预算ID和额度，按L3管控标签路由审批"
activation_condition: "员工提交报销申请"
activated_objects:
  - 报销单
  - 预算项目
  - 预算科目(L1/L2/L3)
  - 角色(部门负责人/中心总经理/法人财务负责人/法人或授权人)
activated_relations:
  - 挂载(报销单→预算项目)
  - 管控(L3科目→报销单)
  - 审批(组织线)
  - 审批(法人线)
activated_rules:
  - fin.budget.no_id_reject
  - fin.control.strong
  - fin.control.weak
  - fin.control.combo
  - fin.control.none
  - fin.approval.org_first
  - fin.approval.legal_second
activated_behaviors:
  - fin.control.route
  - fin.expense.submit
  - fin.approval.org_line
  - fin.approval.legal_line
  - fin.budget.write_off
```

**核心场景清单**（对齐八阶段业务流程）：

| 场景ID | 场景名称 | 对应阶段 | 激活条件 | 核心激活对象 | 核心激活规则数 |
|--------|---------|---------|---------|------------|-------------|
| fin.budget_planning | 预算编制场景 | 阶段一 | Q4启动年度预算编制 | SP/BP、象限、预算科目 | 5 |
| fin.budget_grant | 预算授予场景 | 阶段二 | 阶段一终审完成 | 预算项目、A/B类别 | 5 |
| fin.expense_reimbursement | 费用报销场景 | 阶段三 | 员工提交报销申请 | 报销单、预算科目、L3管控标签 | 7 |
| fin.business_analysis | 经营分析场景 | 阶段四 | 每月12日数据定稿 | 报表、执行率、3GAP+3List | 4 |
| fin.alert_monitoring | 预警监控场景 | 阶段五 | 每日系统扫描/实时数据变更 | 预警记录、阈值 | 16 |
| fin.alert_response | 预警响应场景 | 阶段五 | 预警触发后责任人响应 | 预警记录、整改方案、角色 | 4 |
| fin.b_class_management | B类管理场景 | 阶段二/五 | B类申请/B→A转换/膨胀检测 | B类预算、A类预算、里程碑 | 5 |
| fin.pdca_review | PDCA复盘场景 | 阶段六 | 月度/季度/年度截点 | 复盘报告、3GAP+3List | 5 |
| fin.report_issuance | 报表出具场景 | 阶段七 | 月度5/8/10日截点 | 报表、数据 | 3 |
| fin.next_cycle | 次年采集场景 | 阶段八 | 年度复盘完成 | 年度执行数据库、未关闭预警 | 3 |
| fin.budget_adjustment | 预算调整场景 | 阶段六 | 调增/调减/调拨申请 | 预算项目、象限 | 3 |

---

## 四、核心业务引擎

本章定义AI原生一体化系统的七个核心业务引擎。每个引擎独立运行，共享统一数据模型和本体定义，由事件驱动架构协调联动。引擎内部由本体驱动+原子规则组装，AI内嵌于每个引擎中。

> **架构说明**：七个业务引擎的业务逻辑由 FinanceAgent + 18 Skills 动态组合架构承载。FinanceAgent 是唯一执行引擎（42个工具），运行时根据用户意图动态选择 1~3 个 Skill 注入上下文。写操作经领域引擎执行硬规则门闩并落 `DecisionRecord`。引擎与 Skill 的对应关系：
>
> | 业务引擎 | 对应Skill | 说明 |
> |---------|----------|------|
> | 预算编制引擎 | budget-planning | 预算编制、科目体系、A/B分类 |
> | 预算授予引擎 | budget-planning + b2a-conversion | A/B授予、B→A转换 |
> | 费用报销引擎 | expense-reimbursement + approval-routing | 报销管控路由、双线审批 |
> | 预警监控引擎 | alert-monitor | 预警扫描、四色分级、双签闭环 |
> | 经营分析引擎 | business-analysis | 3GAP归因、3List归类 |
> | PDCA复盘引擎 | pdca-review + budget-adjustment | 复盘、调拨建议 |
> | 报表出具引擎 | report-generation | 月/季/年报编制 |
> | 现金流 / 成本中心 / HCP / 管线 / 情景 / 零基 / 影响评估 / 经营看板 | cash-flow-monitor · cost-center-accounting · hcp-compliance · pipeline-management · scenario-planning · zero-based-budget · impact-assessment · executive-dashboard | 与 18 Skills 对齐 |

### 4.1 预算编制引擎

#### 4.1.1 引擎概述

预算编制引擎负责将SP/BP战略规划转化为年度预算项目清单，是八阶段流程的起点。

#### 4.1.2 引擎输入与输出

- **输入**：SP战略规划数据、BP年度业务计划数据
- **输出**：年度预算项目清单（含A/B分类、象限归属、L3科目映射）

#### 4.1.3 引擎内部流程

```
┌──────────────────────────────────────────────────────────────┐
│                    预算编制引擎内部流程                         │
│                                                              │
│  ① SP/BP数据输入                                             │
│     系统接收SP战略规划和BP年度业务计划数据                     │
│                    │                                         │
│                    ▼                                         │
│  ② AI自动匹配战略举措                                        │
│     AI解析SP/BP内容→提取战略举措清单                          │
│     每个举措自动编号（如G-2.3）→关联三大战略方向              │
│                    │                                         │
│                    ▼                                         │
│  ③ 象限归属推荐                                              │
│     AI根据战略举措内容→推荐象限归属                           │
│     发展/收缩/稳定/探索四象限→资源配置权重匹配                │
│                    │                                         │
│                    ▼                                         │
│  ④ 上下结合PK                                                │
│     下级申报：各中心/部门提交预算申报                          │
│     上级下达：财经中心预算管理部汇总PK                         │
│     AI辅助：自动检测申报与战略举措的对标关系                   │
│     无战略依据的申报→AI标注→不予审批                          │
│                    │                                         │
│                    ▼                                         │
│  ⑤ 预算框架下达                                              │
│     管委会终审→预算框架正式下达                               │
│     系统自动生成预算项目清单                                  │
│     每个项目含：预算ID、A/B分类、象限归属、L3科目映射         │
│                    │                                         │
│                    ▼                                         │
│  ⑥ A/B分类判定                                               │
│     AI根据项目特征自动判定A/B类别                             │
│     A类：立项即全额授予→进入预算授予引擎                      │
│     B类：年初授予0%→进入B类管理流程                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.1.4 AI内嵌能力

- **战略举措自动提取**：AI解析SP/BP文本，自动提取战略举措并编号
- **象限归属智能推荐**：AI根据举措内容推荐象限归属，人工确认
- **对标关系自动检测**：AI检测预算申报与战略举措的对标关系，无依据标注警告
- **A/B分类智能判定**：AI根据项目特征（确定性/进展依赖度）推荐A/B分类

### 4.2 预算授予引擎

#### 4.2.1 引擎概述

预算授予引擎负责根据预算编制结果，对A/B两类预算项目执行差异化的授予和锁定机制。

#### 4.2.2 A类预算授予流程

```
┌──────────────────────────────────────────────────────────────┐
│                    A类预算授予流程                             │
│                                                              │
│  ① A类立项审批                                               │
│     预算项目经审批确认为A类                                   │
│                    │                                         │
│                    ▼                                         │
│  ② 全额冻结                                                  │
│     系统自动锁定：granted_amount = annual_amount              │
│     frozen_amount = annual_amount                            │
│     grant_percentage = 100%                                  │
│                    │                                         │
│                    ▼                                         │
│  ③ 通知业务                                                  │
│     系统自动通知业务部门：预算已授予，可执行报销              │
│                    │                                         │
│                    ▼                                         │
│  ④ 进入执行监控                                              │
│     预算项目状态→执行中                                      │
│     后续由费用报销引擎和预警引擎接管                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.2.3 B类预算授予流程

```
┌──────────────────────────────────────────────────────────────┐
│                    B类预算授予流程                             │
│                                                              │
│  ① B类判定                                                   │
│     预算项目经判定为B类（进展依赖型）                         │
│                    │                                         │
│                    ▼                                         │
│  ② 0%授予                                                    │
│     granted_amount = 0                                       │
│     frozen_amount = 0                                        │
│     grant_percentage = 0%                                    │
│     B类额度不可用于报销                                      │
│                    │                                         │
│                    ▼                                         │
│  ③ 里程碑追踪                                                │
│     系统按季度追踪B类项目里程碑进展                           │
│     AI自动提醒里程碑验证截点                                  │
│                    │                                         │
│                    ▼                                         │
│  ④ B→A转换判定                                               │
│     里程碑验证达标 → 进入B→A转换流程                         │
│     里程碑验证未达标 → 冻结剩余额度                          │
│                    │                                         │
│                    ▼                                         │
│  ⑤ B→A转换执行                                              │
│     转换审批通过 → grant_percentage = 100%                   │
│     frozen_amount = annual_amount                            │
│     更新预算类别为A                                          │
│     每月须向管委会提交《预算B→A转换专项报告》                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.2.4 预算系统锁定机制

| 操作 | 触发条件 | 系统动作 | 数据变更 |
|------|---------|---------|---------|
| A类冻结 | A类立项审批通过 | 全额锁定额度 | frozen_amount = annual_amount |
| B→A转换冻结 | B→A转换审批通过 | 全额锁定额度 | frozen_amount = annual_amount, category = A |
| 报销核销 | 双线审批完成 | 扣减可用额度 | used_amount += 报销金额 |
| 额度释放 | 项目取消/结项 | 释放冻结额度 | frozen_amount -= 释放金额 |
| B类未达标冻结 | 里程碑验证未达标 | 冻结剩余额度 | frozen_amount = 剩余额度 |

### 4.3 费用报销引擎（含四级管控路由+双线审批）

#### 4.3.1 引擎概述

费用报销引擎是系统中最复杂的引擎，负责从报销提交到预算核销的完整流程，包含预算ID校验、L3管控标签识别、四级管控路由、额度校验、双线审批、发票查重、预算核销等全部环节。

#### 4.3.2 报销提交流程总览

```
┌──────────────────────────────────────────────────────────────┐
│                    费用报销引擎完整流程                         │
│                                                              │
│  ① 预算使用审批流                                             │
│     日常类（FM-BUD-USE-001）：                                │
│       立项申请人→预算所属部门负责人→系统额度确认/冻结          │
│     项目类（FM-BUD-USE-PROJ-001）：                           │
│       立项申请人→预算所属部门负责人→财务BP→中心总经理          │
│       →系统额度确认/冻结                                      │
│     不管控科目：系统自动放行                                  │
│                    │                                         │
│                    ▼                                         │
│  ② 报销提交                                                  │
│     员工填写报销单→选择预算ID→上传发票                       │
│                    │                                         │
│                    ▼                                         │
│  ③ 预算ID校验                                                │
│     [HR-001] HardRuleEngine：无/无效预算ID → BLOCK            │
│     拒绝写入并记 Decision.outcome=blocked                     │
│     预算ID有效性校验→额度充足性校验（HR-002 核销时再闸）       │
│                    │                                         │
│                    ▼                                         │
│  ④ L3管控标签识别                                            │
│     系统自动识别报销单关联L3科目的管控标签                    │
│                    │                                         │
│                    ▼                                         │
│  ⑤ 四级管控路由                                              │
│     根据L3管控标签路由到对应审批模式                          │
│     （详见4.3.3节）                                          │
│                    │                                         │
│                    ▼                                         │
│  ⑥ 额度校验                                                  │
│     检查预算余额是否充足                                     │
│     跨部门/跨费用类别/跨品种组合规性校验                     │
│                    │                                         │
│                    ▼                                         │
│  ⑦ 发票查重                                                  │
│     系统自动校验发票号码唯一性                                │
│     重复发票→拦截并提示                                      │
│                    │                                         │
│                    ▼                                         │
│  ⑧ 双线审批                                                  │
│     先组织管理线→后法人架构线                                │
│     （详见4.3.4节）                                          │
│                    │                                         │
│                    ▼                                         │
│  ⑨ 预算核销                                                  │
│     双线审批完成→系统自动核销预算额度                        │
│     更新预算执行率                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.3.3 四级管控路由详细流程

```
┌──────────────────────────────────────────────────────────────┐
│                    四级管控路由决策树                          │
│                                                              │
│  报销单提交                                                  │
│       │                                                      │
│       ▼                                                      │
│  识别L3管控标签                                              │
│       │                                                      │
│       ├── 强管控 ──────────────────────────────────┐        │
│       │   不可跨部门、不可跨费用类别                │        │
│       │   超预算须申请增补                          │        │
│       │   → 标准双线审批                            │        │
│       │                                             │        │
│       ├── 中心弱管控 ──────────────────────────────┐        │
│       │   中心内可跨部门                            │        │
│       │   不可跨费用类别                            │        │
│       │   → 须财经BP+中心GM审批                    │        │
│       │                                             │        │
│       ├── 组合管控 ────────────────────────────────┐        │
│       │   中心内可跨部门+费用类别                   │        │
│       │   → 须财经BP+中心GM审批                    │        │
│       │                                             │        │
│       └── 不管控 ──────────────────────────────────┐        │
│           无需预算即可使用                          │        │
│           → 无需审批，直接通过                      │        │
│                                                    │        │
│       ┌────────────────────────────────────────────┘        │
│       │                                                      │
│       ▼                                                      │
│  路由结果：确定审批模式和审批链                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.3.4 双线审批流程

```
┌──────────────────────────────────────────────────────────────┐
│                    双线审批流程                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 组织管理线                                              │  │
│  │                                                        │  │
│  │  申请人 ──→ 部门负责人 ──→ 中心总经理                   │  │
│  │                                                        │  │
│  │  · 部门负责人审批：确认业务合理性                       │  │
│  │  · 中心总经理审批：确认预算使用合理性                   │  │
│  │  · 任一节点驳回→退回申请人修改                         │  │
│  └──────────────────────────┬─────────────────────────────┘  │
│                             │ 全部通过                        │
│                             ▼                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 法人架构线                                              │  │
│  │                                                        │  │
│  │  法人组织财务负责人 ──→ 法人或授权人                    │  │
│  │                                                        │  │
│  │  · 法人财务负责人审批：确认财务合规性                   │  │
│  │  · 法人或授权人审批：确认法人层面合规                   │  │
│  │  · 任一节点驳回→退回申请人修改                         │  │
│  └──────────────────────────┬─────────────────────────────┘  │
│                             │ 全部通过                        │
│                             ▼                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 双线审批完成 → 触发预算核销                             │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.3.5 发票查重机制

```yaml
invoice_dedup:
  description: "发票查重机制"
  process:
    - step: "发票号码提取"
      action: "系统自动从上传发票中提取发票号码"
    - step: "全库查重"
      action: "在已录入发票库中检索相同发票号码"
    - step: "查重结果处理"
      action_duplicated: "拦截报销提交，提示发票已使用"
      action_unique: "发票号码写入发票库，继续流程"
  fields_checked:
    - invoice_number
    - invoice_code
    - invoice_date
    - invoice_amount
```

#### 4.3.6 预算核销机制

```yaml
budget_write_off:
  description: "预算核销机制"
  trigger: "双线审批完成"
  process:
    - step: "核销校验"
      action: "确认报销金额≤预算可用额度"
    - step: "额度扣减"
      action: "used_amount += 报销金额；available_amount -= 报销金额"
    - step: "执行率更新"
      action: "执行率 = used_amount / annual_amount × 100%"
    - step: "核销记录"
      action: "写入核销记录表，含报销单号、预算ID、核销金额、核销时间"
    - step: "预警检查"
      action: "核销后自动检查是否触发预警规则"
```

#### 4.3.7 AI内嵌能力

- **预算ID智能推荐**：AI根据报销内容自动推荐最匹配的预算ID
- **L3管控标签自动识别**：AI识别费用类别→自动映射L3科目→读取管控标签
- **审批路由自动决策**：AI根据管控标签自动路由到对应审批模式
- **异常报销检测**：AI检测异常报销模式（频繁报销、金额异常、时间异常）

### 4.4 预警引擎（四色分级+三种通用规则+L1专项）

#### 4.4.1 引擎概述

预警引擎负责全系统预警的扫描、触发、分级、推送、闭环和升级。替代v2中"信息技术部系统扫描"的模式，由本系统引擎自主完成每日扫描。

#### 4.4.2 每日扫描机制

```
┌──────────────────────────────────────────────────────────────┐
│                    每日扫描机制                                │
│                                                              │
│  ① 定时触发（每日凌晨）                                      │
│     系统自动启动预警扫描任务                                  │
│                    │                                         │
│                    ▼                                         │
│  ② 数据采集                                                  │
│     从本系统数据模型中读取：                                  │
│     · 各L1/L2/L3科目当月实际发生额                           │
│     · 累计执行额、月度分期计划、年度预算                      │
│     · 项目里程碑计划时间、实际完成时间                        │
│     · 里程碑计划费用、实际费用                                │
│     · 滚动预测数据                                           │
│                    │                                         │
│                    ▼                                         │
│  ③ 三种通用规则执行                                          │
│     逐L1科目执行月度执行进度预警规则                          │
│     季度末追加执行季度滚动预测预警规则                        │
│     项目化管理科目追加执行里程碑预警规则                      │
│                    │                                         │
│                    ▼                                         │
│  ④ L1专项规则匹配                                            │
│     根据L1科目编码匹配专项预警规则                            │
│     B2→研发阶段专项、B4→税务合规专项                         │
│     B5→ROI专项、B6→编制联动专项、B8→投资阶段专项            │
│                    │                                         │
│                    ▼                                         │
│  ⑤ 四色分级推送                                              │
│     按预警级别推送至对应责任人                                │
│     启动响应计时                                              │
│                    │                                         │
│                    ▼                                         │
│  ⑥ 闭环检查                                                  │
│     检查已有预警的响应状态                                    │
│     超时未响应→自动升级                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.4.3 三种通用规则执行流程

**月度执行进度预警**（每月末触发）：

| 预警级别 | 触发条件 | 通用响应 | 通知对象 |
|---------|---------|---------|---------|
| 蓝色 | 累计执行>累计分期计划×105% | 5个工作日内提交偏差说明 | 部门经理 |
| 黄色 | 累计执行>累计分期计划×110% | 冻结新增申请，5个工作日内提交偏差分析+滚动预测 | 财经经理 |
| 红色 | 实际已超年度预算 | 立即冻结，提交预算调增申请 | 财经经理+部门负责人 |

**统一补充规则**：单项目/单供应商偏差超过50万元时，独立触发红色预警（不受比例限制）。

**季度滚动预测预警**（每季度末触发）：

| 预警级别 | 触发条件 | 通用响应 | 通知对象 |
|---------|---------|---------|---------|
| 蓝色 | 滚动预测>年度预算×105% | 10个工作日内提交调整说明 | 部门经理 |
| 黄色 | 滚动预测>年度预算×110% | 冻结新增申请，10个工作日内调增或调减方案 | 财经经理 |
| 红色 | 滚动预测>年度预算×115% | 立即冻结，财经中心上报管委会 | 部门负责人+财经中心 |

**里程碑预警**（适用于绑定项目ID的L3科目）：

三维度独立判断，取最高级别；三维同时触发→立即红色+同步启动预算调增审批。

| 维度 | 蓝色 | 黄色 | 红色 |
|------|------|------|------|
| 时间偏差（大里程碑） | 延期21-30天 | 延期31-60天 | 延期>60天或取消 |
| 里程碑费用偏差 | >计划×110% | >计划×120% | >计划×130%或已超阶段总费用 |
| 累计预算进度偏差 | 累计实际>累计分期计划×105% | 累计实际>累计分期计划×115% | 累计实际≥项目/阶段总费用 |

#### 4.4.4 L1专项规则匹配流程

```
┌──────────────────────────────────────────────────────────────┐
│                    L1专项规则匹配流程                          │
│                                                              │
│  通用规则执行完成                                             │
│       │                                                      │
│       ▼                                                      │
│  L1科目编码判断                                              │
│       │                                                      │
│       ├── B1/B2（资本/研发支出）                             │
│       │   → 里程碑预警（项目化管理科目）                     │
│       │   → B2追加：研发阶段专项阈值                         │
│       │     · IND/NDA：延期即蓝，>7天黄，>14天红            │
│       │     · III期Go/No-Go：延期即蓝，>14天黄，>30天红     │
│       │                                                      │
│       ├── B4（税务支出）                                     │
│       │   → 税务合规专项                                     │
│       │     · 缴纳延迟1-3天→蓝，4-7天→黄，>7天→红          │
│       │     · 超年度预算不触发红色（合规导向不控费用）       │
│       │                                                      │
│       ├── B5（市场推广支出）                                 │
│       │   → ROI专项（按L2子类匹配）                          │
│       │     · 销售驱动：ROI<目标×80%→蓝                     │
│       │     · 医学驱动：KOL维护超预算×150%→红               │
│       │     · 单场活动超预算×120%→黄，×150%→红              │
│       │                                                      │
│       ├── B6（人力成本支出）                                 │
│       │   → 编制联动专项                                     │
│       │     · 实际在职>编制×105%→蓝                         │
│       │     · 超编>20%或年度工资总额超预算→红               │
│       │                                                      │
│       ├── B8（股权投资支出）                                 │
│       │   → 投资阶段专项                                     │
│       │     · 单笔超500万→红（不受比例限制）                │
│       │     · 投资阶段里程碑专用阈值                         │
│       │                                                      │
│       └── B3/B7/B9（通用管控）                               │
│           → 仅适用三种通用规则                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.4.5 四色分级推送机制

| 预警级别 | 颜色标识 | 响应时限 | 通知对象 | 核心语义 |
|---------|---------|---------|---------|---------|
| 蓝色 | 🔵 | 3个自然日内响应 | 部门经理 | 系统提示，需关注并提交偏差说明 |
| 黄色 | 🟡 | 2个自然日内响应 | 财经经理 | 冻结新增申请，须提交偏差分析+滚动预测 |
| 橙色 | 🟠 | 1个自然日内响应 | 财经经理+部门负责人 | 紧急处置，联合评估 |
| 红色 | 🔴 | 即时响应 | 财经经理+部门负责人+财经中心 | 立即冻结，提交预算调增申请 |

#### 4.4.6 双签闭环确认流程

```
┌──────────────────────────────────────────────────────────────┐
│                    双签闭环确认流程                            │
│                                                              │
│  ① 预警触发                                                  │
│     系统检测偏离→生成预警记录→按四色分级推送                 │
│                    │                                         │
│                    ▼                                         │
│  ② 业务响应                                                  │
│     业务单元责任人提交整改方案                                │
│     整改方案须含：原因分析、已采取措施、预期关闭时间          │
│                    │                                         │
│                    ▼                                         │
│  ③ 财经BP确认                                                │
│     财经BP审核整改方案合理性                                  │
│     确认→双签完成→预警关闭                                   │
│     驳回→退回业务补充→重新提交                               │
│                    │                                         │
│                    ▼                                         │
│  ④ 闭环归档                                                  │
│     预警闭环档案：含整改方案+财经BP确认，双签齐全            │
│     系统存档≥3年                                             │
│                                                              │
│  关键规则：                                                   │
│  · 未经双签，预警不得关闭                                    │
│  · 未经财经BP双签擅自关闭预警→预警无效，恢复预警状态        │
│  · 虚假瞒报预警闭环情况→立即冻结相关额度，追责处理           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.4.7 超时自动升级机制

| 超时场景 | 升级动作 |
|---------|---------|
| 蓝色预警超3个自然日未响应 | 通知上级部门经理 |
| 黄色预警超2个自然日未响应 | 通知财经经理+上级 |
| 橙色预警超1个自然日未响应 | 通知财经中心 |
| 红色预警即时未响应 | 通知财经中心+管委会 |

逾期响应预警纳入月度绩效考核。

#### 4.4.8 AI内嵌能力

- **自动归因**：预警触发后AI自动完成归因分析，识别偏离由哪些子科目/项目/供应商贡献
- **智能推送**：AI根据预警级别和责任人活跃时间智能推送
- **预警疲劳检测**：AI监测预警响应率，发现预警疲劳时建议调整阈值
- **L1专项自动匹配**：AI自动识别L1科目，匹配对应专项规则，无需人工判断

### 4.5 经营分析引擎（3GAP+3List）

#### 4.5.1 引擎概述

经营分析引擎负责每月12日数据定稿后的经营分析工作，包括执行率计算、象限合规检查、3GAP+3List分析和**一报一会**编制（一报=月度经营分析快报，一会=月度经营管理会）。

#### 4.5.2 引擎流程

```
┌──────────────────────────────────────────────────────────────┐
│                    经营分析引擎流程                            │
│                                                              │
│  ① 每月12日数据定稿触发                                      │
│     系统自动锁定当月数据，标记为定稿状态                      │
│                    │                                         │
│                    ▼                                         │
│  ② 执行率计算                                                │
│     逐L1/L2/L3科目计算：                                     │
│     · 月度执行率 = 当月实际 / 当月分期计划 × 100%            │
│     · 累计执行率 = 累计实际 / 累计分期计划 × 100%            │
│     · 年度执行率 = 累计实际 / 年度预算 × 100%                │
│                    │                                         │
│                    ▼                                         │
│  ③ 象限合规检查                                              │
│     逐象限检查预算执行合规性：                                │
│     · 发展象限：资源配置权重是否达标                          │
│     · 收缩象限：压降进度是否达标                              │
│     · 稳定象限：维持性支出是否在预算内                        │
│     · 探索象限：创新投入是否按计划执行                        │
│                    │                                         │
│                    ▼                                         │
│  ④ 3GAP+3List分析                                           │
│     GAP1（目标差距）：年度目标 vs 当前预测                    │
│     GAP2（执行差距）：当前预测 vs 已执行                      │
│     GAP3（预测变动）：本期预测 vs 上期预测                    │
│     List1（确定类）：GAP1贡献项，抓执行，重效率               │
│     List2（风险类）：GAP2贡献项，看隐患，清风险               │
│     List3（机会类）：GAP3贡献项，找机会，赢机会               │
│                    │                                         │
│                    ▼                                         │
│  ⑤ 一报一会编制                                              │
│     一报：月度经营分析快报                                    │
│     一会：月度经营分析会材料                                  │
│     含执行率、象限执行、预警闭环追踪、3GAP+3List             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.5.3 三中心分工

| 中心 | 经营分析职责 |
|------|------------|
| 财经中心 | 利润表现、收入进度、管理及研发费用中的维持性费用分析 |
| 运营中心 | 各经营责任中心收入进展、品种表现、新增渠道表现、新产品上市情况、市场推广费用使用情况、销售团队人力情况 |
| 人力中心 | 集团整体人力编制及人力成本使用情况、人力资源管理问题 |

#### 4.5.4 AI内嵌能力

- **自动归因**：3GAP分析中AI自动归因，识别各GAP的贡献因素
- **智能归类**：3List中AI自动将偏差归入确定类/风险类/机会类
- **趋势预测**：AI基于历史数据预测后续月份执行趋势
- **一报一会自动编制**：AI自动生成月度快报和分析会材料初稿

### 4.6 PDCA复盘引擎

#### 4.6.1 引擎概述

PDCA复盘引擎负责月度、季度、年度三个维度的复盘工作，驱动预算体系的持续改进。

#### 4.6.2 PDCA-A月度闭环

```
┌──────────────────────────────────────────────────────────────┐
│                    PDCA-A月度闭环                              │
│                                                              │
│  ① 每月末触发                                                │
│                    │                                         │
│                    ▼                                         │
│  ② 预警闭环检查                                              │
│     · 当月新增预警数量统计                                    │
│     · 当月闭环预警数量统计                                    │
│     · 未闭环预警清单及原因分类                                │
│     · 超时升级统计                                           │
│                    │                                         │
│                    ▼                                         │
│  ③ 闭环率计算                                                │
│     月度闭环率 = 当月闭环数 / 当月新增数 × 100%              │
│                    │                                         │
│                    ▼                                         │
│  ④ 改进措施跟踪                                              │
│     上月改进措施执行情况跟踪                                  │
│     系统性偏差识别（反复出现的同类预警）                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.6.3 PDCA-B季度复盘

```
┌──────────────────────────────────────────────────────────────┐
│                    PDCA-B季度复盘                              │
│                                                              │
│  ① 每季度末触发                                              │
│                    │                                         │
│                    ▼                                         │
│  ② 3GAP+3List季度分析                                        │
│     基于经营分析引擎的季度数据                                │
│                    │                                         │
│                    ▼                                         │
│  ③ 象限内调拨建议                                            │
│     AI分析各象限执行率→生成象限内调拨建议                     │
│     象限内调拨→财经中心审批即可                               │
│     跨象限调拨→须管委会批准                                  │
│                    │                                         │
│                    ▼                                         │
│  ④ 滚动预测更新                                              │
│     各项目更新滚动预测数据                                    │
│     AI辅助预测偏差分析                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 4.6.4 PDCA-C年度校准

```
┌──────────────────────────────────────────────────────────────┐
│                    PDCA-C年度校准                              │
│                                                              │
│  ① 年度结束触发                                              │
│                    │                                         │
│                    ▼                                         │
│  ② 组合校准                                                  │
│     各象限年度执行率评估                                      │
│     战略意图维度执行率评估                                    │
│     预算组合比例合理性评估                                    │
│                    │                                         │
│                    ▼                                         │
│  ③ 次年建议                                                  │
│     AI生成次年战略预算组合调整建议                            │
│     未关闭预警反向输入至次年预算编制                          │
│     年度复盘结论落地追踪                                     │
│                    │                                         │
│                    ▼                                         │
│  ④ 新循环启动                                                │
│     年度执行数据库归档                                        │
│     触发次年预算编制引擎                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.7 报表引擎（三报一会）

#### 4.7.1 引擎概述

报表引擎负责**三报一会**的自动编制和分发（月度快报+季度汇报+年度复盘+经营分析会）。由于本系统数据天然同源，报表数据不存在口径对齐问题，数据唯一性由系统保证。

#### 4.7.2 三报一会定义

| 报表类型 | 名称 | 编制截点 | 核心内容 | 分发对象 |
|---------|------|---------|---------|---------|
| 月度快报 | 月度经营分析快报 | 每月12日数据定稿后 | 执行率/象限执行/预警闭环追踪 | 管委会、财经中心、各中心 |
| 季度汇报PPT | 季度经营分析汇报 | 季度数据汇总完成 | 趋势分析/调拨建议/滚动预测/3GAP+3List | 管委会、财经中心 |
| 年度复盘报告 | 年度经营复盘报告 | 年度结束 | 组合校准/次年建议/战略意图执行率 | 管委会、财经中心 |
| 经营分析会 | 月度经营分析会材料 | 每月12日后 | 含未闭环预警专项汇报 | 各中心财经BP、经营管理部 |

#### 4.7.3 5/8/10日截点自动出具

| 截点日期 | 出具内容 | 数据来源 |
|---------|---------|---------|
| 每月5日 | 单体报表 | 本系统各中心数据自动汇总 |
| 每月8日 | 月度经营分析报告 | 本系统执行率+预警+3GAP数据 |
| 每月10日 | 集团合并报表 | 本系统各单体报表自动合并 |
| 每月12日 | 数据定稿 | 本系统数据锁定，触发经营分析引擎 |

#### 4.7.4 数据唯一性保证

由于本系统是数据唯一源，报表引擎出具的所有报表数据天然一致：

- **不存在口径对齐问题**：所有数据由本系统产生，使用统一数据模型
- **不存在数据同步延迟**：报表引擎直接读取本系统数据，实时计算
- **不存在多版本问题**：数据定稿后锁定，所有报表基于同一版本数据
- **合并抵消自动完成**：集团合并报表的内部交易抵消由系统自动计算

#### 4.7.5 AI内嵌能力

- **自动编制**：AI根据数据自动生成报表初稿，含文字分析
- **异常标注**：AI自动标注异常数据点，附归因分析
- **趋势图表**：AI自动生成趋势分析图表
- **未闭环预警专项说明**：AI自动生成未闭环预警专项汇报材料

---

## 五、事件驱动架构

### 5.1 八阶段业务流程到事件驱动

传统模式下，八阶段业务流程的推进依赖人工驱动——人去跑流程、人去催审批、人去查数据。AI原生体系下，业务事件自动触发引擎行动，实现"数据推动人"。

```
┌──────────────────────────────────────────────────────────────┐
│            八阶段业务流程 → 事件驱动映射                       │
│                                                              │
│  阶段一：SP+BP ──→ sp_bp.decoded ──→ 预算编制引擎启动       │
│                              ──→ AI生成战略举措清单          │
│                              ──→ AI下达预算框架              │
│                                                              │
│  阶段二：预算授予 ──→ budget.granted ──→ 预算授予引擎启动    │
│                    ──→ budget.b2a.converted ──→ 引擎更新类别  │
│                                                              │
│  阶段三：费用报销 ──→ expense.submitted ──→ 费用报销引擎启动 │
│                    ──→ expense.approved ──→ 引擎核销额度     │
│                                                              │
│  阶段四：经营分析 ──→ data.finalized ──→ 经营分析引擎启动    │
│                                                              │
│  阶段五：实时预警 ──→ alert.monthly.triggered ──→ 预警引擎   │
│                    ──→ alert.quarterly.triggered ──→ 预警引擎 │
│                    ──→ alert.milestone.triggered ──→ 预警引擎 │
│                    ──→ alert.response.submitted ──→ 闭环引擎  │
│                                                              │
│  阶段六：PDCA ──→ pdca.monthly ──→ PDCA-A月度闭环           │
│               ──→ pdca.quarterly ──→ PDCA-B季度复盘          │
│               ──→ pdca.yearly ──→ PDCA-C年度校准             │
│                                                              │
│  阶段七：报表出具 ──→ report.monthly_5/8/10 ──→ 报表引擎    │
│                                                              │
│  阶段八：次年采集 ──→ next_cycle.started ──→ 预算编制引擎    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 事件定义与映射

所有事件由本系统内部产生和消费，不存在外部事件源。

| 事件类型 | 事件名称 | 触发条件 | 驱动引擎 | 对应阶段 |
|---------|---------|---------|---------|---------|
| 业务事件 | sp_bp.decoded | SP/BP解码完成 | 预算编制引擎→生成战略举措清单→下达预算框架 | 阶段一 |
| 业务事件 | budget.granted | 年度预算总额终审 | 预算授予引擎→A/B分类授予→系统锁定 | 阶段二 |
| 业务事件 | budget.a_class.approved | A类立项审批通过 | 预算授予引擎→全额冻结额度→通知业务 | 阶段二 |
| 业务事件 | budget.b2a.converted | B→A转换审批通过 | 预算授予引擎→全额锁定→更新预算类别 | 阶段二 |
| 数据事件 | expense.submitted | 报销单提交 | 费用报销引擎→L3管控标签路由→额度校验→进入审批流 | 阶段三 |
| 数据事件 | expense.approved | 报销单双线审批完成 | 费用报销引擎→核销预算额度→更新执行率 | 阶段三 |
| 时间事件 | data.finalized | 每月12日数据定稿 | 经营分析引擎→执行率计算→3GAP+3List→出具月度快报 | 阶段四 |
| 规则事件 | alert.monthly.triggered | 月度执行进度偏离阈值 | 预警引擎→四色分级预警→推送→启动响应计时 | 阶段五 |
| 规则事件 | alert.quarterly.triggered | 季度滚动预测偏离 | 预警引擎→四色分级预警→推送 | 阶段五 |
| 规则事件 | alert.milestone.triggered | 里程碑偏离 | 预警引擎→三维度独立判断→取最高级别 | 阶段五 |
| 业务事件 | alert.response.submitted | 责任人提交整改方案 | 预警引擎→财经BP确认→双签闭环 | 阶段五 |
| 时间事件 | pdca.monthly | 每月末 | PDCA复盘引擎→PDCA-A月度预警闭环检查 | 阶段六 |
| 时间事件 | pdca.quarterly | 每季度末 | PDCA复盘引擎→PDCA-B季度复盘→3GAP+3List→象限内调拨 | 阶段六 |
| 时间事件 | pdca.yearly | 年度结束 | PDCA复盘引擎→PDCA-C年度复盘→组合校准→次年建议 | 阶段六 |
| 时间事件 | report.monthly_5 | 每月5日 | 报表引擎→单体报表出具 | 阶段七 |
| 时间事件 | report.monthly_8 | 每月8日 | 报表引擎→月度经营分析报告 | 阶段七 |
| 时间事件 | report.monthly_10 | 每月10日 | 报表引擎→集团合并报表 | 阶段七 |
| 业务事件 | next_cycle.started | 年度复盘完成 | 预算编制引擎→数据反向输入→未关闭预警梳理→新循环启动 | 阶段八 |

### 5.3 行动建议引擎

事件触发后，行动建议引擎的工作流程：

```
① [数据感知] 从本系统数据模型中读取相关数据
② [场景匹配] 匹配到具体场景→取出激活的对象/关系/规则子集
③ [规则判断] 逐条套用原子规则
④ [分析推理] 组装推理链→归因分析
⑤ [行动建议] 生成附带原因分析和改进建议的通知
⑥ [引擎执行] 调用对应业务引擎执行操作→推送至对应责任人→启动响应计时
```

**行动建议示例**（对齐实际业务术语）：

```
【AI行动建议】🟡黄 | 津康·KA部·Q2招待费用率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 数据事实：
   当前值：15.2%（目标≤12%）
   偏离幅度：+3.2个百分点
   预警类型：月度执行进度预警
   L3科目：招待费（强管控）
   预算ID：B-2026-SK-015
   预算余额：5.2万（剩余额度充足但费用率超标）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 AI归因分析：
   主因（权重62%）：KA进院项目高峰期，3城同步启动
   次因（权重25%）：新入职KA经理招待标准执行偏差
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 建议行动：
   □ 选项A：确认KA进院高峰期合理超支 → AI自动生成说明并归档
   □ 选项B：制定Q3控费方案 → AI生成控费方案模板
   □ 选项C：申请追加预算 → AI预填追加申请表（强管控科目须增补预算）
   □ 选项D：联系财经BP深入分析
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 响应时限：2个自然日内（黄色预警）
⚠️ 注意：超时未响应将自动升级通知上级
```

**行动建议引擎与业务引擎的联动**：

| 事件 | 行动建议引擎操作 | 调用的业务引擎 |
|------|----------------|-------------|
| expense.submitted | 识别L3管控标签→路由审批 | 费用报销引擎 |
| expense.approved | 核销预算额度→更新执行率 | 费用报销引擎 |
| alert.monthly.triggered | 四色分级推送→启动响应计时 | 预警引擎 |
| alert.response.submitted | 财经BP确认→双签闭环 | 预警引擎 |
| data.finalized | 执行率计算→3GAP+3List→出具快报 | 经营分析引擎 |
| pdca.quarterly | 3GAP+3List→象限内调拨建议 | PDCA复盘引擎 |
| report.monthly_5 | 单体报表出具 | 报表引擎 |
| budget.b2a.converted | 全额锁定→更新类别 | 预算授予引擎 |

所有操作均由本系统内部引擎执行，不存在调用外部系统API的情况。

---

## 六、自然语言对话能力

### 6.1 对话能力六级分类

本系统的自然语言对话能力按复杂度划分为六级，从简单查询到自主规划逐层递进。每一级对应不同的AI能力要求、本体依赖深度和引擎协同范围。

| 等级 | 名称 | 能力定义 | 本体依赖 | 引擎协同 | 典型特征 |
|------|------|---------|---------|---------|---------|
| L1 | 事实查询 | 基于已有数据回答事实性问题 | 对象层 | 只读查询 | 单跳、确定性答案 |
| L2 | 关联查询 | 跨对象、跨关系的数据关联与对比 | 对象层+关系层 | 只读查询 | 多跳、需关联推理 |
| L3 | 归因分析 | 解释数据变动原因，定位根因 | 对象层+关系层+行为层 | 只读+分析引擎 | 因果推理、多因素拆解 |
| L4 | 行动建议 | 基于归因结果推荐具体行动方案 | 五层全用 | 分析+行动引擎 | 方案生成、风险评估 |
| L5 | 方案推演 | 对行动方案进行沙盘推演与比较 | 五层全用+场景层 | 全引擎协同 | 假设推理、多方案对比 |
| L6 | 自主规划 | 在目标约束下自主制定并执行多步计划 | 五层全用+场景层+评测集 | 全引擎协同+规则引擎 | 目标分解、步骤编排、闭环验证 |

### 6.2 对话场景示例

#### 场景一：L1 事实查询——预算科目执行率

```
用户：研发支出B2下III期临床项目CX-2026-003的累计执行率是多少？

AI：研发支出B2·III期临床项目CX-2026-003：
    累计执行率：112.3%（累计实际 2,246万 / 累计分期计划 2,000万）
    年度预算：3,500万
    预算余额：1,254万
    里程碑状态：大里程碑"III期临床入组完成"延期25天
    预警状态：🟡黄色（里程碑时间偏差+累计执行偏离）
```

#### 场景二：L2 关联查询——跨科目对比

```
用户：津康和华北区B5市场推广费的执行率对比？

AI：津康 vs 华北区 B5市场推广费对比：
    津康：预算¥2,800,000，已用¥1,960,000，执行率70.0%
    华北区：预算¥2,200,000，已用¥1,870,000，执行率85.0%
    差异：华北区执行率高出15个百分点
    原因：华北区Q2品牌活动前置，津康主要活动集中在Q3
    预警：华北区已触发🟡黄色预警（月度执行进度）
```

#### 场景三：L3 归因分析——费用率偏离

```
用户：津康Q2招待费用率为什么偏离目标3.2个百分点？

AI：津康·Q2招待费用率偏离归因分析：
    目标：≤12%  实际：15.2%  偏离：+3.2个百分点

    归因链：
    ① 主因（权重62%）：KA进院项目高峰期，3城同步启动
       → 招待频次同比+45%，单笔均值¥3,200（标准内）
    ② 次因（权重25%）：新入职KA经理招待标准执行偏差
       → 3笔超单笔上限¥20,000（已触发SR-008软规则）
    ③ 关联（权重13%）：Q2渠道拓展项目CP-2026-012关键谈判期
       → 招待支出与业务阶段吻合（RR-002推理规则确认）

    结论：偏离有业务合理性，但增速不可持续
    L3科目：招待费（强管控），不可跨部门跨费用类别
```

#### 场景四：L4 行动建议——里程碑延期

```
用户：研发项目CX-2026-003里程碑延期25天，我该怎么办？

AI：研发项目CX-2026-003·III期临床入组完成延期25天

    规则组装推理结果：
    ① [fin.alert.milestone.time_blue] 大里程碑延期21-30天 → 🔵蓝色
    ② [fin.alert.milestone.cost_blue] 费用偏差108% → 未触发
    ③ [fin.alert.milestone.cumulative_blue] 累计进度103% → 未触发
    ④ [fin.alert.milestone.max_level] 取最高 → 🔵蓝色
    ⑤ B2研发支出·III期临床Go/No-Go特殊规则：延期>14天 → 建议升级🟡黄色

    📌 建议行动：
    □ 选项A：提交里程碑进展说明（蓝色5工作日内）
    □ 选项B：主动升级黄色预警→冻结该项目L3新增付款→保护预算
    □ 选项C：申请里程碑调整→重新规划后续节点
    □ 选项D：联系财经BP评估对全年研发预算影响

    ⏰ 蓝色响应时限：5个工作日内
```

#### 场景五：L5 方案推演——预算调拨

```
用户：如果把津康发展象限50万调拨到收缩象限，会怎样？

AI：方案推演：津康·发展象限→收缩象限·50万调拨

    规则组装推理：
    ① [fin.adjustment.cross_quadrant] 跨象限调拨 → 须管委会批准
    ② 发展象限调出50万后执行率变化：72%→78%（仍在安全范围）
    ③ 收缩象限调入50万后执行率变化：95%→82%（缓解超支压力）
    ④ 3GAP分析：GAP2执行差距→收缩象限成本优化空间确认
    ⑤ 3List归类：List3机会类→收缩象限有结构性优化机会

    推演结果：
    | 维度 | 调拨前 | 调拨后 | 变化 |
    |------|--------|--------|------|
    | 发展象限执行率 | 72% | 78% | 🟢 上升6个百分点 |
    | 收缩象限执行率 | 95% | 82% | 🟢 下降13个百分点 |
    | 整体费用率 | 28.5% | 28.5% | ⚪ 不变 |
    | 管委会审批 | — | 需要 | 🟡 审批周期约5工作日 |

    结论：调拨方案合理，但须管委会批准。是否需要我生成调拨申请材料？
```

#### 场景六：L6 自主规划——Q3预算优化

```
用户：帮我制定Q3预算优化方案，目标是在不影响收入的前提下将费用率降低2个百分点

AI：已启动自主规划模式。目标：Q3费用率从28.5%→26.5%，收入不受影响。

    Step 1 基线分析 ✅
    - Q3需节约约¥1,850,000
    - 收入敏感科目：B5市场推广、B7货物支出
    - 非敏感科目：B3维持性、B4税务、B9财务费用

    Step 2 识别优化空间 ✅
    - 非敏感科目压缩：约¥420,000
    - 敏感科目结构性优化：约¥980,000
    - A类预算重新评估：约¥450,000
    - 合计：约¥1,850,000 ✅ 达标

    Step 3 方案编排 ✅
    | 优化项 | 预计节约 | 收入影响 | 执行难度 |
    |--------|---------|---------|---------|
    | B3/B4/B9标准下调10% | ¥185,000 | 无 | 低 |
    | B5活动排期优化 | ¥320,000 | <1% | 中 |
    | B7采购合并优化 | ¥280,000 | <2% | 中 |
    | B5招待标准下调 | ¥380,000 | <1% | 低 |
    | B1资本支出部分延至Q4 | ¥450,000 | 无 | 需管委会审批 |
    | B6培训改为内部 | ¥235,000 | 无 | 低 |

    Step 4 规则合规检查 ✅
    - 所有优化项均未违反硬规则
    - B1延后需管委会审批
    - B5标准下调需更新软规则阈值

    Step 5 执行计划 ✅
    W1：提交管委会审批B1延后
    W2：更新B5招待标准软规则
    W3：通知各部门新标准
    W4：启动B5/B7优化
    W5-W8：监控+月度复盘

    方案已生成，是否确认执行？
```

---

## 七、规则原子化、动态推理与自我进化

### 7.1 规则三层架构

```
┌─────────────────────────────────────────────┐
│            硬规则层（Hard Rules）              │
│   法定合规·管委会决策·红线约束·双签闭环       │
│   → 不可违反，系统强制执行                     │
├─────────────────────────────────────────────┤
│            软规则层（Soft Rules）              │
│   预警阈值·膨胀比例·审批门槛·费用率目标        │
│   → 可调整，需审批变更，系统默认执行           │
├─────────────────────────────────────────────┤
│            推理规则层（Reasoning Rules）        │
│   事件关联·趋势预测·异常归因·行动规划          │
│   → 可学习，由AI引擎动态组装                   │
└─────────────────────────────────────────────┘
```

| 维度 | 硬规则 | 软规则 | 推理规则 |
|------|--------|--------|---------|
| 来源 | 法律法规、管委会决议、制度红线 | 管理经验、历史数据、经营目标 | AI学习、业务模式、因果链 |
| 变更方式 | 仅管委会决议可变更 | 审批后可调整参数 | 系统自动学习+人工确认 |
| 违反后果 | 系统拦截，操作不可执行 | 触发预警，需说明原因 | 提示建议，不强制 |
| 执行方式 | 引擎强制校验 | 引擎默认执行+例外审批 | AI推理+引擎辅助 |
| 示例 | 无预算不得支出 | B类膨胀比例≤15% | 差旅费上升与项目数量关联 |

### 7.2 原子规则与组装推理

**原子规则定义**：原子规则是最小不可再分的业务约束单元，每条原子规则只表达一个独立的约束条件。

**硬规则原子规则**：

| 规则ID | 描述 | 参数 |
|--------|------|------|
| HR-001 | 支出必须有对应预算 | 无 |
| HR-002 | 预算核销不可超额 | 无 |
| HR-003 | 预警触发≠超支许可 | 无 |
| HR-004 | 先批后用（A类预算） | 无 |
| HR-005 | 双签闭环（业务+财经BP） | 无 |
| HR-006 | 税务申报数据必须完整准确 | 无 |
| HR-007 | 战略预算组合比例由管委会决定 | 无 |
| HR-008 | 跨象限调拨须管委会批准 | 无 |
| HR-009 | 里程碑延期未完成报备不得自行推进下一里程碑 | 无 |
| HR-010 | 实际支出不得超出里程碑计划金额，确需超支须事前审批 | 无 |
| HR-011 | 里程碑预警触发后新增支出须经对应级别审批后方可执行 | 无 |
| HR-012 | 未闭环预警须在经营分析会中专项汇报 | 无 |

**软规则原子规则**：

| 规则ID | 描述 | 默认参数 |
|--------|------|---------|
| SR-001 | 月度执行进度蓝色阈值 | 当月实际/累计执行>分期计划×105% |
| SR-002 | 月度执行进度黄色阈值 | 当月实际/累计执行>分期计划×110% |
| SR-003 | 月度执行进度红色阈值 | 实际已超年度预算或预计全年>年度预算 |
| SR-004 | 季度滚动预测蓝色阈值 | 105% |
| SR-005 | 季度滚动预测黄色阈值 | 110% |
| SR-006 | 季度滚动预测红色阈值 | 115% |
| SR-007 | B类膨胀比例上限 | 30% |
| SR-008 | 单项目/单供应商偏差红色阈值 | 50万 |
| SR-009 | 部门负责人审批金额门槛 | ¥50,000 |
| SR-010 | 中心总经理审批金额门槛 | ¥200,000 |
| SR-011 | 项目化管理门槛 | 年度预算超50万或新增项目单笔超20万须纳入项目化管理 |

**推理规则原子规则**：

| 规则ID | 描述 | 学习来源 |
|--------|------|---------|
| RR-001 | 差旅费与项目数量正相关 | 历史数据回归 |
| RR-002 | 招待费与渠道拓展阶段关联 | 业务模式分析 |
| RR-003 | 培训费季节性波动模式 | 月度系数矩阵 |
| RR-004 | 预算执行率与剩余时间非线性关系 | S曲线拟合 |
| RR-005 | 研发里程碑延期对后续节点传导效应 | 项目数据学习 |

**组装推理示例：费用报销场景**

```
输入：华北区张伟提交B5业务招待费报销单，金额¥18,500

规则组装推理链：
  ├─ HR-001 检查：B5是否有预算？ → ✅ 有，剩余额度¥52,650
  ├─ HR-002 检查：报销金额是否超额？ → ¥18,500 ≤ ¥52,650 ✅
  ├─ HR-005 检查：需双签闭环 → ✅ 业务+财经BP
  ├─ SR-009 检查：金额¥18,500 < ¥50,000 → 部门负责人审批
  ├─ SR-002 检查：B5当前执行率89.3% > 110% → ⚠️ 已触发黄色预警
  └─ RR-002 推理：渠道拓展项目CP-2026-012关键谈判期 → 招待支出有业务合理性

  组装结论：允许报销，标注黄色预警关联，建议关注B5后续趋势
```

### 7.3 动态规则调整

软规则参数可根据业务变化动态调整，调整必须经过审批并记录完整变更轨迹。

```
触发条件检测 → 影响评估分析 → 审批流程执行 → 参数更新生效 → 评测集验证确认
```

| 触发事件 | 调整内容 | 审批层级 | 评测验证 |
|---------|---------|---------|---------|
| B5连续3个月触发黄色预警 | SR-008单笔上限从¥20,000降至¥15,000 | 财务总监 | 历史数据回放，误报率<5% |
| 费用率连续2季度低于目标 | 费用率目标从26%下调至24% | 管委会 | 模拟新目标下各部门预算充足率 |
| 华东区业务扩张 | SR-009华东区审批门槛从¥50,000上调至¥80,000 | 财务总监 | 审批效率提升，风险可控 |

推理规则由AI引擎基于历史数据自动学习，每次更新需经评测集验证：

```
历史数据 → 模式识别 → 规则候选 → 评测集验证 → 人工确认 → 规则更新
```

### 7.4 自我进化闭环

```
┌─────────────────────────────────────────────────────────────┐
│                    自我进化闭环                               │
│                                                             │
│    ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐       │
│    │ 观测 │────→│ 分析 │────→│ 假设 │────→│ 验证 │       │
│    │      │     │      │     │      │     │      │       │
│    │运行数据│     │偏差定位│     │规则候选│     │评测集  │       │
│    │用户反馈│     │模式发现│     │参数调整│     │A/B测试 │       │
│    └──────┘     └──────┘     └──────┘     └──────┘       │
│         ↑                                      │           │
│         │              ┌──────┐                │           │
│         └──────────────│ 部署 │←───────────────┘           │
│                        │      │                            │
│                        │灰度发布│                            │
│                        │全量生效│                            │
│                        └──────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### 7.5 进化安全边界

**五条进化安全红线**：

| # | 安全红线 | 具体要求 | 违反处理 |
|---|---------|---------|---------|
| 1 | 硬规则不可自动修改 | 任何硬规则变更必须经管委会决议 | 自动修改尝试将被拦截并告警 |
| 2 | 软规则调整需审批 | 软规则参数变更必须经过对应审批层级确认 | 未经审批的变更不生效 |
| 3 | 推理规则需评测通过 | 新增或修改推理规则必须通过评测集验证 | 评测未通过的规则不进入生产 |
| 4 | 所有变更可回退 | 任何规则变更保留前一版本，支持一键回退 | 回退操作需记录原因 |
| 5 | 变更轨迹全程可审计 | 每次规则变更记录完整信息 | 审计日志不可删除 |

**进化权限矩阵**：

| 操作 | AI引擎自动 | 财务总监审批 | 管委会决议 |
|------|-----------|------------|-----------|
| 推理规则新增/修改 | 可提议+评测 | 确认后生效 | — |
| 软规则参数调整 | 可提议+影响评估 | 限额内审批 | 超限额审批 |
| 硬规则修改 | 不可提议 | 不可审批 | 唯一途径 |

---

## 八、评测体系与可追溯性

### 8.1 评测集：一等公民

评测集不是附属的测试工具，而是与业务引擎、规则引擎并列的一等公民。评测集的质量直接决定系统进化的质量和速度。

### 8.2 评测集设计

评测集按业务场景组织，覆盖9大类别：

```
评测集
├── 预算编制评测（A/B分类正确性、战略预算组合比例、B类膨胀控制、科目挂载正确性）
├── 预算授予评测（A类先批后用、B类额度内灵活、系统锁定机制）
├── 费用报销评测（四级管控路由、双线审批流程、预算核销准确性、无预算拦截）
├── 预警监控评测（四色分级准确性、三种通用规则触发、L1专项预警触发、预警≠超支许可）
├── 经营分析评测（3GAP分析正确性、3List生成完整性、象限归属准确性）
├── PDCA复盘评测（PDCA-A/B/C分类、行动项闭环追踪）
├── 规则引擎评测（硬规则不可违反、软规则默认执行、原子规则组装正确性）
├── 对话能力评测（L1-L6各级准确率/完整率/合理性）
└── 进化评测（规则变更后通过率、回退机制有效性、安全边界遵守性）
```

**评测通过标准**：

| 评测类别 | 通过标准 | 回归标准 |
|---------|---------|---------|
| 硬规则评测 | 100%通过 | 任何失败即回退 |
| 软规则评测 | ≥98%通过 | 通过率下降>2%即回退 |
| 推理规则评测 | ≥95%通过 | 通过率下降>5%即回退 |
| 对话能力评测 | ≥90%通过 | 通过率下降>3%即回退 |

### 8.3 推理轨迹格式

每次推理过程都记录完整的推理轨迹，确保可追溯、可审计、可复盘。对话路径仍写 ReasoningTrace；改变世界状态的引擎路径另写 `DecisionRecord`（MySQL + 图投影），可用 `explain_expense` 还原一笔报销的提交/审批/核销链。

```yaml
trace_id: "TRACE-20260528-001"
timestamp: "2026-05-28T14:30:00+08:00"
scene: "费用报销"
input:
  action: "提交报销单"
  subject: "B5业务招待费"
  amount: 18500
  applicant: "张伟"
  department: "华北区"

reasoning_chain:
  - step: 1
    rule_id: "HR-001"
    rule_type: "hard"
    rule_desc: "支出必须有对应预算"
    reasoning: "B5预算存在，剩余额度¥52,650"
    output: "PASS"
    confidence: 1.0

  - step: 2
    rule_id: "HR-002"
    rule_type: "hard"
    rule_desc: "预算核销不可超额"
    reasoning: "¥18,500 ≤ ¥52,650"
    output: "PASS"
    confidence: 1.0

  - step: 3
    rule_id: "HR-005"
    rule_type: "hard"
    rule_desc: "双签闭环"
    reasoning: "B5需业务+财经BP双签"
    output: "REQUIRE_DUAL_SIGN"
    confidence: 1.0

  - step: 4
    rule_id: "SR-009"
    rule_type: "soft"
    rule_desc: "部门负责人审批门槛¥50,000"
    reasoning: "¥18,500 < ¥50,000，部门负责人审批即可"
    output: "ROUTE_TO_DEPT_HEAD"
    confidence: 1.0

  - step: 5
    rule_id: "SR-002"
    rule_type: "soft"
    rule_desc: "月度执行进度黄色阈值110%"
    reasoning: "B5当前执行率89.3% < 110%，但>105%蓝色阈值"
    output: "WARNING_BLUE"
    confidence: 1.0

  - step: 6
    rule_id: "RR-002"
    rule_type: "reasoning"
    rule_desc: "招待费与渠道拓展阶段关联"
    reasoning: "渠道拓展项目CP-2026-012关键谈判期，招待支出有业务合理性"
    output: "BUSINESS_JUSTIFIED"
    confidence: 0.87

conclusion:
  action: "允许报销"
  route: "部门负责人→财经BP"
  annotations: ["蓝色预警关联", "业务合理性确认"]
  post_actions: ["标记B5趋势观察"]

metadata:
  total_steps: 6
  hard_rules_checked: 3
  soft_rules_checked: 2
  reasoning_rules_applied: 1
  min_confidence: 0.87
  execution_time_ms: 120
```

### 8.4 评测驱动迭代闭环

```
变更触发 → 评测执行（全量/增量/性能） → 结果分析（通过率/回归项/新发现）
    ↑                                          │
    │                                   部署决策
    │                                   ·全量通过→发布
    │                                   ·部分失败→修复→重测
    └────────────────────────────────── ·严重回归→回退
```

---

## 九、大模型弱点应对策略

### 9.1 多跳推理衰减

**问题**：大模型在多步推理中，随着推理链长度增加，准确率显著下降。

**应对策略**：

| 策略 | 具体做法 | 效果 |
|------|---------|------|
| 原子规则拆分 | 每步只执行一条原子规则 | 单步推理复杂度降低 |
| 推理链显式化 | 强制输出每步推理的规则ID、输入、输出 | 减少隐式跳步错误 |
| 引擎兜底 | 硬规则由确定性引擎执行，不依赖大模型推理 | 硬规则100%准确 |
| 分段验证 | 每3步设置检查点，验证中间结果一致性 | 及时发现推理偏移 |

### 9.2 精确与大规模计算

**问题**：大模型不擅长精确数值计算和大规模数据处理。

**应对策略**：

| 策略 | 具体做法 | 适用场景 |
|------|---------|---------|
| 计算引擎分离 | 所有数值计算由确定性计算引擎执行 | 预算核销、费用率计算 |
| 双重校验 | 关键计算结果由计算引擎独立验证 | 预警分级、审批金额判断 |
| 批量处理分离 | 大规模数据汇总由数据库引擎执行 | 报表出具、经营分析 |

### 9.3 结果不一致性

**问题**：大模型对相同输入可能产生不同输出。

**应对策略**：

| 策略 | 具体做法 | 应对类型 |
|------|---------|---------|
| 确定性引擎兜底 | 硬规则和数值计算由确定性引擎执行 | 数值+判断不一致 |
| 输出模板约束 | 大模型输出受模板约束，格式固定 | 格式不一致 |
| 规则链完整性校验 | 每次推理必须走完所有适用规则 | 遗漏不一致 |
| 温度参数控制 | 财经场景使用低温度（temperature=0） | 全类型 |
| 缓存机制 | 相同查询在数据未变更时返回缓存结果 | 格式+数值不一致 |

---

## 十、系统架构

### 10.1 一体化系统架构总图

```
┌─────────────────────────────────────────────────────────────────┐
│                      交互层（Interaction Layer）                 │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ 自然语言  │  │ BI驾驶舱 │  │ 移动端   │  │ 消息通知中心  │  │
│  │ 对话界面  │  │ (可视化) │  │ (钉钉等) │  │ (预警/报告)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    AI引擎层（AI Engine Layer）                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ FinanceAgent（唯一Agent，42个工具）                        │  │
│  │  · match_scene_semantic() → 动态选择1~3个Skill            │  │
│  │  · merge_skill_contexts() → 合并激活上下文                │  │
│  │  · 18个Skill：chat-finance / budget-planning /            │  │
│  │    expense-reimbursement / alert-monitor /                 │  │
│  │    business-analysis / report-generation /                 │  │
│  │    b2a-conversion / budget-adjustment /                    │  │
│  │    approval-routing / pdca-review /                        │  │
│  │    cash-flow-monitor / cost-center-accounting /            │  │
│  │    hcp-compliance / impact-assessment /                    │  │
│  │    pipeline-management / scenario-planning /               │  │
│  │    zero-based-budget / executive-dashboard                 │  │
│  │  · 不持有 Neo4j driver；写路径经引擎落 Decision            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ 意图识别+    │  │ 本体驱动+    │  │ 推理引擎+            │ │
│  │ 语义解析     │  │ 场景匹配     │  │ 原子规则组装         │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ OAG上下文    │  │ 事件路由引擎 │  │ 行动建议引擎+        │ │
│  │ 注入+幻觉检测│  │ (Event Bus)  │  │ 推理轨迹+Decision    │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              业务语义本体层（Ontology Layer）                      │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ 对象层   │ │ 关系层   │ │ 行为层   │ │ 规则层   │         │
│  │·L1/L2/L3│ │·挂载     │ │·冻结额度 │ │·硬规则   │         │
│  │ 科目     │ │·对标     │ │·释放额度 │ │·软规则   │         │
│  │·预算项目 │ │·触发     │ │·发起审批 │ │·推理规则 │         │
│  │·预警记录 │ │·响应     │ │·出具报告 │ │ (原子化) │         │
│  │·角色     │ │·裁决     │ │·调拨预算 │ │          │         │
│  │·报表     │ │·归属     │ │·B→A转换  │ │          │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 场景层（11个核心场景对齐八阶段）                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 评测集（一等公民）                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              核心业务引擎层（Business Engine Layer）               │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │预算编制  │ │预算授予  │ │费用报销  │ │预警监控  │         │
│  │引擎      │ │引擎      │ │引擎      │ │引擎      │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │经营分析  │ │PDCA复盘  │ │报表出具  │ │预算调整  │         │
│  │引擎      │ │引擎      │ │引擎      │ │引擎      │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                 │
│  ┌──────────┐ ┌──────────┐                                     │
│  │审批流转  │ │消息通知  │                                     │
│  │引擎      │ │引擎      │                                     │
│  └──────────┘ └──────────┘                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              数据与规则层（Data & Rules Layer）                    │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ MySQL = SoT  │  │ 规则引擎层   │  │ GraphStore 投影      │ │
│  │·预算数据    │  │·硬规则库    │  │·Memory 为读面        │ │
│  │·报销数据    │  │·软规则库    │  │·可选 Neo4j 双写      │ │
│  │·审批数据    │  │·推理规则库  │  │·实例 upsert/tombstone│ │
│  │·预警数据    │  │·阈值参数库  │  │·禁止全量 DETACH DELETE│ │
│  │·报表数据    │  │·RACI矩阵   │  │·Decision 图投影      │ │
│  │·科目主数据  │  │·HR 写入门闩 │  │                      │ │
│  │·组织架构    │  │·SoD 职责分离│  │                      │ │
│  │·角色权限    │  │             │  │                      │ │
│  │·decision_record│ │             │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │ Elasticsearch│  │ Redis        │                             │
│  │·全文检索    │  │·会话缓存    │                             │
│  │·向量搜索    │  │·预算缓存    │                             │
│  │·日志分析    │  │·限流计数    │                             │
│  └──────────────┘  └──────────────┘                             │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 外部接口层（仅用于数据导入/导出，非业务依赖）             │  │
│  │ ·ERP数据导入 ·银行对账数据导入 ·税务申报数据导出         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**五层架构核心原则**：

| 原则 | 说明 |
|------|------|
| 数据自产自销 | 所有业务数据由本系统引擎产生和消费，不依赖外部系统同步 |
| 引擎原生执行 | 所有业务流程由本系统引擎执行，不调用外部系统API |
| 规则内嵌 | 三层规则由本系统规则引擎执行；硬规则在写路径强制门闩，复合推理仍由 LLM 组装 |
| 本体驱动 | 业务语义由本体层统一定义，引擎和AI层共享同一语义空间 |
| 图是投影 | 图查询面从 MySQL 实例 hydrate；不是第二套 SoT |
| 外部可选 | 外部接口仅用于数据导入/导出，断开后系统仍可独立运行 |

### 10.2 技术架构

| 层次 | 技术选型 |
|------|---------|
| 前端 | React 18 + TypeScript + Vite + Zustand；ECharts可视化 |
| 后端 | Python + FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| AI层 | OpenAI及其兼容大模型；GraphStore（Memory + 可选 Neo4j 投影）；Elasticsearch向量+全文检索；自研评测框架；1 Agent (FinanceAgent) + 18 Skills 动态组合 |
| 数据层 | MySQL 业务 SoT（含 decision_record）+ GraphStore 投影 + Elasticsearch全文/向量 + Redis缓存 |

---

## 十一、待实验验证的开放问题

| # | 开放问题 | 为什么重要 | 验证方式 | 预期时间 |
|---|---------|-----------|---------|---------|
| 1 | L4-L6对话能力的实际可用性 | 大模型复杂推理表现不确定 | 真实场景评测集+财务人员盲评 | Phase 2末 |
| 2 | 原子规则组装推理的完备性 | 是否存在规则间隙 | 全场景覆盖验证+间隙检测 | Phase 3中 |
| 3 | 自我进化闭环的收敛速度 | 是否会出现震荡 | 3个月进化数据分析+震荡检测 | Phase 3末 |
| 4 | 本体五层模型的表达能力上限 | 是否需要扩展第六层 | 业务专家反馈+无法表达场景统计 | Phase 2末 |
| 5 | 推理轨迹对审计的实际价值 | 审计人员能否理解 | 审计人员试用+可用性反馈 | Phase 3末 |
| 6 | 大模型+确定性引擎的协作效率 | 切换开销和协作效率 | 性能基准测试 | Phase 2中 |
| 7 | 评测集的维护成本 | 是否可控 | 6个月维护工作量分析 | Phase 3末 |

---

## 十二、总结：AI原生一体化系统的核心特征

**1. 数据自产自销，口径天然一致**——所有业务数据由自身引擎产生和消费，不存在跨系统同步和口径对齐问题。

**2. 引擎原生执行，流程系统内连贯**——10个核心业务引擎覆盖全流程，不存在跨系统调用和API适配问题。

**3. 规则原子化组装，灵活且一致**——三层规则全部原子化；硬规则由确定性引擎在写路径强制执行，复合效果由大模型组装，天然一致。

**4. 本体驱动+引擎协同，新场景即插即用**——新场景只需本体扩展+引擎配置，无需外部依赖。

**5. 评测驱动进化，质量持续保障**——评测集作为一等公民；推理轨迹与 DecisionRecord 分别覆盖对话过程与写操作审计。

一个AI原生的财经管理一体化系统——数据自产自销、引擎原生执行、规则原子组装、本体驱动进化、评测保障质量，彻底消除对外部系统的业务依赖，实现真正的智能财经管理。
