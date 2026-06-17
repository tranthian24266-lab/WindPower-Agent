# windpower_agent3 做成优异智能体项目的必须改造清单

更新时间：2026-06-16  
适用仓库：`C:\Users\luzian\Desktop\windpower_agent3`

## 1. 这份清单的用途

这不是一份泛泛而谈的“AI 产品建议”，而是一份面向当前仓库的执行清单。

目标只有一个：

> 如果要把当前项目做成一个比较优异的智能体项目，哪些改造是必须做的，哪些只是锦上添花。

本文默认沿用当前仓库的硬边界：

- 不修改 `C:\Users\luzian\Desktop\littlemodel` 内的模型代码、权重和测试数据
- 继续通过 `littlemodel/model_registry.json` 和 `inference.py:predict` 调用模型
- 优先复用当前仓库已有的运行时、知识库、报告、治理和前端页面，而不是重写整套系统

## 2. 当前仓库已经具备的基础

先明确一点：这个项目不是从零开始。

当前仓库已经具备一套相当不错的智能体工程基础：

- 后端已经接入 `agent_runs`、`reviews`、`evals`、`knowledge`、`chat` 等路由
- 已有异步 worker 与持久化 run/job 能力
- 已有 run timeline、handoff、audit、review queue、eval dashboard 这类控制面页面
- 已有增强报告 guardrails、知识库检索、Qdrant 集成、RAG 聊天链路

代码证据：

- `backend/app/main.py` 已挂载 agent control-plane 路由，并在 `lifespan` 中启动 embedded worker
- `backend/app/api/agent_runs.py` 已支持 run 创建、查询、timeline、取消、恢复
- `backend/app/core/agent_runtime/run_manager.py` 已持久化 run、step、tool call、queue
- `backend/app/core/telemetry_service.py` 已支持 event 与 trace_span 落盘
- `frontend/src/pages/RunDetailPage.tsx`、`ReviewQueuePage.tsx`、`EvalDashboardPage.tsx` 已具备治理页面雏形

这说明当前项目的问题不是“没有 agent 功能”，而是：

> 现在的 agent 能力还没有成为系统的绝对主干，执行、恢复、评测、治理仍然不够强，离“优异智能体项目”还差关键硬骨架。

## 3. 总判断

如果目标只是“有智能体味道的垂直应用”，当前项目已经不差。

如果目标是“比较优异的智能体项目”，必须补齐下面五类硬能力：

1. `Agent Runtime` 必须成为主干，而不是包装层
2. `Durable Execution` 必须做到真正可恢复，而不是只记录结果
3. `Guardrails + Human Review` 必须覆盖所有高风险输出，而不是只覆盖增强报告
4. `Tracing + Metrics + Eval` 必须形成闭环，而不是只有开发期事件日志
5. `Multi-agent` 必须建立在稳定单智能体 runtime 之上，而不是继续堆 specialist 名称

下面按优先级拆成 `P0 / P1 / P2`。

## 4. P0：必须先做，否则不建议把项目称为“优异智能体项目”

## 4.1 把所有关键业务链路纳入统一的 agent run 体系

### 为什么这是必须项

当前 `agent_runs` 只开放了两个 run type：

- `chat_answer`
- `enhanced_report`

对应代码：

- `backend/app/api/agent_runs.py`
- `backend/app/jobs/task_handlers.py`

这意味着上传、诊断、知识重建、报告发布、审核恢复等关键链路，仍然有一部分跑在 agent runtime 之外。

一个优异的智能体项目，不应该只有“聊天和报告”是 run，其余关键动作还是普通业务接口。  
否则运维、恢复、审计、评测、权限边界都会割裂。

### 必须改成什么

至少把以下能力全部纳入统一 run 体系：

- `diagnosis`
- `chat_answer`
- `enhanced_report`
- `knowledge_reindex`
- `review_publish`
- `case_followup` 或同类后续行动链路

### 主要落点

- `backend/app/api/agent_runs.py`
- `backend/app/jobs/task_handlers.py`
- `backend/app/core/agent_runtime/run_manager.py`
- `backend/app/api/diagnose.py`
- `backend/app/api/knowledge.py`
- `backend/app/api/reviews.py`
- `frontend/src/pages/DiagnosisPage.tsx`
- `frontend/src/pages/KnowledgePage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`

