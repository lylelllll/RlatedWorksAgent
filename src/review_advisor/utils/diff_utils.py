"""Diff utilities for comparing texts."""

import difflib

def generate_inline_diff(original: str, revised: str) -> str:
    """Generate Markdown format inline diff using difflib.ndiff."""
    if not revised:
        return original
    d = difflib.ndiff(original.split(), revised.split())
    result = []
    for token in d:
        if token.startswith('- '):
            result.append(f"~~{token[2:]}~~")
        elif token.startswith('+ '):
            result.append(f"**{token[2:]}**")
        elif token.startswith('  '):
            result.append(token[2:])
            
    # Clean up double spaces from joining
    return " ".join(result).replace("~~ **", "~~**")


def generate_latex_diff(original: str, revised: str) -> str:
    """Generate LaTeX textcolor format diff."""
    if not revised:
        return original
    d = difflib.ndiff(original.split(), revised.split())
    result = []
    for token in d:
        if token.startswith('- '):
            result.append(f"\\textcolor{{red}}{{{token[2:]}}}")
        elif token.startswith('+ '):
            result.append(f"\\textcolor{{blue}}{{{token[2:]}}}")
        elif token.startswith('  '):
            result.append(token[2:])
            
    return " ".join(result)
