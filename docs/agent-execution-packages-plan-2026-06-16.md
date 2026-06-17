# windpower_agent3 智能体改造执行计划书（执行包 A / B / C）

更新时间：2026-06-16  
适用仓库：`C:\Users\luzian\Desktop\windpower_agent3`

## 1. 文档目的

本文把 [agent-must-do-checklist-2026-06-16.md](/C:/Users/luzian/Desktop/windpower_agent3/docs/agent-must-do-checklist-2026-06-16.md) 里的必须改造项，进一步拆成三个可执行工作包。

目标不是“讨论方向”，而是让后续 Codex 可以直接按包实施。

每个执行包都包含：

- 目标边界
- 当前代码现状
- 需要修改的文件范围
- 建议新增的迁移/接口/类型
- 实施顺序
- 验收标准
- 建议验证命令
- 下游 Codex 执行提示

## 2. 总体执行原则

整个计划必须遵守以下约束：

- 不修改 `C:\Users\luzian\Desktop\littlemodel` 中的任何代码、权重和测试数据
- 优先复用当前仓库已有模块，不重写已有诊断、报告、知识库与治理体系
- 每次只做当前执行包和它的直接依赖，不跨包发散
- 每完成一个执行包，都必须运行对应验证命令并回写文档状态
- 长流程设计优先考虑：`可追踪`、`可恢复`、`可审计`、`可评测`

## 3. 当前仓库相关基础

与本次计划直接相关的现有基础如下：

- `backend/app/api/agent_runs.py` 已支持 run 创建、查询、timeline、取消、恢复
- `backend/app/core/agent_runtime/run_manager.py` 已持久化 `agent_runs / agent_run_steps / agent_tool_calls / agent_run_queue`
- `backend/app/jobs/task_handlers.py` 已通过 worker 执行 `chat_answer` 与 `enhanced_report`
- `backend/app/core/review_service.py` 已支持增强报告 review task
- `backend/app/core/telemetry_service.py` 已支持事件和 trace span 落盘
- `frontend/src/pages/RunDetailPage.tsx`、`ReviewQueuePage.tsx`、`EvalDashboardPage.tsx` 已有治理页雏形
- 现有迁移已经到 `0012_multi_agent_governance.sql`

当前短板也很清楚：

- 关键 run type 还太少
- 工作流 step 粒度仍偏粗
- review 主要覆盖增强报告，不是统一治理体系
- observability 仍以仓库内 JSONL 为主
- eval 已有外形，但还不是发布前质量门

## 4. 执行包总览

### 执行包 A

目标：统一关键链路进 run 体系，并把粗粒度执行拆成真正多步骤工作流。

### 执行包 B

目标：把 guardrails 与 human review 扩展成统一治理层，覆盖所有高风险输出。

### 执行包 C

目标：把 observability、eval、worker 生产化补齐，形成优异智能体项目所需的工程闭环。

---

## 5. 执行包 A：统一 run 体系 + 多步骤 runtime 拆解

## 5.1 目标

把当前“只有聊天和增强报告是 agent run”的状态，改造成“关键长链路统一纳入 run 体系”，并把一个大 step 的执行方式拆成多步骤、可检查点恢复的工作流。

## 5.2 本包完成后必须达到的结果

- `diagnosis` 能作为 agent run 启动与追踪
- `knowledge_reindex` 能作为 agent run 启动与追踪
- `review_publish` 或等价恢复发布动作能作为 agent run 启动与追踪
- `chat_answer` 与 `enhanced_report` 的内部执行不再只有一个粗 step
- run detail 页面能显示更细的 step timeline 和恢复位置

## 5.3 当前代码现状

### 当前只支持的 run type

- `backend/app/api/agent_runs.py`
  - `SUPPORTED_RUN_TYPES = {"chat_answer", "enhanced_report"}`

### 当前 worker handler

- `backend/app/jobs/task_handlers.py`
  - 只注册了 `chat_answer`
  - 只注册了 `enhanced_report`

### 当前业务链路仍在 run 体系之外

- `backend/app/api/diagnose.py`
- `backend/app/api/knowledge.py`
- 部分 review 后续发布动作

## 5.4 本包建议新增的 run_type

建议至少新增：

- `diagnosis`
- `knowledge_reindex`
- `review_publish`

可选预留：

- `knowledge_ingest`
- `case_followup`

## 5.5 本包建议新增或修改的数据结构

