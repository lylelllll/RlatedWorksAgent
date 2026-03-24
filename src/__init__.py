"""Related Work Agent 根包——在所有模块之前设置环境变量。"""

import os

# 国内 HuggingFace 镜像加速（必须在 huggingface_hub 被导入前设置）
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
