# windpower_agent3 双人协作最小工作流与使用手册

更新时间：2026-06-16  
适用项目：`C:\Users\luzian\Desktop\windpower_agent3`

## 1. 目标

本文档给这个项目设计一套适合两个人协作推进的最小工作流。

目标不是上复杂流程，而是做到这几件事：

1. 两个人能同时开发，不互相覆盖文件。
2. 每次修改都能知道是谁改了什么。
3. 代码出问题时能回退。
4. 前端、后端、文档都能统一管理。
5. 上手成本低，今天就能开始用。

## 2. 结论

推荐方案：

> `Git + GitHub 私有仓库 + feature 分支 + Pull Request`

这是最适合你们当前项目阶段的双人最小协作方案。

原因：

- 比发压缩包稳定得多
- 比网盘同步安全得多
- 比“大家都直接改主线”风险小得多
- 足够轻量，不会拖慢开发

## 3. 当前项目现状

当前目录：

- 还不是一个 Git 仓库
- 已经有 `.gitignore`
- 前端和后端都在同一个项目目录里，适合放到同一个 GitHub 仓库中统一协作

所以你们应该先做的不是“怎么分支”，而是先把这个项目正式纳入 Git 管理。

## 4. 最小协作架构

## 4.1 仓库形式

建议：

- 建一个 `GitHub private repository`
- 整个 `windpower_agent3` 放进同一个仓库
- 前端、后端、文档、运行指南都一起版本管理

不要拆成两个仓库，除非未来团队扩大、前后端完全独立演进。

对于你们现在这种两人协作，小项目单仓库更简单。

## 4.2 分支结构

只保留两类分支：

1. `main`
2. `feature/...`

含义：

- `main`：稳定主线，可运行版本
- `feature/...`：个人开发分支，用于某个明确任务

不要一开始引入：

- `develop`
- `release`
- `hotfix`
- 多层环境分支

这些对当前项目太重。

## 4.3 推荐分支命名

统一使用：

```text
feature/<owner>-<topic>
```

例如：

- `feature/luzian-frontend-copy-fix`
- `feature/teammate-report-export`
- `feature/luzian-model-library-ui`
- `feature/teammate-chat-api-fix`

如果任务是 bug 修复，也可以统一继续用 `feature/`，不必再引入 `bugfix/`。

保持简单最重要。

## 5. 推荐分工方式

## 5.1 最稳妥的分工原则

双人协作最怕的不是代码能力不够，而是两个人同时改同一块。

所以推荐这样分工：

- 一个人主前端界面、文案、页面交互
- 一个人主后端接口、数据结构、业务流程

当然并不是死规定，但默认职责清晰会大大减少冲突。

## 5.2 本项目建议的职责边界

建议按目录划默认责任：

- A 同学优先负责：
  - `frontend/src/pages/`
  - `frontend/src/components/`
  - `frontend/src/styles.css`
  - `docs/` 中前端和使用说明类文档

- B 同学优先负责：
  - `backend/app/api/`
  - `backend/app/core/`
  - `backend/app/db/`
  - `docs/` 中后端、部署、接口类文档

共同可改但要提前沟通的区域：

- `frontend/src/lib/api.ts`
- `frontend/src/types.ts`
- `backend/app/main.py`
- `.gitignore`
- `README.md`
- `RUN_GUIDE.md`

## 5.3 不要同时改的高风险文件

以下文件最容易冲突，改前先说一声：

- `frontend/src/lib/api.ts`
- `frontend/src/types.ts`
- `frontend/src/styles.css`
- `frontend/src/App.tsx`
- `backend/app/main.py`
- `backend/app/core/settings.py`

规则很简单：

> 谁先占这个文件，谁就在群里或者聊天里说一声。

## 6. 最小日常工作流

## 6.1 每天开始前

每天开始开发前，两个人都做：

1. 拉最新主线
2. 从主线切自己的功能分支
3. 再开始写代码

命令如下：

```powershell
git checkout main
git pull origin main
git checkout -b feature/<your-name>-<task>
```

例如：

```powershell
git checkout main
git pull origin main
git checkout -b feature/luzian-diagnosis-copy-fix
```

## 6.2 开发中

开发中遵守 3 条规则：

1. 一个分支只做一件事
2. 一次提交尽量只包含一个主题
3. 改公共文件前先同步

例如：

- 不要在同一个分支里同时改“前端文案 + 后端诊断逻辑 + 部署文档”
- 应拆成更清晰的任务

## 6.3 开发完成后

开发完成后：

1. 先本地自测
2. 提交代码
3. 推送到 GitHub
4. 发 Pull Request
5. 让对方看一眼再合并

命令如下：

```powershell
git add .
git commit -m "feat: update diagnosis page copy"
git push -u origin feature/luzian-diagnosis-copy-fix
```

## 6.4 合并前必须做什么

Pull Request 合并前，至少做这 3 件事：

1. 确认只包含本任务相关改动
2. 确认本地能运行
3. 确认没有把不该提交的日志、缓存、构建产物带进去

对这个项目，最基本的本地验证建议是：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build
```

如果动了后端，再补：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q
```

## 7. 推荐提交信息规范

不需要上很复杂的 Conventional Commits，但至少要看得懂。

推荐格式：

```text
feat: ...
fix: ...
docs: ...
refactor: ...
style: ...
```

示例：

- `feat: add diagnosis task page layout`
- `fix: correct model library title overflow`
- `docs: add two-person collaboration manual`
- `refactor: simplify model library detail panel`
- `style: update dashboard wording`

## 8. Pull Request 最小规范

每个 PR 描述只写 3 部分：

```text
What:
- 改了什么

Why:
- 为什么改

Check:
- 本地验证了什么
```