### 验收标准

- 关键长链路都能返回 `run_id`
- 前端能从业务页跳到对应 run detail
- 所有高价值异步任务都能通过 `/api/agent-runs/{run_id}` 统一查看状态
- 取消、失败、恢复路径在同一套 run 语义下工作

## 4.2 把“单次整链路调用”改成“多步骤、可检查点恢复”的执行模型

### 为什么这是必须项

当前虽然已经有 `step`、`tool_call` 表，但实际执行仍然比较粗。

例如在 `backend/app/jobs/task_handlers.py` 中：

- `chat_answer` 本质上是一次 `chat.answer`
- `enhanced_report` 本质上是一次 `enhanced_report.generate`

也就是说，一个完整工作流虽然有 handoff 记录，但在 runtime 层常常仍然只表现为一个大 step。

这会带来三个问题：

- 恢复粒度太粗，失败后只能整段重跑
- 评测粒度太粗，无法比较“检索差”还是“生成差”
- 人工审核插入点太少，不能在关键节点中断

### 必须改成什么

把工作流显式拆成可持久化步骤，例如：

`chat_answer`

1. `case.load`
2. `context.prepare`
3. `knowledge.retrieve`
4. `answer.generate`
5. `answer.guardrail`
6. `answer.persist`

`enhanced_report`

1. `case.load`
2. `evidence.collect`
3. `report.generate_structured`
4. `report.validate_schema`
5. `report.guardrail`
6. `review.enqueue`
7. `report.publish_or_wait`

### 主要落点

- `backend/app/core/agent_runtime/step_executor.py`
- `backend/app/core/agent_runtime/tool_registry.py`
- `backend/app/core/agents/orchestrator_agent.py`
- `backend/app/core/agents/diagnosis_agent.py`
- `backend/app/core/agents/retrieval_agent.py`
- `backend/app/core/agents/report_agent.py`
- `backend/app/core/review_service.py`

### 验收标准

- run detail 中能看到真正多步骤 timeline，而不是只有一个大 step
- 任意关键步骤失败时，错误定位能精确到 step 级别
- 至少一个高价值工作流支持从中间检查点恢复，而不是整条链重跑
- telemetry 中能按 step 统计耗时、成功率、失败类型

## 4.3 把治理口径从“增强报告”扩展到所有高风险输出

### 为什么这是必须项

当前 review workflow 最成熟的覆盖面主要是增强报告发布：

- `backend/app/core/review_service.py`
- `frontend/src/pages/ReviewQueuePage.tsx`

这很好，但还不够。

如果项目未来要被认为是优异智能体项目，那么以下输出都必须有统一治理口径：

- 高风险诊断解释
- 维修建议
- 需要落库或发布的增强报告
- 影响知识库内容的重建/覆盖操作
- 后续若新增的外部系统写操作

### 必须改成什么

统一定义高风险动作类型，并支持：

- `guardrail pass`
- `guardrail warn`
- `waiting_review`
- `blocked`

把“提示增强”升级为结构化治理，不要只是在聊天回答后面追加一句提醒。

### 主要落点

- `backend/app/core/agent_runtime/guardrails.py`
- `backend/app/core/agent_service.py`
- `backend/app/core/review_service.py`
- `backend/app/api/reviews.py`
- `backend/app/api/chat.py`
- `backend/app/api/knowledge.py`
- `frontend/src/pages/ReviewQueuePage.tsx`
- `frontend/src/pages/RunDetailPage.tsx`
- `frontend/src/pages/ChatPage.tsx`

### 验收标准

- 聊天高风险输出能进入 review task，而不是只有文本提醒
- review task 支持按 `review_type` 区分不同风险场景
- 审批、驳回、要求修改后，run 状态与业务对象状态一致
- 所有高风险输出都有 audit 记录和 trace 关联

## 4.4 把本地 telemetry 升级为生产级 observability

### 为什么这是必须项

