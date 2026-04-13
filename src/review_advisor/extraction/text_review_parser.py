"""Parse pure text review files."""

from pathlib import Path
from loguru import logger

from src.generation.llm_client import LLMClient
from src.review_advisor import RawAnnotation


class TextReviewParser:
    """Parses text review comments using LLM-fallback structure extraction."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def parse(self, file_path: Path) -> list[RawAnnotation]:
        logger.info(f"Parsing text review from {file_path.name}")
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Cannot read text review file {file_path}: {e}")
            return []
            
        system_prompt = (
            "You are an assistant that extracts individual reviewer comments "
            "from a plaintext review file. Extract each distinct comment into a JSON list. "
            "Only return valid JSON in the exact format: "
            "{\"comments\": [{\"reviewer_label\": \"R1\", \"comment_text\": \"...\"}, ...]}"
        )
        
        user_prompt = f"Extract from the following review text:\n\n{content}"
        
        extracted = []
        try:
            result = await self.llm.generate_json(system_prompt, user_prompt)
            if isinstance(result, dict) and "comments" in result:
                extracted = result["comments"]
            elif isinstance(result, list):
                extracted = result
        except Exception as e:
            logger.error(f"Failed to parse text review with LLM: {e}")
            
        results = []
        for i, item in enumerate(extracted):
            r_label = item.get("reviewer_label", "R1")
            c_text = item.get("comment_text", "").strip()
            if not c_text:
                continue
                
            results.append(RawAnnotation(
                annotation_id=f"txt_{i+1:03d}",
                source_file=file_path.name,
                annot_type="TextReview",
                page_number=-1,
                rect=None,
                highlighted_text="",
                comment_text=c_text,
                author=r_label,
                reviewer_label=r_label,
                section_name="Unknown",
                section_order=0
            ))
            
        return results
