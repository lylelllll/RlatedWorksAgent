# Review Advisor — 开发文档

> **新功能**：基于带批注 PDF + 已有本地知识库，自动解析每条审稿意见，检索支撑证据，生成高质量的逐条修改建议报告。
>
> **集成方式**：作为独立子模块 `src/review_advisor/` 接入现有 RWA 系统，复用已有 RAG 索引（ChromaDB + ColBERT），新增 CLI 入口 `rwa-review`。
>
> **将本文档交给 Claude Code 执行开发。**

---

## 1. 功能定位与核心思路

### 1.1 场景描述

用户从期刊/会议收到审稿意见后，审稿人通常会在论文 PDF 上直接做批注（高亮 + 便签评语），或提交一份单独的审稿意见文本。本功能接受这两种输入：

- **带批注的 PDF**：高亮段落 + Sticky Note 评语，由审稿人在 Adobe Acrobat / Preview 等工具中直接标记
- **纯文本审稿意见**：审稿人提交的 `.txt` / `.md` 格式意见稿（逐条列出，如 "R1C1: ..."）

系统将：
1. 提取每一条批注及其在论文中的上下文
2. 识别批注的意图类型（缺引用 / 逻辑问题 / 数据支撑 / 写作问题 / 结构调整等）
3. 从**已有本地知识库**（background + comparison 论文）中检索最相关的支撑证据
4. 结合上下文 + 检索证据，生成具体可操作的修改建议
5. 输出结构化报告（Markdown + 可选 LaTeX diff）

### 1.2 与现有模块的关系

```
现有 RWA 系统
├── vectordb/（ChromaDB + ColBERT 索引）  ← 直接复用，无需重建
├── src/retrieval/retriever.py             ← 直接复用，复用三阶段检索
├── src/generation/llm_client.py           ← 直接复用，统一 LLM 接口
└── config.yaml                            ← 复用配置，新增 review_advisor 节

新增模块
└── src/review_advisor/                    ← 本文档描述的全部新代码
```

**关键原则**：不修改任何现有文件，只新增代码。通过依赖注入复用已有的 `Retriever`、`LLMClient` 实例。

---

## 2. 新增项目结构

在现有 RWA 项目基础上，新增以下文件（其余文件不变）：

```
related_work_agent/
│
├── config.yaml                            # 新增 review_advisor 配置节（见第 3 节）
│
├── src/
│   └── review_advisor/                    # ★ 全部新增
│       ├── __init__.py
│       ├── pipeline.py                    # Review Advisor 主流程（CLI 入口）
│       │
│       ├── extraction/
│       │   ├── __init__.py
│       │   ├── annotation_extractor.py    # 从带批注 PDF 提取批注
│       │   ├── text_review_parser.py      # 解析纯文本审稿意见
│       │   └── context_assembler.py       # 为每条批注拼装论文上下文
│       │
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── intent_classifier.py       # 批注意图分类（LLM-based）
│       │   └── query_builder.py           # 从批注生成检索 Query
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── suggestion_generator.py    # 逐条修改建议生成
│       │   └── report_builder.py          # 汇总报告构建
│       │
│       └── utils/
│           ├── __init__.py
│           └── diff_utils.py              # 生成 before/after 文本对比
│
├── data/
│   └── review_input/                      # ★ 新增：用户放审稿输入的目录
│       ├── annotated_paper.pdf            # 带批注的论文 PDF（可多个）
│       └── review_comments.txt            # 或纯文本审稿意见（可选）
│
├── outputs/
│   └── review_{timestamp}/               # ★ 新增：本功能的输出目录
│       ├── review_report.md              # 主报告（Markdown，逐条建议）
│       ├── review_report_cn.md           # 中文版报告（如配置语言为中文）
│       ├── annotations_parsed.json       # 所有提取批注的结构化 JSON
│       └── per_comment/                  # 每条批注的详细输出
│           ├── comment_001.md
│           ├── comment_002.md
│           └── ...
│
└── pyproject.toml                        # 新增 rwa-review 入口点
```

---

## 3. 配置扩展

在现有 `config.yaml` 末尾新增 `review_advisor` 节，**不修改任何已有配置项**：

