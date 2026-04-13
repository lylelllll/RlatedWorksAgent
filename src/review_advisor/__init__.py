"""Data structures for the Review Advisor module."""

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
    suggested_revision: str     # 具体修改方案（可能包含建议的新文本）
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
