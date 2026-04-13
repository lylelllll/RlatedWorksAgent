# AcademicAgent — SCI论文多Agent写作系统
# 开发路线图（Claude Code 专用文档）

---

## ⚠️ 重要：开发状态追踪

**当前阶段：Phase 1 — Step 1.1（项目初始化）**

> 每次开始新的开发会话，Claude Code 必须首先读取 `PROGRESS.md`，
> 确认当前所处阶段后再继续工作，绝不跳跃阶段。

---

## 一、系统总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│              React + TypeScript + Vite Frontend              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│   │ 对话界面  │  │ 论文编辑器│  │ 文献管理 │  │ 设置中心 │  │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP / WebSocket
┌─────────────────────▼───────────────────────────────────────┐
│                   FastAPI Backend                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  API Router │  │ WebSocket Hub│  │  Auth & Config     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────────────┘ │
│         └────────────────┼────────────────────────────────  │
│                          │                                   │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │              LangGraph Orchestration Layer            │  │
│  │                                                       │  │
│  │  ┌─────────────┐         ┌────────────────────────┐  │  │
│  │  │  Supervisor │────────▶│   State Machine Graph  │  │  │
│  │  │    Agent    │         └──────────┬─────────────┘  │  │
│  │  └─────────────┘                   │                  │  │
│  │                    ┌───────────────┼──────────────┐  │  │
│  │                    ▼               ▼              ▼  │  │
│  │  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐│  │
│  │  │  Literature │ │  Idea    │ │ Writing  │ │Critic││  │
│  │  │   Review    │ │Generator │ │  Agent   │ │Agent ││  │
│  │  │   Agent     │ └──────────┘ └──────────┘ └──────┘│  │
│  │  └─────────────┘                                     │  │
│  │                    ┌──────────────────────────────┐  │  │
│  │                    │       Memory Agent           │  │  │
│  │                    │  (用户偏好 + 反馈学习)         │  │  │
│  │                    └──────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   RAG System Layer                      │ │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │ │
│  │  │  Bi-Encoder  │  │Cross-Encoder│  │  GraphRAG    │  │ │
│  │  │ (粗排检索)    │  │  (精排重排) │  │  知识图谱    │  │ │
│  │  └──────────────┘  └─────────────┘  └──────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                         ▼
  ┌───────────────┐      ┌─────────────────┐      ┌─────────────────┐
  │  SQLite DB    │      │   ChromaDB      │      │    NetworkX     │
  │               │      │  (向量数据库)    │      │  (知识图谱)     │
  │ - 对话记录    │      │                 │      │                 │
  │ - 论文版本    │      │ - 目标期刊论文  │      │ - 论文引用关系  │
  │ - 用户设置    │      │ - 兴趣论文      │      │ - 概念实体关系  │
  │ - 文献元数据  │      │ - 全量论文      │      │ - 方法演进图谱  │
  └───────────────┘      └─────────────────┘      └─────────────────┘
```

---

## 二、多Agent工作流设计（LangGraph）

### 2.1 Agent角色定义

| Agent | 职责 | 触发条件 |
|-------|------|----------|
| **Supervisor** | 路由用户意图，调度其他Agent，管理全局状态 | 每次用户输入 |
| **LiteratureReview** | 检索RAG，总结相关文献，分析研究现状与gap | 需要文献支撑时 |
| **IdeaGenerator** | 基于文献gap + 用户研究方向，生成创新idea | 头脑风暴/idea阶段 |
| **Writer** | 写作各论文章节（Introduction/Related Work/Method/Experiment） | 写作阶段 |
| **Critic** | 审阅当前草稿，提出修改意见，检查逻辑一致性 | 每次章节完成后 |
| **Memory** | 记录用户偏好、历史反馈、写作风格偏好 | 贯穿全程 |

### 2.2 LangGraph 状态机

```
用户输入
    │
    ▼
┌─────────────┐
│  Supervisor │  ──── 意图分类 ────────────────────────────────┐
└──────┬──────┘                                                 │
       │                                                        │
  ┌────┴─────────────────────────────────────┐                │
  │                                          │                │
  ▼                                          ▼                ▼