```yaml
# ============================================================
# Review Advisor 配置（新增）
# ============================================================
review_advisor:
  # 输入
  input_dir: "data/review_input"

  # 批注提取
  annotation:
    # 支持的 PDF 批注类型（pymupdf annotation type names）
    supported_types:
      - "Text"           # Sticky note（最常见，审稿人的评语气泡）
      - "Highlight"      # 高亮（通常配合 Text 使用）
      - "Underline"      # 下划线
      - "StrikeOut"      # 删除线（审稿人建议删除的内容）
      - "FreeText"       # 内嵌文本批注
      - "Squiggly"       # 波浪线（通常标记有问题的表达）
    # 高亮批注若无配套 Text 评语，是否仍提取（仅凭上下文推断意图）
    extract_highlight_without_comment: true
    # 上下文窗口：提取批注时，前后各取多少个句子作为上下文
    context_sentences_before: 3
    context_sentences_after: 3

  # 意图分类
  intent_classification:
    # 并行分类的批注数量（每批）
    batch_size: 10

  # 检索（复用现有 retrieval 配置，此处可覆盖）
  retrieval:
    dense_top_k: 50         # 针对每条批注的检索数量（比生成任务少，精度优先）
    colbert_top_k: 15
    cross_encoder_top_k: 5  # 最终只取 top-5 支撑证据，避免 prompt 过长

  # 生成
  generation:
    # 是否生成 before/after 对比版本的修改建议
    generate_diff: true
    # 是否同时生成中文版报告
    generate_chinese_report: false
    # 每条建议的最大 token 数
    max_tokens_per_suggestion: 800

  # 输出
  output:
    dir: "outputs"
    # 是否为每条批注单独生成 per_comment/ 文件
    save_per_comment: true
```

---

## 4. 核心数据结构

所有数据结构定义在 `src/review_advisor/__init__.py` 中，便于跨模块引用。

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── 批注意图类型 ─────────────────────────────────────────────
class AnnotationIntent(Enum):
    """
    批注的核心意图分类。
    LLM 在分类时将每条批注归入且仅归入一个主类型，
    可附加 sub_intents 列表表示复合意图。
    """
    MISSING_CITATION     = "missing_citation"      # 缺少引用支撑
    FACTUAL_ERROR        = "factual_error"          # 事实/数据错误
    LOGIC_GAP            = "logic_gap"              # 逻辑跳跃/论证不充分
    COMPARISON_NEEDED    = "comparison_needed"      # 需要与某方法横向对比
    WRITING_CLARITY      = "writing_clarity"        # 表达不清晰/歧义
    GRAMMAR_STYLE        = "grammar_style"          # 语法/格式/风格问题
    STRUCTURE_SUGGESTION = "structure_suggestion"   # 建议调整段落/章节结构
    SCOPE_EXPANSION      = "scope_expansion"        # 建议扩展讨论范围
    DELETE_CONTENT       = "delete_content"         # 建议删除冗余内容
    UNDEFINED            = "undefined"              # 无法分类（兜底）


# ── 单条原始批注 ─────────────────────────────────────────────
@dataclass
class RawAnnotation:
    """从 PDF 或文本文件中提取的原始批注，不含任何分析结果。"""
    annotation_id: str          # 全局唯一 ID，如 "annot_007"
    source_file: str            # 来源文件名
    annot_type: str             # PDF 原始类型："Text"/"Highlight"/...；文本审稿为 "TextReview"
    
    # 位置信息（PDF 批注专用）
    page_number: int            # 页码（1-based）
    rect: Optional[tuple]       # 批注矩形坐标 (x0, y0, x1, y1)
    
    # 内容
    highlighted_text: str       # 被高亮/标记的原文（无则为空串）
    comment_text: str           # 审稿人的评语文字（Sticky Note 内容）
    author: str                 # 批注作者（如 "Reviewer 1"，PDF 元数据中提取）
    
    # 来源标识
    reviewer_label: str         # 人工推断的审稿人标签，如 "R1", "R2", "R3"
    section_name: str           # 批注所在论文章节（如 "Introduction"）
    section_order: int          # 章节顺序


# ── 批注上下文 ───────────────────────────────────────────────
@dataclass
class AnnotationContext:
    """批注在论文中的完整上下文，用于 LLM 理解问题所在。"""
    annotation_id: str
    preceding_text: str         # 批注前 N 句
    annotated_text: str         # 被批注的核心文本
    following_text: str         # 批注后 N 句
    full_paragraph: str         # 批注所在完整段落
    section_name: str
    page_number: int


# ── 分析后的批注（含意图 + 检索结果）────────────────────────
@dataclass
class AnalyzedAnnotation:
    """经过意图分类和知识库检索后的完整批注对象。"""
    raw: RawAnnotation
    context: AnnotationContext
    
    # 意图分析
    intent: AnnotationIntent
    sub_intents: list[AnnotationIntent] = field(default_factory=list)
    intent_reasoning: str = ""          # LLM 的意图判断理由（调试用）
    reformulated_question: str = ""     # LLM 将批注改写成的明确问题（用于检索）
    
    # 知识库检索结果
    retrieved_evidence: list[dict] = field(default_factory=list)
    # 每条 evidence: {"chunk_id", "paper_id", "title", "authors", "year",
    #                 "section", "text", "relevance_score"}


