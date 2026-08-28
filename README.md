# 集团财经管理AI原生系统

集团财经管理 AI 原生一体化系统。业务概念先在本体中定义，运行时由 **Supervisor + 唯一 FinanceAgent + 18 个 Skill** 完成对话与跨域任务；改变世界状态的动作走领域引擎。MySQL 是业务事实（含 `decision_record`）；图是投影。

覆盖：预算编制 / 费用报销 / 审批 / 预警 / 经营分析 / 报表 / PDCA / 现金流 / 零基预算 / 研发管线 / HCP 合规 / 场景规划。

---

## 架构概览

```
Frontend  React 18 · Vite · Zustand · React Query · ECharts
          23 个页面文件（EvalPage 未挂路由）· 51 Components · SSE
                    │ HTTP / WebSocket / SSE
FastAPI   32 REST routers · JWT
                    │
          Supervisor：guardrails → 缓存 → 意图 → 槽位 → Agent → 反思 → 幻觉检测
          FinanceAgent：42 工具 · 1~3 Skill · OAG（不持有 Neo4j driver）
                    │
          Ontology：对象/关系/行为/规则/场景 · HardRule/SoD · DecisionRecorder
                    │
          Engines 38 + Services 24
                    │
Storage   MySQL = SoT
          GraphStore：Memory 读面 + 生产 Neo4j DualWrite 投影
          Elasticsearch · Redis
```

分层：`api → agents → engines → ontology → storage`。

---

## 核心特性

### 本体驱动 (OAG)

- **Agent-Skill**：单一 FinanceAgent + 18 个 `SKILL.md`，运行时选 1~3 个 Skill，合并 `activated_objects/rules/behaviors`
- **CFO 方法论**：`ontology/references/methodology/` 下 5 份标准；另有预算八步、L3 管控标签、指标口径
- **OAG 注入**：对象/规则/行为/关系路径/聚合，按 `relevance_score` 裁剪；硬规则另有 1500 token 预算，裁掉 HR-* 则拒答

### Agent 与编排

- **FinanceAgent**：42 个工具（29 只读）；写工具走引擎 SoT
- **Supervisor**：guardrails → 语义缓存 → 意图 → 槽位 → Agent → 反思（≤3）→ 幻觉检测
- **跨域**：`impact_query` / `scenario_query` / `analysis_query` 串联多个 Agent 节点（均为 FinanceAgent，不同 Skill 上下文）
- **已废弃 Agent**：`budget/expense/alert/analysis/report/general_agent.py` 保留但不注册

### 存储与决策

- **MySQL** 记账；图从实例 **upsert / tombstone** 投影，禁止全量 `DETACH DELETE`
- **生产应连接 Neo4j**（DualWrite）；连不上时 Memory 作为故障读面
- **HR-001**（支出必须有对应预算）在报销提交时强制执行；拦住则 `Decision.outcome=blocked`
- **DecisionRecord**：报销/审批/核销、预警闭环、授予/B→A/调拨等写路径落库 + 图投影
- **SoD**：提交人 ≠ 终审人；预警响应人 ≠ 闭环确认人；调拨发起 ≠ 终审
- **DecisionSandbox** 是事前试运行，不要与 DecisionRecord 混用

### 高级分析与专项引擎

- 趋势预测 / 异常检测 / 根因 / 级联风险 / 预警模式（可由 LLM 组链）
- 业务诊断（杜邦 / BCG）· 零基 · 管线 · 情景与弹性预算 · 成本中心 · HCP · 现金流三件套
- 审批瓶颈 · 报销异常与风险分 · Pareto · 下一周期建议

### 认知服务层（24 个，不含 `__init__.py`）

RAG / 知识库 / 语义切块 / 语义缓存 · 战略/预算/管线认知 · 影响归因 / 谱系 · 查询改写 / 提示词 · 主动顾问 / 演化 · 上下文总线 / 工作流 · guardrails / audit_log / scheduler

### 技能包（18 个 Skill · SKILL.md）

| Skill | 场景 |
|-------|------|
| chat-finance | 综合财经对话 |
| budget-planning / budget-adjustment / zero-based-budget | 预算三类 |
| expense-reimbursement | 报销 |
| alert-monitor | 预警监控 |
| business-analysis / executive-dashboard | 经营分析 |
| report-generation | 报表出具 |
| b2a-conversion | B→A 转换 |
| approval-routing | 审批路由 |
| pdca-review | PDCA 复盘 |
| cash-flow-monitor | 现金流监控 |
| cost-center-accounting | 成本中心核算 |
| hcp-compliance | HCP 合规 |
| impact-assessment | 影响评估 |
| pipeline-management | 管线管理 |
| scenario-planning | 场景规划 |

