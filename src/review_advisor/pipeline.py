"""Main pipeline for Review Advisor."""

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import load_config, Config
from src.generation.llm_client import LLMClient
from src.ingestion.pdf_parser import parse_pdf_directory

from src.review_advisor import AnalyzedAnnotation, ReviewReport
from src.review_advisor.extraction import AnnotationExtractor, TextReviewParser, ContextAssembler
from src.review_advisor.analysis import IntentClassifier, QueryBuilder
from src.review_advisor.generation import SuggestionGenerator, ReportBuilder
from src.review_advisor.retriever_adapter import ReviewRetriever

def indexes_exist(config: Config) -> bool:
    vdb_path = config.resolve_path("vectordb/chroma_db")
    return vdb_path.exists() and any(vdb_path.iterdir())


async def run_review_pipeline(config: Config) -> None:
    logger.info("[Step 0] Loading existing RAG indexes...")
    if not indexes_exist(config):
        logger.warning("RAG indexes not found! Run 'rwa' first to build indexes.")
        raise SystemExit(1)
        
    retriever = ReviewRetriever(config)
    llm_client = LLMClient(config.llm)
    scorer_llm = LLMClient(config.scorer_llm)
    
    logger.info("[Step 1] Scanning review_input/...")
    review_cfg = getattr(config, "review_advisor", {})
    input_dir = config.resolve_path(review_cfg.get("input_dir", "data/review_input"))
    
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        raise SystemExit(1)
        
    pdf_files = list(input_dir.glob("*.pdf"))
    txt_files = list(input_dir.glob("*.txt")) + list(input_dir.glob("*.md"))
    
    logger.info("[Step 2] Parsing my_paper for context assembly...")
    my_paper_dir = config.resolve_path(config.data.my_paper_dir)
    my_paper_sections = await parse_pdf_directory(my_paper_dir, "my_paper")
    
    logger.info("[Step 3] Extracting annotations in parallel...")
    extractor = AnnotationExtractor(config)
    txt_parser = TextReviewParser(llm_client)
    assembler = ContextAssembler(config)
    
    all_raw_annots = []
    
    extraction_tasks = (
        [extractor.extract_from_pdf(f) for f in pdf_files] +
        [txt_parser.parse(f) for f in txt_files]
    )
    if not extraction_tasks:
        logger.warning("No input files found in review_input/")
        return
        
    results = await asyncio.gather(*extraction_tasks)
    for r in results:
        all_raw_annots.extend(r)
        
    logger.info(f"  Extracted {len(all_raw_annots)} annotations total.")
    if not all_raw_annots:
        logger.warning("No annotations extracted. Exiting.")
        return
    
    logger.info("[Step 4] Assembling annotation contexts...")
    contexts = await asyncio.gather(
        *[assembler.assemble(a, my_paper_sections) for a in all_raw_annots]
    )
    
    logger.info("[Step 5] Classifying annotation intents...")
    classifier = IntentClassifier(scorer_llm, config)
    classified = await classifier.classify_batch(all_raw_annots, list(contexts))
    
    analyzed_annots = [
        AnalyzedAnnotation(raw=a, context=c, intent=i, reformulated_question=q, intent_reasoning=r)
        for a, c, (i, r, q) in zip(all_raw_annots, contexts, classified)
    ]
    
    logger.info("[Step 6] Retrieving evidence from knowledge base...")
    query_builder = QueryBuilder(config)
    top_k = review_cfg.get("retrieval", {}).get("cross_encoder_top_k", 5)
    
    async def retrieve_for_annot(analyzed: AnalyzedAnnotation) -> AnalyzedAnnotation:
        queries = query_builder.build_queries(analyzed)
        if not queries:
            return analyzed
            
        bg_ev = await retriever.retrieve_by_queries(queries, paper_type="background", top_k=top_k)
        comp_ev = await retriever.retrieve_by_queries(queries, paper_type="comparison", top_k=top_k)
        
        combined = bg_ev + comp_ev
        combined.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        analyzed.retrieved_evidence = combined[:top_k]
        return analyzed
        
    analyzed_annots = await asyncio.gather(
        *[retrieve_for_annot(a) for a in analyzed_annots]
    )
    
    logger.info("[Step 7] Generating revision suggestions...")
    generator = SuggestionGenerator(llm_client, config)
    suggestions = await generator.generate_batch(list(analyzed_annots))
    
    logger.info("[Step 8] Building report...")
    intent_summary = {}
    for s in suggestions:
        val = s.intent.value
        intent_summary[val] = intent_summary.get(val, 0) + 1
        
    report = ReviewReport(
        source_files=[str(f.name) for f in pdf_files + txt_files],
        total_annotations=len(all_raw_annots),
        processed_annotations=len(suggestions),
        suggestions=suggestions,
        intent_summary=intent_summary,
        timestamp=datetime.now().isoformat(),
    )
    
    builder = ReportBuilder(config)
    
    out_dir_name = report.timestamp.replace(":", "").replace("-", "").replace("T", "_").split(".")[0]
    output_base_dir = config.resolve_path(review_cfg.get("output", {}).get("dir", "outputs"))
    output_dir = output_base_dir / f"review_{out_dir_name}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    md_report = builder.build_markdown_report(suggestions, report)
    (output_dir / "review_report.md").write_text(md_report, encoding="utf-8")
    
    rebuttal = builder.build_rebuttal_template(suggestions)
    (output_dir / "rebuttal_template.md").write_text(rebuttal, encoding="utf-8")
    
    def default_serializer(obj):
        from enum import Enum
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Type {type(obj)} is not JSON serializable")

    (output_dir / "annotations_parsed.json").write_text(
        json.dumps([asdict(a) for a in analyzed_annots], ensure_ascii=False, indent=2, default=default_serializer)
    )
    
    if review_cfg.get("output", {}).get("save_per_comment", True):
        builder.build_per_comment_files(suggestions, output_dir / "per_comment")
        
    logger.success(f"Done! Report saved to: {output_dir}/review_report.md")
    logger.info(f"Rebuttal template: {output_dir}/rebuttal_template.md")
    logger.info(f"Total: {len(suggestions)} suggestions generated.")


def main():
    parser = argparse.ArgumentParser(description="RWA Review Advisor")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--input", help="Override input_dir in config")
    parser.add_argument("--no-per-comment", action="store_true", help="Do not generate per_comment/ dir")
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    # Safely load defaults if config doesn't have review_advisor populated properly
    import yaml
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            raw_cfg = yaml.safe_load(f) or {}
        review_cfg = raw_cfg.get("review_advisor", {})
    except Exception:
        review_cfg = {}
        
    object.__setattr__(config, "review_advisor", review_cfg)
        
    if args.input:
        config.review_advisor["input_dir"] = args.input
        
    if args.no_per_comment:
        if "output" not in config.review_advisor:
            config.review_advisor["output"] = {}
        config.review_advisor["output"]["save_per_comment"] = False
        
    asyncio.run(run_review_pipeline(config))

if __name__ == "__main__":
    main()