# ── 单条修改建议 ─────────────────────────────────────────────
@dataclass
class RevisionSuggestion:
    """针对单条批注生成的完整修改建议。"""
    annotation_id: str
    reviewer_label: str
    intent: AnnotationIntent
    
    # 建议内容
    problem_summary: str        # 用 1-2 句话概括审稿人指出的问题
    suggested_revision: str     # 具体修改建议（可能包含建议的新文本）
    original_text: str          # 被标记的原文
    revised_text: str           # 建议的修改后文本（若适用）
    supporting_evidence: list[str]  # 引用的知识库来源（"[Smith et al., 2023]"）
    response_to_reviewer: str   # 给审稿人的回复模板（rebuttal 用）
    
    # 置信度
    confidence: float           # 0.0-1.0，LLM 对建议质量的自评


# ── 最终报告 ─────────────────────────────────────────────────
@dataclass
class ReviewReport:
    """完整审稿意见处理报告。"""
    source_files: list[str]
    total_annotations: int
    processed_annotations: int
    suggestions: list[RevisionSuggestion]
    intent_summary: dict[str, int]   # {"missing_citation": 5, "logic_gap": 3, ...}
    timestamp: str
```

---

## 5. 模块详细设计

### 5.1 批注提取（`src/review_advisor/extraction/`）

#### 5.1.1 PDF 批注提取（`annotation_extractor.py`）

**核心依赖**：`pymupdf`（已在现有系统中安装）

pymupdf 通过 `page.annots()` 遍历所有批注，每个 `fitz.Annot` 对象包含：

```python
annot.type        # (int, str) 类型元组，如 (1, "Text")
annot.info        # dict: {"title": author, "content": comment_text, ...}
annot.rect        # fitz.Rect: 批注位置
annot.colors      # 颜色（高亮颜色可区分审稿人）
```

**提取策略**：

```python
class AnnotationExtractor:
    
    def extract_from_pdf(self, pdf_path: Path) -> list[RawAnnotation]:
        """
        遍历 PDF 所有页，提取所有支持类型的批注。
        
        关键逻辑：
        1. 遍历 page.annots()，过滤 config 中 supported_types
        2. 对 Highlight/Underline/StrikeOut 类型：
           - 用 page.get_textbox(annot.rect) 提取被标记的原文
           - 查找同页是否有 Text 类型批注与此批注位置相邻（距离阈值 50pt）
           - 若有，将其 content 作为 comment_text；若无，comment_text 为空
        3. 对 Text/FreeText 类型：
           - comment_text = annot.info["content"]
           - 用 annot.rect 附近的文本作为 highlighted_text
        4. 识别 reviewer_label：
           - 优先从 annot.info["title"] 提取（如 "Reviewer 1"）
           - 若为空，按颜色分组推断（不同颜色视为不同审稿人）
           - 若只有一种颜色，统一标记为 "R1"
        5. 识别 section_name：
           - 扫描当前页已解析的章节结构（复用 pdf_parser.py 的输出）
           - 按页码和 y 坐标定位批注属于哪个章节
        """
    
    def _get_highlighted_text(self, page, annot) -> str:
        """提取 Highlight/Underline 类型批注覆盖的文本。"""
    
    def _find_associated_comment(self, page, annot, all_annots) -> str:
        """
        寻找与高亮批注关联的 Text 类型批注（Sticky Note）。
        审稿人通常高亮一段文字，再在旁边加便签评语，两者位置相邻。
        """
    
    def _infer_reviewer_label(self, annots: list) -> dict[str, str]:
        """
        按颜色或 author 字段推断审稿人标签。
        返回 {annot_id: "R1"} 的映射。
        高亮颜色映射示例：
          黄色 → R1，绿色 → R2，蓝色 → R3，粉色 → AC（Associate Editor）
        """
```

#### 5.1.2 纯文本审稿意见解析（`text_review_parser.py`）

支持常见格式（期刊/会议系统导出的审稿意见）：

```
# 格式 1：数字编号
R1C1: The authors claim X but do not provide...
R1C2: Missing comparison with [Smith 2023]...

# 格式 2：大段落
Reviewer 1:
Comment 1: ...
Comment 2: ...

# 格式 3：Markdown 列表
## Reviewer 2
- [Major] The experimental setup is unclear...
- [Minor] Typo on page 3...
```

```python
class TextReviewParser:
    
    def parse(self, file_path: Path) -> list[RawAnnotation]:
        """
        解析纯文本审稿意见文件，转换为统一的 RawAnnotation 格式。
        
        策略：
        1. 尝试正则匹配已知格式（R1C1、Reviewer N:、## Reviewer N 等）
        2. 若匹配失败，调用 LLM 进行结构化提取（兜底）
        3. 每条意见：
           - highlighted_text = ""（无原文标记）
           - comment_text = 意见正文
           - reviewer_label = 推断的审稿人编号
           - page_number = -1（文本审稿无页码）
        """
    
    def _extract_with_llm(self, raw_text: str) -> list[dict]:
        """当正则无法解析时，用 LLM 提取结构化条目，返回 JSON 列表。"""
