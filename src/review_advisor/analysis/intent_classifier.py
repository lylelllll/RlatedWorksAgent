"""Classify annotation intents with LLM."""

import asyncio
from typing import Tuple

from loguru import logger

from src.config import Config
from src.generation.llm_client import LLMClient
from src.review_advisor import (
    RawAnnotation, AnnotationContext, AnnotationIntent
)


class IntentClassifier:
    """Classifies annotation intent and builds search questions using LLM."""

    def __init__(self, scorer_llm: LLMClient, config: Config):
        self.llm = scorer_llm
        self.config = config
        
        review_cfg = getattr(config, "review_advisor", {})
        intent_cfg = review_cfg.get("intent_classification", {})
        self.batch_size = intent_cfg.get("batch_size", 10)

    async def classify_batch(
        self,
        annots: list[RawAnnotation],
        contexts: list[AnnotationContext]
    ) -> list[Tuple[AnnotationIntent, str, str]]:
        """Process annotations in parallel batches."""
        results = []
        for i in range(0, len(annots), self.batch_size):
            batch_annots = annots[i:i + self.batch_size]
            batch_ctx = contexts[i:i + self.batch_size]
            
            tasks = [self.classify_single(a, c) for a, c in zip(batch_annots, batch_ctx)]
            batch_result = await asyncio.gather(*tasks)
            results.extend(batch_result)
            
        return results

    async def classify_single(
        self, annot: RawAnnotation, context: AnnotationContext
    ) -> Tuple[AnnotationIntent, str, str]:
        system_prompt = (
            "You are an expert academic paper reviewer. Analyze the review comment and:\n"
            "1. Classify the intent into one of: missing_citation, factual_error, logic_gap, "
            "comparison_needed, writing_clarity, grammar_style, structure_suggestion, "
            "scope_expansion, delete_content, undefined.\n"
            "2. Reformulate the comment into a specific academic question (in English) "
            "to query a literature database.\n\n"
            "Output JSON:\n"
            "{\"intent\": \"...\", \"reasoning\": \"...\", \"reformulated_question\": \"...\"}"
        )
        
        user_prompt = (
            f"Section: {context.section_name}\n"
            f"Annotated Text: \"{context.annotated_text}\"\n"
            f"Preceding Context: \"{context.preceding_text}\"\n"
            f"Reviewer Comment: \"{annot.comment_text}\""
        )
        
        try:
            res = await self.llm.generate_json(system_prompt, user_prompt)
            intent_str = res.get("intent", "undefined")
            try:
                intent = AnnotationIntent(intent_str)
            except ValueError:
                intent = AnnotationIntent.UNDEFINED
                
            reason = res.get("reasoning", "")
            q = res.get("reformulated_question", "")
            return intent, reason, q
        except Exception as e:
            logger.error(f"Intent classification failed for {annot.annotation_id}: {e}")
            return AnnotationIntent.UNDEFINED, str(e), ""
