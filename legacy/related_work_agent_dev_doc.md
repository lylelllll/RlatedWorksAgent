# Related Work Agent — 开发文档

> **用途**：基于本地学术论文 PDF，为目标期刊自动生成 Related Work 章节（LaTeX 输出），支持多轮迭代优化。
> **直接将本文档交给 Claude Code 执行开发。**

---

## 1. 项目结构

```
related_work_agent/
├── README.md
├── pyproject.toml
├── config.yaml                        # 用户主配置文件（LLM、路径、参数）
├── .env                               # API Keys（git ignore）
│
├── data/
│   ├── background_papers/             # 【输入】背景/传统方案论文（Related Work 前几段）
│   ├── comparison_papers/             # 【输入】高度相似论文（横向对比段落）
│   ├── venue_style_papers/            # 【输入】目标期刊同类论文（风格参考）
│   └── my_paper/                      # 【输入】用户当前论文草稿（PDF 或 .tex）
│
├── vectordb/
│   ├── chroma_db/                     # ChromaDB 持久化目录
│   ├── colbert_index/                 # RAGatouille ColBERT 索引目录
│   └── index_manifest.json           # 已索引论文清单（增量更新用）
│
├── src/
│   ├── __init__.py
│   ├── pipeline.py                    # 主流程编排（CLI 入口）
│   ├── config.py                      # 配置加载与验证
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py              # PDF 全文解析与章节结构化
│   │   ├── chunker.py                 # 章节感知分块
│   │   └── my_paper_parser.py         # 解析用户自己的论文草稿
│   │
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── embedder.py                # Dense embedding（SPECTER2）
│   │   ├── colbert_indexer.py         # ColBERT 索引构建（RAGatouille）
│   │   └── vector_store.py            # ChromaDB 封装
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── retriever.py               # 两阶段检索（Dense + ColBERT rerank）
│   │   └── reranker.py                # Cross-Encoder 第三轮精排
│   │
│   ├── style_analyzer/
│   │   ├── __init__.py
│   │   └── venue_analyzer.py          # 目标期刊 Related Work 风格分析
│   │
│   ├── generation/
│   │   ├── __init__.py
│   │   ├── llm_client.py              # 统一 LLM 客户端（多后端适配）
│   │   ├── prompt_builder.py          # Prompt 构建
│   │   ├── writer.py                  # Related Work 生成与迭代控制
│   │   └── scorer.py                  # 草稿质量评分
│   │
│   └── utils/
│       ├── __init__.py
│       ├── parallel.py                # asyncio 并行工具
│       ├── latex_utils.py             # LaTeX 格式处理工具
│       └── logging_utils.py
│
├── outputs/
│   └── {timestamp}/
│       ├── iteration_1/
│       │   ├── draft.tex              # LaTeX 草稿
│       │   ├── draft_readable.md      # 可读版本（Markdown）
│       │   └── score.json            # 评分详情
│       ├── iteration_2/
│       ├── iteration_3/
│       ├── final_best.tex             # 最终最优草稿（直接使用）
│       └── references_draft.bib       # 自动生成的 .bib 条目草稿
│
└── tests/
    ├── test_pdf_parser.py
    ├── test_chunker.py
    ├── test_retriever.py
    └── test_generation.py
```

---

## 2. 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| PDF 解析 | `pymupdf` (fitz) | 速度快，支持双栏检测、字体大小识别标题层级 |
| 文本分块 | `langchain` + 自定义 | 章节感知分块，保留结构元数据 |
| Dense Embedding | `sentence-transformers` (`SPECTER2`) | 学术论文专用，优于通用 embedding |
| 向量数据库 | `ChromaDB` | 本地持久化，支持 metadata 过滤 |
| ColBERT | `RAGatouille` | 封装 ColBERT v2，token-level 精细匹配 |
| Cross-Encoder 精排 | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 第三轮重排序 |
| LLM 接入 | 见第 4 节（多后端统一接口） | 通过 `config.yaml` 切换，无需改代码 |
| 流程编排 | `langchain` + `asyncio` | 并行处理与流程控制 |
| 配置管理 | `pydantic-settings` + `PyYAML` | 类型安全，支持 YAML + .env |
| LaTeX 输出 | 自定义 `latex_utils.py` | 生成合法 LaTeX，处理特殊字符转义 |

