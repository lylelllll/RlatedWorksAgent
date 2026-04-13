"""LLM-based suggestion generator."""

import asyncio

from loguru import logger

from src.config import Config
from src.generation.llm_client import LLMClient
from src.review_advisor import AnalyzedAnnotation, RevisionSuggestion


class SuggestionGenerator:
    """Generates revision suggestions using LLM based on intent and evidence."""

    def __init__(self, llm_client: LLMClient, config: Config):
        self.llm = llm_client
        self.config = config

    async def generate_batch(self, analyzed_annots: list[AnalyzedAnnotation]) -> list[RevisionSuggestion]:
        tasks = [self.generate_single(a) for a in analyzed_annots]
        return await asyncio.gather(*tasks)

    async def generate_single(self, analyzed: AnalyzedAnnotation) -> RevisionSuggestion:
        intent = analyzed.intent
        context = analyzed.context
        
        # Format evidence
        evidence_text = ""
        for i, ev in enumerate(analyzed.retrieved_evidence):
            title = ev.get("title", "Unknown")
            authors = ev.get("authors", "")
            year = ev.get("year", "")
            chunk = ev.get("text", "")
            evidence_text += f"[Evidence {i+1}] {title} ({authors}, {year})\nContent: {chunk[:500]}\n\n"
            
        system_prompt = (
            "You are a top-tier academic paper revision advisor. Help the author respond to "
            "the reviewer's comment with a high-quality, actionable revision plan.\n"
            "Produce JSON strictly matching this schema:\n"
            "{\n"
            "  \"problem_summary\": \"1-2 sentence summary of the issue\",\n"
            "  \"suggested_revision\": \"Detailed action plan\",\n"
            "  \"revised_text\": \"The new or revised text to insert\",\n"
            "  \"supporting_evidence\": [\"[Author et al., Year]\", ...],\n"
            "  \"response_to_reviewer\": \"Template for rebuttal letter\",\n"
            "  \"confidence\": 0.95\n"
            "}"
        )
        
        user_prompt = (
            f"Section: {context.section_name}\n"
            f"Original Text: \"{context.annotated_text}\"\n"
            f"Preceding: \"{context.preceding_text}\"\n"
            f"Following: \"{context.following_text}\"\n\n"
            f"Reviewer ({analyzed.raw.reviewer_label}) says:\n"
            f"\"{analyzed.raw.comment_text}\"\n"
            f"Intent Category: {intent.value}\n\n"
            f"Retrieved Evidence:\n{evidence_text if evidence_text else 'None'}"
        )
        
        try:
            res = await self.llm.generate_json(system_prompt, user_prompt)
            # handle case where res is a list containing the dict
            if isinstance(res, list) and len(res) > 0:
                res = res[0]
            if not isinstance(res, dict):
                res = {}
                
            conf = res.get("confidence", 0.5)
            if isinstance(conf, str):
                try: conf = float(conf)
                except ValueError: conf = 0.5
                
            return RevisionSuggestion(
                annotation_id=analyzed.raw.annotation_id,
                reviewer_label=analyzed.raw.reviewer_label,
                intent=intent,
                problem_summary=res.get("problem_summary", ""),
                suggested_revision=res.get("suggested_revision", ""),
                original_text=context.annotated_text,
                revised_text=res.get("revised_text", ""),
                supporting_evidence=res.get("supporting_evidence", []),
                response_to_reviewer=res.get("response_to_reviewer", ""),
                confidence=conf
            )
        except Exception as e:
            logger.error(f"Generation failed for {analyzed.raw.annotation_id}: {e}")
            return RevisionSuggestion(
                annotation_id=analyzed.raw.annotation_id,
                reviewer_label=analyzed.raw.reviewer_label,
                intent=intent,
                problem_summary="Error generating suggestion.",
                suggested_revision=str(e),
                original_text=context.annotated_text,
                revised_text="",
                supporting_evidence=[],
                response_to_reviewer="",
                confidence=0.0
            )