[探索阶段]                              [写作阶段]         [反馈阶段]
  │                                          │                │
  ├─ LiteratureReview ──▶ IdeaGenerator     ├─ Writer        ├─ Memory.update()
  │      (检索gaps)          (生成ideas)     │   (按节写作)   │
  │                               │          ├─ Critic        └─ Writer.revise()
  │                               ▼          │   (审阅)
  │                       用户选择/反馈       └─ 用户反馈
  │                               │
  └───────────────────────────────┘
              循环迭代

全局状态 (GraphState):
{
  "session_id": str,
  "paper_stage": enum[EXPLORE, IDEA, OUTLINE, WRITING, REVIEW, DONE],
  "current_section": enum[INTRO, RELATED, METHOD, EXPERIMENT, CONCLUSION],
  "paper_draft": dict[section -> content],
  "paper_versions": list[PaperVersion],
  "user_feedback_history": list[Feedback],
  "memory_context": dict,
  "rag_context": list[RetrievedChunk],
  "active_agent": str,
  "messages": list[Message]
}
```

### 2.3 RAG 三层检索架构

```
用户Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Query 预处理（关键词提取 + 学术短语识别）             │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
  [目标期刊集合]  [兴趣论文集合]  [全量论文集合]
  (写作风格参考)  (idea来源)     (知识基础)
          │            │            │
          └────────────┼────────────┘
                       │
                       ▼
         ┌─────────────────────────┐
         │  Bi-Encoder 粗排        │
         │  (sentence-transformers)│
         │  Top-50 candidates      │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │  Cross-Encoder 精排     │
         │  (ms-marco reranker)    │
         │  Top-10 results         │
         └────────────┬────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │  GraphRAG 增强          │
         │  相关节点扩展 + 关系推理 │
         └────────────┬────────────┘
                      │
                      ▼
              最终上下文注入Agent
```

---

## 三、技术栈

| 层次 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | React 18 + TypeScript + Vite | 单页应用 |
| UI组件 | shadcn/ui + Tailwind CSS | 现代风格 |
| 论文编辑器 | CodeMirror 6 / TipTap | 支持LaTeX语法 |
| 后端 | FastAPI + uvicorn | 异步支持 |
| 实时通信 | WebSocket | 流式输出 |
| SQL数据库 | SQLite + SQLAlchemy | 本地存储，无需安装服务 |
| 向量数据库 | ChromaDB | 本地运行，无需服务器 |
| 知识图谱 | NetworkX + pickle持久化 | 轻量，纯Python |
| LLM框架 | LangChain + LangGraph | Agent编排 |
| Bi-Encoder | sentence-transformers | 本地运行 |
| Cross-Encoder | cross-encoder/ms-marco | 本地运行 |
| PDF解析 | PyMuPDF (fitz) | 速度快，效果好 |
| 论文导出 | python-docx + LaTeX模板 | Word/LaTeX双格式 |
| 打包 | PyInstaller / Electron | 桌面应用分发 |

---

## 四、数据库 Schema

### SQLite 表结构

```sql
-- 用户配置
CREATE TABLE user_config (
    id INTEGER PRIMARY KEY,
    llm_provider TEXT,        -- openai/anthropic/ollama
    api_key TEXT,             -- 加密存储
    model_name TEXT,
    embedding_model TEXT,
    created_at TIMESTAMP
);

