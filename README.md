# 风电智能诊断平台

这是一个面向风电场景的智能诊断项目，围绕小模型库构建，提供模型浏览、诊断任务执行、案例查看、报告生成与知识问答等能力。

当前仓库已经包含完整的 `littlemodel/` 模型库，拉取仓库后可以直接配合前后端运行。

## 项目定位

- 后端：`FastAPI`
- 前端：`React 18` + `TypeScript` + `Vite`
- 路由：`React Router`
- 样式：`Tailwind CSS`
- 测试：`pytest` + `Playwright`

## 核心能力

- 模型库展示与模型信息查看
- 风电数据上传与诊断任务执行
- 诊断结果、案例与报告管理
- 知识库检索与问答增强
- 可扩展的多智能体诊断流程

## 项目结构

```text
windpower_agent3/
├─ backend/          后端服务与接口
├─ frontend/         前端单页应用
├─ knowledge_base/   风电领域知识与模型说明
├─ littlemodel/      本地模型库与模型权重
├─ RUN_GUIDE.md      本地运行说明
└─ docker-compose.qdrant.yml
```

## 运行要求

- Python 3.10+
- Node.js 18+
- 仓库内已自带 `littlemodel/`
- 如需改用外部模型库，也可以通过 `WINDPOWER_LITTLEMODEL_ROOT` 指向其他路径

## 快速启动

后端依赖安装与启动：

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端依赖安装与启动：

```powershell
cd frontend
npm install
npm run dev
```

## 说明

- 本项目默认复用 `littlemodel` 中已经整理好的模型能力，不直接改动模型源码和权重。
- `knowledge_base/raw/`、`knowledge_base/models/`、`knowledge_base/domain_knowledge/` 属于应保留的源知识内容。
- 运行生成的缓存、日志、报告、中间文件不建议上传到 GitHub。
