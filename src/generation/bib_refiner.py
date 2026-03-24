"""BibTeX 精修模块——利用 LLM 将草稿 bib 条目修正为准确的学术引用。"""

from __future__ import annotations

import re

from loguru import logger

from src.generation.llm_client import LLMClient


# ── Prompt 模板 ──────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert academic reference librarian. Your task is to refine \
draft BibTeX entries into accurate, complete bibliographic records.

You will be given:
1. Draft BibTeX entries (generated from PDF filenames, with placeholder data)
2. A LaTeX Related Work section that cites these entries (providing contextual clues about authors, venues, years)

For each entry, you must:
- Keep the EXACT SAME citation key (do NOT change it)
- Infer the correct: title, author(s), year, journal/booktitle, volume, number, pages, DOI
- Use proper BibTeX formatting (@article, @inproceedings, @incollection, etc.)
- Use "and" to separate authors in the author field
- Protect proper nouns and acronyms in titles with braces, e.g., {UAV}, {IoT}
- If you cannot determine a field with confidence, omit it rather than guess

Output ONLY the complete .bib file content, no explanations or markdown fences.\
"""

_USER_PROMPT_TEMPLATE = """\
## Draft BibTeX Entries

{draft_bib}

## LaTeX Related Work Section (for context)

{latex_content}

Please output the refined .bib file with accurate bibliographic data for every entry.\
"""


async def refine_bibliography(
    draft_bib: str,
    latex_content: str,
    llm_client: LLMClient,
) -> str:
    """
    利用 LLM 精修 BibTeX 草稿条目。

    Args:
        draft_bib: 由 build_bibliography_entries() 生成的草稿 .bib 内容
        latex_content: 最终的 LaTeX Related Work 正文（提供引用上下文）
        llm_client: 已初始化的 LLM 客户端

    Returns:
        精修后的 .bib 文件内容
    """
    if not draft_bib.strip():
        logger.warning("草稿 bib 为空，跳过精修")
        return draft_bib

    logger.info("[BibRefiner] 使用 LLM 精修 BibTeX 条目...")

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        draft_bib=draft_bib,
        latex_content=latex_content,
    )

    raw_output = await llm_client.generate(_SYSTEM_PROMPT, user_prompt)

    # 清理 LLM 输出（去除可能的 markdown 代码块包裹）
    refined = _clean_bib_output(raw_output)

    # 验证：确保所有原始 citation key 都存在于输出中
    original_keys = _extract_citation_keys(draft_bib)
    refined_keys = _extract_citation_keys(refined)

    missing_keys = original_keys - refined_keys
    if missing_keys:
        logger.warning(
            f"[BibRefiner] LLM 输出缺少 {len(missing_keys)} 个引用键: {missing_keys}"
        )
        # 将缺失的条目从草稿中补回
        for key in missing_keys:
            entry = _extract_entry_by_key(draft_bib, key)
            if entry:
                refined += "\n" + entry + "\n"

    # 在文件头添加注释
    header = (
        "% ============================================================\n"
        "% 参考文献（由 LLM 自动精修，建议人工核验 DOI 和页码）\n"
        "% ============================================================\n\n"
    )

    logger.success(f"[BibRefiner] 精修完成，共 {len(_extract_citation_keys(refined))} 个条目")
    return header + refined


def _clean_bib_output(raw: str) -> str:
    """清理 LLM 输出，提取纯 .bib 内容。"""
    # 去除 ```bibtex ... ``` 或 ```bib ... ``` 包裹
    pattern = r"```(?:bibtex|bib|latex)?\s*\n(.*?)```"
    match = re.search(pattern, raw, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果输出以 @ 开头，直接使用
    if raw.strip().startswith("@"):
        return raw.strip()

    # 尝试找到第一个 @ 开头的位置
    idx = raw.find("@")
    if idx >= 0:
        return raw[idx:].strip()

    return raw.strip()


def _extract_citation_keys(bib_content: str) -> set[str]:
    """从 .bib 内容中提取所有 citation key。"""
    return set(re.findall(r"@\w+\{([^,\s]+)", bib_content))


def _extract_entry_by_key(bib_content: str, key: str) -> str | None:
    """从 .bib 内容中提取指定 key 的完整条目。"""
    # 找到 @type{key, 开始到对应的 } 结束
    escaped_key = re.escape(key)
    pattern = rf"(@\w+\{{{escaped_key},.*?\n\}})"
    match = re.search(pattern, bib_content, re.DOTALL)
    return match.group(1) if match else None