当前表结构已足够支撑第一轮落地，不建议在本包里大改已有表。

本包建议最小增强：

### 建议新增迁移

- `0013_agent_runtime_expansion.sql`

### 迁移建议内容

- 为 `agent_runs` 增补更清晰的恢复字段
  - `resume_from_step TEXT NULL`
  - `workflow_version TEXT NULL`
- 为 `agent_run_steps` 增补恢复/分类字段
  - `checkpoint_key TEXT NULL`
  - `step_group TEXT NULL`
- 为 `agent_tool_calls` 增补幂等/语义字段
  - `tool_kind TEXT NULL`

说明：

- 这些字段不是绝对必须一次做全，但建议本包就先补齐，后面 B/C 包会复用

## 5.6 本包要修改的后端文件

### 必改

- `backend/app/api/agent_runs.py`
- `backend/app/api/diagnose.py`
- `backend/app/api/knowledge.py`
- `backend/app/jobs/task_handlers.py`
- `backend/app/core/agent_runtime/run_manager.py`
- `backend/app/core/agent_runtime/step_executor.py`
- `backend/app/core/agent_runtime/tool_registry.py`
- `backend/app/core/agents/orchestrator_agent.py`
- `backend/app/core/agents/diagnosis_agent.py`
- `backend/app/core/agents/retrieval_agent.py`
- `backend/app/core/agents/report_agent.py`
- `backend/app/core/review_service.py`
- `backend/app/db/schemas.py`

### 大概率需要同步

- `backend/tests/test_agent_runs_api.py`
- `backend/tests/test_agent_async_runs.py`
- `backend/tests/test_run_timeline_api.py`
- `backend/tests/test_diagnose.py`
- `backend/tests/test_knowledge_api.py`
- `backend/tests/test_multi_agent_governance.py`

## 5.7 本包要修改的前端文件

### 必改

- `frontend/src/pages/DiagnosisPage.tsx`
- `frontend/src/pages/KnowledgePage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`
- `frontend/src/types.ts`
- `frontend/src/lib/api.ts`

### 视情况改

- `frontend/src/pages/ReviewQueuePage.tsx`
- `frontend/src/pages/SpecialistDashboardPage.tsx`

## 5.8 本包接口改造建议

### 方案一：保留现有业务接口，同时增加 async 入口

优先建议采用这条路径，兼容性风险更低。

#### 诊断

- 保留：`POST /api/diagnose`
- 新增：`POST /api/agent-runs` with `run_type=diagnosis`
- 前端诊断页增加“同步诊断”和“异步诊断”模式，默认走异步

#### 知识重建

- 保留：`POST /api/knowledge/reindex`
- 新增：`POST /api/agent-runs` with `run_type=knowledge_reindex`
- 知识页优先走异步重建，并跳转到 run detail

#### 审核后发布

- 新增：`POST /api/agent-runs` with `run_type=review_publish`
- review approve 后如果需要补充发布动作，则转入 agent run，而不是直接同步完成

## 5.9 本包工作流拆解建议

### `diagnosis`

建议拆成：

1. `diagnosis.file_load`
2. `diagnosis.route_model`
3. `diagnosis.run_model`
4. `diagnosis.persist_case`
5. `diagnosis.emit_summary`

### `chat_answer`

建议拆成：

1. `chat.case_load`
2. `chat.context_prepare`
3. `chat.knowledge_retrieve`
4. `chat.answer_generate`
5. `chat.answer_guardrail`
6. `chat.answer_persist`

### `enhanced_report`

建议拆成：

1. `report.case_load`
2. `report.evidence_collect`
3. `report.generate_structured`
4. `report.validate_schema`
5. `report.guardrail`
6. `report.review_or_publish`

### `knowledge_reindex`

建议拆成：

1. `knowledge.load_documents`
2. `knowledge.embed_chunks`
3. `knowledge.ensure_collection`
4. `knowledge.upsert_vectors`
5. `knowledge.persist_status`

## 5.10 本包实施顺序

1. 扩展 `AgentRunCreateRequest` 和 `SUPPORTED_RUN_TYPES`
2. 为新增 run type 接入 `task_handlers.py`
3. 在 `run_manager.py` 中补恢复所需字段和读取逻辑
4. 把 `chat_answer` 与 `enhanced_report` 从单大 step 拆为多 step
5. 接入 `diagnosis` 的异步 run
6. 接入 `knowledge_reindex` 的异步 run
7. 接入 `review_publish` 的异步 run
8. 更新前端业务页跳转与 run detail 展示
9. 更新测试

## 5.11 本包验收标准

- `POST /api/agent-runs` 可接受 `diagnosis / knowledge_reindex / review_publish`
- 新增 run type 可正确入队、执行、完成、失败
- `RunDetailPage` 能看到多步骤 timeline
- 至少 `chat_answer` 与 `enhanced_report` 的步骤数明显增加，不再只是一条大 step
- `DiagnosisPage` 和 `KnowledgePage` 可跳转到 run detail
- 至少一个失败场景可从中间步骤恢复或重新入队

## 5.12 本包验证命令

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q backend/tests/test_agent_runs_api.py backend/tests/test_agent_async_runs.py backend/tests/test_run_timeline_api.py backend/tests/test_diagnose.py backend/tests/test_knowledge_api.py

cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npx playwright test
```

## 5.13 本包给下游 Codex 的执行提示

你现在执行的是 `执行包 A：统一 run 体系 + 多步骤 runtime 拆解`。

要求：

- 只修改执行包 A 涉及的文件和直接依赖
- 保留现有同步接口兼容性，优先增加异步 agent run 能力，不直接替换所有老接口
- 不修改 `littlemodel`
- 优先复用 `run_manager`、`step_executor`、`review_service`、`vector_index_service`
- 在动手前先说明要改哪些文件
- 每完成一部分都补对应测试

---

## 6. 执行包 B：统一治理层（Guardrails + Human Review）

## 6.1 目标

把当前主要围绕增强报告的治理能力，扩展成统一的高风险输出治理层。

## 6.2 本包完成后必须达到的结果

- 聊天高风险输出可以进入结构化 review task
- 高风险诊断建议可以进入结构化 review task
- review task 类型不再局限于增强报告发布
- run 状态、review 状态、业务对象状态能一致联动
- audit 与 trace 可以贯穿所有 review 触发和审批动作

## 6.3 当前代码现状

当前 review 最成熟的链路主要在：

- `backend/app/core/review_service.py`
- `backend/app/api/reviews.py`
- `frontend/src/pages/ReviewQueuePage.tsx`

当前聊天高风险守卫更多是在：

- `backend/app/core/agent_service.py`

其行为偏保守提示，而不是结构化 review gate。

## 6.4 本包建议新增 review_type

建议新增以下 `review_type`：

- `chat_high_risk_answer`
- `diagnosis_recommendation`
- `knowledge_reindex_publish`
- `enhanced_report_publication`（保留）
- `model_alias_change`（如已有治理入口可统一纳入）

## 6.5 本包建议新增或修改的数据结构

### 建议新增迁移

- `0014_review_governance_expansion.sql`

### 迁移建议内容

- 为 `agent_review_tasks` 增补语义字段
  - `resource_type TEXT NULL`
  - `resource_id TEXT NULL`
  - `risk_level TEXT NULL`
  - `blocking_run_step TEXT NULL`
- 为 `agent_review_actions` 增补上下文
  - `trace_id TEXT NULL`
  - `run_id TEXT NULL`

说明：

- 这些字段能让不同类型 review task 共用同一页面和 API

## 6.6 本包要修改的后端文件

### 必改

- `backend/app/core/agent_runtime/guardrails.py`
- `backend/app/core/agent_service.py`
- `backend/app/core/review_service.py`
- `backend/app/api/reviews.py`
- `backend/app/api/chat.py`
- `backend/app/api/diagnose.py`
- `backend/app/api/knowledge.py`
- `backend/app/core/audit_service.py`
- `backend/app/db/schemas.py`

### 大概率需要同步

- `backend/tests/test_guardrails.py`
- `backend/tests/test_reviews_api.py`
- `backend/tests/test_chat.py`
- `backend/tests/test_diagnose.py`
- `backend/tests/test_auth.py`

## 6.7 本包要修改的前端文件

### 必改

- `frontend/src/pages/ReviewQueuePage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`
- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/CaseDetailPage.tsx`
- `frontend/src/types.ts`
- `frontend/src/lib/api.ts`

## 6.8 本包功能改造建议

### 聊天高风险输出

当前：

- 高风险回答在无 citation 时追加提示语

目标：

