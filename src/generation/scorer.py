"""草稿质量评分——LLM 评分 + 程序级 LaTeX 验证。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from loguru import logger

from src.config import LLMConfig
from src.generation.llm_client import LLMClient
from src.generation.prompt_builder import GenerationContext
from src.utils.latex_utils import validate_latex_syntax


@dataclass
class DraftScore:
    """草稿评分结果。"""
    total: float = 0.0
    coverage: float = 0.0
    accuracy: float = 0.0
    comparison_quality: float = 0.0
    style_compliance: float = 0.0
    coherence: float = 0.0
    novelty_highlight: float = 0.0
    latex_validity: float = 0.0
    improvement_suggestions: list[str] = field(default_factory=list)


# 加权规则
WEIGHTS = {
    "coverage": 0.20,
    "accuracy": 0.20,
    "comparison_quality": 0.20,
    "style_compliance": 0.15,
    "coherence": 0.10,
    "novelty_highlight": 0.10,
    "latex_validity": 0.05,
}


SCORER_SYSTEM_PROMPT = """You are an expert academic writing evaluator. 
Score the given Related Work LaTeX draft on these dimensions (0-10 each):

1. coverage: How well does it cover the provided references?
2. accuracy: Are the descriptions of cited works accurate and not fabricated?
3. comparison_quality: Quality of lateral comparison with similar works
4. style_compliance: Does it match the target venue's writing style?
5. coherence: Is the text logically organized and flows well?
6. novelty_highlight: Does it effectively highlight the current paper's innovations?

Also provide 3-5 specific improvement suggestions.

Respond in JSON format:
{
    "coverage": 8.0,
    "accuracy": 7.5,
    "comparison_quality": 7.0,
    "style_compliance": 8.5,
    "coherence": 8.0,
    "novelty_highlight": 7.0,
    "improvement_suggestions": ["suggestion1", "suggestion2", ...]
}"""


class Scorer:
    """草稿评分器。"""

    def __init__(self, llm_config: LLMConfig):
        self.llm_client = LLMClient(llm_config)

    async def score(
        self, latex_code: str, context: GenerationContext
    ) -> DraftScore:
        """对草稿进行评分。"""
        # 1. 程序级 LaTeX 验证
        is_valid, errors = validate_latex_syntax(latex_code, context.known_paper_ids)
        latex_score = 10.0 if is_valid else max(0, 10.0 - len(errors) * 2)

        # 2. LLM 评分
        user_prompt = self._build_scorer_prompt(latex_code, context)

        try:
            result = await self.llm_client.generate_json(
                SCORER_SYSTEM_PROMPT, user_prompt
            )
        except Exception as e:
            logger.error(f"LLM 评分调用失败: {e}")
            result = {}

        # 3. 组装评分
        score = DraftScore(
            coverage=float(result.get("coverage", 5.0)),
            accuracy=float(result.get("accuracy", 5.0)),
            comparison_quality=float(result.get("comparison_quality", 5.0)),
            style_compliance=float(result.get("style_compliance", 5.0)),
            coherence=float(result.get("coherence", 5.0)),
            novelty_highlight=float(result.get("novelty_highlight", 5.0)),
            latex_validity=latex_score,
            improvement_suggestions=result.get("improvement_suggestions", []),
        )

        # 4. 计算加权总分
        score.total = sum(
            getattr(score, dim) * w for dim, w in WEIGHTS.items()
        )

        if errors:
            score.improvement_suggestions.extend(
                [f"[LaTeX Error] {e}" for e in errors[:3]]
            )

        return score

    def _build_scorer_prompt(
        self, latex_code: str, context: GenerationContext
    ) -> str:
        """构建评分 Prompt。"""
        parts = [
            "## Draft to Evaluate\n",
            f"```latex\n{latex_code}\n```\n",
            f"\n## Paper Title: {context.my_paper.title}\n",
            f"\n## Paper Abstract:\n{context.my_paper.abstract}\n",
            f"\n## Number of background references provided: {len(context.background_chunks)}",
            f"## Number of comparison references provided: {len(context.comparison_chunks)}",
            f"\n## Available paper IDs: {', '.join(sorted(context.known_paper_ids))}",
            f"\n## Target venue style:",
            f"  - Word count: ~{context.venue_style.avg_word_count}",
            f"  - Paragraphs: ~{context.venue_style.avg_paragraph_count}",
            f"  - Subsections: {'Yes' if context.venue_style.has_subsections else 'No'}",
        ]
        return "\n".join(parts)
