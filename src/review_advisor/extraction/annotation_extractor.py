"""PDF Annotation Extraction Module."""

import asyncio
from pathlib import Path
from typing import Optional

import fitz
from loguru import logger

from src.config import Config
from src.review_advisor import RawAnnotation
from src.ingestion.pdf_parser import PDFParser


class AnnotationExtractor:
    """Extracts annotations from reviewed PDF files."""

    def __init__(self, config: Config):
        self.config = config
        # Use defaults if config doesn't have review_advisor keys yet during partial initialization
        review_cfg = getattr(config, "review_advisor", {})
        annot_cfg = review_cfg.get("annotation", {})
        
        self.supported_types = set(annot_cfg.get(
            "supported_types", 
            ["Text", "Highlight", "Underline", "StrikeOut", "FreeText", "Squiggly"]
        ))
        self.extract_highlight_without_comment = annot_cfg.get(
            "extract_highlight_without_comment", True
        )

    async def extract_from_pdf(self, pdf_path: Path) -> list[RawAnnotation]:
        """Extract annotations from a single PDF document in a thread."""
        return await asyncio.to_thread(self._extract_sync, pdf_path)

    def _extract_sync(self, pdf_path: Path) -> list[RawAnnotation]:
        logger.info(f"Extracting annotations from {pdf_path.name}")
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path.name}: {e}")
            return []
            
        parser = PDFParser()
        sections = parser.parse(pdf_path, "my_paper")
        
        all_annots = []
        raw_annots = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            for annot in page.annots():
                if annot is None:
                    continue
                atype_name = annot.type[1]
                if atype_name not in self.supported_types:
                    continue
                all_annots.append({
                    "page_num": page_num,
                    "annot": annot,
                    "type": atype_name,
                    "page": page
                })
        
        for item in all_annots:
            page_num = item["page_num"]
            annot = item["annot"]
            atype = item["type"]
            page = item["page"]
            
            comment_text = ""
            highlighted_text = ""
            
            info = annot.info
            content = info.get("content", "").strip()
            if not content:
                content = info.get("subject", "").strip()
                
            if atype in ("Highlight", "Underline", "StrikeOut", "Squiggly"):
                highlighted_text = self._get_highlighted_text(page, annot)
                associated = self._find_associated_comment(page, annot, all_annots)
                if associated:
                    comment_text = associated
                else:
                    comment_text = content
                    if not comment_text and not self.extract_highlight_without_comment:
                        continue
            elif atype in ("Text", "FreeText"):
                comment_text = content
                if not comment_text:
                    continue
            
            if not comment_text and not highlighted_text:
                continue
                
            author = info.get("title", "").strip()
            rect = (annot.rect.x0, annot.rect.y0, annot.rect.x1, annot.rect.y1)
            section_name = self._find_section_name(page_num, annot.rect.y0, sections)
            
            raw_annots.append({
                "source_file": pdf_path.name,
                "annot_type": atype,
                "page_number": page_num + 1,
                "rect": rect,
                "highlighted_text": highlighted_text,
                "comment_text": comment_text,
                "author": author,
                "section_name": section_name,
            })
            
        labels = self._infer_reviewer_labels(raw_annots)
        
        results = []
        for i, raw in enumerate(raw_annots):
            results.append(RawAnnotation(
                annotation_id=f"annot_{i+1:03d}",
                source_file=raw["source_file"],
                annot_type=raw["annot_type"],
                page_number=raw["page_number"],
                rect=raw["rect"],
                highlighted_text=raw["highlighted_text"],
                comment_text=raw["comment_text"],
                author=raw["author"],
                reviewer_label=labels[i],
                section_name=raw["section_name"],
                section_order=0
            ))
            
        doc.close()
        return results

    def _get_highlighted_text(self, page: fitz.Page, annot: fitz.Annot) -> str:
        return page.get_textbox(annot.rect).replace("\n", " ").strip()

    def _find_associated_comment(self, page, annot, all_annots) -> str:
        best_comment = ""
        min_dist = 50.0
        
        for other in all_annots:
            if other["page_num"] != page.number or other["annot"] == annot:
                continue
            if other["type"] == "Text":
                o_annot = other["annot"]
                content = o_annot.info.get("content", "").strip()
                if not content:
                    continue
                dy = abs(annot.rect.y0 - o_annot.rect.y0)
                if dy < min_dist:
                    min_dist = dy
                    best_comment = content
                    
        return best_comment

    def _find_section_name(self, page_num: int, y0: float, sections: list) -> str:
        best_sec = "Unknown"
        for sec in sections:
            start_p, end_p = sec.page_range
            if start_p <= page_num <= end_p:
                best_sec = sec.section_name
        return best_sec

    def _infer_reviewer_labels(self, raw_annots: list[dict]) -> list[str]:
        authors = set(a["author"] for a in raw_annots if a["author"])
        author_to_label = {author: f"R{i+1}" for i, author in enumerate(sorted(authors))}
        return [author_to_label.get(a["author"], "R1") for a in raw_annots]