- 若命中高风险且缺少足够证据，进入 `waiting_review`
- 生成 `chat_high_risk_answer` review task
- 前端明确显示“待审核”状态，而不是只展示回答文本

### 诊断建议

目标：

- 诊断本身可以完成，但高风险维修建议或自动总结进入 review gate
- case detail 页面可看到“建议待审核”状态

### 知识库重建发布

目标：

- 知识重建完成后，如果涉及覆盖默认知识或高风险来源写入，可进入 review

## 6.9 本包实施顺序

1. 扩展 `guardrails.py` 的风险分类与输出结构
2. 扩展 `review_service.py`，支持多 `review_type`
3. 让 `chat` 链路进入 review gate
4. 让 `diagnosis` 建议链路进入 review gate
5. 视改造成本，让 `knowledge_reindex` 或 `knowledge_ingest` 进入 review gate
6. 更新 `ReviewQueuePage`，支持多类型任务展示
7. 在 `RunDetailPage` 和业务详情页显示 review 关联信息
8. 更新审计与权限测试

## 6.10 本包验收标准

- review queue 中能看到不止增强报告一种任务
- 高风险聊天输出可进入结构化 review
- review approve/reject/request-changes 后，对应 run 状态和业务状态一致变化
- 所有 review 决策都能在 audit logs 中看到
- review task detail 中可以追溯到 `run_id / trace_id / resource`

## 6.11 本包验证命令

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q backend/tests/test_guardrails.py backend/tests/test_reviews_api.py backend/tests/test_chat.py backend/tests/test_diagnose.py backend/tests/test_auth.py

cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npx playwright test
```

## 6.12 本包给下游 Codex 的执行提示

你现在执行的是 `执行包 B：统一治理层（Guardrails + Human Review）`。

要求：

- 不改执行包 C 的 observability/OTel/生产部署内容
- 先统一 review 语义，再扩展前端页面
- 让高风险聊天输出进入结构化 review，而不是只保留免责声明
- 保持增强报告现有行为不退化
- 所有审批动作都要带 audit 记录

---

## 7. 执行包 C：Observability + Eval + Worker 生产化

## 7.1 目标

把当前已经具备雏形的 tracing、eval、worker 机制升级成生产可治理闭环。

## 7.2 本包完成后必须达到的结果

- trace 不再只依赖本地 JSONL，可导出到标准观测后端
- metrics 能统计 run、step、tool、review、failure、latency
- eval 能成为发布前质量门，而不只是可查看页面
- worker 可支持开发/生产两种运行模式

## 7.3 当前代码现状

现有基础：

- `backend/app/core/telemetry_service.py`
- `backend/app/api/system.py`
- `backend/app/core/eval_service.py`
- `backend/app/jobs/worker_runtime.py`
- `frontend/src/pages/EvalDashboardPage.tsx`

当前不足：

- telemetry 仍主要是 JSONL
- 缺少标准 exporter 管线
- 缺少 metrics 仪表定义
- eval suite 与发布流程还未真正绑定
- worker 仍偏单机/嵌入式

## 7.4 本包建议新增或修改的数据结构

### 建议新增迁移

- `0015_eval_and_runtime_versioning.sql`

### 迁移建议内容

- 为 `agent_runs` 增补：
  - `prompt_version TEXT NULL`
  - `toolset_version TEXT NULL`
  - `policy_version TEXT NULL`
- 为 `agent_eval_runs` 增补：
  - `runtime_version TEXT NULL`
  - `comparison_target TEXT NULL`

说明：

- 这能让 eval 结果和运行版本建立稳定关联

## 7.5 本包要修改的后端文件

### 必改

- `backend/app/core/telemetry_service.py`
- `backend/app/api/system.py`
- `backend/app/core/eval_service.py`
- `backend/app/jobs/worker_runtime.py`
- `backend/app/jobs/worker_entry.py`
- `backend/app/core/settings.py`
- `backend/app/core/deepseek_client.py`
- `backend/app/core/rag_service.py`
- `backend/app/core/agent_runtime/step_executor.py`
- `backend/app/db/schemas.py`

### 文档与部署同步

- `docs/deployment-notes.md`
- `docs/testing-playbook.md`
- `backend/README.md`

### 大概率需要同步

- `backend/tests/test_observability.py`
- `backend/tests/test_eval_api.py`
- `backend/tests/test_agent_async_runs.py`
- `backend/tests/test_run_timeline_api.py`

## 7.6 本包要修改的前端文件

### 必改

- `frontend/src/pages/EvalDashboardPage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`
- `frontend/src/pages/AuditLogPage.tsx`
- `frontend/src/types.ts`
- `frontend/src/lib/api.ts`

## 7.7 本包功能改造建议

### Observability

本包不要求一口气接完整企业级平台，但至少要实现：

- 保留现有 JSONL 作为本地 fallback
- 增加 OTel 开关和 exporter 配置
- 对 `run / step / tool / review / llm / retrieval` 输出标准 trace attributes
- 在 `/api/system/observability-summary` 中增加关键指标摘要

### Metrics

至少覆盖：

- run count by type/status
- step duration histogram
- tool failure count
- review pending count
- llm latency / token usage
- retrieval citation count / empty retrieval count

### Eval

把 eval 从“能手工跑”推进到“可作为质量门”：

- 高风险黄金集落地
- case-level failure 明细展示
- 对比上一次或指定版本结果
- 在文档中明确什么时候必须跑 eval

### Worker 生产化

建议采用双模式：

- 开发模式：保留 SQLite + embedded worker
- 生产模式：独立 worker 入口 + 外部 queue/broker 配置位

本包不必彻底接完 Redis 全家桶，但要把代码结构调整到可切换。

## 7.8 本包实施顺序

1. 扩展 `telemetry_service.py` 结构与配置项
2. 增加关键 trace attributes 和 metrics 输出点
3. 扩展 `system.py` 的观测汇总接口
4. 扩展 eval run 的版本与比较能力
5. 更新 `EvalDashboardPage`
6. 重构 worker 配置，明确 embedded 与 standalone 两种模式
7. 更新部署文档与测试文档

## 7.9 本包验收标准

- 本地模式下现有 run/timeline 行为不退化
- 若启用 OTel 配置，trace 能输出到标准后端
- `/api/system/observability-summary` 能展示更有用的指标摘要
- `EvalDashboardPage` 能看到 case-level 失败样例和版本对比信息
- worker 可以独立于 web 进程启动
- 文档中明确开发模式与生产模式的启动方式

## 7.10 本包验证命令

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q backend/tests/test_observability.py backend/tests/test_eval_api.py backend/tests/test_agent_async_runs.py backend/tests/test_run_timeline_api.py

cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build

cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npx playwright test
```

