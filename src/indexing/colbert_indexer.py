"""ColBERT 索引构建（可选，通过 config.yaml 启用）——RAGatouille 封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger


class ColBERTIndexer:
    """ColBERT 索引（可选）。使用 RAGatouille 封装 ColBERT v2。"""

    def __init__(
        self,
        model_name: str = "colbert-ir/colbertv2.0",
        index_dir: str = "vectordb/colbert_index",
    ):
        self.model_name = model_name
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._model = None

    def _load_model(self):
        """惰性加载 RAGatouille 模型。"""
        if self._model is None:
            try:
                from ragatouille import RAGPretrainedModel
                logger.info(f"加载 ColBERT 模型: {self.model_name}")
                self._model = RAGPretrainedModel.from_pretrained(self.model_name)
                logger.info("ColBERT 模型加载完成")
            except ImportError:
                logger.error(
                    "RAGatouille 未安装。请运行: pip install 'related-work-agent[colbert]'"
                )
                raise

    def build_index(
        self,
        documents: list[str],
        document_ids: list[str],
        index_name: str = "rwa_colbert",
    ) -> None:
        """构建 ColBERT 索引。"""
        self._load_model()
        assert self._model is not None
        logger.info(f"构建 ColBERT 索引: {len(documents)} 个文档...")

        self._model.index(
            collection=documents,
            document_ids=document_ids,
            index_name=index_name,
            split_documents=False,
        )
        logger.info("ColBERT 索引构建完成")

    def search(
        self, query: str, k: int = 30, index_name: str = "rwa_colbert"
    ) -> list[dict]:
        """ColBERT 检索。"""
        self._load_model()
        assert self._model is not None

        results = self._model.search(query=query, k=k, index_name=index_name)
        return [
            {
                "chunk_id": r.get("document_id", ""),
                "text": r.get("content", ""),
                "score": r.get("score", 0.0),
            }
            for r in results
        ]

    def index_exists(self, index_name: str = "rwa_colbert") -> bool:
        """检查索引是否已存在。"""
        # RAGatouille 存储在 .ragatouille/ 目录下
        possible_paths = [
            Path(".ragatouille") / "colbert" / "indexes" / index_name,
            self.index_dir / index_name,
        ]
        return any(p.exists() and any(p.iterdir()) for p in possible_paths if p.exists())
