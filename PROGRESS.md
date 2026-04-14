# PROGRESS.md — AcademicAgent 开发进度追踪

> ⚠️ Claude Code 必须在每次开发会话开始时首先读取本文件
> 确认当前阶段，绝不跳跃步骤

---

## 当前状态

```
当前阶段：Phase 1 — Step 1.4（基础对话界面（无Agent））
状态：🔲 未开始
```

---

## 总体进度

| Phase | 名称 | 状态 |
|-------|------|------|
| Phase 1 | 基础骨架 | 🔄 进行中 |
| Phase 2 | RAG系统 | 🔲 未开始 |
| Phase 3 | 多Agent系统 | 🔲 未开始 |
| Phase 4 | 完整工作流 | 🔲 未开始 |
| Phase 5 | 优化与打包 | 🔲 未开始 |

---

## Phase 1 — 基础骨架

| Step | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| 1.1 | 项目初始化与目录结构 | ✅ 已完成 | 2026-04-13 |
| 1.2 | 数据库初始化 | ✅ 已完成 | 2026-04-14 |
| 1.3 | 设置页面与LLM配置 | ✅ 已完成 | 2026-04-14 |
| 1.4 | 基础对话界面（无Agent） | 🔲 未开始 | — |
| 1.5 | 论文编辑器页面（骨架） | 🔲 未开始 | — |

## Phase 2 — RAG系统

| Step | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| 2.1 | PDF解析与文本切块 | 🔲 未开始 | — |
| 2.2 | ChromaDB向量存储 | 🔲 未开始 | — |
| 2.3 | 两阶段检索（粗排+精排） | 🔲 未开始 | — |
| 2.4 | GraphRAG知识图谱 | 🔲 未开始 | — |
| 2.5 | RAG系统集成测试 | 🔲 未开始 | — |

## Phase 3 — 多Agent系统

| Step | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| 3.1 | LangGraph基础框架与状态定义 | 🔲 未开始 | — |
| 3.2 | LiteratureReview Agent | 🔲 未开始 | — |
| 3.3 | IdeaGenerator Agent | 🔲 未开始 | — |
| 3.4 | Writer Agent（分节写作） | 🔲 未开始 | — |
| 3.5 | Critic Agent | 🔲 未开始 | — |
| 3.6 | Memory Agent（反馈学习） | 🔲 未开始 | — |

## Phase 4 — 完整工作流

| Step | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| 4.1 | 写作阶段引导流程 | 🔲 未开始 | — |
| 4.2 | 论文版本管理与对比 | 🔲 未开始 | — |
| 4.3 | PLACEHOLDER管理系统 | 🔲 未开始 | — |
| 4.4 | 论文导出（Word/LaTeX） | 🔲 未开始 | — |

## Phase 5 — 优化与打包

| Step | 名称 | 状态 | 完成日期 |
|------|------|------|----------|
| 5.1 | UI/UX优化 | 🔲 未开始 | — |
| 5.2 | 性能优化 | 🔲 未开始 | — |
| 5.3 | 错误处理与健壮性 | 🔲 未开始 | — |
| 5.4 | 一键启动脚本 | 🔲 未开始 | — |

---

## 状态图例

- 🔲 未开始
- 🔄 进行中
- ✅ 已完成（已通过Code Review）
- ❌ 有问题（需要返工）

---

## 变更日志

| 日期 | 变更内容 |
|------|----------|
| 2026-04-13 | Step 1.1 完成：前端(Vite+React+TS+Tailwind+shadcn/ui)、后端(FastAPI)骨架搭建完成 |
| — | 文档初始化 |
| 2026-04-14 | Step 1.2 完成：实现 SQLAlchemy ORM Models、database async session 配置、基础 CRUD 函数，并通过了初始化测试。 |
| 2026-04-14 | Step 1.3 完成：实现设置界面、配置接口及验证。 |

---

## 当前Step的详细任务清单

### Step 1.1 — 项目初始化与目录结构 ✅

- [x] 创建完整子目录结构（frontend/ + backend/）
- [x] 初始化前端：Vite + React + TypeScript（react-ts 模板）
- [x] 安装前端依赖：shadcn/ui、Tailwind CSS v4、zustand、react-router-dom、axios、react-markdown
- [x] 创建后端 `requirements.txt`（fastapi、uvicorn、sqlalchemy、aiosqlite、python-dotenv、pydantic）
- [x] 创建 `backend/main.py`（FastAPI + CORS + `/health` 健康检查）
- [x] 更新 `.gitignore`（添加 node_modules/、frontend/dist/、data 子目录）
- [x] 创建前端页面骨架：ChatPage、EditorPage、LibraryPage、SettingsPage + 路由导航
- [x] 创建后端目录骨架：api/routes/、agents/、rag/、db/、core/、utils/
- [x] 创建 data/ 子目录：sqlite/、chroma/、graphs/、uploads/ + .gitkeep
- [x] 验证：`npm run dev` ✅ 前端正常加载，导航可切换页面
- [x] 验证：`uvicorn main:app` ✅ 后端启动正常，`/health` 返回 200，`/docs` Swagger 正常

---

### Step 1.2 — 数据库初始化（下一步） ✅

- [x] 实现 `db/models.py`（按 DEVELOPMENT_ROADMAP Schema 建所有表）
- [x] 实现 `db/database.py`（SQLAlchemy async engine，auto-create tables on startup）
- [x] 实现 `db/crud.py`（基础CRUD：创建project、查询project列表、插入conversation）
- [x] 编写数据库初始化测试脚本 `backend/test_db.py`
- [x] 验证：`data/sqlite/app.db` 创建成功，能插入和查询记录

---

### Step 1.3 — 设置页面与LLM配置 ✅

- [x] 后端：实现 `/api/config` GET/POST 接口（读写user_config表，API key用base64简单混淆）
- [x] 后端：实现 `core/llm_factory.py`（支持OpenAI、Anthropic、Ollama三种provider，返回LangChain LLM实例）
- [x] 前端：实现 `SettingsPage.tsx`（下拉选provider、输入api key、选model、保存按钮）
- [x] 前端：实现 `/api/config/test` 接口：发一条测试消息，验证配置是否有效

**完成后操作（需进入 Step 1.4）：**
1. 读取新阶段
2. 提供新的开发计划