---

## 3. 配置系统设计

### 3.1 主配置文件 `config.yaml`

这是用户唯一需要编辑的文件，所有可调参数集中于此：

```yaml
# ============================================================
# LLM 配置（切换模型只需修改此处，代码无需改动）
# ============================================================
llm:
  provider: "anthropic"          # 可选: anthropic | openai | azure_openai | ollama | deepseek
  model: "claude-opus-4-5"       # 对应 provider 的模型名称
  max_tokens: 4096
  temperature: 0.3
  # Azure OpenAI 额外配置（provider=azure_openai 时生效）
  azure_endpoint: ""
  azure_api_version: "2024-02-01"
  azure_deployment: ""
  # Ollama 额外配置（provider=ollama 时生效，无需 API key）
  ollama_base_url: "http://localhost:11434"

# ============================================================
# 评分 LLM（可与生成 LLM 不同，建议用更快/便宜的模型）
# ============================================================
scorer_llm:
  provider: "anthropic"
  model: "claude-haiku-4-5"      # 轻量模型，节省成本
  max_tokens: 1024
  temperature: 0.0

# ============================================================
# 数据路径（相对项目根目录）
# ============================================================
data:
  background_papers_dir: "data/background_papers"
  comparison_papers_dir: "data/comparison_papers"
  venue_style_papers_dir: "data/venue_style_papers"
  my_paper_dir: "data/my_paper"

# ============================================================
# Embedding & 检索模型
# ============================================================
retrieval:
  embedding_model: "allenai/specter2_base"
  colbert_model: "colbert-ir/colbertv2.0"
  reranker_model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  dense_top_k: 100               # Dense 检索召回数量
  colbert_top_k: 30              # ColBERT 重排后保留数量
  cross_encoder_top_k: 15        # Cross-Encoder 精排后最终数量

# ============================================================
# 分块参数
# ============================================================
chunking:
  default_chunk_size: 400        # tokens
  default_overlap: 50
  method_chunk_size: 500
  method_overlap: 80

# ============================================================
# 生成参数
# ============================================================
generation:
  max_iterations: 3              # 最大迭代轮次
  target_venue: "IEEE TMC"       # 目标期刊名（写入 Prompt）
  language: "english"
  latex_bib_style: "IEEEtran"    # 参考文献样式: IEEEtran | ACM | plain

# ============================================================
# 并行参数
# ============================================================
parallel:
  max_pdf_workers: 8
  embedding_batch_size: 64

# ============================================================
# 输出
# ============================================================
output:
  dir: "outputs"
  save_all_iterations: true
```

### 3.2 `.env` 文件（API Keys）

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AZURE_OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
# Ollama 本地运行无需 key
```

### 3.3 LLM 客户端统一接口（`src/generation/llm_client.py`）

实现一个 `LLMClient` 类，屏蔽不同 provider 的 SDK 差异。**切换 LLM 只改 `config.yaml`，此文件不动。**

```python
class LLMClient:
    """
    统一 LLM 调用接口。
    支持 provider：
      anthropic    → anthropic SDK
      openai       → openai SDK
      azure_openai → openai SDK（Azure 端点）
      deepseek     → openai SDK（兼容 OpenAI API，base_url 指向 DeepSeek）
      ollama       → langchain_community Ollama（本地，无需 key）
    """

    def __init__(self, llm_config: LLMConfig): ...

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """统一调用，返回纯文本"""

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """要求 JSON 格式输出（评分模块专用）"""
```

所有调用加指数退避 retry 装饰器（最多 3 次），并设置 timeout（生成 120s，评分 60s）。

---

## 4. 模块详细设计

### 4.1 PDF 解析（`src/ingestion/pdf_parser.py`）

**目标**：全文结构化解析，识别章节，不只取摘要。

**核心数据结构**：

```python
@dataclass
class ParsedSection:
    paper_id: str           # 文件名（不含扩展名）
    paper_type: str         # "background" | "comparison" | "venue_style"
    title: str              # 论文标题（首页提取）
    authors: str
    year: int
    venue: str
    section_name: str       # 规范化章节名（见下表）
    section_order: int      # 章节在论文中的顺序
    text: str
    page_range: tuple[int, int]