```

#### 5.1.3 上下文拼装（`context_assembler.py`）

为每条批注提取论文原文上下文：

```python
class ContextAssembler:
    """
    需要访问用户论文的解析结果（来自 my_paper_parser.py）。
    通过 paper_sections（ParsedSection 列表）定位批注所在段落。
    """
    
    def assemble(self, annot: RawAnnotation, 
                 paper_sections: list[ParsedSection]) -> AnnotationContext:
        """
        定位批注上下文的策略：
        
        PDF 批注：
          - 按 page_number + section_name 找到对应 ParsedSection
          - 在 section.text 中全文搜索 highlighted_text（模糊匹配，Levenshtein 距离 < 5）
          - 找到匹配位置后，向前取 N 句、向后取 N 句
          - 提取整段（以段落分隔符 \n\n 为边界）
        
        文本审稿（无 highlighted_text）：
          - preceding_text / following_text 均为空
          - 仅保留 comment_text 本身作为上下文
          - 后续 LLM 分析时提示"审稿人未指定具体位置"
        """
    
    def _fuzzy_locate(self, needle: str, haystack: str) -> tuple[int, int]:
        """
        模糊定位 highlighted_text 在 section.text 中的位置。
        处理 PDF 提取时的换行、连字符、空格差异。
        使用 rapidfuzz 库的 partial_ratio 方法。
        """
```

---

### 5.2 意图分析（`src/review_advisor/analysis/`）

#### 5.2.1 意图分类（`intent_classifier.py`）

**使用 `scorer_llm`（轻量模型），批量并行处理。**

```python
class IntentClassifier:
    
    async def classify_batch(self, 
                              annots: list[RawAnnotation],
                              contexts: list[AnnotationContext]) -> list[AnnotationIntent]:
        """
        批量分类（config.review_advisor.intent_classification.batch_size 条/批），
        并行发送 LLM 请求。
        """
    
    async def classify_single(self, annot: RawAnnotation, 
                               context: AnnotationContext) -> tuple[AnnotationIntent, str, str]:
        """
        返回 (intent, intent_reasoning, reformulated_question)
        
        reformulated_question：LLM 将审稿人的批注改写成一个
        具体的学术问题，用于后续检索。
        例：
          批注原文："The comparison is insufficient."
          改写问题："What are the key performance differences between
                     [method in paper] and recent state-of-the-art
                     approaches in [task domain]?"
        """
```

**分类 Prompt**：

```
[System]
你是一位资深学术论文审稿专家。请分析以下审稿批注，完成两项任务：
1. 将批注意图归类为以下类型之一：
   - missing_citation：缺少引用支撑
   - factual_error：事实或数据错误
   - logic_gap：逻辑跳跃或论证不充分
   - comparison_needed：需要与某方法横向对比
   - writing_clarity：表达不清晰或歧义
   - grammar_style：语法/格式/风格问题
   - structure_suggestion：建议调整段落或章节结构
   - scope_expansion：建议扩展讨论范围
   - delete_content：建议删除冗余内容
   - undefined：无法明确分类

2. 将批注改写为一个具体的学术检索问题（用于文献检索，英文）。

[User]
论文章节：{section_name}
被标注的文本：
"""
{annotated_text}
"""
前文上下文：
"""
{preceding_text}
"""
审稿人评语：
"""
{comment_text}
"""

请输出 JSON 格式：
{
  "intent": "missing_citation",
  "sub_intents": [],
  "reasoning": "审稿人指出 X 缺少文献支撑，属于 missing_citation",
  "reformulated_question": "What methods have been proposed for X in the context of Y?"
}
```

#### 5.2.2 检索 Query 构建（`query_builder.py`）

```python
class QueryBuilder:
    
    def build_queries(self, analyzed: AnalyzedAnnotation) -> list[str]:
        """
        根据意图类型，构建 1-3 个互补的检索 Query。
        
        策略（按意图类型）：
        
        missing_citation / comparison_needed：
          - Query 1: analyzed.reformulated_question（改写的学术问题）
          - Query 2: annotated_text（被标记的原文，寻找直接相关论文）
          - Query 3: f"{section_name} {keywords}"（章节 + 关键词）
        
        factual_error：
          - Query 1: reformulated_question
          - Query 2: "experimental results {task} {dataset} {metric}"（数据支撑）
        
        logic_gap / scope_expansion：
          - Query 1: reformulated_question
          - Query 2: annotated_text
        
        writing_clarity / grammar_style / delete_content：
          - 不检索知识库（与文献内容无关）
          - 返回空列表，后续直接调用 LLM 给出写作建议
        
        structure_suggestion：
          - Query 1: 从 venue_style_papers 检索结构参考（用特殊 paper_type 过滤）
        """
