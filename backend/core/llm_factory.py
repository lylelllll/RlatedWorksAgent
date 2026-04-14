from langchain_core.language_models.chat_models import BaseChatModel

def get_llm(provider: str, api_key: str, model_name: str, **kwargs) -> BaseChatModel:
    """
    根据给定的 provider、api_key 和 model_name 获取对应的 LangChain ChatModel 实例。
    """
    provider = provider.lower() if provider else ""
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "gpt-4o",
            **kwargs
        )
        
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=api_key,
            model_name=model_name or "claude-3-5-sonnet-20240620",
            **kwargs
        )
        
    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        # 默认对于 ollama, api_key可以为空，但可以作为 host 等传入
        return ChatOllama(
            model=model_name or "llama3",
            **kwargs
        )
        
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            **kwargs
        )
        
    elif provider == "kimi":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "moonshot-v1-8k",
            base_url="https://api.moonshot.cn/v1",
            **kwargs
        )
        
    elif provider == "qwen":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "qwen-max",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            **kwargs
        )
        
    elif provider == "glm":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "glm-4",
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            **kwargs
        )
        
    elif provider == "minimax":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=api_key,
            model_name=model_name or "abab6.5-chat",
            base_url="https://api.minimax.chat/v1",
            **kwargs
        )
        
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