```

**解析策略**：
1. `pymupdf` 按页提取文本块，保留字体大小信息
2. 字体明显大于正文 → 视为章节标题
3. 双栏 PDF 列排序修正（先左列后右列）
4. 规范化章节名（如 "2. RELATED WORK" → "RelatedWork"）
5. 提取参考文献列表，构建 `paper_id → ref_titles` 映射

**章节权重**（检索 boost 用）：

| 章节 | 权重 |
|------|------|
| Abstract | 1.0 |
| Introduction（前3段）| 0.95 |
| RelatedWork | 0.95 |
| Method / System | 0.85 |
| Conclusion | 0.80 |
| Experiment | 0.70 |
| 其他 | 0.50 |

---

### 4.2 用户论文解析（`src/ingestion/my_paper_parser.py`）

解析 `data/my_paper/` 中的用户草稿，支持 `.pdf`、`.tex`、`.txt`、`.md`。

```python
@dataclass
class MyPaperContext:
    title: str
    abstract: str
    introduction: str
    contributions: list[str]   # 从 Introduction 中识别 contribution 列表
    keywords: list[str]        # 构建检索 Query 用
    full_text: str
```

对 `.tex` 文件，直接提取 `\begin{abstract}...\end{abstract}` 和 `\section{Introduction}` 块，无需 PDF 转换。

---

### 4.3 智能分块（`src/ingestion/chunker.py`）

按章节类型使用不同分块策略：

| 章节 | 策略 | chunk_size | overlap |
|------|------|-----------|---------|
| Abstract | 整体 1 个 chunk | — | — |
| Introduction | 前3段各独立；其余 400 tokens | 400 | 50 |
| RelatedWork | 按段落独立 | 300 | 30 |
| Method/System | 按子章节（H2 级） | 500 | 80 |
| Experiment | 按子章节，保留 Table/Figure caption | 400 | 50 |
| Conclusion | 整体或按段落 | 300 | 30 |

**Chunk Metadata**（存入向量库）：

```python
{
    "chunk_id": "{paper_id}_{section}_{idx}",
    "paper_id": str,
    "paper_type": str,         # background | comparison | venue_style
    "title": str,
    "authors": str,
    "year": int,
    "venue": str,
    "section": str,
    "section_order": int,
    "chunk_index": int,
    "importance_score": float,  # 章节权重
    "text": str
}
```

---

### 4.4 索引构建（`src/indexing/`）

#### Dense Embedding（`embedder.py` + `vector_store.py`）

- 模型：`allenai/specter2_base`（学术论文专用）
- 存储：ChromaDB，按 `paper_type` 分 collection，支持 metadata 过滤
- 批量 embedding，`embedding_batch_size` 可配置，自动检测 CUDA

#### ColBERT 索引（`colbert_indexer.py`）

```python
from ragatouille import RAGPretrainedModel

class ColBERTIndexer:
    def build_index(self, chunks: list[Chunk], index_name: str):
        """首次构建，持久化到 vectordb/colbert_index/"""

    def search(self, query: str, k: int = 30) -> list[ColBERTResult]:
        """token-level late interaction 检索"""

    def index_exists(self, index_name: str) -> bool:
        """避免重复构建"""

    def add_documents(self, new_chunks: list[Chunk]):
        """增量添加（新增论文时使用）"""
