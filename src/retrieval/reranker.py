"""Cross-Encoder 精排封装。"""

from __future__ import annotations

from loguru import logger


class Reranker:
    """Cross-Encoder 重排序器。"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """惰性加载模型。"""
        if self._model is None:
            from src.indexing.embedder import _setup_hf_mirror
            _setup_hf_mirror()
            from sentence_transformers import CrossEncoder
            logger.info(f"加载 Cross-Encoder 模型: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            logger.info("Cross-Encoder 模型加载完成")

    def rerank(
        self, query: str, candidates: list[dict], top_k: int = 15
    ) -> list[dict]:
        """
        对候选结果进行精排。

        Args:
            query: 查询文本
            candidates: 候选列表（每个 dict 需有 "text" 字段）
            top_k: 返回前 k 个

        Returns:
            按精排分数降序排列的候选列表（添加 "rerank_score" 字段）
        """
        if not candidates:
            return []

        self._load_model()
        assert self._model is not None

        # 构建 (query, document) 对
        pairs = [(query, c["text"]) for c in candidates]
        scores = self._model.predict(pairs, show_progress_bar=False)

        # 添加分数并排序
        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]
