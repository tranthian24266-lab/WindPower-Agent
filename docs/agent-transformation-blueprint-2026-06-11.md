# 风电智能诊断平台智能体化改造书

更新时间：2026-06-11  
适用仓库：`C:\Users\luzian\Desktop\windpower_agent3`

## 1. 文档目标

本文档用于把当前“风电小模型智能诊断平台”改造成一个工程质量较高、具备可编排、可追踪、可恢复、可审计能力的垂直智能体项目。

这不是一份泛泛而谈的概念说明，而是一份面向当前仓库的技术改造书，重点回答三件事：

1. 这个项目要补哪些能力，才能从“带 LLM 能力的诊断系统”升级为“优秀的智能体项目”。
2. 每项改造应该落到哪些代码目录、数据库结构、接口、页面和测试用例。
3. 整个改造应该按什么阶段推进，才能降低风险、保持可交付。

## 2. 当前项目基线

### 2.1 当前已有能力

当前仓库已经具备一个不错的垂直场景底座：

- 后端：FastAPI，主要代码位于 `backend/app/api`、`backend/app/core`、`backend/app/db`
- 前端：React + Vite，主要代码位于 `frontend/src/pages`、`frontend/src/components`、`frontend/src/lib`
- 模型执行：通过 `littlemodel` 外部模型库统一调用 `inference.py:predict`
- 案例管理：上传、诊断、案例详情、基础报告、增强报告、聊天、知识库、模型目录
- RAG 能力：本地索引 + 可选 Qdrant
- 基础观测：`telemetry_service.py` 已有事件落盘雏形
- 测试：后端 `pytest`，前端 `build` 和 Playwright E2E

### 2.2 当前结构的核心问题

当前项目距离“优秀智能体项目”的差距，不在于少一个聊天框，而在于缺少智能体运行时这一层。

现状更接近：

- 一个诊断平台
- 若干服务模块串联
- 少量 LLM 增强能力

但还不是：

- 有明确运行状态的 Agent Workflow
- 可暂停/恢复/审阅的执行系统
- 有证据链和 guardrails 的决策系统
- 有完整 tracing / eval / review 的智能体平台

## 3. 改造边界与硬约束

改造必须遵守以下边界：

- 不修改 `C:\Users\luzian\Desktop\littlemodel` 内的模型代码、权重、测试数据
- 模型调用仍通过已有注册表与 `inference.py:predict` 进行
- 智能体层只包裹现有诊断、检索、报告、聊天链路，不侵入外部模型资产
- 在每一个阶段都要保证已有上传、诊断、案例、报告主链路可运行

## 4. 对标优秀智能体项目后的结论

本改造书主要参考以下几类官方或主流智能体体系：

- OpenAI Agents SDK：强调 `tools`、`handoffs`、`guardrails`、`human-in-the-loop`、`tracing`
- OpenAI《A practical guide to building agents》：强调“什么时候该做 agent”、“工具与工作流设计”、“guardrails”
- LangGraph：强调 `durable execution`、`persistence`、`human-in-the-loop`、`stateful workflow`
- Microsoft Agent Framework：强调 `workflow orchestration`、`events`、`observability`
- CrewAI：强调 `flows`、`state`、`memory`、`knowledge`、`observability`

结合这些项目的共同点，一个“比较优异的智能体项目”至少具备以下特征：

- 有显式工作流，而不是隐式函数串联
- 有运行状态和持久化，不怕长任务失败
- 有工具边界和 guardrails，不让模型胡乱越权
- 有人工审核节点，尤其是高风险输出
- 有 tracing、metrics、eval 和回归机制
- 有清晰的 agent 角色划分，而不是所有逻辑都塞进一个 service

## 5. 目标形态

### 5.1 目标产品形态

目标不是把系统改成“多智能体炫技 demo”，而是改成：

> 面向风电诊断场景的智能体工作台  
> 具备诊断、检索、证据绑定、报告生成、人工审阅、追踪与评测闭环

### 5.2 目标技术形态

建议最终形成如下分层：

1. `Domain Layer`
   当前已有：上传、模型路由、模型执行、案例、知识库、报告

2. `Agent Runtime Layer`
   新增：agent run、step、tool call、handoff、review gate、resume

3. `Safety & Governance Layer`
   新增：guardrails、权限、审计、证据绑定、输出校验

4. `Observability & Evaluation Layer`
   新增：trace、metric、run timeline、eval dataset、quality dashboard

5. `Operator UI Layer`
   新增：Run Center、Review Queue、Trace Detail、Eval Dashboard

## 6. 总体改造策略

### 6.1 大方向

整个改造遵循以下原则：

- 先把单智能体工作流做好，再做多智能体
- 先把持久化执行和审计做好，再追求“更聪明”
- 先把证据链和稳定性做好，再追求复杂 autonomy
- 优先复用现有模块，不推倒重来

### 6.2 推荐技术栈演进

基于当前仓库，推荐演进路径如下：

- Web API：继续使用 FastAPI
- 前端：继续使用 React + Vite
- 关系型数据库：
  - 阶段 1 可继续沿用 SQLite 以降低改造门槛
  - 阶段 2 开始必须支持 PostgreSQL，作为生产主库
- 异步任务队列：
  - 推荐引入 Redis + Dramatiq
  - 也可以接受 Redis + RQ / Arq，但不建议继续依赖同步 HTTP 长请求
- 可观测性：
  - OpenTelemetry
  - Prometheus + Grafana
  - Trace 后端可选 Jaeger / Tempo
- 文档与结构化输出：
  - 继续使用 Pydantic 作为 agent I/O schema

## 7. 目标架构设计

### 7.1 目标后端模块拆分

建议在 `backend/app/core` 之上新增 `agent_runtime` 相关目录，示例：