```

---

### 4.5 三阶段检索（`src/retrieval/retriever.py`）

```
多维度 Query（来自 MyPaperContext）
         │
         ▼  4 个 query 并行检索，RRF 合并
┌─────────────────────────┐
│  Stage 1: Dense         │  SPECTER2 + ChromaDB → top-100
│  按 paper_type 分组检索 │  background 和 comparison 分别检索
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Stage 2: ColBERT       │  RAGatouille ColBERT v2 → top-30
│  token-level rerank     │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Stage 3: Cross-Encoder │  ms-marco → top-15（最终）
│  精排                   │
└──────────┬──────────────┘
           │
           ▼
  background_chunks（top-15）+ comparison_chunks（top-15）
```

**多维度 Query**（从 `MyPaperContext` 构建，并行检索后用 RRF 合并排名）：

```python
queries = [
    my_paper.abstract,
    " ".join(my_paper.contributions),
    f"{my_paper.title} challenges limitations existing methods",
    " ".join(my_paper.keywords),
]
```

---

### 4.6 目标期刊风格分析（`src/style_analyzer/venue_analyzer.py`）

分析 `venue_style_papers/` 中论文的 Related Work 章节，提取写作规律：

```python
@dataclass
class VenueStyle:
    avg_word_count: int
    avg_paragraph_count: int
    has_subsections: bool
    avg_citations_per_paragraph: float
    avg_sentences_per_method: float
    paragraph_structure: str            # e.g., "problem→method→limitation"
    transition_phrases: list[str]       # few-shot 过渡词示例
    sample_paragraphs: list[str]        # 1-2 段风格示例（few-shot 用）
    latex_structure: str                # 有无 \subsection 等结构模板
```

---

### 4.7 Prompt 设计（`src/generation/prompt_builder.py`）

#### System Prompt

```
你是一位顶级计算机科学学术写作专家，擅长撰写符合 {target_venue} 风格的 Related Work 章节。
输出必须是合法的 LaTeX 代码，可直接嵌入 .tex 文件。
```

#### User Prompt 结构

```
## 我的论文

标题: {title}
摘要: {abstract}
核心贡献:
{contributions}

---

## 目标期刊写作风格参考（{target_venue}）

- 建议约 {avg_word_count} 词，{avg_paragraph_count} 段
- 是否使用子标题: {has_subsections}
- 每段平均引用: {avg_citations_per_paragraph} 篇
- 描述每个方案的句数: 约 {avg_sentences_per_method} 句
- 段落结构模式: {paragraph_structure}

风格示例段落（参考语气和句式，不要复制内容）:
{sample_paragraphs}

---

## 背景与传统方案参考文献（用于 Related Work 前几段）

{formatted_background_chunks}
格式：[paper_id] 标题 | 作者, 年份 | 关键内容摘要

---

## 高度相似论文（用于横向对比段落）

{formatted_comparison_chunks}
格式：[paper_id] 标题 | 作者, 年份 | 关键内容摘要

---

## 写作要求

1. 输出完整 LaTeX Related Work 章节，从 \section{Related Work} 开始
2. 结构：先几段介绍背景/传统方案，最后 1-2 段与高度相似论文横向对比并突出本文创新
3. 引用格式：\cite{paper_id}（paper_id 即上方 [] 中的 ID）
4. 每段末尾指出局限性或与本文的区别
5. 不得直接复制参考文献原文，需用学术语言归纳
6. LaTeX 语法必须正确，特殊字符（% & _ # $ ^ { }）需正确转义

{迭代轮次 >= 2 时追加:}
---
## 上一轮草稿评分与改进建议

总分: {prev_score.total}/10
{prev_score.dimension_details}

改进建议:
{prev_score.improvement_suggestions}

