"""Build retrieval queries from intents."""

from src.config import Config
from src.review_advisor import AnalyzedAnnotation, AnnotationIntent


class QueryBuilder:
    """Builds retrieval queries based on annotation intent."""

    def __init__(self, config: Config):
        self.config = config

    def build_queries(self, analyzed: AnalyzedAnnotation) -> list[str]:
        intent = analyzed.intent
        context = analyzed.context
        
        queries = []
        if intent in (AnnotationIntent.MISSING_CITATION, AnnotationIntent.COMPARISON_NEEDED):
            if analyzed.reformulated_question:
                queries.append(analyzed.reformulated_question)
            if context.annotated_text:
                queries.append(context.annotated_text[:100])
        elif intent == AnnotationIntent.FACTUAL_ERROR:
            if analyzed.reformulated_question:
                queries.append(analyzed.reformulated_question)
        elif intent in (AnnotationIntent.LOGIC_GAP, AnnotationIntent.SCOPE_EXPANSION):
            if analyzed.reformulated_question:
                queries.append(analyzed.reformulated_question)
            if context.annotated_text:
                queries.append(context.annotated_text[:100])
                
        # writing_clarity, grammar_style, delete_content returns []
        return list(dict.fromkeys(queries))