示例：

```text
What:
- 修改总览页和模型库文案
- 缩短模型库里的英文模型名称

Why:
- 解决标题超出边框和表述不统一的问题

Check:
- npm run build
- 本地浏览器检查首页、模型库、诊断页
```

## 9. 双人协作中的沟通规则

## 9.1 每次开始前发一句

每次开始做任务时，在聊天里发一条：

```text
我现在开始做：
- 任务：
- 分支：
- 预计会改的文件：
```

例如：

```text
我现在开始做：
- 任务：诊断页文案修正
- 分支：feature/luzian-diagnosis-copy-fix
- 预计会改的文件：frontend/src/pages/DiagnosisPage.tsx
```

这条消息能极大减少撞车。

## 9.2 改公共文件前先说

如果要改这些公共文件之一，先发一句：

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/lib/api.ts`
- `frontend/src/types.ts`
- `backend/app/main.py`

## 9.3 不直接口头同步代码状态

不要只说：

- “我改好了”
- “你拉一下”

而是要说清楚：

- 分支名
- PR 链接
- 改动范围
- 是否可以合并

## 10. 冲突处理规则

## 10.1 什么时候最容易冲突

常见冲突来源：

- 两个人同时改同一个文件
- 一个人还没 pull 最新 main 就继续开发
- 一个分支拖太久不合并

## 10.2 冲突的处理方式

标准做法：

```powershell
git checkout main
git pull origin main
git checkout feature/<your-branch>
git merge main
```

如果出现冲突：

1. 打开冲突文件
2. 保留正确内容
3. 删除冲突标记
4. 重新提交

不要用粗暴方式：

- 覆盖对方整个文件
- 直接删掉冲突内容不看

## 10.3 什么时候应该暂停合并

如果冲突文件是以下之一，先别急着硬合：

- `frontend/src/styles.css`
- `frontend/src/types.ts`
- `frontend/src/lib/api.ts`
- `backend/app/main.py`

这时最好两个人先同步 5 分钟再决定怎么合。

## 11. 推荐初始化步骤

因为当前目录还不是 Git 仓库，建议由其中一个人先做初始化。

## 11.1 本地初始化

在项目根目录执行：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3
git init
git add .
git commit -m "chore: initial project snapshot"
```

## 11.2 GitHub 新建私有仓库

在 GitHub 上：

1. 新建一个 private repo
2. 名称建议直接叫：

```text
windpower_agent3
```

3. 不要勾选自动创建 README、.gitignore、license

因为本地已经有内容。

## 11.3 关联远程仓库

```powershell
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

## 11.4 邀请同学

在 GitHub 仓库设置中把你的同学加为 collaborator。

对方拿到后执行：

```powershell
git clone <your-github-repo-url>
```

## 12. 本项目的特殊约束

## 12.1 不要把这些东西提交上去

当前 `.gitignore` 已经忽略了很多内容，但你们仍要有意识：

不要提交：

- `frontend/dist/`
- 各类 `.log`
- 测试输出
- 缓存目录
- 本地环境文件

特别注意：

- `backend/.env` 不要上传

## 12.2 与 `littlemodel` 的关系

这个项目依赖外部路径：

```text
C:\Users\luzian\Desktop\littlemodel
```

不要把那个项目混进当前仓库。

规则：

- 当前仓库只管 `windpower_agent3`
- 外部模型库路径作为本地依赖存在
- 不要把 `littlemodel` 复制进来再提交

## 12.3 文档也要走分支和 PR

不是只有代码才走协作流程。

这些文件也建议照样提 PR：

- `docs/*.md`
- `README.md`
- `RUN_GUIDE.md`

这样后面你们写计划书、手册、接口说明都不会混乱。

## 13. 推荐的最小角色分工模板

可以直接这样用：

### 同学 A

- 前端页面
- 页面文案
- 页面样式
- 使用手册

### 同学 B

- 后端接口
- 数据结构
- 模型调用链
- 部署和运行问题

### 两人共同负责

- 集成测试
- 路由连通
- README / 运行文档
- 最终验收

## 14. 推荐每周/每日节奏

## 14.1 每天开始前

两个人先同步一句：

- 今天各自做什么
- 会不会动公共文件
- 有没有必须先合并的分支

## 14.2 每天结束前

每个人发一条收尾消息：

```text
今天完成：
- ...

当前分支：
- ...

是否已推送：
- yes / no

是否需要你 review：
- yes / no
```

## 14.3 每周至少一次整理 main

不要让很多小分支长期飘着。

建议：

- 能合并的尽快合并
- 合并完删除远程分支

## 15. 最小使用手册

## 15.1 你今天要开始开发

```powershell
git checkout main
git pull origin main
git checkout -b feature/<your-name>-<task>
```

## 15.2 你改完了

```powershell
git add .
git commit -m "feat: <your-change>"
git push -u origin feature/<your-name>-<task>
```

然后去 GitHub 提 PR。

## 15.3 你要合并对方的代码

1. 看 PR
2. 看改动文件
3. 本地跑基本验证
4. 没问题再 merge

## 15.4 你拉了代码跑不起来

先排查：

1. 有没有拉到最新 `main`
2. 有没有本地 `.env`
3. 前后端依赖有没有装
4. `littlemodel` 路径是否存在

## 16. 最终推荐

如果你们只想用一套最省心的协作方式，直接照这个执行：

1. 建 GitHub 私有仓库
2. 整个项目纳入 Git
3. `main` 只放稳定代码
4. 两个人都从 `main` 拉 `feature/...` 分支开发
5. 改完走 PR
6. 合并前至少跑一次最基本验证

这套就已经足够支撑你们把这个项目稳定推进下去。