### 业务能力

- **战略对齐**：结构化报告 + 双维覆盖度（项数 + 金额）
- **预算精细化**：调拨 4 步 + 里程碑证据 + B 类膨胀预警
- **报销战略审核**：4 维评估 + score<30 强制 / 30–40 建议 + 90 天效果追踪
- **3GAP / 3List**：滚动预测 + 季节因子 + 业务语义分类
- **双口径报表**：B1–B9 映射 + 白名单 eval
- **实时预警**：预算事件驱动 + 24h 去重 + 预测性预警
- **现金流 / 零基 / 管线 / HCP / 情景弹性预算**

### 事件驱动

- **16 种领域事件**：OBJECT_* / RELATION_* / RULE_VIOLATED / ALERT_* / BUDGET_* / SCENE_ACTIVATED / CONSISTENCY_ISSUE
- **4 类订阅者**：审计、Write-Back、一致性告警、事件驱动预警
- **Write-Back**：STRONG / EVENTUAL + 死信 + 重试 3 次

### 权限与审批

- **字段级 + OBAC + ABAC**；关键写路径叠加 SoD
- **AI 权限 L1–L4**：只读 / 建议 / 低风险执行 / 高风险执行
- **9 步审批链**：组织线 5 + 法人线 4
- **四级管控**：强管控 / 中心弱管控 / 组合管控 / 不管控
- **战略审核步**：score<30 mandatory / 30≤score<40 advisory

### 预警体系

- **四色**：蓝（>60% 站内信 72h）/ 黄（>80% 站+邮 24h）/ 橙（>95% + 短信 4h）/ 红（超预算 + 电话立即）
- L1 专项阈值可配；预测：移动平均 + 线性回归 + 季节调整

### 幻觉检测

- **4 策略**：事实锚定 / 数值（约 5% 容差）/ 关系 / 上下文充分性
- 硬规则被窗口裁掉 → `truncated_hard_rules` → **拒答**

### 变更管理

版本快照、回滚、血缘、差异（`change_management.py`）

### 可视化

ECharts：趋势、热力、象限、瀑布、仪表盘、雷达、桑基、散点、对比柱、面积图

---

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + aiomysql |
| Agent | Supervisor + FinanceAgent（42 工具）+ LangChain / LangGraph |
| LLM | OpenAI-compatible API + 语义缓存 + RAG |
| 关系库 | MySQL 8（业务 SoT） |
| 图 | GraphStore Protocol；生产 Neo4j 5 投影（读走 Memory） |
| 检索 / 缓存 | Elasticsearch 8 · Redis 7 |
| 调度 | APScheduler（daily_alert_scan / auto_escalate / predictive_scan） |
| 前端 | React 18 + TypeScript + Vite + React Query + Zustand + Tailwind + ECharts |
| 流式 | SSE + WebSocket |

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0+ / Neo4j 5+（生产） / Elasticsearch 8+ / Redis 7+

### 后端启动

```bash
cd backend

pip install -r requirements.txt

cp .env.example .env
# 编辑 MYSQL_URL / NEO4J_URL / NEO4J_USER / NEO4J_PASSWORD / ELASTIC_URL / REDIS_URL / LLM_API_URL / SECRET_KEY

python -m seed.seed_all
# 开发也可 SEED_ON_START=True（生产不要开）

uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

驱动实际使用 `NEO4J_URL`（bolt）。`NEO4J_URI` 亦在配置中，请与集群协议保持一致。

### 前端启动

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev            # http://localhost:5173
npm run build
```

---

## 项目结构（实际代码）

