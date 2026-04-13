"""Assemble context from paper sections."""

from rapidfuzz import fuzz

from src.config import Config
from src.review_advisor import RawAnnotation, AnnotationContext
from src.ingestion.pdf_parser import ParsedSection


class ContextAssembler:
    """Locates annotation contexts via fuzzy matching within sections."""

    def __init__(self, config: Config):
        self.config = config

    async def assemble(self, annot: RawAnnotation, paper_sections: list[ParsedSection]) -> AnnotationContext:
        if annot.annot_type == "TextReview" or not annot.highlighted_text:
            return self._empty_context(annot)
            
        best_section = next((sec for sec in paper_sections if sec.section_name == annot.section_name), None)
        
        if not best_section and paper_sections:
            best_section = paper_sections[0]
            
        if not best_section:
            return self._empty_context(annot)
            
        text = best_section.text
        
        # Simple fuzzy positioning using rapidfuzz string comparison
        # A more robust implementation would use sliding windows for fuzz.partial_ratio
        # This is a performant heuristic:
        fragment = annot.highlighted_text[:50]
        idx = text.find(fragment)
        
        if idx == -1 and len(annot.highlighted_text) > 20:
            fragment = annot.highlighted_text[-50:]
            idx = text.find(fragment)
            if idx != -1:
                idx = max(0, idx - len(annot.highlighted_text) + len(fragment))
                
        preceding = ""
        following = ""
        paragraph = text
        
        if idx != -1:
            start_idx = max(0, idx - 400)
            end_idx = min(len(text), idx + len(annot.highlighted_text) + 400)
            preceding = text[start_idx:idx].split('.')[-3:] # Last 3 sentences heuristic
            preceding = ".".join(preceding).strip()
            
            following_full = text[idx + len(annot.highlighted_text):end_idx].split('.')
            following = ".".join(following_full[:3]).strip()
            
        return AnnotationContext(
            annotation_id=annot.annotation_id,
            preceding_text=preceding,
            annotated_text=annot.highlighted_text,
            following_text=following,
            full_paragraph=paragraph[:1500],
            section_name=annot.section_name,
            page_number=annot.page_number
        )
        
    def _empty_context(self, annot: RawAnnotation) -> AnnotationContext:
        return AnnotationContext(
            annotation_id=annot.annotation_id,
            preceding_text="",
            annotated_text=annot.highlighted_text,
            following_text="",
            full_paragraph="",
            section_name=annot.section_name,
            page_number=annot.page_number
        )
