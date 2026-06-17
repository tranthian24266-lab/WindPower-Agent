# 项目瘦身记录（2026-06-07）

## 目标

在不影响当前平台运行、诊断、问答、增强报告和知识检索的前提下，删除历史沉淀文档、测试产物和可再生缓存。

## 保留内容

- 运行与调试文档：
  - `README.md`
  - `backend/README.md`
  - `frontend/README.md`
  - `RUN_GUIDE.md`
  - `docs/deployment-notes.md`
  - `docs/security-mode.md`
  - `docs/testing-playbook.md`
- 知识库实际知识源：
  - `knowledge_base/domain_knowledge/*.md`
  - `knowledge_base/models/*.md`
  - `knowledge_base/raw/papers/*.md`
  - `knowledge_base/raw/datasets/*.md`
- 当前后端、前端、数据库、案例数据、报告链路代码

## 删除内容

- `docs/` 下历史执行计划、阶段报告、开发过程文档、设计草案目录
- 顶层历史总结与测试报告副本
- `test-reports/` 截图产物
- 前后端日志、构建缓存、`__pycache__`、`tsbuildinfo`
- `knowledge_base/processed/` 与 `knowledge_base/index_manifest/` 中的可再生缓存文件

## 备份位置

- `C:\Users\luzian\Desktop\windpower_agent3_backup_before_slimming_20260607`

## 说明

- 这次没有修改 `C:\Users\luzian\Desktop\littlemodel`
- 这次没有删除 `backend/outputs`、`backend/reports`、`backend/uploads` 和 `backend/windpower.db`，避免误删现有案例与用户侧诊断结果
- 如果后续再次执行“重新扫描入库”或“重建索引”，知识库缓存会按当前保留的知识源重新生成
