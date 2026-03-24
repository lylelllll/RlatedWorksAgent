"""章节感知分块——按章节类型使用不同策略。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from src.config import ChunkingConfig
from src.ingestion.pdf_parser import ParsedSection, get_section_weight


@dataclass
class Chunk:
    """带元数据的文本块。"""
    chunk_id: str
    paper_id: str
    paper_type: str
    title: str
    authors: str
    year: int
    venue: str
    section: str
    section_order: int
    chunk_index: int
    importance_score: float
    text: str

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "paper_id": self.paper_id,
            "paper_type": self.paper_type,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "section": self.section,
            "section_order": self.section_order,
            "chunk_index": self.chunk_index,
            "importance_score": self.importance_score,
        }


class Chunker:
    """章节感知分块器。"""

    def __init__(self, config: ChunkingConfig):
        self.config = config

    def chunk_section(self, section: ParsedSection) -> list[Chunk]:
        """对单个章节进行分块。"""
        sec_name = section.section_name
        text = section.text.strip()
        if not text:
            return []

        weight = get_section_weight(sec_name)

        # 根据章节类型选择策略
        if sec_name == "Abstract":
            # 摘要整体作为 1 个 chunk
            return [self._make_chunk(section, text, 0, weight)]

        elif sec_name == "Introduction":
            return self._chunk_introduction(section, text, weight)

        elif sec_name == "RelatedWork":
            # 按段落独立分块
            return self._chunk_by_paragraph(section, text, weight, chunk_size=300, overlap=30)

        elif sec_name in ("Method", "System"):
            # 按子章节或较大块
            return self._chunk_by_size(
                section, text, weight,
                chunk_size=self.config.method_chunk_size,
                overlap=self.config.method_overlap,
            )

        elif sec_name == "Experiment":
            return self._chunk_by_size(
                section, text, weight,
                chunk_size=self.config.default_chunk_size,
                overlap=self.config.default_overlap,
            )

        elif sec_name == "Conclusion":
            return self._chunk_by_paragraph(section, text, weight, chunk_size=300, overlap=30)

        else:
            return self._chunk_by_size(
                section, text, weight,
                chunk_size=self.config.default_chunk_size,
                overlap=self.config.default_overlap,
            )

    def _chunk_introduction(
        self, section: ParsedSection, text: str, weight: float
    ) -> list[Chunk]:
        """Introduction 分块：前 3 段各独立，其余按默认大小。"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []

        # 前 3 段各独立
        for i, para in enumerate(paragraphs[:3]):
            chunks.append(self._make_chunk(section, para, i, weight))

        # 其余合并后按大小分块
        if len(paragraphs) > 3:
            remaining = "\n\n".join(paragraphs[3:])
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.default_chunk_size,
                chunk_overlap=self.config.default_overlap,
                separators=["\n\n", "\n", ". ", " "],
            )
            sub_chunks = splitter.split_text(remaining)
            for j, sub in enumerate(sub_chunks):
                chunks.append(self._make_chunk(section, sub, len(chunks), weight))

        return chunks

    def _chunk_by_paragraph(
        self, section: ParsedSection, text: str, weight: float,
        chunk_size: int = 300, overlap: int = 30,
    ) -> list[Chunk]:
        """按段落分块，过长段落再细分。"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n", ". ", " "],
        )

        for para in paragraphs:
            if len(para) <= chunk_size * 1.3:
                chunks.append(self._make_chunk(section, para, len(chunks), weight))
            else:
                for sub in splitter.split_text(para):
                    chunks.append(self._make_chunk(section, sub, len(chunks), weight))

        return chunks

    def _chunk_by_size(
        self, section: ParsedSection, text: str, weight: float,
        chunk_size: int = 400, overlap: int = 50,
    ) -> list[Chunk]:
        """按固定大小分块。"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " "],
        )
        sub_texts = splitter.split_text(text)
        return [
            self._make_chunk(section, sub, i, weight)
            for i, sub in enumerate(sub_texts)
        ]

    def _make_chunk(
        self, section: ParsedSection, text: str, index: int, weight: float
    ) -> Chunk:
        """构造 Chunk 对象。"""
        return Chunk(
            chunk_id=f"{section.paper_id}_{section.section_name}_{index}",
            paper_id=section.paper_id,
            paper_type=section.paper_type,
            title=section.title,
            authors=section.authors,
            year=section.year,
            venue=section.venue,
            section=section.section_name,
            section_order=section.section_order,
            chunk_index=index,
            importance_score=weight,
            text=text,
        )


def chunk_sections(sections: list[ParsedSection], config) -> list[Chunk]:
    """批量分块。"""
    chunker = Chunker(config.chunking)
    all_chunks = []
    for section in sections:
        chunks = chunker.chunk_section(section)
        all_chunks.extend(chunks)
    logger.info(f"分块完成: {len(sections)} 个章节 → {len(all_chunks)} 个 chunk")
    return all_chunks