```

---

### 5.3 修改建议生成（`src/review_advisor/generation/`）

#### 5.3.1 逐条建议生成（`suggestion_generator.py`）

**使用主生成 LLM（`llm` 配置，高质量模型）。**

```python
class SuggestionGenerator:
    
    async def generate_batch(self, 
                              analyzed_annots: list[AnalyzedAnnotation]) -> list[RevisionSuggestion]:
        """
        对所有批注并行生成修改建议。
        writing_clarity / grammar_style 类型无需检索证据，可更快处理。
        """
    
    async def generate_single(self, analyzed: AnalyzedAnnotation) -> RevisionSuggestion:
        """
        为单条批注生成完整的修改建议，包含：
        - problem_summary：1-2 句话概括问题
        - suggested_revision：具体修改方案（文字描述）
        - revised_text：建议的修改后原文（若适用）
        - supporting_evidence：引用的知识库来源
        - response_to_reviewer：给审稿人的回复模板
        """
```

**生成 Prompt**（按意图类型分支，以 `missing_citation` 为例）：

```
[System]
你是一位顶级学术论文修改顾问，专注于帮助作者高质量地回复审稿意见。
你的建议必须：具体可操作、有文献支撑、符合学术写作规范。

[User]
## 论文上下文

章节：{section_name}
原文（被审稿人标注的部分）：
"""
{original_text}
"""
前文：{preceding_text}
后文：{following_text}

## 审稿人意见

审稿人标签：{reviewer_label}
意图类型：{intent}（缺少引用支撑）
审稿人原话：
"""
{comment_text}
"""

## 从本地知识库检索到的相关文献（Top-5）

{formatted_evidence}
每条格式：
[证据 N] {title} ({authors}, {year}, {venue})
内容摘要：{chunk_text}

## 任务

请生成以下内容（JSON 格式输出）：

1. problem_summary（str）：用 1-2 句话概括审稿人指出的核心问题
2. suggested_revision（str）：具体修改方案，说明应如何修改这段文字
3. revised_text（str）：建议的修改后文本（若改动较小，直接给出；若改动复杂，给出框架）
4. supporting_evidence（list[str]）：本建议引用的知识库文献，格式 "[Author et al., Year]"
5. response_to_reviewer（str）：给审稿人的英文回复模板（rebuttal letter 用），
   需引用上述文献，说明已做哪些修改
6. confidence（float）：0.0-1.0，你对这条建议质量的自评

输出 JSON：
{
  "problem_summary": "...",
  "suggested_revision": "...",
  "revised_text": "...",
  "supporting_evidence": ["[Smith et al., 2023]", "..."],
  "response_to_reviewer": "Thank you for this comment. We have added ...",
  "confidence": 0.85
}
```

**按意图类型的 Prompt 差异**：

| 意图类型 | Prompt 核心指令 | 知识库证据 |
|----------|----------------|-----------|
| `missing_citation` | 从证据中找最匹配的引用，给出引用位置和 \cite{} 格式 | 必须有 |
| `factual_error` | 核查数据，若证据支持审稿人，给出更正方案；若不支持，给出论证文字 | 必须有 |
| `logic_gap` | 指出逻辑断点，给出补充论证的段落草稿 | 推荐有 |
| `comparison_needed` | 从证据中找对比方法，生成对比文字和可能的实验补充建议 | 必须有 |
| `writing_clarity` | 重写为更清晰的表达，不需要文献支撑 | 无需 |
| `grammar_style` | 直接给出修正后的文本 | 无需 |
| `structure_suggestion` | 参考期刊风格，给出重组方案 | 从 venue_style 检索 |
| `scope_expansion` | 给出扩展讨论的写作框架和相关引用 | 推荐有 |
| `delete_content` | 给出删减后的简化版本，解释删减理由 | 无需 |

---

#### 5.3.2 报告构建（`report_builder.py`）

```python
class ReportBuilder:
    
    def build_markdown_report(self, suggestions: list[RevisionSuggestion],
                               report: ReviewReport) -> str:
        """
        构建结构化 Markdown 报告。
        
        报告结构：
        
        # Review Response Report
        ## 概览
        - 总批注数、已处理数
        - 意图类型分布饼状文字描述
        - 平均置信度
        
        ## 按审稿人分组
        ### Reviewer 1 (R1)
        #### [R1-001] missing_citation | Section: Introduction | Page: 3
        **原文**：...
        **审稿人意见**：...
        **问题摘要**：...
        **修改建议**：...
        **建议修改后文本**：
        ```
        [修改后的文本]
        ```
        **支撑文献**：[Smith et al., 2023], [Jones et al., 2022]
        **给审稿人的回复（Rebuttal 模板）**：
        > Thank you for this comment. We have added...
        ---
        
        ## Rebuttal Letter 模板
        （将所有回复按审稿人聚合，生成完整的 rebuttal letter 框架）
        """
    
    def build_rebuttal_template(self, suggestions: list[RevisionSuggestion]) -> str:
        """
        生成完整的 rebuttal letter 模板（纯英文，学术格式）。
        按 Reviewer 1 / Reviewer 2 / ... 分组，
        每条意见配一段感谢 + 说明修改的回复。
        """
    
    def build_per_comment_files(self, suggestions: list[RevisionSuggestion],
                                 output_dir: Path) -> None:
        """为每条批注生成独立的 Markdown 文件（per_comment/ 目录）。"""