请在上轮基础上针对上述问题改进，输出完整改进版 LaTeX 代码。
```

---

### 4.8 质量评分（`src/generation/scorer.py`）

调用 `scorer_llm` 对草稿打分，返回结构化 JSON：

```python
@dataclass
class DraftScore:
    total: float                          # 加权总分（0-10）
    coverage: float                       # 覆盖度
    accuracy: float                       # 准确性
    comparison_quality: float             # 横向对比质量
    style_compliance: float               # 风格符合度
    coherence: float                      # 连贯性
    novelty_highlight: float              # 创新点突出度
    latex_validity: float                 # LaTeX 语法合法性（程序验证）
    improvement_suggestions: list[str]    # 具体改进建议
```

**加权规则**：

```python
weights = {
    "coverage": 0.20,
    "accuracy": 0.20,
    "comparison_quality": 0.20,
    "style_compliance": 0.15,
    "coherence": 0.10,
    "novelty_highlight": 0.10,
    "latex_validity": 0.05,
}
```

**程序级 LaTeX 验证**（不依赖 LLM）：
- `\begin{}`/`\end{}` 配对检查
- `\cite{}` 中的 ID 是否在已知 `paper_id` 集合中
- 未转义特殊字符检测（`%`、`&`、`_`、`#`）

---

### 4.9 迭代生成控制（`src/generation/writer.py`）

```python
async def iterative_generate(context: GenerationContext, config: Config) -> FinalOutput:
    best_draft, best_score = None, None
    all_iterations = []

    for i in range(1, config.generation.max_iterations + 1):
        logger.info(f"=== Iteration {i}/{config.generation.max_iterations} ===")

        prompt = build_prompt(context, iteration=i,
                              previous_draft=best_draft, prev_score=best_score)
        raw_output = await llm_client.generate(SYSTEM_PROMPT, prompt)

        # 从 LLM 输出中提取 LaTeX 代码（去除多余说明文字）
        latex_code = extract_latex(raw_output)

        # 若 LaTeX 有语法错误，自动触发一次修复请求
        is_valid, errors = validate_latex_syntax(latex_code, context.known_paper_ids)
        if not is_valid:
            latex_code = await llm_client.generate(FIX_SYSTEM_PROMPT,
                                                    build_fix_prompt(latex_code, errors))
            latex_code = extract_latex(latex_code)

        score = await scorer.score(latex_code, context)
        save_iteration(latex_code, score, iteration=i, config=config)
        all_iterations.append(IterationResult(draft=latex_code, score=score, iteration=i))

        logger.info(f"  Score: {score.total:.2f}/10  |  "
                    f"Coverage={score.coverage:.1f} Comparison={score.comparison_quality:.1f}")

        if best_score is None or score.total > best_score.total:
            best_draft, best_score = latex_code, score

    best = max(all_iterations, key=lambda x: x.score.total)
    logger.success(f"Best: iteration #{best.iteration} (score={best.score.total:.2f})")
    return FinalOutput(latex=best.draft, score=best.score)
```

---

### 4.10 LaTeX 工具（`src/utils/latex_utils.py`）

```python
def extract_latex(llm_output: str) -> str:
    """从 LLM 输出提取 LaTeX 代码，去除 ```latex ``` 包裹等冗余内容"""

def escape_special_chars(text: str) -> str:
    """转义 LaTeX 特殊字符：% & _ # $ ^ { } ~ \\"""

def validate_latex_syntax(code: str, known_paper_ids: set[str]) -> tuple[bool, list[str]]:
    """程序级语法验证，返回 (is_valid, error_messages)"""

def build_bibliography_entries(chunks: list[Chunk]) -> str:
    """根据 chunks 的 metadata 生成 .bib 条目草稿（需人工核验）"""
```

---

## 5. 主流程（`src/pipeline.py`）

