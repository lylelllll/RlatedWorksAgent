"""多阶段检索——Dense + (可选 ColBERT) + Cross-Encoder，多 Query RRF 合并。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from loguru import logger

from src.config import Config
from src.indexing.embedder import Embedder
from src.indexing.vector_store import VectorStore
from src.ingestion.my_paper_parser import MyPaperContext
from src.retrieval.reranker import Reranker


def _reciprocal_rank_fusion(
    result_lists: list[list[dict]], k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion——合并多组检索结果。

    RRF(d) = Σ 1 / (k + rank_i(d))
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, dict] = {}

    for results in result_lists:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc.get("chunk_id", doc.get("metadata", {}).get("chunk_id", str(rank)))
            rrf_scores[doc_id] += 1.0 / (k + rank)
            if doc_id not in doc_map:
                doc_map[doc_id] = doc

    # 按 RRF 分数降序排列
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    results = []
    for doc_id in sorted_ids:
        doc = doc_map[doc_id].copy()
        doc["rrf_score"] = rrf_scores[doc_id]
        results.append(doc)

    return results


def _build_queries(my_paper: MyPaperContext) -> list[str]:
    """从用户论文上下文构建多维度查询。"""
    queries = []

    if my_paper.abstract:
        queries.append(my_paper.abstract)

    if my_paper.contributions:
        queries.append(" ".join(my_paper.contributions))

    if my_paper.title:
        queries.append(
            f"{my_paper.title} challenges limitations existing methods"
        )

    if my_paper.keywords:
        queries.append(" ".join(my_paper.keywords))

    if not queries and my_paper.full_text:
        # 降级：使用全文前 500 字符
        queries.append(my_paper.full_text[:500])

    return queries


class Retriever:
    """多阶段检索器。"""

    def __init__(self, config: Config):
        self.config = config
        self.embedder = Embedder(
            model_name=config.retrieval.embedding_model,
            batch_size=config.parallel.embedding_batch_size,
        )
        self.vector_store = VectorStore(
            persist_dir=str(config.resolve_path("vectordb/chroma_db")),
            embedder=self.embedder,
        )
        self.reranker = Reranker(model_name=config.retrieval.reranker_model)
        self.colbert_indexer = None

    def _get_colbert(self):
        """惰性加载 ColBERT（仅当 use_colbert=True 时）。"""
        if self.colbert_indexer is None and self.config.retrieval.use_colbert:
            from src.indexing.colbert_indexer import ColBERTIndexer
            self.colbert_indexer = ColBERTIndexer(
                model_name=self.config.retrieval.colbert_model,
                index_dir=str(self.config.resolve_path("vectordb/colbert_index")),
            )
        return self.colbert_indexer

    async def retrieve(
        self, my_paper: MyPaperContext, paper_type: str | None = None
    ) -> list[dict]:
        """
        执行多阶段检索。

        Args:
            my_paper: 用户论文上下文
            paper_type: 可选过滤 paper_type

        Returns:
            精排后的 chunk 列表
        """
        queries = _build_queries(my_paper)
        if not queries:
            logger.warning("无法从用户论文中构建查询")
            return []

        logger.info(f"构建了 {len(queries)} 个检索查询")

        # Stage 1: Dense 检索（多 query 并行 + RRF 合并）
        where_filter = {"paper_type": paper_type} if paper_type else None
        all_query_results = []

        for query in queries:
            query_embedding = self.embedder.embed_query(query)
            hits = self.vector_store.query(
                query_embedding=query_embedding,
                n_results=self.config.retrieval.dense_top_k,
                where=where_filter,
            )
            all_query_results.append(hits)

        # RRF 合并多 query 结果
        fused = _reciprocal_rank_fusion(all_query_results)
        logger.info(f"  Stage 1 (Dense + RRF): {len(fused)} 个候选")

        # Stage 2: 可选 ColBERT 重排
        if self.config.retrieval.use_colbert:
            colbert = self._get_colbert()
            if colbert and colbert.index_exists():
                combined_query = " ".join(queries[:2])  # 用前两个 query
                colbert_results = colbert.search(
                    query=combined_query,
                    k=self.config.retrieval.colbert_top_k,
                )
                # 合并 ColBERT 结果与 Dense 结果
                fused = _reciprocal_rank_fusion([fused, colbert_results])
                logger.info(f"  Stage 2 (ColBERT rerank): {len(fused)} 个候选")

        # Stage 3 (or 2): Cross-Encoder 精排
        combined_query = queries[0]  # 主 query = abstract
        final = self.reranker.rerank(
            query=combined_query,
            candidates=fused[:50],  # 只精排前 50 个
            top_k=self.config.retrieval.reranker_top_k,
        )
        logger.info(f"  Stage {'3' if self.config.retrieval.use_colbert else '2'} "
                     f"(Cross-Encoder): {len(final)} 个最终结果")

        return final


async def retrieve_chunks(my_paper: MyPaperContext, config: Config) -> list[dict]:
    """分别检索 background 和 comparison 类型的文献。"""
    retriever = Retriever(config)

    background_results, comparison_results = await asyncio.gather(
        retriever.retrieve(my_paper, paper_type="background"),
        retriever.retrieve(my_paper, paper_type="comparison"),
    )

    # 标记 paper_type
    for r in background_results:
        r.setdefault("metadata", {})["paper_type"] = "background"
        r["paper_type"] = "background"
    for r in comparison_results:
        r.setdefault("metadata", {})["paper_type"] = "comparison"
        r["paper_type"] = "comparison"

    all_results = background_results + comparison_results
    logger.info(
        f"检索完成: {len(background_results)} background + "
        f"{len(comparison_results)} comparison = {len(all_results)} 总计"
    )
    return all_results
