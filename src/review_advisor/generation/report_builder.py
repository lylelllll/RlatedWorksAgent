"""Report building utilities."""

from pathlib import Path

from src.config import Config
from src.review_advisor import ReviewReport, RevisionSuggestion


class ReportBuilder:
    """Assembles final markdown reports and rebuttal templates."""

    def __init__(self, config: Config):
        self.config = config

    def build_markdown_report(self, suggestions: list[RevisionSuggestion], report: ReviewReport) -> str:
        lines = [
            "# Review Response Report",
            f"**Generated**: {report.timestamp}",
            f"**Total Annotations**: {report.total_annotations} | **Processed**: {report.processed_annotations}",
            "",
            "## Intent Distribution",
            "| Intent | Count |",
            "|---|---|",
        ]
        
        for k, v in report.intent_summary.items():
            lines.append(f"| {k} | {v} |")
        lines.append("\n---\n")
        
        by_reviewer = {}
        for s in suggestions:
            by_reviewer.setdefault(s.reviewer_label, []).append(s)
            
        for reviewer in sorted(by_reviewer.keys()):
            lines.append(f"## {reviewer}\n")
            for s in by_reviewer[reviewer]:
                lines.append(f"### [{s.annotation_id}] `{s.intent.value}`")
                lines.append(f"> **Original**: {s.original_text}")
                lines.append(f"**Problem**: {s.problem_summary}")
                lines.append(f"**Revision**: {s.suggested_revision}")
                if s.revised_text:
                    lines.append("```text\n" + s.revised_text + "\n```")
                if s.supporting_evidence:
                    lines.append(f"**Evidence**: {', '.join(s.supporting_evidence)}")
                lines.append(f"**Response**:\n> {s.response_to_reviewer}\n")
                lines.append("---\n")
                
        return "\n".join(lines)

    def build_rebuttal_template(self, suggestions: list[RevisionSuggestion]) -> str:
        by_reviewer = {}
        for s in suggestions:
            by_reviewer.setdefault(s.reviewer_label, []).append(s)
            
        lines = ["# Rebuttal Letter Template\n"]
        for reviewer in sorted(by_reviewer.keys()):
            lines.append(f"## Response to {reviewer}\n")
            for s in by_reviewer[reviewer]:
                lines.append(f"**Comment {s.annotation_id}**:")
                lines.append(f"*Issue*: {s.problem_summary}\n")
                lines.append(f"**Response**:\n{s.response_to_reviewer}\n")
        return "\n".join(lines)

    def build_per_comment_files(self, suggestions: list[RevisionSuggestion], output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for s in suggestions:
            content = (
                f"# {s.annotation_id} - {s.intent.value}\n\n"
                f"## Problem\n{s.problem_summary}\n\n"
                f"## Suggested Revision\n{s.suggested_revision}\n\n"
                f"## Revised Text\n```\n{s.revised_text}\n```\n\n"
                f"## Response\n> {s.response_to_reviewer}\n"
            )
            file_path = output_dir / f"{s.reviewer_label}_{s.annotation_id}_{s.intent.value}.md"
            file_path.write_text(content, encoding="utf-8")