-- 项目（一篇论文 = 一个项目）
CREATE TABLE projects (
    id TEXT PRIMARY KEY,      -- UUID
    title TEXT,
    research_direction TEXT,
    target_journal TEXT,
    stage TEXT,               -- EXPLORE/IDEA/WRITING/REVIEW/DONE
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 对话记录
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    role TEXT,                -- user/assistant/system
    content TEXT,
    agent_type TEXT,          -- supervisor/writer/critic等
    metadata JSON,
    created_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 论文版本（每次保存生成一个版本）
CREATE TABLE paper_versions (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    version_number INTEGER,
    content JSON,             -- {intro: "...", related: "...", method: "..."}
    change_summary TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 用户反馈记录
CREATE TABLE feedbacks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    section TEXT,
    feedback_text TEXT,
    agent_action TEXT,        -- 记录agent如何响应
    created_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 上传文献元数据
CREATE TABLE papers (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    filename TEXT,
    title TEXT,
    authors TEXT,
    year INTEGER,
    abstract TEXT,
    paper_category TEXT,      -- JOURNAL/INTEREST/DOMAIN
    file_path TEXT,
    chunk_count INTEGER,
    indexed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 用户记忆（Memory Agent持久化）
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    memory_type TEXT,         -- preference/style/feedback_pattern
    content TEXT,
    importance FLOAT,
    created_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

---

## 五、项目目录结构

```
academic-agent/
├── PROGRESS.md                    # ← 开发进度追踪（必读）
├── DEVELOPMENT_ROADMAP.md         # ← 本文件
├── README.md
├── .gitignore
│
├── frontend/                      # React前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx       # 主对话界面
│   │   │   ├── EditorPage.tsx     # 论文编辑器
│   │   │   ├── LibraryPage.tsx    # 文献管理
│   │   │   └── SettingsPage.tsx   # 设置
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   ├── editor/
│   │   │   ├── library/
│   │   │   └── common/
│   │   ├── hooks/
│   │   ├── stores/                # Zustand状态管理
│   │   └── api/                   # API调用层
│   └── public/
│
├── backend/                       # FastAPI后端
│   ├── main.py                    # 入口
│   ├── requirements.txt
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py
│   │   │   ├── papers.py
│   │   │   ├── projects.py
│   │   │   └── config.py
│   │   └── websocket.py
│   ├── agents/                    # LangGraph Agents
│   │   ├── graph.py               # 主工作流图
│   │   ├── state.py               # GraphState定义
│   │   ├── supervisor.py
│   │   ├── literature_review.py
│   │   ├── idea_generator.py
│   │   ├── writer.py
│   │   ├── critic.py
│   │   └── memory_agent.py
│   ├── rag/                       # RAG系统
│   │   ├── ingestion.py           # PDF解析+切块
│   │   ├── bi_encoder.py          # 粗排
│   │   ├── cross_encoder.py       # 精排
│   │   ├── graph_rag.py           # 知识图谱
│   │   └── retriever.py           # 统一检索接口
│   ├── db/
│   │   ├── database.py            # SQLAlchemy配置
│   │   ├── models.py              # ORM模型
│   │   └── crud.py                # 数据库操作
│   ├── core/
│   │   ├── config.py              # 应用配置
│   │   ├── llm_factory.py         # LLM初始化工厂
│   │   └── security.py            # API key加密
│   └── utils/
│       ├── pdf_parser.py
│       └── latex_exporter.py
│
└── data/                          # 本地数据目录（gitignore）
    ├── sqlite/
    ├── chroma/
    ├── graphs/
    └── uploads/
```

---

## 六、分阶段开发计划

---

### 🔵 Phase 1：基础骨架（Foundation）

**目标：** 跑通前后端基本通信，用户可以配置LLM并进行基础对话。

---

#### Step 1.1 — 项目初始化与目录结构
**工作量：** 小  
**任务：**
- 创建完整目录结构
- 初始化 `PROGRESS.md`（记录当前阶段）
- 前端：`npm create vite@latest frontend -- --template react-ts`，安装依赖（shadcn/ui、tailwind、zustand、react-router-dom、axios）
- 后端：创建 `requirements.txt`，包含fastapi、uvicorn、sqlalchemy、aiosqlite、python-dotenv、pydantic
- 创建 `.gitignore`，忽略 `data/`、`.env`、`node_modules/`、`__pycache__/`

**验收标准：**
- `cd frontend && npm run dev` 能看到默认页面
- `cd backend && uvicorn main:app --reload` 能启动，访问 `/docs` 有Swagger文档
- `PROGRESS.md` 存在，内容为"当前阶段: Phase 1 - Step 1.1 ✅ 完成，下一步: Step 1.2"

---

#### Step 1.2 — 数据库初始化
**工作量：** 小  
**任务：**
- 实现 `db/models.py`（按上文Schema建所有表）
- 实现 `db/database.py`（SQLAlchemy async engine，auto-create tables on startup）
- 实现 `db/crud.py`（基础CRUD：创建project、查询project列表、插入conversation）
- 编写数据库初始化测试脚本 `backend/test_db.py`

**验收标准：**
- 运行测试脚本，`data/sqlite/app.db` 文件创建成功
- 能插入和查询project、conversation记录
- 不报任何SQLAlchemy错误

---

#### Step 1.3 — 设置页面与LLM配置
**工作量：** 中  
**任务：**
- 后端：实现 `/api/config` GET/POST 接口（读写user_config表，API key用base64简单混淆）
- 后端：实现 `core/llm_factory.py`（支持OpenAI、Anthropic、Ollama三种provider，返回LangChain LLM实例）
- 前端：实现 `SettingsPage.tsx`（下拉选provider、输入api key、选model、保存按钮）
- 前端：实现 `/api/config/test` 接口：发一条测试消息，验证配置是否有效

**验收标准：**
- 前端能保存OpenAI配置，测试接口返回成功
- 配置持久化到SQLite，重启后仍存在

---

#### Step 1.4 — 基础对话界面（无Agent）
**工作量：** 中  
**任务：**
- 后端：实现WebSocket endpoint `/ws/chat/{session_id}`，接收消息，直接调LLM，流式返回
- 后端：对话消息存入conversations表
- 前端：实现 `ChatPage.tsx`（左侧项目列表，右侧对话框，消息流式显示，Markdown渲染）
- 前端：实现项目创建弹窗（填写项目名、研究方向、目标期刊）
- 前端：使用Zustand管理当前project状态

**验收标准：**
- 能创建项目，能和LLM对话，消息流式显示
- 对话历史保存到DB，刷新页面后历史仍存在
- Markdown格式正确渲染

---

#### Step 1.5 — 论文编辑器页面（骨架）
**工作量：** 小  
**任务：**
- 前端：实现 `EditorPage.tsx`（分栏显示论文各章节：Abstract/Introduction/Related Work/Methodology/Experiments/Conclusion）
- 每个章节是一个可折叠的文本区域（暂用 `<textarea>`）
- 后端：实现 `/api/projects/{id}/paper` GET/POST 接口（读写paper_versions表）
- 前端：保存按钮 → 调用保存接口 → 提示"版本 #N 已保存"

**验收标准：**
- 编辑器页面可以手动输入各章节内容并保存
- 保存后版本号递增
- 页面切换后数据不丢失

---

**Phase 1 完成标志：** 用户能配置LLM、创建项目、进行基础对话、手动编辑论文草稿。

---

### 🟡 Phase 2：RAG系统构建

**目标：** 完整的文献处理流水线，支持三类论文分类存储和两阶段检索。

---

#### Step 2.1 — PDF解析与文本切块
**工作量：** 中  
**任务：**
- 安装 `PyMuPDF`，实现 `utils/pdf_parser.py`
- 解析功能：提取标题、作者、年份（正则+启发式）、摘要、正文
- 切块策略：按段落切，chunk_size=512 tokens，overlap=64 tokens，保留章节信息作为元数据
- 后端：实现 `/api/papers/upload` POST 接口（上传PDF，支持批量，multipart/form-data）
- 上传时指定论文category（JOURNAL/INTEREST/DOMAIN）
- 前端：实现 `LibraryPage.tsx`（文件上传区，论文列表，category标签）

**验收标准：**
- 上传PDF后，元数据存入papers表
- 能从PDF提取到title、abstract（至少80%准确）
- 切块结果合理（无乱码，无截断句子）

---

#### Step 2.2 — ChromaDB向量存储
**工作量：** 中  
**任务：**
- 安装 `chromadb`、`sentence-transformers`
- 实现 `rag/bi_encoder.py`：加载 `BAAI/bge-m3`（支持中英文）模型，提供encode方法
- ChromaDB创建3个collection：`journal_papers`、`interest_papers`、`domain_papers`
- 实现索引pipeline：PDF chunks → embedding → 存入对应collection（附metadata：paper_id, title, section, chunk_index）
- 后端：上传PDF后自动触发后台索引任务（FastAPI BackgroundTasks）
- 前端：论文列表显示索引状态（待处理/索引中/已完成）

**验收标准：**
- 上传10篇论文，全部索引完成，无报错
- ChromaDB中能查到chunk数量与预期一致
- 支持进度回调（通过WebSocket通知前端）

---

#### Step 2.3 — 两阶段检索（粗排+精排）
**工作量：** 中  
**任务：**
- 实现 `rag/cross_encoder.py`：加载 `cross-encoder/ms-marco-MiniLM-L-6-v2`
- 实现 `rag/retriever.py`：统一检索接口
  - 输入：query, collection_types, top_k_coarse=50, top_k_fine=10
  - 步骤：Bi-Encoder检索50个 → Cross-Encoder重排 → 返回Top 10
- 编写检索测试接口 `/api/rag/search`（开发调试用）

**验收标准：**
- 给定查询词，能返回10个相关chunk，有标题和来源
- Cross-Encoder重排后结果相关性明显优于单纯向量检索（人工评估3个case）
- 检索耗时 < 3秒（本地CPU）

---

#### Step 2.4 — GraphRAG知识图谱
**工作量：** 大  
**任务：**
- 安装 `networkx`
- 实现 `rag/graph_rag.py`，建图逻辑：
  - **节点类型**：Paper（论文）、Concept（关键概念/方法）、Author（作者）
  - **边类型**：CITES（引用关系，从reference section提取）、USES（论文使用某方法）、SIMILAR_TO（embedding相似度 > 0.85）
  - 从PDF摘要+关键词提取Concept节点（用LLM或KeyBERT）
- 图的持久化：保存为pickle文件到 `data/graphs/`
- 查询接口：给定paper_id，返回N跳邻居（方法演进路径、引用网络）
- 集成进retriever：向量检索结果 → 图扩展 → 返回扩展上下文

**验收标准：**
- 上传20篇论文后，图中节点数 > 50，边数 > 100
- 能查询某篇论文的引用网络（2跳）
- 能找到两篇论文共同引用的核心方法

---

#### Step 2.5 — RAG系统集成测试
**工作量：** 小  
**任务：**
- 编写端到端测试脚本：上传5篇论文 → 索引 → 检索 → 验证结果
- 在 `LibraryPage` 添加"测试检索"功能（输入query，显示检索结果及来源）
- 性能优化：大批量论文时异步并行处理embedding

**验收标准：**
- 完整流程无错误
- 前端能展示RAG检索结果和来源论文

---

**Phase 2 完成标志：** 完整RAG流水线，上传文献后可语义检索，知识图谱构建完成。

---

### 🟠 Phase 3：多Agent系统（LangGraph核心）

**目标：** 实现完整的多Agent工作流，每个Agent有明确职责。

---

#### Step 3.1 — LangGraph基础框架与状态定义
**工作量：** 中  
**任务：**
- 安装 `langgraph`、`langchain`
- 实现 `agents/state.py`：定义 `GraphState`（TypedDict，包含所有字段）
- 实现 `agents/graph.py`：创建StateGraph骨架，定义节点和边（先用占位函数）
- 实现 `agents/supervisor.py`：
  - 接收用户消息，分类意图（EXPLORE/IDEA/WRITE_SECTION/FEEDBACK/QUESTION）
  - 根据意图路由到对应Agent节点
  - 使用LLM进行意图分类（few-shot prompt）
- WebSocket接收消息 → 触发LangGraph图运行 → 流式回传结果

**验收标准：**
- 用户发消息，Supervisor能正确分类意图（测试5种情况）
- LangGraph图能运行完整，不报错
- WebSocket流式输出Agent的中间状态（"正在检索文献..."等）

---

#### Step 3.2 — LiteratureReview Agent
**工作量：** 中  
**任务：**
- 实现 `agents/literature_review.py`
- 工作流程：
  1. 从state中提取当前query/topic
  2. 调用RAG retriever检索相关文献
  3. 用LLM总结：主要研究方向、核心方法、研究gap
  4. 返回结构化结果：`{summary: str, gaps: list[str], key_papers: list[PaperRef]}`
- Prompt设计：系统提示包含"你是一个学术文献分析专家"，结合检索到的chunk

**验收标准：**
- 给定研究方向，能返回3-5个研究gap
- 引用的论文来自RAG检索结果（有来源）
- 输出格式正确，前端能展示

---

#### Step 3.3 — IdeaGenerator Agent
**工作量：** 中  
**任务：**
- 实现 `agents/idea_generator.py`
- 工作流程：
  1. 接收LiteratureReview的gaps + 用户研究方向
  2. 从INTEREST论文集合中额外检索灵感
  3. 用LLM生成3个研究idea，每个包含：标题、核心贡献、技术路线、与现有工作的区别
  4. 以卡片形式返回，用户可选择或继续生成
- 支持用户反馈后改进idea（"太复杂了"/"换个方向"）

**验收标准：**
- 生成的idea有明确的技术可行性描述
- 用户给反馈后，下一轮idea有明显调整
- 3个idea之间有差异性

---

#### Step 3.4 — Writer Agent（分节写作）
**工作量：** 大  
**任务：**
- 实现 `agents/writer.py`，支持写作各章节
- **Introduction**：4段结构（研究背景→现有工作→研究gap→本文贡献），参考JOURNAL论文风格
- **Related Work**：按子主题分组，每组2-3篇文献，对比分析
- **Methodology**：根据用户描述的方案（或idea），写方法描述；对于需要实验的部分，插入 `[EXPERIMENT_PLACEHOLDER: 请用户填写xxx实验结果]` 标记
- **Experiments**：写实验设置、数据集描述、评价指标；实验数字部分用 `[RESULT_PLACEHOLDER]` 标记
- **Conclusion**：总结贡献，展望未来
- 写作时从JOURNAL集合检索写作风格参考，注入prompt

**验收标准：**
- 每个章节生成内容 > 300字，学术风格
- PLACEHOLDER标记正确插入（不编造数据）
- 写出的内容与RAG检索到的文献保持一致，无明显幻觉

---

#### Step 3.5 — Critic Agent
**工作量：** 中  
**任务：**
- 实现 `agents/critic.py`
- 审阅维度：逻辑连贯性、学术表达、引用是否支撑论点、章节完整性
- 生成 `CriticReport`：`{issues: list[Issue], suggestions: list[str], score: int}`
- Writer Agent完成每个章节后自动触发Critic
- 前端展示审阅意见，用户可选择"接受建议"（触发Writer修改）或"忽略"

**验收标准：**
- Critic能找到Writer生成内容中的至少1个改进点
- 接受建议后，Writer修改版本有实质性改变
- Critic不能对PLACEHOLDER内容报错

---

#### Step 3.6 — Memory Agent（反馈学习）
**工作量：** 中  
**任务：**
- 实现 `agents/memory_agent.py`
- 记录内容：写作风格偏好（简洁/详细）、用户常见修改模式、偏好的论文结构
- 存储：memories表 + 内存中的短期缓存
- 影响：每次Writer写作前，从Memory提取偏好注入到prompt
- 实现简单的反馈提取：从用户的修改指令中提取偏好规律（用LLM）

**验收标准：**
- 用户反馈"写得太啰嗦"后，后续输出明显更简洁
- 偏好持久化到DB，重启后生效
- 内存不超过2000 tokens（实现截断机制）

---

**Phase 3 完成标志：** 完整多Agent工作流运行，能从文献探索到各章节写作，支持反馈学习。

---

### 🔴 Phase 4：论文写作完整工作流

**目标：** 打通从探索→Idea→写作→审阅的完整流程，论文版本管理完善。

---

#### Step 4.1 — 写作阶段引导流程
**工作量：** 中  
**任务：**
- 在ChatPage实现引导式UI：不同写作阶段显示不同的"建议操作"面板
  - EXPLORE阶段：显示"分析文献gap"、"生成研究idea"按钮
  - IDEA阶段：显示3个idea卡片，用户选定后进入WRITING
  - WRITING阶段：章节进度条（Introduction→Related Work→Method→Experiments→Conclusion）
- 章节写作顺序可灵活调整
- 写作某章节时，自动在右侧打开EditorPage对应章节

**验收标准：**
- 全流程能走通，阶段转换有明确提示
- 用户选定idea后，idea内容注入到后续所有Agent的上下文

---

#### Step 4.2 — 论文版本管理与对比
**工作量：** 中  
**任务：**
- 后端：每次Agent更新章节后自动创建新版本（paper_versions表）
- 前端：EditorPage右上角版本历史下拉框，可切换查看历史版本
- 实现版本diff展示（高亮新增/删除内容）
- 一键回滚到任意历史版本

**验收标准：**
- 版本号正确递增
- Diff视图正确高亮变化
- 回滚成功且不影响后续版本追加

---

#### Step 4.3 — PLACEHOLDER管理系统
**工作量：** 中  
**任务：**
- 前端：在EditorPage中，PLACEHOLDER用特殊样式高亮显示（黄色背景+图标）
- 用户点击PLACEHOLDER，弹出填写框，输入实验结果后替换
- 后端：实现 `/api/projects/{id}/fill_placeholder` 接口
- 所有PLACEHOLDER填写完成后，Critic Agent重新审阅相关章节

**验收标准：**
- PLACEHOLDER在编辑器中清晰可见
- 填写后内容正确替换，不影响周围文本
- 显示"还有N个待填写"的进度提示

---

#### Step 4.4 — 论文导出
**工作量：** 中  
**任务：**
- 后端：实现Word导出（python-docx，学术格式：双栏/单栏可选，标题/摘要/章节格式）
- 后端：实现LaTeX导出（基于模板，生成.tex文件，支持IEEE/ACM模板）
- 前端：导出按钮，选择格式，下载文件

**验收标准：**
- Word导出格式正确，章节标题层级正确
- LaTeX文件能用 `pdflatex` 编译（在本地测试）
- 参考文献部分导出为BibTeX格式

---

**Phase 4 完成标志：** 完整的论文写作体验，从idea到可导出的草稿。

---

### 🟣 Phase 5：优化与打包

**目标：** 产品化，提升用户体验，准备开源发布。

---

#### Step 5.1 — UI/UX优化
**工作量：** 大  
**任务：**
- 参考Cursor/Claude.ai设计，优化整体视觉风格
- 添加深色模式
- 优化加载状态、错误提示、空状态展示
- 响应式布局（支持不同屏幕尺寸）
- 添加新手引导（首次使用时的Step-by-step提示）

---

#### Step 5.2 — 性能优化
**工作量：** 中  
**任务：**
- 大量论文时，索引任务队列化（避免阻塞）
- ChromaDB查询缓存（相同query短时间内复用结果）
- 前端虚拟列表（论文列表条目多时）
- Embedding模型按需加载（首次使用时才下载）

---

#### Step 5.3 — 错误处理与健壮性
**工作量：** 中  
**任务：**
- API Key无效时的友好提示
- PDF解析失败时的降级处理（跳过该文件，报告失败原因）
- LangGraph节点超时处理（设置30s超时，超时后返回部分结果）
- 所有API添加错误响应Schema，前端统一错误处理

---

#### Step 5.4 — 一键启动脚本
**工作量：** 中  
**任务：**
- 编写 `start.sh`（Mac/Linux）和 `start.bat`（Windows）
- 脚本功能：检查Python/Node版本，安装依赖，初始化DB，同时启动前后端
- 编写 `README.md`：安装指南、使用说明、FAQ
- 首次运行时自动下载Embedding模型（约500MB，带进度条）

**验收标准：**
- 全新环境下，执行start脚本后5分钟内可用
- README足够清晰，非技术用户能自行安装

---

**Phase 5 完成标志：** 可以作为开源项目发布的产品级软件。

---

## 七、开发规范

### 代码规范
- Python：Black格式化，类型注解，docstring
- TypeScript：ESLint + Prettier，严格模式
- 所有API返回统一格式：`{"success": bool, "data": any, "error": str|null}`
- 每个函数不超过50行，复杂逻辑拆分子函数

### Prompt规范
- 所有LLM Prompt存放在 `backend/agents/prompts/` 目录下（.txt文件）
- Prompt使用 `{variable}` 占位符，便于调试
- 每个Agent的system prompt和user prompt分开存储

### 测试规范
- 每个Step完成后，在对应目录下创建 `test_stepX_X.py` 验证脚本
- Phase完成后，运行所有该Phase的测试

### Git规范
- 每个Step完成后提交一次，commit message格式：`feat(phase1/step1.1): 项目初始化完成`
- 每个Phase完成后打tag：`v0.1.0-phase1`

---

## 八、⚠️ 开发注意事项

1. **不要一次性实现所有功能**，严格按Step顺序开发
2. **每个Step开始前**，先读 `PROGRESS.md` 确认当前状态
3. **Embedding模型**：首选 `BAAI/bge-m3`（中英文）；本地CPU运行较慢，开发阶段可用小模型 `all-MiniLM-L6-v2` 替代
4. **不要在Phase 1-2引入LangGraph**，先确保基础功能稳定
5. **PLACEHOLDER机制很关键**：不能让Agent编造实验数据，必须留白
6. **API Key安全**：仅做简单混淆即可，本地应用不需要高强度加密，但绝不明文存储
7. **内存管理**：Embedding模型加载后保持在内存中，不要每次请求都重载
8. **ChromaDB注意**：同一个collection name不能重复创建，启动时检查是否已存在

---

*文档版本：v1.0 | 创建日期：2024年 | 适用于：Claude Code*
