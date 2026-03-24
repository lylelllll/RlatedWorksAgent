"""目标期刊 Related Work 风格分析。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from src.ingestion.pdf_parser import ParsedSection


@dataclass
class VenueStyle:
    """目标期刊的 Related Work 写作风格。"""
    avg_word_count: int = 0
    avg_paragraph_count: int = 0
    has_subsections: bool = False
    avg_citations_per_paragraph: float = 0.0
    avg_sentences_per_method: float = 0.0
    paragraph_structure: str = ""
    transition_phrases: list[str] = field(default_factory=list)
    sample_paragraphs: list[str] = field(default_factory=list)
    latex_structure: str = ""


def _count_citations(text: str) -> int:
    """统计文本中的引用数量。"""
    # 匹配 \cite{...}, [1], [1,2,3] 等
    latex_cites = re.findall(r"\\cite\{[^}]+\}", text)
    bracket_cites = re.findall(r"\[\d+(?:[,\s]*\d+)*\]", text)
    return len(latex_cites) + len(bracket_cites)


def _count_sentences(text: str) -> int:
    """粗略统计句子数。"""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return len([s for s in sentences if len(s) > 10])


def _detect_paragraph_structure(paragraphs: list[str]) -> str:
    """分析段落结构模式。"""
    patterns = []
    for para in paragraphs[:5]:  # 分析前 5 段
        lower = para.lower()
        components = []
        if any(w in lower for w in ["problem", "challenge", "issue", "limitation"]):
            components.append("problem")
        if any(w in lower for w in ["propose", "present", "introduce", "develop"]):
            components.append("method")
        if any(w in lower for w in ["however", "but", "limitation", "drawback", "lack"]):
            components.append("limitation")
        if any(w in lower for w in ["in contrast", "unlike", "differ", "compared"]):
            components.append("comparison")
        if components:
            patterns.append("→".join(components))

    if patterns:
        from collections import Counter
        most_common = Counter(patterns).most_common(1)[0][0]
        return most_common
    return "background→method→limitation"


def _extract_transition_phrases(paragraphs: list[str]) -> list[str]:
    """提取过渡词和连接短语。"""
    transitions = set()
    transition_patterns = [
        r"(?:^|\.\s+)(In (?:addition|contrast|particular|recent years|this (?:context|paper|work)))",
        r"(?:^|\.\s+)(However|Moreover|Furthermore|Nevertheless|Meanwhile|Specifically|Similarly)",
        r"(?:^|\.\s+)(To (?:address|overcome|tackle|solve|mitigate) (?:this|these|the above))",
        r"(?:^|\.\s+)(Unlike|Different from|Compared (?:with|to)|Inspired by)",
        r"(?:^|\.\s+)(More recently|Along (?:this|another) (?:line|direction))",
    ]
    for para in paragraphs:
        for pattern in transition_patterns:
            matches = re.findall(pattern, para, re.IGNORECASE)
            transitions.update(matches)

    return sorted(transitions)[:15]


async def analyze_venue_style(
    venue_sections: list[ParsedSection], config=None
) -> VenueStyle:
    """分析目标期刊论文中 Related Work 章节的写作风格。"""
    # 筛选 Related Work 章节
    rw_sections = [s for s in venue_sections if s.section_name == "RelatedWork"]

    if not rw_sections:
        logger.warning("未在风格参考论文中找到 Related Work 章节，使用默认风格")
        return VenueStyle(
            avg_word_count=1200,
            avg_paragraph_count=6,
            has_subsections=True,
            avg_citations_per_paragraph=4.0,
            avg_sentences_per_method=3.0,
            paragraph_structure="background→method→limitation",
            transition_phrases=[
                "However", "In contrast", "Moreover", "To address this",
                "More recently", "Unlike", "Furthermore",
            ],
            sample_paragraphs=[],
            latex_structure="\\section{Related Work}\n\\subsection{...}",
        )

    logger.info(f"分析 {len(rw_sections)} 篇论文的 Related Work 风格")

    word_counts = []
    paragraph_counts = []
    citations_per_paragraph = []
    all_paragraphs = []
    has_subsec_votes = []

    for section in rw_sections:
        text = section.text

        # 词数
        words = text.split()
        word_counts.append(len(words))

        # 段落数
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 30]
        paragraph_counts.append(len(paragraphs))
        all_paragraphs.extend(paragraphs)

        # 每段引用数
        for para in paragraphs:
            cites = _count_citations(para)
            citations_per_paragraph.append(cites)

        # 是否有子标题
        has_sub = bool(re.search(r"\\subsection|^[A-Z]\.\s|\d+\.\d+", text, re.MULTILINE))
        has_subsec_votes.append(has_sub)

    # 计算平均值
    avg_words = int(sum(word_counts) / len(word_counts)) if word_counts else 1200
    avg_paras = int(sum(paragraph_counts) / len(paragraph_counts)) if paragraph_counts else 6
    avg_cites = sum(citations_per_paragraph) / len(citations_per_paragraph) if citations_per_paragraph else 4.0
    has_sub = sum(has_subsec_votes) > len(has_subsec_votes) / 2 if has_subsec_votes else True

    # 每个方法的平均描述句数（粗略估计）
    method_sentences = []
    for para in all_paragraphs:
        sents = _count_sentences(para)
        cites = _count_citations(para)
        if cites > 0:
            method_sentences.append(sents / cites)
    avg_sents_per_method = (
        sum(method_sentences) / len(method_sentences) if method_sentences else 3.0
    )

    # 段落结构
    structure = _detect_paragraph_structure(all_paragraphs)

    # 过渡词
    transitions = _extract_transition_phrases(all_paragraphs)

    # 样例段落（取最有代表性的 1-2 段）
    sample = []
    for para in all_paragraphs:
        if 100 < len(para.split()) < 300 and _count_citations(para) >= 2:
            sample.append(para)
            if len(sample) >= 2:
                break

    # LaTeX 结构模板
    latex_struct = "\\section{Related Work}"
    if has_sub:
        latex_struct += "\n\\subsection{...}"

    style = VenueStyle(
        avg_word_count=avg_words,
        avg_paragraph_count=avg_paras,
        has_subsections=has_sub,
        avg_citations_per_paragraph=round(avg_cites, 1),
        avg_sentences_per_method=round(avg_sents_per_method, 1),
        paragraph_structure=structure,
        transition_phrases=transitions,
        sample_paragraphs=sample,
        latex_structure=latex_struct,
    )

    logger.info(
        f"风格分析完成: ~{avg_words} 词, ~{avg_paras} 段, "
        f"子标题={'是' if has_sub else '否'}, "
        f"每段引用={avg_cites:.1f}"
    )
    return style
