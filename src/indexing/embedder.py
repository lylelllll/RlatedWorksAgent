"""Dense Embedding 封装——SPECTER2 + 自动设备检测 + HuggingFace 镜像支持。"""

from __future__ import annotations

import os
from typing import Optional

import torch
from loguru import logger


def _setup_hf_mirror():
    """设置 HuggingFace 镜像（国内用户加速下载）。"""
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        logger.info("已设置 HuggingFace 镜像: https://hf-mirror.com")


class Embedder:
    """使用 sentence-transformers 加载 embedding 模型。"""

    def __init__(self, model_name: str = "allenai/specter2_base", batch_size: int = 64):
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None
        self._device = self._detect_device()

    def _detect_device(self) -> str:
        """自动检测最佳设备：CUDA > MPS > CPU。"""
        if torch.cuda.is_available():
            logger.info("检测到 CUDA GPU，使用 GPU 进行 embedding")
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("检测到 Apple MPS，使用 MPS 进行 embedding")
            return "mps"
        else:
            logger.info("使用 CPU 进行 embedding")
            return "cpu"

    def _load_model(self):
        """惰性加载模型。"""
        if self._model is None:
            _setup_hf_mirror()
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载 embedding 模型: {self.model_name}")
            logger.info("首次加载需要下载模型（约 440MB），请耐心等待...")
            self._model = SentenceTransformer(self.model_name, device=self._device)
            logger.info("embedding 模型加载完成")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embedding。"""
        self._load_model()
        assert self._model is not None
        logger.info(f"Embedding {len(texts)} 个文本，batch_size={self.batch_size}...")
        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """单个 query embedding。"""
        self._load_model()
        assert self._model is not None
        embedding = self._model.encode(
            [query], normalize_embeddings=True
        )
        return embedding[0].tolist()