当前 `telemetry_service.py` 的 JSONL 事件落盘模式，适合本地开发和仓库内验证，但还不够支撑优秀 agent 项目的生产运维。

缺口主要在：

- 还不是标准 OTel exporter 管线
- 缺少真正的指标体系
- 缺少跨进程、跨 worker、跨环境的聚合分析

### 必须改成什么

至少补齐以下能力：

- OpenTelemetry trace/export
- run、step、tool 级 metrics
- 错误类型、重试次数、人工介入率统计
- token/延迟/检索命中/引用数量等质量指标

推荐目标：

- Trace backend：Jaeger 或 Tempo
- Metrics：Prometheus + Grafana

### 主要落点

- `backend/app/core/telemetry_service.py`
- `backend/app/api/system.py`
- `backend/app/jobs/worker_runtime.py`
- `backend/app/core/agent_runtime/step_executor.py`
- `backend/app/core/deepseek_client.py`
- `backend/app/core/rag_service.py`
- `docs/deployment-notes.md`

### 验收标准

- 一个 run 能在外部 trace 系统里按 trace_id 串起来
- 能看到 run 数、失败率、平均耗时、重试率、review 命中率
- 能区分模型问题、检索问题、工具问题、审核问题
- 生产排障不再依赖手工翻 JSONL

## 4.5 建立真正可回归的 agent eval 闭环

### 为什么这是必须项

当前仓库已经有 `evals` 页面和 suite 文件，这是非常好的基础。  
但如果 eval 还只是“能手工跑一下”，它还不够成为优秀 agent 项目的质量门。

优异项目的关键不是“有 eval 页面”，而是：

- 每次 prompt、tool、guardrail、检索逻辑、模型参数变更，都能跑回归
- 能知道变好还是变坏
- 能阻止明显退化进入主线

### 必须改成什么

至少补齐四类评测集：

- `grounding / citation fidelity`
- `diagnosis explanation quality`
- `maintenance recommendation safety`
- `enhanced report schema and evidence quality`

同时把 eval 接入发布前门禁：

- 本地变更可手工跑
- CI 或预发布流程可自动跑

### 主要落点

- `backend/app/core/eval_service.py`
- `backend/evals/suites/*.json`
- `backend/tests/test_eval_api.py`
- `frontend/src/pages/EvalDashboardPage.tsx`
- `docs/testing-playbook.md`

### 验收标准

- 至少存在一套稳定的高风险黄金集
- eval run 能输出 case-level 失败明细，而不是只有总分
- prompt/tool/guardrail 变更后可复跑对比
- 某一类关键质量指标明显退化时，能作为发布阻断条件

## 4.6 把 worker 从“本地可跑”提升到“生产可治理”

### 为什么这是必须项

当前 `AgentWorker` 适合本地嵌入式运行，已经足够做阶段性验证，但还不是成熟生产执行层。

主要问题：

- Web 进程与任务执行仍耦合较深
- 重试、退避、死信、并发治理还不够完整
- 横向扩展和多 worker 竞争控制还不够明确

### 必须改成什么

至少满足以下两种模式：

- 本地开发模式：保留当前 SQLite + embedded worker
- 生产模式：独立 worker 进程 + 外部 broker/queue

推荐生产增强路线：

- Redis + Dramatiq
- 或 Redis + Arq / RQ

### 主要落点

- `backend/app/jobs/worker_runtime.py`
- `backend/app/jobs/worker_entry.py`
- `backend/app/core/settings.py`
- `backend/app/core/agent_runtime/run_manager.py`
- `docs/deployment-notes.md`

### 验收标准

- worker 可与 web 进程解耦部署
- 任务支持租约、超时、重试、死信或等价治理能力
- 多 worker 并发领取任务时不会重复执行
- 失败恢复路径在生产模式下可验证

## 5. P1：强烈建议尽快做，决定项目上限

## 5.1 把 memory 分层做清楚

当前项目有案例、聊天历史、知识库，但还缺一套清晰的智能体 memory 分层。

建议明确分成三层：

- `run state`：当前任务检查点与上下文
- `operational memory`：案例复盘、人工审核结论、设备历史偏好
- `knowledge memory`：论文、领域知识、模型说明、案例知识库

