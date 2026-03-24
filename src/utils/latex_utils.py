"""LaTeX 格式处理工具——提取、转义、验证、bib 生成。"""

from __future__ import annotations

import re
from dataclasses import dataclass


def extract_latex(llm_output: str) -> str:
    """从 LLM 输出中提取 LaTeX 代码，去除 ```latex ``` 包裹等冗余内容。"""
    # 尝试提取 ```latex ... ``` 块
    pattern = r"```(?:latex|tex)\s*\n(.*?)```"
    match = re.search(pattern, llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 尝试提取 ``` ... ``` 块
    pattern2 = r"```\s*\n(.*?)```"
    match2 = re.search(pattern2, llm_output, re.DOTALL)
    if match2:
        code = match2.group(1).strip()
        if "\\section" in code or "\\subsection" in code:
            return code

    # 如果输出本身包含 \section，直接使用
    if "\\section" in llm_output:
        # 从 \section 开始截取
        idx = llm_output.index("\\section")
        return llm_output[idx:].strip()

    return llm_output.strip()


# 需要转义的 LaTeX 特殊字符（\ 不在此列因为可能是命令前缀）
_SPECIAL_CHARS = {
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "#": r"\#",
    "$": r"\$",
    "^": r"\^{}",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
}


def escape_special_chars(text: str) -> str:
    """转义 LaTeX 特殊字符，保留已有的 LaTeX 命令不受影响。"""
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1].isalpha():
            # 已有 LaTeX 命令，保留
            j = i + 1
            while j < len(text) and text[j].isalpha():
                j += 1
            result.append(text[i:j])
            i = j
        elif ch in _SPECIAL_CHARS:
            # 检查是否已经被转义
            if i > 0 and text[i - 1] == "\\":
                result.append(ch)
            else:
                result.append(_SPECIAL_CHARS[ch])
            i += 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


def validate_latex_syntax(
    code: str, known_paper_ids: set[str] | None = None
) -> tuple[bool, list[str]]:
    """
    程序级 LaTeX 语法验证。

    Returns:
        (is_valid, error_messages)
    """
    errors: list[str] = []

    # 1. \begin{} / \end{} 配对检查
    begins = re.findall(r"\\begin\{(\w+)\}", code)
    ends = re.findall(r"\\end\{(\w+)\}", code)
    begin_counts: dict[str, int] = {}
    end_counts: dict[str, int] = {}
    for b in begins:
        begin_counts[b] = begin_counts.get(b, 0) + 1
    for e in ends:
        end_counts[e] = end_counts.get(e, 0) + 1
    for env in set(list(begin_counts.keys()) + list(end_counts.keys())):
        bc = begin_counts.get(env, 0)
        ec = end_counts.get(env, 0)
        if bc != ec:
            errors.append(
                f"环境 '{env}' 不匹配: {bc} 个 \\begin vs {ec} 个 \\end"
            )

    # 2. \cite{} 中的 ID 验证
    if known_paper_ids:
        cite_ids = re.findall(r"\\cite\{([^}]+)\}", code)
        for cite_group in cite_ids:
            for cid in cite_group.split(","):
                cid = cid.strip()
                if cid and cid not in known_paper_ids:
                    errors.append(f"\\cite{{{cid}}} 中的 ID 不在已知论文列表中")

    # 3. 未转义特殊字符检测
    # 排除 LaTeX 命令中使用的字符
    lines = code.split("\n")
    for line_no, line in enumerate(lines, 1):
        # 跳过注释行
        if line.strip().startswith("%"):
            continue
        # 检测裸 & （不在 tabular 环境中时可能有问题，但此处只做初步检查）
        # 检测裸 _ 和 #（不在命令参数内）
        for ch in ["#"]:
            # 简单检测：如果字符前没有 \，可能有问题
            for i, c in enumerate(line):
                if c == ch and (i == 0 or line[i - 1] != "\\"):
                    # 排除一些常见的合法用法
                    if ch == "#" and "\\#" not in line:
                        errors.append(
                            f"第 {line_no} 行可能有未转义的 '{ch}'"
                        )
                        break

    is_valid = len(errors) == 0
    return is_valid, errors


def build_bibliography_entries(chunks: list) -> str:
    """根据 chunks 的 metadata 生成 .bib 条目草稿。"""
    seen: set[str] = set()
    bib_entries: list[str] = []

    for chunk in chunks:
        meta = chunk.get("metadata", {}) if isinstance(chunk, dict) else getattr(chunk, "metadata", {})
        paper_id = meta.get("paper_id", "")
        if not paper_id or paper_id in seen:
            continue
        seen.add(paper_id)

        title = meta.get("title", "Unknown Title")
        authors = meta.get("authors", "Unknown Authors")
        year = meta.get("year", 2024)
        venue = meta.get("venue", "")

        entry = (
            f"@inproceedings{{{paper_id},\n"
            f"  title={{{title}}},\n"
            f"  author={{{authors}}},\n"
            f"  year={{{year}}},\n"
        )
        if venue:
            entry += f"  booktitle={{{venue}}},\n"
        entry += "}\n"
        bib_entries.append(entry)

    return "\n".join(bib_entries)


def build_compilable_tex(
    related_work_latex: str,
    bib_filename: str = "references",
    bib_style: str = "IEEEtran",
) -> str:
    """
    将 Related Work LaTeX 片段包装为可编译的完整 .tex 文件。

    Args:
        related_work_latex: \\section{Related Work} ... 的 LaTeX 代码
        bib_filename: .bib 文件名（不含扩展名）
        bib_style: 参考文献样式（IEEEtran, ACM, plain 等）

    Returns:
        完整的 .tex 文件内容
    """
    template = r"""\documentclass[journal]{{IEEEtran}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{amsmath,amssymb}}
\usepackage{{cite}}
\usepackage{{hyperref}}
\usepackage{{url}}

\begin{{document}}

\title{{Related Work}}
\maketitle

{content}

\bibliographystyle{{{bib_style}}}
\bibliography{{{bib_filename}}}

\end{{document}}
"""
    return template.format(
        content=related_work_latex,
        bib_style=bib_style,
        bib_filename=bib_filename,
    )