```text
backend/app/core/
  agent_runtime/
    run_manager.py
    step_executor.py
    tool_registry.py
    guardrails.py
    handoff_manager.py
    review_manager.py
    run_serializer.py
  agents/
    orchestrator_agent.py
    diagnosis_agent.py
    retrieval_agent.py
    report_agent.py
    review_agent.py
  jobs/
    worker_entry.py
    report_jobs.py
    chat_jobs.py
    eval_jobs.py
```

现有模块的角色变化建议如下：

- `model_runner.py`
  保持为底层工具，不直接承担 agent 编排
- `rag_service.py`
  变为 Retrieval Tool 背后的调用服务
- `report_generator.py`
  变为 Base Report Tool
- `enhanced_report_service.py`
  变为 Enhanced Report Tool / Report Agent 能力的一部分
- `agent_service.py`
  不再承担唯一“agent”角色，应逐步降级为聊天兼容层或迁移为 orchestrator facade
- `telemetry_service.py`
  扩展为 run-level tracing 事件桥接层

### 7.2 目标前端模块拆分

前端除了保留现有页面，还应新增：

- `RunsPage`
  展示所有 agent run 列表、状态、耗时、当前阶段、失败原因
- `RunDetailPage`
  展示 step timeline、输入输出摘要、工具调用、引用、人工审核记录
- `ReviewQueuePage`
  展示待人工确认的建议、报告、模型切换操作
- `EvalDashboardPage`
  展示 agent 质量评测结果、失败样本、趋势

现有页面需要被改造成 agent-aware：

- `DiagnosisPage.tsx`
  不再只等同步诊断结果，而是创建 `run_id` 并跳转到 run/case 状态页
- `CaseDetailPage.tsx`
  增加“证据链”、“agent run 摘要”、“审阅状态”
- `ReportsPage.tsx`
  增加生成中状态、失败恢复、审阅/发布按钮
- `ChatPage.tsx`
  增加引用状态、工具调用摘要、模型/降级模式说明
- `KnowledgePage.tsx`
  增加文档可信度、版本、索引健康度

## 8. 数据库改造设计

### 8.1 为什么必须扩表

当前数据库适合“结果存储”，不适合“智能体运行存储”。  
优秀智能体项目通常需要记录：

- 一次 run 的生命周期
- run 内每一步执行情况
- 每次工具调用
- 每次人审暂停与恢复
- 每次评测结果
- 每次追踪元数据

### 8.2 新增表建议

建议新增以下核心表：

#### `agent_runs`

用于记录一次完整的 agent 工作流。

建议字段：

- `run_id TEXT PRIMARY KEY`
- `run_type TEXT`
  例如 `diagnosis`, `chat_answer`, `enhanced_report`, `review_publish`
- `case_id TEXT NULL`
- `session_id TEXT NULL`
- `status TEXT`
  例如 `queued`, `running`, `waiting_review`, `succeeded`, `failed`, `cancelled`
- `current_step TEXT NULL`
- `input_json TEXT`
- `output_json TEXT NULL`
- `error_json TEXT NULL`
- `started_at TEXT`
- `updated_at TEXT`
- `finished_at TEXT NULL`
- `triggered_by TEXT NULL`
  后续接用户体系

#### `agent_run_steps`

用于记录每一步执行。

- `step_id TEXT PRIMARY KEY`
- `run_id TEXT`
- `step_name TEXT`
- `step_type TEXT`
  例如 `tool_call`, `llm_generation`, `guardrail`, `handoff`, `review_gate`
- `status TEXT`
- `input_json TEXT`
- `output_json TEXT NULL`
- `error_json TEXT NULL`
- `duration_ms INTEGER NULL`
- `sequence_no INTEGER`
- `started_at TEXT`
- `finished_at TEXT NULL`

#### `agent_tool_calls`

用于记录工具层调用。

- `tool_call_id TEXT PRIMARY KEY`
- `run_id TEXT`
- `step_id TEXT`
- `tool_name TEXT`
- `tool_version TEXT NULL`
- `request_json TEXT`
- `response_json TEXT NULL`
- `status TEXT`
- `duration_ms INTEGER NULL`
- `created_at TEXT`

#### `agent_review_tasks`

用于人工审核。

- `review_task_id TEXT PRIMARY KEY`
- `run_id TEXT`
- `case_id TEXT NULL`
- `review_type TEXT`
  例如 `maintenance_advice`, `enhanced_report_publish`, `model_alias_change`
- `status TEXT`
  `pending`, `approved`, `rejected`, `changes_requested`
- `payload_json TEXT`
- `decision_json TEXT NULL`
- `created_at TEXT`
- `decided_at TEXT NULL`
- `reviewer_id TEXT NULL`

#### `agent_eval_runs`

用于评测 agent 质量。

- `eval_run_id TEXT PRIMARY KEY`
- `eval_suite_name TEXT`
- `target_version TEXT`
- `status TEXT`
- `summary_json TEXT`
- `started_at TEXT`
- `finished_at TEXT NULL`

#### `agent_eval_cases`

- `eval_case_id TEXT PRIMARY KEY`
- `eval_run_id TEXT`
- `case_name TEXT`
- `input_json TEXT`
- `expected_json TEXT`
- `actual_json TEXT NULL`
- `score_json TEXT NULL`
- `status TEXT`

### 8.3 迁移策略

建议增加新迁移序列：

```text
0008_agent_runs.sql
0009_agent_reviews.sql
0010_agent_evals.sql
0011_agent_run_indexes.sql
```

索引必须补齐：

- `agent_runs(status, updated_at)`
- `agent_runs(case_id, started_at)`
- `agent_run_steps(run_id, sequence_no)`
- `agent_review_tasks(status, created_at)`
- `agent_tool_calls(run_id, created_at)`

## 9. 核心改造项与实施方法

以下为必须做的核心改造项。

### 9.1 改造项 A：建立 Agent Runtime

#### 为什么必须做

没有 runtime，就没有真正的 agent。  
当前项目的“agent”主要体现在 `agent_service.py` 的对话逻辑，但它没有：

- 显式步骤
- 可恢复运行状态
- 审批中断点
- 通用工具调用注册

#### 要怎么做

