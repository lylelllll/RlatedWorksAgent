"""统一 LLM 客户端——多 provider 适配，通过 config.yaml 切换。"""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import LLMConfig


class LLMClient:
    """
    统一 LLM 调用接口。

    支持 provider：
      anthropic    → anthropic SDK
      openai       → openai SDK
      azure_openai → openai SDK（Azure 端点）
      deepseek     → openai SDK（兼容 API，base_url 指向 DeepSeek）
      dashscope    → openai SDK（兼容 API，base_url 指向 DashScope）
      ollama       → openai SDK（兼容 API，base_url 指向本地 Ollama）
    """

    def __init__(self, llm_config: LLMConfig):
        self.config = llm_config
        self._client = None
        self._is_anthropic = llm_config.provider == "anthropic"

    def _init_client(self):
        """惰性初始化 SDK 客户端。"""
        if self._client is not None:
            return

        provider = self.config.provider
        logger.info(f"初始化 LLM 客户端: provider={provider}, model={self.config.model}")

        if provider == "anthropic":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY 未设置。请在 .env 文件中配置。")
            self._client = anthropic.AsyncAnthropic(api_key=api_key)

        elif provider == "openai":
            import openai
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY 未设置。请在 .env 文件中配置。")
            self._client = openai.AsyncOpenAI(api_key=api_key)

        elif provider == "azure_openai":
            import openai
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("AZURE_OPENAI_API_KEY 未设置。请在 .env 文件中配置。")
            self._client = openai.AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=self.config.azure_endpoint,
                api_version=self.config.azure_api_version,
            )

        elif provider == "deepseek":
            import openai
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY 未设置。请在 .env 文件中配置。")
            self._client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )

        elif provider == "dashscope":
            import openai
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY 未设置。请在 .env 文件中配置。")
            self._client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

        elif provider == "ollama":
            import openai
            self._client = openai.AsyncOpenAI(
                api_key="ollama",  # Ollama 不需要真实 key
                base_url=f"{self.config.ollama_base_url}/v1",
            )

        else:
            raise ValueError(f"不支持的 LLM provider: {provider}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM 调用失败，第 {retry_state.attempt_number} 次重试..."
        ),
    )
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """统一调用，返回纯文本。"""
        self._init_client()

        if self._is_anthropic:
            response = await self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

        else:
            # OpenAI 兼容接口（openai / azure / deepseek / dashscope / ollama）
            response = await self._client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
    )
    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """要求 JSON 格式输出（评分模块专用）。"""
        self._init_client()

        json_instruction = "\n\nYou must respond with valid JSON only, no extra text."
        full_system = system_prompt + json_instruction

        if self._is_anthropic:
            response = await self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=full_system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text

        else:
            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": user_prompt},
                ],
            }
            # OpenAI 和兼容 API 支持 response_format
            if self.config.provider in ("openai", "azure_openai", "deepseek"):
                kwargs["response_format"] = {"type": "json_object"}

            response = await self._client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or "{}"

        # 解析 JSON
        try:
            # 尝试提取 JSON 块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"JSON 解析失败，原始输出: {text[:200]}")
            return {"error": "JSON 解析失败", "raw": text}
