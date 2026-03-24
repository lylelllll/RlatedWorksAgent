"""配置加载与验证——基于 pydantic-settings + PyYAML。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, PrivateAttr
from dotenv import load_dotenv


# ── 子配置模型 ─────────────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.3
    azure_endpoint: str = ""
    azure_api_version: str = "2024-02-01"
    azure_deployment: str = ""
    ollama_base_url: str = "http://localhost:11434"


class DataConfig(BaseModel):
    background_papers_dir: str = "data/background_papers"
    comparison_papers_dir: str = "data/comparison_papers"
    venue_style_papers_dir: str = "data/venue_style_papers"
    my_paper_dir: str = "data/my_paper"


class RetrievalConfig(BaseModel):
    embedding_model: str = "allenai/specter2_base"
    use_colbert: bool = False
    colbert_model: str = "colbert-ir/colbertv2.0"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    dense_top_k: int = 100
    colbert_top_k: int = 30
    reranker_top_k: int = 15


class ChunkingConfig(BaseModel):
    default_chunk_size: int = 400
    default_overlap: int = 50
    method_chunk_size: int = 500
    method_overlap: int = 80


class GenerationConfig(BaseModel):
    max_iterations: int = 3
    target_venue: str = "IEEE TMC"
    language: str = "english"
    latex_bib_style: str = "IEEEtran"
    refine_bib: bool = True


class ParallelConfig(BaseModel):
    max_pdf_workers: int = 8
    embedding_batch_size: int = 64


class OutputConfig(BaseModel):
    dir: str = "outputs"
    save_all_iterations: bool = True


# ── 总配置 ─────────────────────────────────────────────────────

class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scorer_llm: LLMConfig = Field(default_factory=LLMConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # 运行时标志（非配置文件字段）
    _force_skip_indexing: bool = PrivateAttr(default=False)
    _project_root: Path = PrivateAttr(default_factory=lambda: Path("."))

    def resolve_path(self, relative_path: str) -> Path:
        """将相对路径解析为绝对路径（基于项目根目录）。"""
        return (self._project_root / relative_path).resolve()


def load_config(config_path: str = "config.yaml") -> Config:
    """从 YAML 文件加载配置，自动加载 .env。"""
    config_file = Path(config_path).resolve()
    project_root = config_file.parent

    # 加载 .env 文件（如果存在）
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    # 加载 YAML
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    config = Config(**raw)
    # 手动设置 private 属性
    object.__setattr__(config, "_project_root", project_root)
    return config