1. 新增 `run_manager.py`
   负责创建、更新、终结 `agent_runs`
2. 新增 `step_executor.py`
   抽象每一步执行的统一入口
3. 新增 `tool_registry.py`
   把现有能力包装成统一 Tool
4. 新增 `orchestrator_agent.py`
   负责决定当前 run 的流程走向

#### Tool Registry 第一版应包含

- `run_diagnosis_tool`
  封装 `model_runner.py`
- `retrieve_knowledge_tool`
  封装 `retrieval_service.py`
- `generate_base_report_tool`
  封装 `report_generator.py`
- `generate_enhanced_report_tool`
  封装 `enhanced_report_service.py`
- `load_case_tool`
  封装 `case_store.py`
- `save_chat_message_tool`
  封装 `case_store.py`

#### 关键实现原则

- Tool 层做强约束输入输出
- Orchestrator 不直接操作底层文件和数据库
- 每次 tool call 必须记录 request/response 摘要
- 每一步都要有 `step_name` 与 `step_type`

### 9.2 改造项 B：把长任务改造成异步工作流

#### 为什么必须做

当前增强报告、LLM 调用、知识检索等流程容易超时。  
优秀智能体项目不会把长耗时 agent run 绑死在一个同步 HTTP 请求里。

#### 要怎么做

推荐引入：

- Redis
- Dramatiq Worker

#### 实施步骤

1. 新增 `jobs/worker_entry.py`
2. 新增任务：
   - `run_diagnosis_job`
   - `generate_enhanced_report_job`
   - `chat_answer_job`
   - `eval_suite_job`
3. API 改成：
   - `POST /api/agent-runs`
   - 返回 `run_id`
4. 前端轮询：
   - `GET /api/agent-runs/{run_id}`
   - 或 WebSocket / SSE 推送状态

#### 初期状态机建议

- `queued`
- `running`
- `waiting_review`
- `succeeded`
- `failed`
- `cancelled`

### 9.3 改造项 C：增加 Guardrails

#### 为什么必须做

工业场景里，guardrails 是必须项。  
没有 guardrails 的“智能体”只能叫实验功能。

#### Guardrails 最少要做四层

1. `Input Guardrail`
   - 文件格式、尺寸、任务类型、参数范围校验
2. `Tool Guardrail`
   - 某些 run 只能调用某些工具
3. `Output Guardrail`
   - Pydantic schema 校验
   - 关键字段完整性校验
4. `Evidence Guardrail`
   - 高风险建议必须绑定证据
   - 报告关键结论必须绑定引用来源

#### 具体落地

新增 `guardrails.py`，实现以下检查器：

- `validate_run_input()`
- `validate_tool_access()`
- `validate_report_payload()`
- `validate_evidence_binding()`
- `validate_publish_gate()`

#### 最关键的一条强规则

对于 `warning` / `critical` 风险等级的最终建议：

- 不允许纯“无引用文本”直接发布
- 必须至少绑定：
  - `case_result`
  - `model_metadata`
  - `knowledge_chunk` 或 `similar_case`

### 9.4 改造项 D：引入 Human-in-the-Loop

#### 为什么必须做

在风电运维场景中，以下行为不适合完全自动执行：

- 发布最终维护建议
- 发布增强报告
- 切换默认模型别名
- 对高风险案例给出停机级建议

#### 要怎么做

新增 review gate：

- agent 在关键节点写入 `agent_review_tasks`
- run 状态变为 `waiting_review`
- 前端 Review Queue 展示待审内容
- 审核后调用：
  - `POST /api/reviews/{review_task_id}/approve`
  - `POST /api/reviews/{review_task_id}/reject`
  - `POST /api/reviews/{review_task_id}/request-changes`
- 审核结果写回 run，继续执行

#### 页面改造

新增：

- `ReviewQueuePage.tsx`
- `ReviewDetailPanel.tsx`

在 `ReportsPage.tsx`、`CaseDetailPage.tsx` 中加入：

- 当前审阅状态
- 审阅意见
- 审阅时间

### 9.5 改造项 E：建立 Observability 与 Tracing

#### 为什么必须做

智能体如果不可观测，线上问题很难复盘。  
优秀 agent 项目通常能看到：

- 模型调用
- 工具调用
- 路由分支
- 审批暂停
- 错误与重试

#### 要怎么做

第一层：仓库内可落地的轻量 tracing

- 扩展 `telemetry_service.py`
- 每个 run / step / tool call 都发事件
- 事件字段统一

第二层：接入 OpenTelemetry

- 在 FastAPI 请求入口创建 trace span
- 在 step、tool、LLM generation、review gate 上创建子 span
- span attributes 至少包括：
  - `run_id`
  - `case_id`
  - `step_name`
  - `tool_name`
  - `model_name`
  - `fallback_used`
  - `review_required`

第三层：落地监控后端

- 本地开发：JSONL + debug endpoint
- 生产建议：OTel -> Tempo/Jaeger + Prometheus + Grafana

### 9.6 改造项 F：建立 Evaluation 体系

#### 为什么必须做

没有评测，就无法证明 agent 在变好。  
当前项目只有“代码测试”，缺少“智能体质量测试”。

#### 要怎么做

新建目录：

```text
backend/evals/
  datasets/
    diagnosis_cases.jsonl
    chat_grounding.jsonl
    report_quality.jsonl
  scorers/
    grounding_scorer.py
    report_schema_scorer.py
    recommendation_policy_scorer.py
```

#### 评测维度

1. `Grounding`
   回答是否能被引用支持
2. `Recommendation Safety`
   高风险建议是否过度/不足
3. `Schema Validity`
   报告结构是否完整
4. `Fallback Stability`
   外部 LLM 不可用时系统是否仍能给出可发布结果
5. `Latency`
   关键路径耗时是否受控

#### 评测接口

- `POST /api/evals/run`
- `GET /api/evals/{eval_run_id}`
- `GET /api/evals/suites`

### 9.7 改造项 G：知识库治理