```
ai-finance/
├── backend/
│   ├── main.py                       # lifespan：DB → seed → 实例 → GraphStore hydrate → Decision hydrate
│   ├── websocket.py
│   ├── agents/                       # finance_agent.py（42 工具）· supervisor · base · state
│   ├── storage/                      # GraphStore · Memory · Neo4j · DualWrite · runtime
│   ├── ontology/                     # 对象/关系/行为/场景/规则 · OAG · 事件 · 实例
│   │   ├── decision_record.py / decision_recorder.py / write_hooks.py / sod.py / provenance.py
│   │   ├── graph_query.py / graph_projection.py
│   │   ├── rules/                    # hard_rules · soft_rules · reasoning_rules
│   │   └── references/               # 八步 / L3 / 口径 + methodology/ 五份 CFO 标准
│   ├── engines/                      # 38 个领域引擎（不含 __init__.py）
│   ├── services/                     # 24 个认知服务
│   ├── skills/                       # 18 个 SKILL.md + skill_loader.py
│   ├── api/                          # 32 routers（含 decisions.py）
│   ├── models/                       # 含 decision.py
│   ├── eval/                         # 7 类脚本 + runner + eval_cases.yaml
│   └── utils/
├── frontend/src/
│   ├── pages/                        # 23 文件；EvalPage 未接入 App.tsx
│   └── components/                   # 51 个 .tsx
├── docs/
└── README.md
```

引擎与 Skill 目录清单与仓库一致，此处不重复罗列。完整树以仓库为准。

---

## API 文档

启动后访问 `http://localhost:8000/docs`（Swagger）。以下路径与代码一致；完整列表以 OpenAPI 为准。

| 域 | 端点 |
|----|------|
| **AI 对话** | `POST /api/stream/chat`（SSE）· `GET /api/agents` · `POST /api/agents/{name}/execute` |
| **认证** | `POST /api/auth/login` · `POST /api/auth/refresh` · `GET /api/auth/me` |
| **预算** | `GET /api/budget/items` · `POST /api/budgets/transfers` |
| **报销** | `POST /api/expenses` · `GET /api/expenses` · `POST /api/expenses/{id}/write-off` |
| **审批** | `GET /api/approvals/pending` · `POST /api/approvals/{id}/approve` |
| **预警** | `GET /api/alerts` · `POST /api/alerts/cascade-risk` · `POST /api/alerts/pattern-analysis` |
| **分析** | `POST /api/analysis/predict-trend` · `POST /api/analysis/detect-anomalies` · `POST /api/analysis/root-cause` · `POST /api/analysis/compare-periods` |
| **报表** | `POST /api/reports/trend-analysis` · `POST /api/reports/risk-assessment` · `POST /api/reports/special` |
| **决策** | `GET /api/decisions/{id}` · `GET /api/decisions/{id}/chain` · `POST /api/decisions/search` · `GET /api/decisions/explain/expense/{id}` |
| **本体** | `POST /api/ontology/instances` · `POST /api/ontology/graph/path` · `GET /api/ontology/runtime/traces` · `GET /api/ontology/synonyms` |
| **战略** | `GET /api/strategic/matrix` |
| **现金流** | `GET /api/cashflow/forecast` · `GET /api/cashflow/aging` |
| **场景** | `GET /api/scenarios` |
| **零基** | `POST /api/zbb/reviews` |
| **成本中心** | `POST /api/cost-centers/standard-costs` |
| **HCP** | `POST /api/hcp/verify` · `GET /api/hcp/{id}/risk` |
| **管线** | `GET /api/pipelines` |
| **复盘** | `POST /api/business-review/agenda` |
| **洞察** | `GET /api/insights/active` |
| **谱系** | `GET /api/lineage/expense/{id}` · `GET /api/lineage/alert/{id}` · `GET /api/lineage/budget/{id}` |
| **设置** | `GET /api/settings/alert-thresholds` · `GET /api/settings/alignment-map` · `GET /api/settings/caliber-mappings` |
| **评估** | `POST /api/eval/run` · `GET /api/eval/results` · `GET /api/eval/baseline` |
| **健康** | `GET /api/health` |

Supervisor 运行指标在进程内（`Supervisor.get_metrics()`），**没有** `GET /api/agents/metrics`。无注册接口。

---

## 配置说明

配置见 `backend/.env.example`。

| 配置 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_URL` | MySQL 连接串 | `mysql+aiomysql://...` |
| `NEO4J_URL` | Neo4j bolt（驱动使用此项） | `bolt://localhost:7687` |
| `NEO4J_URI` | Neo4j URI | `neo4j://localhost:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | Neo4j 认证 | `neo4j` / — / `neo4j` |
| `ELASTIC_URL` | ES | `http://localhost:9200` |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` |
| `LLM_API_URL` | LLM | `http://localhost:11434/v1` |
| `LLM_MODEL` | 模型名 | `Qwen2.5-14B-Instruct-1M` |
| `SECRET_KEY` | JWT | — |
| `SEED_ON_START` | 启动自动 seed | `False` |
| `SEED_FORCE_RELOAD` | 清空再 seed | `False` |