```python
async def run_pipeline(config: Config) -> None:

    # Phase 1: 并行解析所有 PDF ─────────────────────────────
    logger.info("[Phase 1] Parsing PDFs in parallel...")
    bg_sections, cmp_sections, venue_sections, my_paper = await asyncio.gather(
        parse_pdf_directory(config.data.background_papers_dir, "background"),
        parse_pdf_directory(config.data.comparison_papers_dir, "comparison"),
        parse_pdf_directory(config.data.venue_style_papers_dir, "venue_style"),
        parse_my_paper(config.data.my_paper_dir),
    )

    # Phase 2: 分块 ────────────────────────────────────────
    logger.info("[Phase 2] Chunking...")
    all_chunks = chunk_sections(bg_sections + cmp_sections, config)

    # Phase 3: 建立/加载索引 ───────────────────────────────
    logger.info("[Phase 3] Building indexes (skip if exists)...")
    if not indexes_exist(config):
        await asyncio.gather(
            build_chroma_index(all_chunks, config),
            build_colbert_index(all_chunks, config),
        )
    else:
        logger.info("  Indexes found, skipping rebuild.")

    # Phase 4: 并行：检索 + 风格分析 ─────────────────────
    logger.info("[Phase 4] Retrieval & Style Analysis in parallel...")
    retrieved_chunks, venue_style = await asyncio.gather(
        retrieve_chunks(my_paper, config),
        analyze_venue_style(venue_sections, config),
    )
    background_chunks = [c for c in retrieved_chunks if c.paper_type == "background"]
    comparison_chunks = [c for c in retrieved_chunks if c.paper_type == "comparison"]

    # Phase 5: 迭代生成 ────────────────────────────────────
    logger.info("[Phase 5] Iterative generation...")
    context = GenerationContext(
        my_paper=my_paper,
        background_chunks=background_chunks,
        comparison_chunks=comparison_chunks,
        venue_style=venue_style,
        known_paper_ids={c.paper_id for c in retrieved_chunks},
    )
    output = await iterative_generate(context, config)

    # 输出 ──────────────────────────────────────────────────
    save_final_output(output, config)
    logger.success(f"Done! → {config.output.dir}/final_best.tex  "
                   f"(score={output.score.total:.2f}/10)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Related Work Agent")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--skip-indexing", action="store_true")
    parser.add_argument("--iterations", type=int)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.skip_indexing:
        config._force_skip_indexing = True
    if args.iterations:
        config.generation.max_iterations = args.iterations

    asyncio.run(run_pipeline(config))
```

---

## 6. 并行处理总览

```
Phase 1 ── 全并行
  background/   ──┐
  comparison/   ──┼──► asyncio.gather + ThreadPoolExecutor(max_workers=8)
  venue_style/  ──┤
  my_paper/     ──┘

Phase 2 ── 串行（依赖 Phase 1）

Phase 3 ── 两路并行
  ChromaDB 索引构建  ──┐
                       ├──► asyncio.gather
  ColBERT 索引构建   ──┘

Phase 4 ── 两路并行
  多 query 检索（4路 asyncio.gather + RRF 合并）  ──┐
                                                     ├──► asyncio.gather
  venue 风格分析                                    ──┘

Phase 5 ── 串行（评分驱动迭代）
  Draft 1 → Score 1 → Draft 2 → Score 2 → Draft 3 → Score 3 → 取最优
```

---

## 7. 依赖安装（`pyproject.toml`）

```toml
[project]
name = "related-work-agent"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "pymupdf>=1.23.0",
    "langchain>=0.2.0",
    "langchain-community>=0.2.0",
    "langchain-anthropic>=0.1.0",
    "langchain-openai>=0.1.0",
    "sentence-transformers>=3.0.0",
    "transformers>=4.40.0",
    "torch>=2.0.0",
    "ragatouille>=0.0.8",
    "chromadb>=0.5.0",
    "anthropic>=0.28.0",
    "openai>=1.30.0",
    "pydantic-settings>=2.0.0",
    "pyyaml>=6.0",
    "numpy>=1.26.0",
    "tqdm>=4.66.0",
    "loguru>=0.7.0",
    "rich>=13.0.0",
    "aiofiles>=23.0.0",
]

[project.scripts]
rwa = "src.pipeline:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends.legacy:build"
```