#### 为什么必须做

当前知识库偏“可检索”，还不够“可治理”。  
优秀智能体项目需要知道：引用来源是谁、版本是什么、是否可信、是否过期。

#### 要怎么做

扩充知识文档元数据：

- `source_authority`
- `source_version`
- `effective_date`
- `expiry_date`
- `trust_level`
- `review_status`

在知识文档与 chunk 层增加：

- 是否可用于生产建议
- 是否只可用于参考说明

前端 `KnowledgePage.tsx` 增加：

- 文档可信度
- 审核状态
- 最后更新时间

### 9.8 改造项 H：多智能体拆分

#### 为什么必须做

不是所有项目都需要多智能体，但如果要做成“比较优异”的 agent 项目，后期最好具备明确角色拆分，而不是所有事情都堆在一个 orchestrator prompt 里。

#### 推荐角色

- `Diagnosis Agent`
  负责理解任务、调用诊断工具、生成结构化诊断结论
- `Retrieval Agent`
  负责知识检索、相似案例检索、证据聚合
- `Report Agent`
  负责生成增强报告草稿
- `Review Agent`
  负责执行规则审校与发布前检查
- `Orchestrator Agent`
  负责调度其他 agent 或将其视为 tools

#### 设计建议

第一阶段不要立即做 agent handoff。  
先做“manager-style orchestration”：

- 一个 orchestrator 保持控制权
- specialist agent 作为 tool 调用

这样更容易控制一致性、审计和前端状态同步。

## 10. 分阶段实施计划

以下阶段按依赖关系排列，建议按顺序推进。

## 阶段 0：基线加固与可执行性修复

### 目标

先修复会阻碍智能体化改造的基础问题。

### 必做项

- 修复前端移动端横向滚动与长 ID 溢出
- 修复前端 E2E 文案与实际 UI 不一致问题
- 修复聊天/报告中的中文编码异常
- 补齐基础报告 PDF 依赖或明确关闭功能
- 让 Qdrant 开关与实际运行状态一致

### 代码落点

