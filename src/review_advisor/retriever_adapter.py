"""Adapter for querying vector stores directly given raw text queries."""

from src.config import Config
from src.retrieval.retriever import Retriever, _reciprocal_rank_fusion

class ReviewRetriever(Retriever):
    """Adapter to allow querying by explicit query strings instead of MyPaperContext."""
    
    async def retrieve_by_queries(self, queries: list[str], paper_type: str = None, top_k: int = 5) -> list[dict]:
        if not queries:
            return []
            
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
            
        fused = _reciprocal_rank_fusion(all_query_results)
        
        if self.config.retrieval.use_colbert:
            colbert = self._get_colbert()
            if colbert and colbert.index_exists():
                combined_query = " ".join(queries[:2])
                colbert_results = colbert.search(
                    query=combined_query,
                    k=self.config.retrieval.colbert_top_k,
                )
                fused = _reciprocal_rank_fusion([fused, colbert_results])
                
        if not fused:
            return []
            
        combined_query = queries[0]
        final = self.reranker.rerank(
            query=combined_query,
            candidates=fused[:50],
            top_k=top_k,
        )
        return final
