"""Related Work Agent 主流程编排 + CLI 入口。"""

from __future__ import annotations

import asyncio
import argparse
from pathlib import Path

from loguru import logger

from src.config import Config, load_config
from src.utils.logging_utils import setup_logging


async def run_pipeline(config: Config) -> None:
    """主流程，分 5 个阶段执行。"""
    from src.ingestion.pdf_parser import parse_pdf_directory
    from src.ingestion.my_paper_parser import parse_my_paper
    from src.ingestion.chunker import chunk_sections
    from src.indexing.embedder import Embedder
    from src.indexing.vector_store import VectorStore
    from src.retrieval.retriever import retrieve_chunks
    from src.style_analyzer.venue_analyzer import analyze_venue_style
    from src.generation.prompt_builder import GenerationContext
    from src.generation.writer import iterative_generate

    # ── Phase 1: 并行解析所有 PDF ────────────────────────────
    logger.info("[Phase 1] Parsing PDFs in parallel...")
    bg_sections, cmp_sections, venue_sections, my_paper = await asyncio.gather(
        parse_pdf_directory(
            config.resolve_path(config.data.background_papers_dir),
            "background",
            max_workers=config.parallel.max_pdf_workers,
        ),
        parse_pdf_directory(
            config.resolve_path(config.data.comparison_papers_dir),
            "comparison",
            max_workers=config.parallel.max_pdf_workers,
        ),
        parse_pdf_directory(
            config.resolve_path(config.data.venue_style_papers_dir),
            "venue_style",
            max_workers=config.parallel.max_pdf_workers,
        ),
        parse_my_paper(config.resolve_path(config.data.my_paper_dir)),
    )

    if not my_paper.title and not my_paper.abstract:
        logger.error("未能解析用户论文，请检查 data/my_paper/ 目录")
        return

    logger.info(f"  用户论文: {my_paper.title}")
    logger.info(f"  背景论文章节: {len(bg_sections)} | 对比论文章节: {len(cmp_sections)} | 风格论文章节: {len(venue_sections)}")

    # ── Phase 2: 分块 ────────────────────────────────────────
    logger.info("[Phase 2] Chunking...")
    all_chunks = chunk_sections(bg_sections + cmp_sections, config)

    if not all_chunks:
        logger.error("未生成任何 chunk，请检查论文目录中是否有 PDF 文件")
        return

    # ── Phase 3: 建立/加载索引 ───────────────────────────────
    logger.info("[Phase 3] Building indexes...")
    embedder = Embedder(
        model_name=config.retrieval.embedding_model,
        batch_size=config.parallel.embedding_batch_size,
    )
    vector_store = VectorStore(
        persist_dir=str(config.resolve_path("vectordb/chroma_db")),
        embedder=embedder,
    )

    skip_indexing = getattr(config, "_force_skip_indexing", False)
    if skip_indexing and vector_store.exists():
        logger.info("  跳过索引构建（使用已有索引）")
    else:
        # Dense 索引
        vector_store.clear()
        vector_store.add_chunks(all_chunks)

        # ColBERT 索引（可选）
        if config.retrieval.use_colbert:
            try:
                from src.indexing.colbert_indexer import ColBERTIndexer
                colbert = ColBERTIndexer(
                    model_name=config.retrieval.colbert_model,
                    index_dir=str(config.resolve_path("vectordb/colbert_index")),
                )
                if not colbert.index_exists():
                    docs = [c.text for c in all_chunks]
                    doc_ids = [c.chunk_id for c in all_chunks]
                    colbert.build_index(docs, doc_ids)
            except ImportError:
                logger.warning("RAGatouille 未安装，跳过 ColBERT 索引。"
                               "安装: pip install 'related-work-agent[colbert]'")

    # ── Phase 4: 并行：检索 + 风格分析 ──────────────────────
    logger.info("[Phase 4] Retrieval & Style Analysis...")
    retrieved_chunks, venue_style = await asyncio.gather(
        retrieve_chunks(my_paper, config),
        analyze_venue_style(venue_sections, config),
    )

    background_chunks = [c for c in retrieved_chunks if c.get("paper_type") == "background"]
    comparison_chunks = [c for c in retrieved_chunks if c.get("paper_type") == "comparison"]

    logger.info(f"  检索结果: {len(background_chunks)} background + {len(comparison_chunks)} comparison")

    # ── Phase 5: 迭代生成 ──────────────────────────────────
    logger.info("[Phase 5] Iterative generation...")
    known_ids = set()
    for c in retrieved_chunks:
        meta = c.get("metadata", {})
        pid = meta.get("paper_id", "")
        if pid:
            known_ids.add(pid)

    context = GenerationContext(
        my_paper=my_paper,
        background_chunks=background_chunks,
        comparison_chunks=comparison_chunks,
        venue_style=venue_style,
        known_paper_ids=known_ids,
    )

    output = await iterative_generate(context, config)

    logger.success(
        f"Done! Final score: {output.score.total:.2f}/10  |  "
        f"Output: {config.output.dir}/"
    )


def main():
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="Related Work Agent — 自动生成 Related Work 章节",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  rwa                              # 使用默认 config.yaml 运行
  rwa --config my_config.yaml      # 指定配置文件
  rwa --skip-indexing              # 跳过索引重建
  rwa --iterations 1               # 只运行 1 轮（快速测试）
        """,
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="配置文件路径 (default: config.yaml)",
    )
    parser.add_argument(
        "--skip-indexing", action="store_true",
        help="跳过索引重建（索引已存在时使用）",
    )
    parser.add_argument(
        "--iterations", type=int,
        help="覆盖迭代轮次",
    )
    args = parser.parse_args()

    # 初始化日志
    setup_logging()

    # 加载配置
    config = load_config(args.config)
    if args.skip_indexing:
        object.__setattr__(config, "_force_skip_indexing", True)
    if args.iterations:
        config.generation.max_iterations = args.iterations

    # 运行
    asyncio.run(run_pipeline(config))


if __name__ == "__main__":
    main()