- `frontend/src/styles.css`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/CasesPage.tsx`
- `frontend/src/pages/ReportsPage.tsx`
- `frontend/tests/e2e/main-flow.spec.ts`
- `backend/app/core/agent_service.py`
- `backend/app/core/report_generator.py`
- `backend/requirements.txt`

### 验收标准

- `pytest -q` 通过
- `npm run build` 通过
- `npx playwright test` 通过
- 390px viewport 无主要页面横向滚动

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已修复 `frontend/src/components/Layout.tsx`、`frontend/src/pages/CasesPage.tsx`、`frontend/src/pages/ReportsPage.tsx` 的中文乱码，并补齐长 ID/长文本换行样式。
  - 已更新 `frontend/tests/e2e/main-flow.spec.ts`，让 E2E 与当前 UI 结构一致，并避免依赖易漂移的英文文案。
  - 已将基础报告 PDF 生成从隐式 `weasyprint` 依赖切回仓库现有 `reportlab` 能力，保证功能默认可执行。
  - 已修复 `backend/app/core/agent_service.py` 的聊天中文提示词与本地回退文案乱码。
  - 已在 `backend/app/api/system.py` 中区分 `qdrant_config_enabled`、`qdrant_enabled`、`qdrant_remote_available`，避免把配置开关与真实运行状态混淆。
  - 移动端 390px 验收截图已生成：`frontend/docs/verification/stage0-home-390.png`、`frontend/docs/verification/stage0-cases-390.png`、`frontend/docs/verification/stage0-reports-390.png`。

## 阶段 1：单智能体运行时落地

### 目标

把“诊断、聊天、增强报告”统一纳入一个可记录 run 的 agent runtime。

### 必做项

- 新增 `agent_runs`、`agent_run_steps`、`agent_tool_calls`
- 新增 `run_manager.py`、`tool_registry.py`、`step_executor.py`
- 新增 `/api/agent-runs`、`/api/agent-runs/{run_id}`
- 将增强报告与聊天接入统一 run 流程

### 实施顺序

1. 数据库迁移
2. Runtime 核心类
3. Tool 包装层
4. API 层
5. 前端 Run 状态显示

### 验收标准

- 每次增强报告生成都有 `run_id`
- 每个 run 至少能看到 step timeline
- 失败后能看到具体失败 step 与错误摘要

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增迁移 `backend/app/db/migrations/0008_agent_runtime.sql`，落地 `agent_runs`、`agent_run_steps`、`agent_tool_calls`，并为增强报告版本补充 `run_id` 关联。
  - 已新增 `backend/app/core/agent_runtime/run_manager.py`、`tool_registry.py`、`step_executor.py`，形成最小可记录 runtime 闭环。
  - 已新增 `backend/app/api/agent_runs.py`，并将 `/api/agent-runs`、`/api/agent-runs/{run_id}` 挂载到主应用。
  - 已将 `backend/app/api/chat.py` 与 `backend/app/api/enhanced_reports.py` 接入统一 run 流程，聊天答复与增强报告返回值均携带 `run_id`。
  - 已在 `backend/app/core/agent_service.py`、`backend/app/core/enhanced_report_service.py` 中把 `run_id` 写入消息元数据与报告版本，保证案例问答、报告版本、agent run 三者可追踪关联。
  - 已新增 `frontend/src/pages/RunDetailPage.tsx`，并更新 `frontend/src/App.tsx`、`frontend/src/pages/ChatPage.tsx`、`frontend/src/pages/ReportsPage.tsx`，补齐最小 run 详情入口与页面跳转。
  - 已新增 `backend/tests/test_agent_runs_api.py`，并更新 `backend/tests/test_model_sync.py`、`backend/tests/test_enhanced_reports.py`，覆盖 run 查询、报告版本关联与当前 PDF 可恢复跳过行为。
  - 为适配当前 `pytorch` Python 3.9 测试环境，已对本仓库内部的 `Optional` 类型注解、`dataclass(slots=True)`、`zip(..., strict=False)` 做最小兼容修复；未修改 `C:\Users\luzian\Desktop\littlemodel` 中任何代码、权重或测试数据。

## 阶段 2：异步执行与持久化恢复

### 目标

把长任务从同步请求迁出，形成真正可恢复的长流程执行。

### 必做项

- 引入 Redis + Dramatiq
- 增强报告、聊天、批量评测切换为异步任务
- run 状态支持 `queued/running/waiting_review/succeeded/failed`
- 前端使用轮询或 SSE

### 推荐实现方式

- 新增 `backend/app/jobs`
- 当前仓库先落地 SQLite 持久队列 + worker loop 的本地可执行版，保证阶段 2 能在现有环境内自测与恢复
- Redis + Dramatiq 作为同阶段的生产增强路线，待部署骨架补齐后可平滑替换 broker 层
- 新增 worker 启动命令
- 新增 `docker-compose.worker.yml` 或合并到部署文档

### 验收标准

- 用户触发增强报告后立即获得 `run_id`
- 页面可看到“进行中”
- worker 宕机后 run 至少能保留状态，不丢失上下文

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增迁移 `backend/app/db/migrations/0009_agent_run_queue.sql`，落地 `agent_run_queue`，补齐任务状态、租约、重试、错误摘要等持久化字段。
  - 已新增 `backend/app/jobs/task_handlers.py`、`worker_runtime.py`、`worker_entry.py`，形成可嵌入主进程、也可独立启动的 worker 执行闭环。
  - 已扩展 `backend/app/core/agent_runtime/run_manager.py`，支持任务入队、抢占、完成、失败、取消、恢复与 run/job 联查，保证长流程可追踪、可恢复、可审计。
  - 已新增 `POST /api/agent-runs`、`POST /api/agent-runs/{run_id}/cancel`、`POST /api/agent-runs/{run_id}/resume`，并在 `backend/app/main.py` 中接入 embedded worker 启停。
  - 已将 `frontend/src/pages/ChatPage.tsx`、`ReportsPage.tsx`、`RunDetailPage.tsx` 改为围绕异步 run 轮询刷新，前端可查看排队/运行状态、取消任务、恢复失败或已取消 run。
  - 已更新 `frontend/src/lib/api.ts`、`frontend/src/types.ts`，补齐异步 run 提交与 job 元数据结构；已更新 `frontend/vite.config.ts`、`frontend/playwright.config.ts`，让 E2E 使用隔离端口和可配置开发代理，避免本地常驻服务干扰。
  - 已新增 `backend/tests/test_agent_async_runs.py`，覆盖异步聊天、异步增强报告、手动 worker 消费、失败/取消后恢复等主链路。
  - 已完成阶段 2 相关验证：`pytest -q backend/tests/test_agent_async_runs.py backend/tests/test_agent_runs_api.py backend/tests/test_chat.py backend/tests/test_enhanced_reports.py backend/tests/test_model_sync.py` 通过（24 passed）；`npm run build` 通过；`CI=1 npx playwright test` 通过（3 passed）；`backend` 目录下 `pytest -q` 全量回归通过（86 passed）。
  - 未修改 `C:\Users\luzian\Desktop\littlemodel` 内任何代码、权重和测试数据。
- 剩余风险：
  - 当前阶段 2 先落地的是 `SQLite 持久队列 + worker loop`，满足本地可执行、可恢复与可审计；`Redis + Dramatiq` 仍作为后续生产增强路线。
  - `backend/app/main.py` 仍使用 FastAPI `on_event` 启停 embedded worker，测试可通过，但后续宜在阶段 5 前迁移到 lifespan 事件，消除弃用告警。
  - 目前 `worker_max_attempts` 默认值为 1，更偏保守与可审计；若后续引入自动重试，需要同步补强幂等性与 review/告警策略。

## 阶段 3：Guardrails 与证据链

### 目标

把系统从“能跑”升级到“可控”。

### 必做项

- 高风险建议必须 evidence-bound
- 输出 schema 与字段完整性校验
- 工具权限控制
- 报告发布前检查

### 代码落点

- `backend/app/core/agent_runtime/guardrails.py`
- `backend/app/core/report_evidence_service.py`
- `backend/app/core/enhanced_report_service.py`
- `backend/app/core/rag_service.py`

### 验收标准

- 无引用高风险建议不能发布
- 增强报告缺少关键 section 时自动失败或进入 review

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增 `backend/app/core/agent_runtime/guardrails.py`，集中实现阶段 3 的工具权限校验、报告发布前检查、高风险证据绑定判定。
  - 已更新 `backend/app/core/agent_runtime/tool_registry.py` 与 `step_executor.py`，为工具注册增加 `allowed_run_types`，并在执行时按 `run_type` 做权限守卫，防止跨流程误调用。
  - 已更新 `backend/app/api/chat.py`、`backend/app/api/enhanced_reports.py`、`backend/app/jobs/task_handlers.py`，将聊天与增强报告工具都绑定到各自允许的 `run_type`，并为增强报告 guardrail 失败补充 `422` 返回。
  - 已更新 `backend/app/core/enhanced_report_service.py`，在证据补丁之后增加发布前 guardrail 判定：关键 section 为空或引用未知证据时直接失败；高风险建议缺少 grounded evidence 或缺少 citations 时转为 `waiting_review`，并把 `report_status` 与 guardrail 元数据持久化到 `report_versions` 和接口返回值中。
  - 已更新 `backend/app/core/agent_service.py`，对高风险但未绑定外部证据引用的聊天答复追加明确提示，避免把未证据绑定的建议误当成处置依据。
  - 已新增 `backend/tests/test_guardrails.py`，覆盖跨 `run_type` 工具调用拒绝、高风险报告进入 `waiting_review`、关键 section 缺失触发 guardrail 失败等主场景；并同步更新 `backend/tests/test_chat.py` 以匹配新的高风险提示行为。
  - 已完成阶段 3 相关验证：`pytest -q backend/tests/test_guardrails.py backend/tests/test_enhanced_reports.py backend/tests/test_chat.py backend/tests/test_agent_async_runs.py` 通过（22 passed）；`python -m compileall backend/app` 通过；`npm run build` 通过；`backend` 目录下 `pytest -q` 全量回归通过（89 passed）；`CI=1 npx playwright test` 通过（3 passed）。
  - 未修改 `C:\Users\luzian\Desktop\littlemodel` 内任何代码、权重和测试数据。
- 剩余风险：
  - 当前 `waiting_review` 只是持久化状态与前置拦截，阶段 4 仍需补齐真正的审核任务表、审批 API 和恢复执行闭环。
  - 聊天高风险守卫目前采用“追加明确提示”的保守策略，还没有像增强报告那样进入结构化 review 流；这与蓝图阶段顺序一致，但后续应在阶段 4 合并治理口径。
  - `backend/app/main.py` 的 FastAPI `on_event` 弃用告警仍存在，功能未受影响，建议在阶段 5 前迁移到 lifespan 事件。

## 阶段 4：Human-in-the-Loop

### 目标

把高风险输出纳入人工审核闭环。

### 必做项

- 新增 `agent_review_tasks`
- 新增审核 API
- 新增 Review Queue 页面
- 高风险建议、报告发布进入待审状态

### 验收标准

- 可以暂停 run
- 可以审批后恢复 run
- 审批记录可追溯

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增迁移 `backend/app/db/migrations/0010_agent_reviews.sql`，落地 `agent_review_tasks` 与 `agent_review_actions`，把审核任务与审核动作拆开持久化，满足可追踪、可恢复、可审计要求。
  - 已新增 `backend/app/core/review_service.py`，封装审核任务创建、详情查询、批准、驳回、要求修改，以及审批结果对 `report_versions` / `agent_runs` 的收敛逻辑。
  - 已新增 `backend/app/api/reviews.py`，挂出 `GET /api/reviews`、`GET /api/reviews/{review_task_id}`、`POST /api/reviews/{review_task_id}/approve`、`/reject`、`/request-changes` 审核接口；并在 `backend/app/main.py` 中接入路由。
  - 已扩展 `backend/app/core/agent_runtime/run_manager.py`，新增 `waiting_review` 状态写入能力，并在 run 详情中返回关联审核任务摘要。
  - 已更新 `backend/app/api/enhanced_reports.py` 与 `backend/app/jobs/task_handlers.py`，把增强报告的 `waiting_review` 从“状态标签”升级为“审核流程入口”：当报告需人工审核时自动创建审核任务、暂停 run，审批通过后将 run 置为 `succeeded`，驳回或要求修改后将 run 置为 `failed`。
  - 已新增前端审核页面 `frontend/src/pages/ReviewQueuePage.tsx`，并更新 `frontend/src/App.tsx`、`frontend/src/components/Layout.tsx`、`frontend/src/lib/api.ts`、`frontend/src/types.ts`，补齐 Review Queue 页面、审核动作调用和最小导航入口。
  - 已新增 `backend/tests/test_reviews_api.py`，覆盖增强报告进入 `waiting_review`、批准后恢复 run、驳回/要求修改后的状态收敛与审计动作记录；并同步更新 `backend/tests/test_model_sync.py` 以纳入 `0010_agent_reviews` 迁移验证。
  - 已完成阶段 4 相关验证：`pytest -q backend/tests/test_reviews_api.py backend/tests/test_guardrails.py backend/tests/test_agent_async_runs.py backend/tests/test_enhanced_reports.py backend/tests/test_model_sync.py` 通过（25 passed）；`npm run build` 通过；`backend` 目录下 `pytest -q` 全量回归通过（92 passed）；`CI=1 npx playwright test` 通过（3 passed）。
  - 未修改 `C:\Users\luzian\Desktop\littlemodel` 内任何代码、权重和测试数据。
- 剩余风险：
  - 当前审核闭环优先覆盖增强报告发布场景，聊天高风险提示仍是“提示增强”而非独立审核任务；若后续要把问答也纳入同一治理口径，可在阶段 5/6 继续扩展。
  - 审批通过后的“恢复执行”当前采用状态收敛到 `succeeded` 的轻量实现，尚未引入更复杂的多步中断后继续执行语义；对当前单步增强报告发布流程是够用的。
  - `backend/app/main.py` 仍使用 FastAPI `on_event`，测试通过但有弃用告警，建议在阶段 5 前迁移到 lifespan 事件。

## 阶段 5：Tracing、Metrics、Eval

### 目标

建立质量闭环与线上可观测性。

### 必做项

- OTel tracing
- run timeline endpoint
- eval dataset 与 scorer
- Eval Dashboard 页面

### 验收标准

- 能按 `run_id` 追查完整执行链
- 能跑出至少 3 套 eval
- 能看到版本对比结果

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增迁移 `backend/app/db/migrations/0011_tracing_and_eval.sql`，为 `agent_runs` 补充 `trace_id`，并新增 `eval_runs`、`eval_run_items` 持久化表，保证 tracing 与评测结果可追踪、可恢复、可审计。
  - 已更新 `backend/app/core/telemetry_service.py`、`backend/app/core/agent_runtime/run_manager.py`、`backend/app/core/agent_runtime/step_executor.py`、`backend/app/core/agent_service.py`、`backend/app/core/enhanced_report_service.py`、`backend/app/core/deepseek_client.py`，把 `trace_id` 与 span 事件接入 run、step、tool call、LLM 调用和报告生成链路。
  - 已新增 `GET /api/agent-runs/{run_id}/timeline` 与 `GET /api/system/observability-summary`，并更新 `backend/app/api/agent_runs.py`、`backend/app/api/system.py`，支持按 `run_id` / `trace_id` 汇总执行时间线与近期观测事件。
  - 已新增 `backend/evals/suites/fault_diagnosis_smoke.json`、`rul_prediction_smoke.json`、`anomaly_report_smoke.json` 三套 smoke eval，并新增 `backend/app/core/eval_service.py`、`backend/app/api/evals.py`，落地 `GET /api/evals/suites`、`POST /api/evals/run`、`GET /api/evals`、`GET /api/evals/{eval_run_id}`。
  - 已更新 `backend/app/core/file_manager.py`，新增本地样本导入能力，供 eval 在不修改 `C:\Users\luzian\Desktop\littlemodel` 的前提下复用现有测试数据。
  - 已更新 `frontend/src/lib/api.ts`、`frontend/src/types.ts`、`frontend/src/components/Layout.tsx`、`frontend/src/App.tsx`，并新增 `frontend/src/pages/EvalDashboardPage.tsx`，提供 Eval Dashboard、观测摘要和评测历史查看入口；同时重写 `frontend/src/pages/RunDetailPage.tsx`，补齐 run timeline 展示。
  - 已新增 `backend/tests/test_eval_api.py`、`backend/tests/test_run_timeline_api.py`、`frontend/tests/e2e/eval-dashboard.spec.ts`，并更新 `backend/tests/test_model_sync.py` 以纳入 `0011_tracing_and_eval` 迁移验证。
  - 已完成阶段 5 相关验证：`pytest -q backend/tests/test_run_timeline_api.py backend/tests/test_eval_api.py backend/tests/test_observability.py backend/tests/test_chat.py backend/tests/test_enhanced_reports.py backend/tests/test_model_sync.py` 通过（24 passed）；`pytest -q backend/tests/test_guardrails.py::test_report_missing_critical_section_content_fails_guardrail backend/tests/test_enhanced_reports.py backend/tests/test_eval_api.py backend/tests/test_run_timeline_api.py` 通过（16 passed）；`python -m compileall backend/app` 通过；`npm run build` 通过；`backend` 目录下 `pytest -q` 全量回归通过（95 passed）；`CI=1 npx playwright test` 通过（4 passed）。
  - 未修改 `C:\Users\luzian\Desktop\littlemodel` 内任何代码、权重和测试数据。
- 剩余风险：
  - 当前 tracing 采用仓库内 telemetry 事件与 `trace_id` / span 结构实现，已满足本阶段可追踪性要求，但还不是完整 exporter 驱动的生产级 OTel 管线。
  - 当前 eval 以 smoke suite 为主，重点验证链路可执行、结果可持久化与版本可回看，尚未引入更细粒度的语义评分器与基线对比策略。
  - `backend/app/main.py` 仍使用 FastAPI `on_event`，本阶段测试全部通过，但弃用告警仍在；如要继续推进生产化治理，建议在阶段 6 切换到 lifespan 事件。

## 阶段 6：多智能体与生产化治理

### 目标

在单智能体稳定后，引入 specialist agents 与更强治理能力。

### 必做项

- orchestrator + specialist agents
- 角色级工具边界
- 审计、权限、RBAC
- PostgreSQL 生产迁移
- 多环境部署配置

### 验收标准

- 至少 3 个 specialist agents 稳定运行
- 前端可展示 agent step、specialist tool 调用、handoff 摘要
- 生产环境具备可用的 trace、review、eval、audit

### 完成状态

- 状态：已完成（2026-06-11）
- 执行记录：
  - 已新增 `backend/app/core/agents/orchestrator_agent.py`、`diagnosis_agent.py`、`retrieval_agent.py`、`report_agent.py`、`review_agent.py`，按 manager-style orchestration 落地 `orchestrator + specialist agents`，并把 handoff 事件统一写入 telemetry 与 audit。
  - 已更新 `backend/app/api/chat.py`、`backend/app/api/enhanced_reports.py`、`backend/app/jobs/task_handlers.py`，把聊天与增强报告执行链路切到 orchestrator 调度，同时保留原有异步 run 兼容层，不推倒重来。
  - 已新增迁移 `backend/app/db/migrations/0012_multi_agent_governance.sql`，并新增 `backend/app/core/audit_service.py`，落地 `agent_audit_logs`，补齐 run 创建、handoff、review、eval 等关键动作的审计记录。
  - 已更新 `backend/app/core/auth.py` 与 `backend/app/core/settings.py`，引入基于权限映射的轻量 RBAC：支持 `X-Actor-Id`、`X-Actor-Role`、`require_permissions(...)`，并覆盖 agent run、enhanced report、eval、review 等高价值写接口。
  - 已更新 `backend/app/db/database.py`、`backend/app/db/migration_runner.py`、`backend/app/core/case_store.py`，补齐 SQLite / PostgreSQL 双兼容运行时：支持 `WINDPOWER_DATABASE_URL`、`? -> %s` 占位符转换、SQLite `PRAGMA` 迁移跳过，以及 upsert 语句的跨数据库兼容。
  - 已更新 `backend/requirements.txt`、`backend/.env.example`、`backend/.env.full-features.example`，并新增/重写 `docs/db-migration-guide.md`、`docs/deployment-notes.md`，补齐 PostgreSQL 生产迁移和多环境部署配置说明。
  - 已更新 `backend/app/api/system.py`，新增 `GET /api/system/audit-summary`、`GET /api/system/audit-logs`、`GET /api/system/specialist-summary`，并在 `config-summary` 中补充数据库、RBAC、audit 配置摘要。
  - 已将 `backend/app/main.py` 的 embedded worker 生命周期从 FastAPI `on_event` 迁移到 `lifespan`，消除前几阶段遗留的弃用告警。
  - 已新增前端页面 `frontend/src/pages/SpecialistDashboardPage.tsx`、`frontend/src/pages/AuditLogPage.tsx`，并重写 `frontend/src/pages/RunDetailPage.tsx`，使前端可展示 agent step、specialist handoff 摘要、audit 记录与运行细节；同时更新 `frontend/src/lib/api.ts`、`frontend/src/types.ts`、`frontend/src/App.tsx`、`frontend/src/components/Layout.tsx`。
  - 已新增 `frontend/tests/e2e/governance-pages.spec.ts`，并更新 `backend/tests/test_multi_agent_governance.py`、`backend/tests/test_auth.py`、`backend/tests/test_model_sync.py`，覆盖 specialist summary、audit summary、RBAC、PostgreSQL 适配检测与 `0012_multi_agent_governance` 迁移注册。
  - 已完成阶段 6 相关验证：`pytest -q backend/tests/test_multi_agent_governance.py backend/tests/test_auth.py backend/tests/test_model_sync.py backend/tests/test_observability.py backend/tests/test_agent_async_runs.py backend/tests/test_reviews_api.py` 通过（22 passed）；`python -m compileall backend/app` 通过；`npm run build` 通过；`backend` 目录下 `pytest -q` 全量回归通过（100 passed）；`CI=1 npx playwright test` 通过（5 passed）。
  - 未修改 `C:\Users\luzian\Desktop\littlemodel` 内任何代码、权重和测试数据。
- 剩余风险：
  - 当前 PostgreSQL 支持已进入运行时和迁移层，但仍采用“兼容现有原生 SQL”的轻量适配策略；后续若引入更复杂 SQL 方言或连接池治理，仍建议补充更深入的生产压测。
  - 当前 RBAC 已满足阶段 6 的角色级工具边界与治理闭环，但仍以静态权限映射为主；如果后续要接企业级身份系统，还可以继续扩展到更细粒度的资源授权模型。

## 11. 每阶段输出物清单

### 阶段 0 输出物

- 修复 PR / 代码变更
- 更新后的 E2E 测试
- 移动端验收截图

### 阶段 1 输出物

- agent run 表结构
- runtime 基础代码
- run detail API

### 阶段 2 输出物

- worker 进程
- 任务队列配置
- run status 前端

### 阶段 3 输出物

- guardrail 实现
- evidence binding 校验
- 发布前检查器

### 阶段 4 输出物

- review queue API
- review UI
- resume execution 逻辑

### 阶段 5 输出物

- tracing 集成
- eval 套件
- 质量仪表盘

### 阶段 6 输出物

- multi-agent orchestration
- RBAC / audit
- 生产部署手册

## 12. 关键接口设计建议

### 12.1 Agent Run API

```text
POST   /api/agent-runs
GET    /api/agent-runs
GET    /api/agent-runs/{run_id}
POST   /api/agent-runs/{run_id}/cancel
POST   /api/agent-runs/{run_id}/resume
```

### 12.2 Review API

```text
GET    /api/reviews
GET    /api/reviews/{review_task_id}
POST   /api/reviews/{review_task_id}/approve
POST   /api/reviews/{review_task_id}/reject
POST   /api/reviews/{review_task_id}/request-changes
```

### 12.3 Eval API

```text
POST   /api/evals/run
GET    /api/evals
GET    /api/evals/{eval_run_id}
GET    /api/evals/suites
```

## 13. 测试策略

### 13.1 代码层测试

- runtime 单元测试
- tool registry 单元测试
- guardrail 单元测试
- review gate 单元测试

### 13.2 集成测试

- 诊断 run 创建 -> 成功完成
- 增强报告 run -> review gate -> approve -> publish
- LLM 失败 -> fallback -> run 仍成功
- Qdrant 不可用 -> 本地检索 fallback

### 13.3 前端 E2E

新增场景：

- Run Center 查看状态
- 审核队列审批
- 报告生成中的轮询体验
- 聊天引用详情展开
- 移动端无横向滚动

### 13.4 评测测试

- grounding 评测集
- recommendation safety 评测集
- enhanced report schema 评测集

## 14. 风险与注意事项

### 14.1 不建议一上来做的事情

- 不建议一开始就做非常复杂的 agent-to-agent 自主协商
- 不建议一开始就把所有业务都交给 LLM 决策
- 不建议在 SQLite + 同步请求上继续堆长流程

### 14.2 最容易踩坑的点

- 过早做多智能体，导致链路不可控
- 没有 run state，导致线上问题无法复盘
- 没有 evidence guardrail，导致高风险建议不可审计
- 只做 tracing，不做 eval，最后无法比较版本

## 15. 建议的执行顺序

建议严格按以下顺序执行：

1. 阶段 0：修复基础问题
2. 阶段 1：建立单智能体 runtime
3. 阶段 2：异步化与恢复能力
4. 阶段 3：guardrails 与证据绑定
5. 阶段 4：human-in-the-loop
6. 阶段 5：tracing + eval
7. 阶段 6：多智能体与生产治理

如果时间和资源有限，至少要做到阶段 4。  
做到阶段 4，项目已经可以被称为“工程化较强的垂直智能体项目”。  
做到阶段 6，才更接近“比较优异的智能体项目”。

## 16. 对当前仓库的最终建议

最重要的不是先引入更多模型，而是先引入更好的执行系统。  
这个项目已经有很好的领域价值和业务骨架，真正缺的是：

- Agent Runtime
- Durable Execution
- Guardrails
- Human Review
- Tracing + Eval

把这五件事做好，项目的上限会被真正打开。

## 17. 参考资料

- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/agents/
- OpenAI Agents SDK Tracing: https://openai.github.io/openai-agents-python/tracing/
- OpenAI Agents SDK Human-in-the-loop: https://openai.github.io/openai-agents-python/human_in_the_loop/
- OpenAI《A practical guide to building agents》: https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
- LangGraph Overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- Microsoft Agent Framework Workflows: https://learn.microsoft.com/en-us/agent-framework/workflows/
- Microsoft Agent Framework Observability: https://learn.microsoft.com/en-us/agent-framework/agents/observability
- CrewAI Documentation: https://docs.crewai.com/
- CrewAI Flows: https://docs.crewai.com/en/concepts/flows
- CrewAI Memory: https://docs.crewai.com/en/concepts/memory
- CrewAI Human Feedback in Flows: https://docs.crewai.com/en/learn/human-feedback-in-flows
