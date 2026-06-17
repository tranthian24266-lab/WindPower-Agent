# PostgreSQL 生产迁移指南

## 目标

将当前默认的 SQLite 运行模式迁移为 PostgreSQL 生产主库，同时保持现有原生 SQL 和迁移脚本的兼容性。

## 1. 环境变量

在目标环境中至少配置以下变量：

```env
WINDPOWER_DATABASE_URL=postgresql://user:password@db-host:5432/windpower_db
WINDPOWER_DB_POOL_SIZE=20
WINDPOWER_DB_MAX_OVERFLOW=10
```

如果 `WINDPOWER_DATABASE_URL` 为空，系统会继续使用本地 SQLite。

## 2. 当前适配策略

后端 `app/db/database.py` 已支持以下兼容策略：

- 自动识别 `sqlite` / `postgresql`
- 在 PostgreSQL 模式下把原有 SQL 中的 `?` 占位符转换为 `%s`
- 通过 `RealDictCursor` 保持字典风格查询结果
- 迁移执行时自动跳过 SQLite 专属 `PRAGMA` 语句

这意味着大部分现有 service 层代码不需要重写。

## 3. 迁移步骤

1. 在 PostgreSQL 中创建空库，例如 `windpower_db`。
2. 安装依赖：`pip install -r backend/requirements.txt`
3. 配置 `WINDPOWER_DATABASE_URL`
4. 启动后端一次，让 `schema_migrations` 和业务表自动初始化
5. 如需迁移历史 SQLite 数据，再执行离线导出/导入

## 4. SQLite 历史数据迁移

如果需要把旧库数据导入 PostgreSQL，建议采用“新库建表后导入数据”的流程：

1. 从 SQLite 导出数据
2. 只迁移业务数据，不直接复用旧的 SQLite DDL
3. 优先迁移以下核心表：
   - `uploaded_files`
   - `diagnosis_cases`
   - `chat_sessions`
   - `chat_messages`
   - `agent_runs`
   - `agent_run_steps`
   - `agent_tool_calls`
   - `agent_review_tasks`
   - `agent_review_actions`
   - `eval_runs`
   - `eval_run_items`
   - `agent_audit_logs`

## 5. 验证清单

迁移完成后至少验证：

- `GET /api/system/config-summary` 中 `database_backend=postgresql`
- `pytest -q` 全量通过
- `CI=1 npx playwright test` 通过
- 能成功创建 diagnosis / chat / report / review / eval / audit 记录

## 6. 回滚策略

如果 PostgreSQL 环境异常：

1. 先保留 PostgreSQL 数据库快照
2. 清空 `WINDPOWER_DATABASE_URL`
3. 重启后端，系统会回退到 SQLite

这样可以保证长流程改造具备可恢复性和可审计性。
