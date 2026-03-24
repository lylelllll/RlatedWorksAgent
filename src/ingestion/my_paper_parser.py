"""解析用户自己的论文草稿——支持 .pdf / .tex / .txt / .md。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class MyPaperContext:
    """用户论文上下文，用于构建检索 Query 和 Prompt。"""
    title: str = ""
    abstract: str = ""
    introduction: str = ""
    contributions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    full_text: str = ""


def _parse_tex(content: str) -> MyPaperContext:
    """从 .tex 文件提取结构化信息。"""
    ctx = MyPaperContext(full_text=content)

    # 提取标题
    m = re.search(r"\\title\{(.+?)\}", content, re.DOTALL)
    if m:
        ctx.title = re.sub(r"\s+", " ", m.group(1)).strip()

    # 提取摘要
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL)
    if m:
        ctx.abstract = m.group(1).strip()

    # 提取关键词
    m = re.search(r"\\(?:keywords|IEEEkeywords)\{(.+?)\}", content, re.DOTALL)
    if not m:
        m = re.search(
            r"\\begin\{(?:keywords|IEEEkeywords)\}(.*?)\\end\{(?:keywords|IEEEkeywords)\}",
            content, re.DOTALL,
        )
    if m:
        kw_text = m.group(1).strip()
        ctx.keywords = [k.strip() for k in re.split(r"[,;，；]", kw_text) if k.strip()]

    # 提取 Introduction
    m = re.search(
        r"\\section\{Introduction\}(.*?)(?=\\section\{|\\end\{document\})",
        content, re.DOTALL | re.IGNORECASE,
    )
    if m:
        ctx.introduction = m.group(1).strip()

    # 从 Introduction 中提取贡献列表
    if ctx.introduction:
        ctx.contributions = _extract_contributions(ctx.introduction)

    return ctx


def _parse_pdf(pdf_path: Path) -> MyPaperContext:
    """从 PDF 文件提取信息（复用 PDFParser）。"""
    from src.ingestion.pdf_parser import PDFParser

    parser = PDFParser()
    sections = parser.parse(pdf_path, "my_paper")

    ctx = MyPaperContext()
    for sec in sections:
        if not ctx.title:
            ctx.title = sec.title
        if sec.section_name == "Abstract":
            ctx.abstract = sec.text
        elif sec.section_name == "Introduction":
            ctx.introduction = sec.text

    ctx.full_text = "\n\n".join(sec.text for sec in sections)

    if ctx.introduction:
        ctx.contributions = _extract_contributions(ctx.introduction)

    # 从摘要中提取关键词（简单策略）
    if ctx.abstract and not ctx.keywords:
        ctx.keywords = _extract_keywords_from_abstract(ctx.abstract)

    return ctx


def _parse_text(content: str, ext: str) -> MyPaperContext:
    """从纯文本或 Markdown 文件提取信息。"""
    ctx = MyPaperContext(full_text=content)

    lines = content.strip().split("\n")
    if lines:
        # 第一个非空行作为标题
        for line in lines:
            if line.strip():
                ctx.title = line.strip().lstrip("# ").strip()
                break

    # 尝试提取 Abstract 段落
    abstract_match = re.search(
        r"(?:^|\n)(?:#+\s*)?(?:Abstract|摘要)[:\s]*\n(.*?)(?=\n(?:#+\s*)?(?:Introduction|1[\.\)]|关键词|Keywords)|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if abstract_match:
        ctx.abstract = abstract_match.group(1).strip()

    # 尝试提取 Introduction
    intro_match = re.search(
        r"(?:^|\n)(?:#+\s*)?(?:Introduction|引言)[:\s]*\n(.*?)(?=\n(?:#+\s*)?(?:Related|Background|Method|2[\.\)]|相关工作)|\Z)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if intro_match:
        ctx.introduction = intro_match.group(1).strip()
        ctx.contributions = _extract_contributions(ctx.introduction)

    return ctx


def _extract_contributions(intro_text: str) -> list[str]:
    """从 Introduction 中识别贡献列表。"""
    contributions = []

    # 模式 1: \begin{itemize} ... \end{itemize} (LaTeX)
    itemize_match = re.search(
        r"\\begin\{(?:itemize|enumerate)\}(.*?)\\end\{(?:itemize|enumerate)\}",
        intro_text, re.DOTALL,
    )
    if itemize_match:
        items = re.findall(r"\\item\s+(.*?)(?=\\item|$)", itemize_match.group(1), re.DOTALL)
        contributions = [item.strip() for item in items if item.strip()]
        if contributions:
            return contributions

    # 模式 2: numbered list "1) ... 2) ..."
    numbered = re.findall(r"(?:^|\n)\s*(?:\d+[\)\.]|•|[-–])\s+(.+?)(?=\n\s*(?:\d+[\)\.]|•|[-–])|\Z)", intro_text, re.DOTALL)
    if numbered:
        contributions = [item.strip() for item in numbered if item.strip()]
        if contributions:
            return contributions

    # 模式 3: 包含 "contribution" 关键词的段落
    contrib_match = re.search(
        r"(?:contributions?|novelties)\s+(?:are|include|of this)\s*[:\.]?\s*(.*?)(?:\n\n|\Z)",
        intro_text, re.DOTALL | re.IGNORECASE,
    )
    if contrib_match:
        text = contrib_match.group(1)
        sentences = re.split(r"(?<=[.。])\s+", text)
        contributions = [s.strip() for s in sentences if len(s.strip()) > 20]

    return contributions


def _extract_keywords_from_abstract(abstract: str) -> list[str]:
    """从摘要中提取关键术语（简单频率策略）。"""
    # 移除常见停用词
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "this",
        "that", "these", "those", "it", "its", "we", "our", "they", "their",
        "which", "what", "where", "when", "who", "how", "not", "no", "nor",
        "but", "or", "and", "if", "than", "too", "very", "just", "also",
        "both", "each", "more", "most", "other", "some", "such", "only",
        "own", "same", "so", "then", "there", "here", "all", "any", "few",
        "many", "much", "several",  "paper", "proposed", "propose",
        "approach", "method", "results", "show", "based",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", abstract.lower())
    filtered = [w for w in words if w not in stop_words]

    # 简单的 bigram 提取
    bigrams = [f"{filtered[i]} {filtered[i+1]}" for i in range(len(filtered) - 1)]
    from collections import Counter
    freq = Counter(bigrams)
    keywords = [bg for bg, _ in freq.most_common(8)]

    # 加入高频单词
    word_freq = Counter(filtered)
    top_words = [w for w, c in word_freq.most_common(5) if c >= 2]
    keywords.extend(top_words)

    return keywords[:10]


async def parse_my_paper(dir_path: str | Path) -> MyPaperContext:
    """解析用户论文目录中的论文草稿。"""
    dir_path = Path(dir_path)
    if not dir_path.exists():
        logger.error(f"用户论文目录不存在: {dir_path}")
        return MyPaperContext()

    # 按优先级查找文件
    for ext in [".tex", ".pdf", ".md", ".txt"]:
        files = sorted(dir_path.glob(f"*{ext}"))
        if files:
            file_path = files[0]
            logger.info(f"解析用户论文: {file_path.name}")

            if ext == ".tex":
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                return _parse_tex(content)
            elif ext == ".pdf":
                return _parse_pdf(file_path)
            else:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                return _parse_text(content, ext)

    logger.error(f"未在 {dir_path} 中找到论文文件 (.tex/.pdf/.md/.txt)")
    return MyPaperContext()