```

**报告输出示例**（`review_report.md` 片段）：

```markdown
# Review Response Report
**Generated**: 2026-03-26 14:32:11
**Source**: annotated_paper.pdf
**Total Annotations**: 23 | **Processed**: 23

## Intent Distribution
| 类型 | 数量 | 占比 |
|------|------|------|
| missing_citation | 8 | 34.8% |
| comparison_needed | 5 | 21.7% |
| logic_gap | 4 | 17.4% |
| writing_clarity | 3 | 13.0% |
| factual_error | 2 | 8.7% |
| grammar_style | 1 | 4.3% |

---

## Reviewer 1

### [R1-001] `missing_citation` | Introduction | Page 2

> **审稿人原话**：The authors claim that existing methods fail to handle sparse graphs, but no citation is provided.

**🔍 问题摘要**：Introduction 第 2 段声称现有方法无法处理稀疏图，缺少文献支撑。

**✏️ 修改建议**：在"existing methods fail to handle sparse graphs"后添加 2-3 篇直接相关的引用，优先使用知识库中的以下证据。

**📝 建议修改后文本**：
```
While graph neural networks have shown remarkable success in various tasks [Smith et al., 2023; Jones et al., 2022], 
existing methods struggle to maintain performance on sparse graphs due to the limited neighborhood 
information available [Wang et al., 2021].
```

**📚 支撑文献**：
- [Smith et al., 2023] *Fast GNN for Sparse Graphs* — Method 章节：直接讨论稀疏图的挑战
- [Wang et al., 2021] *Sparse Graph Learning* — Introduction：提供数据支撑

**📨 Rebuttal 模板**：
> Thank you for pointing this out. We agree that the claim required proper citation. 
> We have added references [Smith et al., 2023] and [Wang et al., 2021] to support 
> this statement, as these works explicitly analyze the limitations of dense-assumption 
> GNN methods when applied to sparse graph settings (see revised manuscript, Page 2, Line 8).

---
```

---

### 5.4 Diff 工具（`src/review_advisor/utils/diff_utils.py`）

```python
def generate_inline_diff(original: str, revised: str) -> str:
    """
    生成 Markdown 格式的 inline diff，便于快速对比修改。
    使用 difflib.ndiff，删除用 ~~红色~~，新增用 **绿色** 标注。
    
    示例输出：
    ~~existing methods fail~~ **existing methods, including [Smith et al., 2023], struggle**
    """

def generate_latex_diff(original: str, revised: str) -> str:
    """
    生成 LaTeX \textcolor{} 格式的 diff，可直接编译查看变化。
    """
