"""PDF 全文解析与章节结构化——使用 pymupdf。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # pymupdf
from loguru import logger


# ── 数据结构 ─────────────────────────────────────────────────

@dataclass
class ParsedSection:
    """论文中的一个章节。"""
    paper_id: str           # 文件名（不含扩展名）
    paper_type: str         # "background" | "comparison" | "venue_style"
    title: str              # 论文标题
    authors: str = ""
    year: int = 0
    venue: str = ""
    section_name: str = ""  # 规范化章节名
    section_order: int = 0
    text: str = ""
    page_range: tuple[int, int] = (0, 0)


# 章节权重（检索 boost 用）
SECTION_WEIGHTS: dict[str, float] = {
    "Abstract": 1.0,
    "Introduction": 0.95,
    "RelatedWork": 0.95,
    "Method": 0.85,
    "System": 0.85,
    "Conclusion": 0.80,
    "Experiment": 0.70,
}
DEFAULT_SECTION_WEIGHT = 0.50


# 章节名规范化映射
_SECTION_ALIASES: dict[str, str] = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "related work": "RelatedWork",
    "related works": "RelatedWork",
    "literature review": "RelatedWork",
    "background": "RelatedWork",
    "preliminaries": "Preliminaries",
    "preliminary": "Preliminaries",
    "method": "Method",
    "methodology": "Method",
    "proposed method": "Method",
    "proposed approach": "Method",
    "approach": "Method",
    "system model": "System",
    "system design": "System",
    "system architecture": "System",
    "system overview": "System",
    "experiment": "Experiment",
    "experiments": "Experiment",
    "experimental results": "Experiment",
    "evaluation": "Experiment",
    "performance evaluation": "Experiment",
    "simulation": "Experiment",
    "simulation results": "Experiment",
    "results": "Experiment",
    "result": "Experiment",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "conclusion and future work": "Conclusion",
    "concluding remarks": "Conclusion",
    "discussion": "Discussion",
    "references": "References",
    "acknowledgment": "Acknowledgment",
    "acknowledgments": "Acknowledgment",
    "acknowledgement": "Acknowledgment",
}


def normalize_section_name(raw: str) -> str:
    """将原始章节标题规范化。"""
    # 移除数字编号、点、罗马数字前缀
    cleaned = re.sub(r"^[\dIVXLCDM]+[\.\):\s]+", "", raw.strip())
    cleaned = cleaned.strip().lower()
    return _SECTION_ALIASES.get(cleaned, cleaned.title().replace(" ", ""))


def get_section_weight(section_name: str) -> float:
    """获取章节权重。"""
    return SECTION_WEIGHTS.get(section_name, DEFAULT_SECTION_WEIGHT)


# ── PDF 解析器 ─────────────────────────────────────────────────

class PDFParser:
    """解析单个学术论文 PDF，提取结构化章节。"""

    def __init__(self, min_heading_font_ratio: float = 1.15):
        """
        Args:
            min_heading_font_ratio: 标题字体大小相对正文的最小比例
        """
        self.min_heading_font_ratio = min_heading_font_ratio

    def parse(self, pdf_path: str | Path, paper_type: str) -> list[ParsedSection]:
        """解析 PDF 文件，返回结构化章节列表。"""
        pdf_path = Path(pdf_path)
        raw_id = pdf_path.stem
        import re
        paper_id = re.sub(r"[^\w]+", "_", raw_id).strip("_")
        logger.info(f"解析 PDF: {pdf_path.name}")

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.error(f"无法打开 PDF {pdf_path.name}: {e}")
            return []

        # 步骤 1: 提取所有文本块，保留字体信息
        all_blocks = self._extract_blocks_with_fonts(doc)

        # 步骤 2: 确定正文字体大小
        body_font_size = self._detect_body_font_size(all_blocks)

        # 步骤 3: 识别章节标题并分段
        sections = self._segment_sections(all_blocks, body_font_size, doc.page_count)

        # 步骤 4: 提取论文元信息（标题、作者等）
        title = self._extract_title(all_blocks, body_font_size)
        authors = self._extract_authors(doc)

        # 步骤 5: 构建 ParsedSection 列表
        results = []
        for i, (sec_name, sec_text, page_range) in enumerate(sections):
            normalized = normalize_section_name(sec_name)
            if normalized == "References" or normalized == "Acknowledgment":
                continue  # 跳过参考文献和致谢

            results.append(ParsedSection(
                paper_id=paper_id,
                paper_type=paper_type,
                title=title,
                authors=authors,
                section_name=normalized,
                section_order=i,
                text=sec_text.strip(),
                page_range=page_range,
            ))

        doc.close()

        if not results:
            # 如果没有识别到章节，将全文作为一个 section
            full_text = "\n".join(b["text"] for b in all_blocks if b.get("text"))
            results.append(ParsedSection(
                paper_id=paper_id,
                paper_type=paper_type,
                title=title,
                authors=authors,
                section_name="FullText",
                section_order=0,
                text=full_text.strip(),
                page_range=(0, doc.page_count - 1),
            ))

        logger.debug(f"  解析到 {len(results)} 个章节: {[s.section_name for s in results]}")
        return results

    def _extract_blocks_with_fonts(self, doc: fitz.Document) -> list[dict]:
        """提取所有页面的文本块，保留字体大小信息。"""
        blocks = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # 获取详细的文本信息
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # 0 = text block
                    continue
                for line in block.get("lines", []):
                    text_parts = []
                    font_sizes = []
                    for span in line.get("spans", []):
                        t = span.get("text", "").strip()
                        if t:
                            text_parts.append(t)
                            font_sizes.append(span.get("size", 10.0))
                    if text_parts:
                        avg_size = sum(font_sizes) / len(font_sizes)
                        line_text = " ".join(text_parts)
                        blocks.append({
                            "text": line_text,
                            "font_size": avg_size,
                            "page": page_num,
                            "y0": line.get("bbox", [0, 0, 0, 0])[1] if "bbox" in line else block.get("bbox", [0, 0, 0, 0])[1],
                            "x0": line.get("bbox", [0, 0, 0, 0])[0] if "bbox" in line else block.get("bbox", [0, 0, 0, 0])[0],
                        })
        return blocks

    def _detect_body_font_size(self, blocks: list[dict]) -> float:
        """检测最常见的字体大小作为正文字号。"""
        if not blocks:
            return 10.0
        from collections import Counter
        sizes = [round(b["font_size"], 1) for b in blocks if len(b.get("text", "")) > 20]
        if not sizes:
            return 10.0
        counter = Counter(sizes)
        return counter.most_common(1)[0][0]

    def _segment_sections(
        self, blocks: list[dict], body_font_size: float, total_pages: int
    ) -> list[tuple[str, str, tuple[int, int]]]:
        """根据字体大小识别章节标题，分割文本。"""
        threshold = body_font_size * self.min_heading_font_ratio
        sections: list[tuple[str, str, tuple[int, int]]] = []
        current_title = "Abstract"
        current_text_parts: list[str] = []
        current_start_page = 0

        # 常见章节标题的正则模式
        heading_pattern = re.compile(
            r"^(?:[\dIVXLCDM]+[\.\):\s]+)?\s*"
            r"(Abstract|Introduction|Related\s*Work|Background|"
            r"Preliminaries|Methodology|Method|Approach|"
            r"System\s*(?:Model|Design|Architecture|Overview)|"
            r"Experiment|Evaluation|Results?|Simulation|"
            r"Discussion|Conclusion|Acknowledgment|References)",
            re.IGNORECASE,
        )

        for block in blocks:
            text = block["text"].strip()
            font_size = block["font_size"]
            page = block["page"]

            if not text:
                continue

            # 判断是否是章节标题
            is_heading = (
                font_size >= threshold
                and len(text) < 80
                and heading_pattern.match(text)
            )

            if is_heading:
                # 保存上一个章节
                if current_text_parts:
                    sections.append((
                        current_title,
                        "\n".join(current_text_parts),
                        (current_start_page, page),
                    ))
                current_title = text
                current_text_parts = []
                current_start_page = page
            else:
                current_text_parts.append(text)

        # 保存最后一个章节
        if current_text_parts:
            sections.append((
                current_title,
                "\n".join(current_text_parts),
                (current_start_page, total_pages - 1),
            ))

        return sections

    def _extract_title(self, blocks: list[dict], body_font_size: float) -> str:
        """提取论文标题（首页最大字体的文本）。"""
        first_page_blocks = [b for b in blocks if b["page"] == 0]
        if not first_page_blocks:
            return "Unknown Title"

        # 找首页最大字体
        max_size = max(b["font_size"] for b in first_page_blocks)
        title_parts = [
            b["text"]
            for b in first_page_blocks
            if abs(b["font_size"] - max_size) < 0.5 and len(b["text"]) > 3
        ]
        title = " ".join(title_parts[:3])  # 最多取 3 行
        return title.strip() if title.strip() else "Unknown Title"

    def _extract_authors(self, doc: fitz.Document) -> str:
        """尝试从元数据提取作者。"""
        meta = doc.metadata
        if meta and meta.get("author"):
            return meta["author"]
        return ""


# ── 批量解析 ─────────────────────────────────────────────────

def parse_single_pdf(args: tuple[Path, str]) -> list[ParsedSection]:
    """解析单个 PDF（用于并行调用）。"""
    pdf_path, paper_type = args
    parser = PDFParser()
    return parser.parse(pdf_path, paper_type)


async def parse_pdf_directory(
    dir_path: str | Path, paper_type: str, max_workers: int = 8
) -> list[ParsedSection]:
    """并行解析目录中所有 PDF 文件。"""
    from src.utils.parallel import parallel_map

    dir_path = Path(dir_path)
    if not dir_path.exists():
        logger.warning(f"目录不存在: {dir_path}")
        return []

    pdf_files = sorted(dir_path.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"目录中没有 PDF 文件: {dir_path}")
        return []

    logger.info(f"解析 {len(pdf_files)} 个 {paper_type} PDF...")
    args_list = [(f, paper_type) for f in pdf_files]

    results = await parallel_map(parse_single_pdf, args_list, max_workers=max_workers)
    all_sections = []
    for section_list in results:
        all_sections.extend(section_list)

    logger.info(f"  共提取 {len(all_sections)} 个章节")
    return all_sections