主要落点：

- `backend/app/core/agent_runtime/*`
- `backend/app/core/case_store.py`
- `backend/app/core/rag_service.py`
- `backend/app/core/knowledge_repository.py`

## 5.2 做 prompt、schema、tool version 的版本治理

如果智能体项目迭代多了，没有版本治理很快就会失控。

至少要能追踪：

- 使用了哪个 prompt 版本
- 使用了哪个 report schema 版本
- 使用了哪个 tool 版本
- 某次 eval 对应的是哪个 runtime/prompt 组合

主要落点：

- `backend/app/core/agent_runtime/run_manager.py`
- `backend/app/core/deepseek_client.py`
- `backend/app/core/enhanced_report_llm.py`
- `backend/app/core/eval_service.py`

## 5.3 为“可行动工具”做幂等与权限边界

如果后续 agent 不只回答问题，而是开始触发工单、计划、写操作，那么必须提前做好：

- 幂等 key
- actor / role 权限边界
- 审批前禁止提交
- 审计可回放

主要落点：

- `backend/app/core/auth.py`
- `backend/app/core/audit_service.py`
- `backend/app/core/agent_runtime/guardrails.py`
- 新的 action tool 模块

## 6. P2：最后再做，不应抢在前面

## 6.1 做真正动态的多智能体协作

当前 `OrchestratorAgent` 已经有 specialist handoff 概念，但仍然偏静态编排。  
在 P0 没做硬之前，不建议优先把精力放在更复杂的动态 agent-to-agent 协商上。

只有在下面条件满足后，才值得继续推进：

- 单智能体 runtime 稳定
- review/guardrail 口径统一
- eval 和 observability 已经能兜底

那时再考虑：

- planner / executor / reviewer 分层
- 基于任务类型的动态 delegation
- 更细的 specialist tool domain

主要落点：

- `backend/app/core/agents/orchestrator_agent.py`
- `backend/app/core/agents/*`
- `backend/app/core/agent_runtime/handoff_manager.py`（如新增）

## 6.2 做外部系统联动型 agent action

例如：

- 自动生成工单
- 自动生成巡检计划
- 自动写回运维系统

这些都很有价值，但必须排在 P0 和大部分 P1 后面。  
否则项目会先面临治理风险，而不是能力不足。

## 7. 不建议现在优先做的事情

如果目标是尽快迈向“优异智能体项目”，以下事项不应排在前面：

- 继续增加更多 specialist 名称，但不增强 runtime
- 一上来就做复杂 agent-to-agent 自主协商
- 只美化控制台页面，不补执行与评测骨架
- 继续把高风险问答停留在“加一句免责声明”
- 只做 tracing 展示，不做 eval 闭环

## 8. 推荐执行顺序

建议严格按下面顺序推进：

1. 统一关键链路进 run 体系
2. 把粗粒度执行拆成可检查点恢复的多步骤工作流
3. 扩展 guardrails 和 human review 到所有高风险输出
4. 升级 observability 到生产级 trace + metrics
5. 建立真正的 eval 回归门
6. 强化 worker 生产部署模式
7. 再做更动态的多智能体协作

## 9. 一句话结论

这个项目要想变成一个比较优异的智能体项目，最核心的不是“再多加几个 agent”，而是把下面五件事做硬：

- `Agent Runtime`
- `Durable Execution`
- `Guardrails + Human Review`
- `Tracing + Metrics + Eval`
- `Production Worker Architecture`

把这些补齐后，当前仓库会从“有智能体功能的平台”，升级为“以智能体运行时为核心的工程化平台”。

## 10. 下一步实施建议

如果接下来要进入开发，建议不要同时铺开全部事项，而是拆成三个连续执行包：

1. `执行包 A`
   目标：统一 run 体系 + 多步骤 runtime 拆解
2. `执行包 B`
   目标：治理扩面 + review 闭环统一
3. `执行包 C`
   目标：observability / eval / worker 生产化

建议每个执行包都产出：

- 目标文件列表
- 接口变更清单
- 数据表迁移清单
- 验收命令
- 一个下游 Codex 可直接执行的短 prompt