如本包接入本地 Qdrant/观测验证，还应补人工 smoke：

```powershell
docker compose -f C:\Users\luzian\Desktop\windpower_agent3\docker-compose.qdrant.yml up -d

cd C:\Users\luzian\Desktop\windpower_agent3\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

Invoke-RestMethod -Uri http://127.0.0.1:8010/api/system/observability-summary
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/evals
```

## 7.11 本包给下游 Codex 的执行提示

你现在执行的是 `执行包 C：Observability + Eval + Worker 生产化`。

要求：

- 不回头重做 A/B 包已经完成的业务逻辑，除非是直接依赖
- 保留本地 JSONL telemetry 兼容性
- 优先做标准化 trace/metrics 输出点，再做 UI 展示
- eval 结果必须能看见失败明细与版本关联
- worker 必须保留开发模式，同时增强生产部署路径

---

## 8. 三个执行包之间的依赖关系

必须按以下顺序推进：

1. 执行包 A
2. 执行包 B
3. 执行包 C

原因：

- 没有 A，B 的 review 触发面会割裂
- 没有 A/B，C 的 observability 和 eval 只能覆盖半套系统
- 如果先做 C，再补 A/B，很多 trace、metric、eval case 还要返工

## 9. 每个执行包交付后都要更新的文档

建议每包完成后至少更新：

- `docs/agent-execution-packages-plan-2026-06-16.md`
  - 标注已完成项
- `docs/agent-must-do-checklist-2026-06-16.md`
  - 标注必须项进度
- 如涉及部署/测试变化：
  - `docs/deployment-notes.md`
  - `docs/testing-playbook.md`

## 10. 给你的最终建议

如果你要让后续 Codex 真正开始改代码，最合适的启动点是：

- 先执行 `执行包 A`
- 等 A 落完并通过测试后，再进入 `执行包 B`
- 最后再做 `执行包 C`

不要一开始就让它同时做三包。  
这个仓库现在最需要的是稳步把 runtime 主干做实，而不是一次性铺开过多面。