---

## 8. 运行指南

### 初次设置

```bash
# 1. 安装
pip install -e .

# 2. 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml → 设置 llm.provider / llm.model / target_venue

# 3. API Key
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> .env

# 4. 放入论文
#   data/background_papers/   ← 背景/传统方案论文 PDF
#   data/comparison_papers/   ← 高度相似论文 PDF
#   data/venue_style_papers/  ← 目标期刊同类论文 PDF
#   data/my_paper/            ← 自己论文草稿（.pdf / .tex / .txt）

# 5. 运行
rwa
```

### 常用命令

```bash
rwa                                  # 正常运行
rwa --config my_config.yaml          # 指定配置
rwa --skip-indexing                  # 跳过索引重建（已有索引时）
rwa --iterations 1                   # 快速测试，只跑 1 轮

rm -rf vectordb/ && rwa              # 新增论文后重建索引
```

---

## 9. 输出文件说明

```
outputs/20240115_143022/
├── iteration_1/
│   ├── draft.tex              # LaTeX 源码
│   ├── draft_readable.md      # Markdown 可读版（快速审阅用）
│   └── score.json             # 详细评分与改进建议
├── iteration_2/
├── iteration_3/
├── final_best.tex             # ★ 最终最优草稿（直接 \input 到主 .tex）
└── references_draft.bib       # 自动生成的 .bib 条目草稿（需人工核验补全）
```

`final_best.tex` 输出示例：

```latex
\section{Related Work}

\subsection{Traditional Approaches}
Existing solutions for ... can be broadly categorized into ...
Early work by \cite{smith2019fast} proposed a heuristic method that ...
While effective in small-scale scenarios, these approaches suffer from ...

\subsection{Learning-based Methods}
Recent advances in deep learning have inspired several works \cite{jones2021deep, wang2022graph}.
Specifically, \cite{jones2021deep} leverages attention mechanisms to ...
However, these methods assume ..., which limits their applicability to ...

\subsection{Comparison with Most Related Work}
The most closely related to ours is \cite{chen2023efficient}, which addresses ...
Unlike \cite{chen2023efficient}, our approach explicitly models ...
thereby achieving ... without requiring ...
```

---

## 10. 实现注意事项

**ColBERT 优势**：Late interaction 让 query 和 document 每个 token 单独 embed 后做 MaxSim 聚合，对方法名、指标名、数据集名等细粒度学术词汇的匹配远优于 dense 单向量检索。

**SPECTER2 优势**：在 citation graph 上预训练，语义空间与学术文本高度对齐，召回相关论文效果显著优于通用 embedding（如 `text-embedding-ada-002`）。

**RRF 合并**：多 query 检索结果合并时使用 Reciprocal Rank Fusion，优于简单 score 相加，避免高分 query 主导结果。

**索引增量更新**：`vectordb/index_manifest.json` 记录已索引文件列表和 hash，新增论文时只对新文件做增量 embedding，无需全量重建。

**GPU 自动检测**：embedding 和 ColBERT 均自动检测 `torch.cuda.is_available()`，50 篇论文建索引：GPU 约 5-10 分钟，CPU 约 20-40 分钟。

---

## 11. 后续可扩展方向

- [ ] 增量更新：自动检测新增 PDF，只对新文件建索引
- [ ] 引用格式自动对齐：根据期刊自动输出 IEEE / ACM / Author-Year 格式
- [ ] 人工反馈循环：用户批注草稿后作为 context 重新生成
- [ ] Web UI：Gradio/Streamlit 可视化检索结果与逐轮迭代对比
- [ ] 多语言：支持输出中文 Related Work（中文期刊投稿场景）