```

---

## 6. 主流程（`src/review_advisor/pipeline.py`）

```python
async def run_review_pipeline(config: Config) -> None:
    
    # ── Step 0: 加载/验证已有 RAG 索引 ─────────────────────
    logger.info("[Step 0] Loading existing RAG indexes...")
    if not indexes_exist(config):
        logger.warning("RAG indexes not found! Run 'rwa' first to build indexes.")
        raise SystemExit(1)
    
    retriever = Retriever(config)        # 复用现有三阶段检索器
    llm_client = LLMClient(config.llm)  # 复用现有 LLM 客户端
    scorer_llm = LLMClient(config.scorer_llm)
    
    # ── Step 1: 扫描输入目录，加载带批注 PDF + 文本意见 ────
    logger.info("[Step 1] Scanning review_input/...")
    input_dir = Path(config.review_advisor.input_dir)
    pdf_files = list(input_dir.glob("*.pdf"))
    txt_files = list(input_dir.glob("*.txt")) + list(input_dir.glob("*.md"))
    
    # ── Step 2: 解析用户论文（获取章节结构，用于上下文定位）
    logger.info("[Step 2] Parsing my_paper for context assembly...")
    my_paper_sections = await parse_my_paper_sections(config.data.my_paper_dir)
    
    # ── Step 3: 并行提取批注（PDF + 文本）────────────────────
    logger.info("[Step 3] Extracting annotations in parallel...")
    extractor = AnnotationExtractor(config)
    txt_parser = TextReviewParser(llm_client)
    assembler = ContextAssembler(config)
    
    all_raw_annots: list[RawAnnotation] = []
    
    extraction_tasks = (
        [extractor.extract_from_pdf(f) for f in pdf_files] +
        [txt_parser.parse(f) for f in txt_files]
    )
    results = await asyncio.gather(*extraction_tasks)
    for r in results:
        all_raw_annots.extend(r)
    
    logger.info(f"  Extracted {len(all_raw_annots)} annotations total.")
    
    # ── Step 4: 并行拼装上下文 ─────────────────────────────
    logger.info("[Step 4] Assembling annotation contexts...")
    contexts = await asyncio.gather(
        *[assembler.assemble(a, my_paper_sections) for a in all_raw_annots]
    )
    
    # ── Step 5: 批量意图分类（并行，使用 scorer_llm）────────
    logger.info("[Step 5] Classifying annotation intents...")
    classifier = IntentClassifier(scorer_llm, config)
    classified = await classifier.classify_batch(all_raw_annots, list(contexts))
    
    # 组装 AnalyzedAnnotation（含 intent + reformulated_question）
    analyzed_annots: list[AnalyzedAnnotation] = [
        AnalyzedAnnotation(raw=a, context=c, intent=i, 
                           reformulated_question=q, intent_reasoning=r)
        for a, c, (i, r, q) in zip(all_raw_annots, contexts, classified)
    ]
    
    # ── Step 6: 并行检索知识库（按批注并行）─────────────────
    logger.info("[Step 6] Retrieving evidence from knowledge base...")
    query_builder = QueryBuilder(config)
    
    async def retrieve_for_annot(analyzed: AnalyzedAnnotation) -> AnalyzedAnnotation:
        queries = query_builder.build_queries(analyzed)
        if not queries:             # writing_clarity 等类型无需检索
            return analyzed
        evidence = await retriever.retrieve(
            queries=queries,
            paper_types=["background", "comparison"],
            top_k=config.review_advisor.retrieval.cross_encoder_top_k,
        )
        analyzed.retrieved_evidence = evidence
        return analyzed
    
    analyzed_annots = await asyncio.gather(
        *[retrieve_for_annot(a) for a in analyzed_annots]
    )
    
    # ── Step 7: 并行生成修改建议（使用主 LLM）───────────────
    logger.info("[Step 7] Generating revision suggestions...")
    generator = SuggestionGenerator(llm_client, config)
    suggestions = await generator.generate_batch(list(analyzed_annots))
    
    # ── Step 8: 构建报告 ───────────────────────────────────
    logger.info("[Step 8] Building report...")
    report = ReviewReport(
        source_files=[str(f) for f in pdf_files + txt_files],
        total_annotations=len(all_raw_annots),
        processed_annotations=len(suggestions),
        suggestions=suggestions,
        intent_summary=compute_intent_summary(suggestions),
        timestamp=datetime.now().isoformat(),
    )
    builder = ReportBuilder(config)
    
    output_dir = prepare_output_dir(config, prefix="review")
    
    # 主报告
    md_report = builder.build_markdown_report(suggestions, report)
    (output_dir / "review_report.md").write_text(md_report, encoding="utf-8")
    
    # Rebuttal letter 模板
    rebuttal = builder.build_rebuttal_template(suggestions)
    (output_dir / "rebuttal_template.md").write_text(rebuttal, encoding="utf-8")
    
    # 结构化 JSON（供二次开发使用）
    (output_dir / "annotations_parsed.json").write_text(
        json.dumps([asdict(a) for a in analyzed_annots], ensure_ascii=False, indent=2)
    )
    
    # 逐条文件
    if config.review_advisor.output.save_per_comment:
        builder.build_per_comment_files(suggestions, output_dir / "per_comment")
    
    logger.success(f"Done! Report saved to: {output_dir}/review_report.md")
    logger.info(f"Rebuttal template: {output_dir}/rebuttal_template.md")
    logger.info(f"Total: {len(suggestions)} suggestions generated.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RWA Review Advisor")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--input", help="覆盖 config 中的 input_dir")
    parser.add_argument("--no-per-comment", action="store_true", 
                        help="不生成 per_comment/ 目录")
    args = parser.parse_args()
    
    config = load_config(args.config)
    if args.input:
        config.review_advisor.input_dir = args.input
    if args.no_per_comment:
        config.review_advisor.output.save_per_comment = False
    
    asyncio.run(run_review_pipeline(config))
```

---

## 7. 并行处理设计

```
Step 0  加载索引（串行，前置检查）

Step 1  扫描输入目录（串行，I/O 操作）

Step 2  解析 my_paper（串行，依赖文件系统）

Step 3  提取批注（全并行）
  PDF 1 提取  ──┐
  PDF 2 提取  ──┼──► asyncio.gather()
  TXT 1 解析  ──┘

