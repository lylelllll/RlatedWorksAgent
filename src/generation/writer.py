"""Related Work 迭代生成与控制。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import Config
from src.generation.llm_client import LLMClient
from src.generation.prompt_builder import (
    GenerationContext, build_prompt, build_fix_prompt, FIX_SYSTEM_PROMPT,
)
from src.generation.scorer import DraftScore, Scorer
from src.utils.latex_utils import (
    extract_latex, validate_latex_syntax, build_bibliography_entries, build_compilable_tex,
)
from src.generation.bib_refiner import refine_bibliography


@dataclass
class IterationResult:
    """单轮迭代结果。"""
    draft: str
    score: DraftScore
    iteration: int


@dataclass
class FinalOutput:
    """最终输出。"""
    latex: str
    score: DraftScore
    bib: str = ""


async def iterative_generate(
    context: GenerationContext, config: Config
) -> FinalOutput:
    """迭代生成 Related Work 草稿。"""
    llm_client = LLMClient(config.llm)
    scorer = Scorer(config.scorer_llm)

    best_draft: str | None = None
    best_score: DraftScore | None = None
    all_iterations: list[IterationResult] = []

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = config.resolve_path(config.output.dir) / timestamp
    output_base.mkdir(parents=True, exist_ok=True)

    for i in range(1, config.generation.max_iterations + 1):
        logger.info(f"=== Iteration {i}/{config.generation.max_iterations} ===")

        # 构建 Prompt
        system_prompt, user_prompt = build_prompt(
            context=context,
            target_venue=config.generation.target_venue,
            language=config.generation.language,
            iteration=i,
            previous_draft=best_draft,
            prev_score=best_score,
        )

        # 生成 LaTeX
        raw_output = await llm_client.generate(system_prompt, user_prompt)
        latex_code = extract_latex(raw_output)

        # LaTeX 语法验证 + 自动修复
        is_valid, errors = validate_latex_syntax(latex_code, context.known_paper_ids)
        if not is_valid:
            logger.warning(f"  LaTeX 语法错误 ({len(errors)} 个)，尝试自动修复...")
            fix_prompt = build_fix_prompt(latex_code, errors)
            fix_output = await llm_client.generate(FIX_SYSTEM_PROMPT, fix_prompt)
            latex_code = extract_latex(fix_output)

        # 评分
        score = await scorer.score(latex_code, context)

        # 保存本轮结果
        if config.output.save_all_iterations:
            _save_iteration(latex_code, score, i, output_base)

        all_iterations.append(IterationResult(
            draft=latex_code, score=score, iteration=i,
        ))

        logger.info(
            f"  Score: {score.total:.2f}/10  |  "
            f"Coverage={score.coverage:.1f} "
            f"Comparison={score.comparison_quality:.1f} "
            f"Style={score.style_compliance:.1f}"
        )

        if best_score is None or score.total > best_score.total:
            best_draft, best_score = latex_code, score

    # 选择最优
    best = max(all_iterations, key=lambda x: x.score.total)
    logger.success(
        f"Best: iteration #{best.iteration} (score={best.score.total:.2f})"
    )

    # 生成 .bib 草稿
    all_chunks = context.background_chunks + context.comparison_chunks
    bib_content = build_bibliography_entries(all_chunks)

    # 保存草稿 bib（保留原始版本）
    draft_bib_path = output_base / "references_draft.bib"
    draft_bib_path.write_text(bib_content, encoding="utf-8")

    # LLM 精修 BibTeX
    refined_bib = bib_content
    if config.generation.refine_bib:
        try:
            refined_bib = await refine_bibliography(
                draft_bib=bib_content,
                latex_content=best.draft,
                llm_client=llm_client,
            )
        except Exception as e:
            logger.warning(f"BibTeX 精修失败，使用草稿版本: {e}")
            refined_bib = bib_content

    # 保存精修后的 bib
    refined_bib_path = output_base / "references.bib"
    refined_bib_path.write_text(refined_bib, encoding="utf-8")

    # 保存 Related Work 片段
    final_tex_path = output_base / "final_best.tex"
    final_tex_path.write_text(best.draft, encoding="utf-8")

    # 生成可编译的 main.tex
    compilable_tex = build_compilable_tex(
        related_work_latex=best.draft,
        bib_filename="references",
        bib_style=config.generation.latex_bib_style,
    )
    main_tex_path = output_base / "main.tex"
    main_tex_path.write_text(compilable_tex, encoding="utf-8")

    logger.success(f"输出已保存: {output_base}")
    logger.info(f"  final_best.tex  — Related Work 片段")
    logger.info(f"  main.tex        — 可编译完整 LaTeX")
    logger.info(f"  references.bib  — 精修参考文献")

    return FinalOutput(
        latex=best.draft, score=best.score, bib=refined_bib,
    )


def _save_iteration(
    latex_code: str, score: DraftScore, iteration: int, output_base: Path
) -> None:
    """保存单轮迭代结果。"""
    iter_dir = output_base / f"iteration_{iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    # LaTeX 草稿
    (iter_dir / "draft.tex").write_text(latex_code, encoding="utf-8")

    # Markdown 可读版
    md_content = f"# Related Work (Iteration {iteration})\n\n"
    md_content += "```latex\n" + latex_code + "\n```\n"
    (iter_dir / "draft_readable.md").write_text(md_content, encoding="utf-8")

    # 评分 JSON
    score_dict = {
        "total": round(score.total, 2),
        "coverage": round(score.coverage, 1),
        "accuracy": round(score.accuracy, 1),
        "comparison_quality": round(score.comparison_quality, 1),
        "style_compliance": round(score.style_compliance, 1),
        "coherence": round(score.coherence, 1),
        "novelty_highlight": round(score.novelty_highlight, 1),
        "latex_validity": round(score.latex_validity, 1),
        "improvement_suggestions": score.improvement_suggestions,
    }
    (iter_dir / "score.json").write_text(
        json.dumps(score_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )
