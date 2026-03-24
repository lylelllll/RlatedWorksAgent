"""Prompt 构建——System Prompt + User Prompt 模板。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.ingestion.my_paper_parser import MyPaperContext
from src.style_analyzer.venue_analyzer import VenueStyle


@dataclass
class GenerationContext:
    """生成上下文，传递给 Prompt 构建和生成器。"""
    my_paper: MyPaperContext
    background_chunks: list[dict]
    comparison_chunks: list[dict]
    venue_style: VenueStyle
    known_paper_ids: set[str]


def _build_system_prompt(target_venue: str, language: str = "english") -> str:
    """构建 System Prompt。"""
    lang_instruction = "in English" if language.lower() == "english" else f"in {language}"
    return (
        f"You are a top-tier computer science academic writing expert, "
        f"specializing in writing Related Work sections that match the style of {target_venue}. "
        f"Your output must be valid LaTeX code that can be directly embedded into a .tex file. "
        f"Write {lang_instruction}. "
        f"Do NOT include any explanatory text outside the LaTeX code. "
        f"Do NOT wrap the output in ```latex``` code blocks."
    )


FIX_SYSTEM_PROMPT = (
    "You are a LaTeX expert. Fix the LaTeX syntax errors in the provided code. "
    "Output only the corrected LaTeX code, nothing else."
)


def _format_chunks(chunks: list[dict], label: str) -> str:
    """格式化 chunks 为 Prompt 中的参考文献列表。"""
    if not chunks:
        return f"（无 {label} 参考文献）"

    lines = []
    seen_papers: set[str] = set()

    for chunk in chunks:
        meta = chunk.get("metadata", {})
        paper_id = meta.get("paper_id", chunk.get("chunk_id", "unknown"))
        title = meta.get("title", "Unknown Title")
        authors = meta.get("authors", "")
        year = meta.get("year", "")
        text = chunk.get("text", "")

        # 每篇论文只显示一次标题信息
        if paper_id not in seen_papers:
            seen_papers.add(paper_id)
            header = f"[{paper_id}] {title}"
            if authors:
                header += f" | {authors}"
            if year:
                header += f", {year}"
            lines.append(header)

        # 添加关键内容摘要（限制长度）
        if text:
            summary = text[:300] + "..." if len(text) > 300 else text
            lines.append(f"  摘要: {summary}")
        lines.append("")

    return "\n".join(lines)


def build_prompt(
    context: GenerationContext,
    target_venue: str,
    language: str = "english",
    iteration: int = 1,
    previous_draft: str | None = None,
    prev_score: Any = None,
) -> tuple[str, str]:
    """
    构建完整的 Prompt。

    Returns:
        (system_prompt, user_prompt)
    """
    system_prompt = _build_system_prompt(target_venue, language)

    parts = []

    # ── 我的论文 ──
    parts.append("## My Paper\n")
    parts.append(f"Title: {context.my_paper.title}")
    if context.my_paper.abstract:
        parts.append(f"\nAbstract: {context.my_paper.abstract}")
    if context.my_paper.contributions:
        parts.append("\nKey Contributions:")
        for i, c in enumerate(context.my_paper.contributions, 1):
            parts.append(f"  {i}. {c}")
    parts.append("")

    # ── 目标期刊写作风格 ──
    vs = context.venue_style
    parts.append(f"---\n\n## Target Venue Writing Style ({target_venue})\n")
    parts.append(f"- Recommended length: ~{vs.avg_word_count} words, ~{vs.avg_paragraph_count} paragraphs")
    parts.append(f"- Use subsections: {'Yes' if vs.has_subsections else 'No'}")
    parts.append(f"- Average citations per paragraph: {vs.avg_citations_per_paragraph}")
    parts.append(f"- Average sentences per method description: ~{vs.avg_sentences_per_method}")
    parts.append(f"- Paragraph structure pattern: {vs.paragraph_structure}")

    if vs.transition_phrases:
        parts.append(f"\nCommon transition phrases: {', '.join(vs.transition_phrases[:8])}")

    if vs.sample_paragraphs:
        parts.append("\nStyle example paragraphs (reference tone and patterns, do NOT copy content):")
        for sp in vs.sample_paragraphs[:2]:
            parts.append(f"\n> {sp[:500]}")
    parts.append("")

    # ── 背景与传统方案 ──
    parts.append("---\n\n## Background & Traditional Approach References (for the first few paragraphs)\n")
    parts.append(_format_chunks(context.background_chunks, "background"))

    # ── 高度相似论文 ──
    parts.append("---\n\n## Highly Similar Papers (for comparative analysis paragraphs)\n")
    parts.append(_format_chunks(context.comparison_chunks, "comparison"))

    # ── 写作要求 ──
    parts.append("---\n\n## Writing Requirements\n")
    parts.append("1. Output a complete LaTeX Related Work section, starting with \\section{Related Work}")
    parts.append("2. Structure: first several paragraphs on background/traditional approaches, "
                  "last 1-2 paragraphs for lateral comparison with similar work and highlight innovations")
    parts.append("3. Citation format: \\cite{paper_id} (paper_id is the ID in [] above)")
    parts.append("4. End each paragraph by pointing out limitations or differences from our work")
    parts.append("5. Do NOT copy reference text verbatim; summarize in academic language")
    parts.append("6. LaTeX syntax must be correct; properly escape special characters (% & _ # $ ^ { })")
    parts.append(f"7. Available paper IDs for \\cite{{}}: {', '.join(sorted(context.known_paper_ids))}")

    # ── 迭代改进（第2轮起） ──
    if iteration >= 2 and prev_score is not None:
        parts.append("\n---\n\n## Previous Draft Score & Improvement Suggestions\n")
        parts.append(f"Total Score: {prev_score.total:.2f}/10")
        parts.append(f"- Coverage: {prev_score.coverage:.1f}")
        parts.append(f"- Accuracy: {prev_score.accuracy:.1f}")
        parts.append(f"- Comparison Quality: {prev_score.comparison_quality:.1f}")
        parts.append(f"- Style Compliance: {prev_score.style_compliance:.1f}")
        parts.append(f"- Coherence: {prev_score.coherence:.1f}")
        parts.append(f"- Novelty Highlight: {prev_score.novelty_highlight:.1f}")
        parts.append(f"- LaTeX Validity: {prev_score.latex_validity:.1f}")

        if prev_score.improvement_suggestions:
            parts.append("\nImprovement Suggestions:")
            for sug in prev_score.improvement_suggestions:
                parts.append(f"  - {sug}")

        parts.append("\nPlease improve based on the above feedback. Output the complete improved LaTeX code.")

        if previous_draft:
            parts.append(f"\n---\n\n## Previous Draft (to improve upon)\n\n```latex\n{previous_draft}\n```")

    user_prompt = "\n".join(parts)
    return system_prompt, user_prompt


def build_fix_prompt(latex_code: str, errors: list[str]) -> str:
    """构建 LaTeX 修复 Prompt。"""
    error_list = "\n".join(f"  - {e}" for e in errors)
    return (
        f"The following LaTeX code has syntax errors:\n\n"
        f"```latex\n{latex_code}\n```\n\n"
        f"Errors found:\n{error_list}\n\n"
        f"Please fix all errors and output the corrected LaTeX code only."
    )