Step 4  拼装上下文（全并行，每条批注独立）
  annot_001 ──┐
  annot_002 ──┼──► asyncio.gather()
  annot_N   ──┘

Step 5  意图分类（批并行，batch_size=10）
  [batch 1: annot 1-10]  ──┐
  [batch 2: annot 11-20] ──┼──► asyncio.gather()（批间并行）
  [batch N: ...]         ──┘

Step 6  知识库检索（全并行，每条批注独立检索）
  annot_001 retrieve ──┐
  annot_002 retrieve ──┼──► asyncio.gather()（最耗时步骤，并行收益最大）
  annot_N retrieve   ──┘

Step 7  生成修改建议（全并行，每条批注独立生成）
  annot_001 generate ──┐
  annot_002 generate ──┼──► asyncio.gather()
  annot_N generate   ──┘

Step 8  构建报告（串行，汇总）
```

**性能预估**（以 20 条批注为例，使用 Claude Sonnet）：
- Step 3-4：< 10s（本地 CPU 操作）
- Step 5：约 15s（批量 LLM 分类，并行）
- Step 6：约 30s（20 路并行检索）
- Step 7：约 60s（20 路并行 LLM 生成）
- 总计：**< 2 分钟** 处理 20 条批注

---

## 8. pyproject.toml 新增入口

在现有 `pyproject.toml` 的 `[project.scripts]` 节新增一行：

```toml
[project.scripts]
rwa = "src.pipeline:main"
rwa-review = "src.review_advisor.pipeline:main"    # ← 新增
```

新增依赖（在现有基础上追加）：

```toml
# pyproject.toml [project.dependencies] 追加：
"rapidfuzz>=3.6.0",   # 批注文本模糊匹配（上下文定位）
"difflib",            # 标准库，diff 生成（无需额外安装）
```

---

## 9. 运行方式

```bash
# 1. 将带批注的 PDF 放入输入目录
cp my_reviewed_paper.pdf data/review_input/

# 2. 或放纯文本审稿意见
cp reviewer_comments.txt data/review_input/

# 3. 确保已有 RAG 索引（先运行过 rwa）
# 若没有，先运行：
rwa --skip-generation   # 只建索引，不生成 Related Work

# 4. 运行 Review Advisor
rwa-review

# 5. 指定输入目录（覆盖 config）
rwa-review --input /path/to/my/review/

# 6. 不生成 per_comment 文件（节省 I/O）
rwa-review --no-per-comment
```

---

## 10. 输出文件说明

```
outputs/review_20260326_143211/
├── review_report.md          # ★ 主报告：逐条修改建议，按审稿人分组
├── rebuttal_template.md      # ★ Rebuttal letter 框架（直接填入即可）
├── annotations_parsed.json   # 所有批注的结构化数据（调试/二次开发）
└── per_comment/
    ├── R1_001_missing_citation.md
    ├── R1_002_logic_gap.md
    ├── R2_001_comparison_needed.md
    └── ...
```

---

## 11. 实现注意事项

**批注提取的边界情况**：
- 部分 PDF 编辑器（如 Preview on macOS）保存的批注，`annot.info["content"]` 可能为空字符串，需 fallback 到 `annot.info.get("subject", "")`
- 扫描版 PDF 无法提取文本，需检测并跳过，输出警告
- 同一位置存在多个批注（高亮 + Sticky Note）时，需按坐标相邻度聚合为一条

**LLM 输出鲁棒性**：
- 所有 LLM 调用要求输出 JSON，使用 `generate_json()` 方法，加 JSON Schema 验证
- 若 JSON 解析失败，自动 retry 一次，携带错误信息要求 LLM 修正格式
- `confidence < 0.5` 的建议在报告中用 ⚠️ 标注，提示用户人工审核

**知识库复用**：
- 检索时明确过滤 `paper_type in ["background", "comparison"]`，排除 `venue_style` 类型（风格参考论文不应作为内容证据）
- 每条批注的检索结果去重（按 `paper_id` 聚合，同一论文的多个 chunk 合并展示）

---

## 12. 后续可扩展方向

- [ ] **多论文批注合并**：同一论文收到多位审稿人意见时，自动识别重复关切点并合并处理
- [ ] **修改追踪**：将建议的 `revised_text` 自动写回 `.tex` 文件，生成带 `\textcolor{red}{删除} \textcolor{blue}{新增}` 的 diff 版本
- [ ] **交互式模式**：用 Gradio 展示每条批注及建议，支持用户一键采纳/拒绝/修改，实时更新 rebuttal template
- [ ] **期刊投稿系统集成**：解析 ScholarOne / Editorial Manager 导出的 HTML/PDF 格式审稿意见
- [ ] **多轮迭代**：与 Related Work 生成功能类似，对修改建议本身也做多轮质量评估取最优
