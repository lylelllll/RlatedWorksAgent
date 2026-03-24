"""ChromaDB 向量数据库封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import chromadb
from loguru import logger

from src.indexing.embedder import Embedder
from src.ingestion.chunker import Chunk


class VectorStore:
    """ChromaDB 向量数据库——支持按 paper_type 分 collection。"""

    def __init__(
        self,
        persist_dir: str = "vectordb/chroma_db",
        embedder: Optional[Embedder] = None,
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.embedder = embedder
        self._collections: dict[str, Any] = {}

    def _get_collection(self, name: str):
        """获取或创建 collection。"""
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def add_chunks(self, chunks: list[Chunk], collection_name: str = "papers") -> None:
        """批量添加 chunks 到向量库。"""
        if not chunks:
            return

        collection = self._get_collection(collection_name)
        texts = [c.text for c in chunks]
        ids = [c.chunk_id for c in chunks]
        metadatas = [c.metadata for c in chunks]

        # 生成 embeddings
        if self.embedder:
            embeddings = self.embedder.embed(texts)
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
        else:
            # 使用 ChromaDB 内置 embedding（效果不如 SPECTER2）
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
            )

        logger.info(f"已添加 {len(chunks)} 个 chunk 到 collection '{collection_name}'")

    def query(
        self,
        query_embedding: list[float],
        collection_name: str = "papers",
        n_results: int = 100,
        where: dict | None = None,
    ) -> list[dict]:
        """向量检索。"""
        collection = self._get_collection(collection_name)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        if collection.count() == 0:
            return []

        results = collection.query(**kwargs)

        hits = []
        for i in range(len(results["ids"][0])):
            hits.append({
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return hits

    def collection_count(self, collection_name: str = "papers") -> int:
        """获取 collection 中的文档数量。"""
        collection = self._get_collection(collection_name)
        return collection.count()

    def exists(self, collection_name: str = "papers") -> bool:
        """检查 collection 是否存在且非空。"""
        try:
            collection = self._get_collection(collection_name)
            return collection.count() > 0
        except Exception:
            return False

    def clear(self, collection_name: str = "papers") -> None:
        """清除 collection。"""
        try:
            self.client.delete_collection(collection_name)
            self._collections.pop(collection_name, None)
            logger.info(f"已清除 collection '{collection_name}'")
        except Exception:
            pass
