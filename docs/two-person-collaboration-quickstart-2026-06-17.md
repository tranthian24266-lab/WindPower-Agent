# 双人协作 5 分钟上手清单

适用项目：`C:\Users\luzian\Desktop\windpower_agent3`

## 1. 第一次开始

由一人先完成：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3
git init
git branch -M main
git add .
git commit -m "chore: initial project snapshot"
```

然后把项目推到 GitHub 私有仓库。

## 2. 另一人加入

```powershell
git clone <GitHub 私有仓库地址>
cd windpower_agent3
```

## 3. 每次开始开发前

```powershell
git checkout main
git pull origin main
git checkout -b feature/<你的名字>-<任务名>
```

例子：

```powershell
git checkout -b feature/luzian-diagnosis-copy-fix
```

## 4. 开发时的最小规则

- 一个分支只做一件事
- 改公共文件前先在聊天里说一声
- 不直接在 `main` 上开发

高冲突文件：

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/lib/api.ts`
- `frontend/src/types.ts`
- `backend/app/main.py`

## 5. 改完后

```powershell
git add .
git commit -m "feat: <改动说明>"
git push -u origin feature/<你的名字>-<任务名>
```

然后去 GitHub 提 Pull Request。

## 6. 合并前检查

前端改动至少跑：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\frontend
npm run build
```

后端改动至少跑：

```powershell
cd C:\Users\luzian\Desktop\windpower_agent3\backend
pytest -q
```

## 7. 每次开始前发一句

```text
我现在开始做：
- 任务：
- 分支：
- 预计会改的文件：
```

## 8. 最简单结论

- `main` 只放稳定代码
- 每次从 `main` 拉 `feature/...` 分支
- 改完提 PR
- 对方看过再合并

