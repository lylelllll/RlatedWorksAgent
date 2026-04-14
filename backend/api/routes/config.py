from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from db import crud
from core.security import encode_api_key, decode_api_key
from core.llm_factory import get_llm
from langchain_core.messages import HumanMessage

router = APIRouter()

class ConfigUpdate(BaseModel):
    llm_provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    embedding_model: Optional[str] = None

class ConfigResponse(BaseModel):
    llm_provider: Optional[str]
    api_key_configured: bool
    api_key: Optional[str]  # Return actual key or empty for UI to display
    model_name: Optional[str]
    embedding_model: Optional[str]

    class Config:
        from_attributes = True

@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    config = await crud.get_user_config(db)
    decoded_key = decode_api_key(config.api_key) if config.api_key else ""
    return ConfigResponse(
        llm_provider=config.llm_provider,
        api_key_configured=bool(config.api_key),
        api_key=decoded_key,
        model_name=config.model_name,
        embedding_model=config.embedding_model,
    )

@router.post("", response_model=ConfigResponse)
async def update_config(payload: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    encoded_key = encode_api_key(payload.api_key) if payload.api_key is not None else None
    
    config = await crud.update_user_config(
        db=db,
        provider=payload.llm_provider,
        api_key=encoded_key,
        model_name=payload.model_name,
        embedding_model=payload.embedding_model
    )
    decoded_key = decode_api_key(config.api_key) if config.api_key else ""
    return ConfigResponse(
        llm_provider=config.llm_provider,
        api_key_configured=bool(config.api_key),
        api_key=decoded_key,
        model_name=config.model_name,
        embedding_model=config.embedding_model,
    )

@router.post("/test")
async def test_config(payload: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    db_config = await crud.get_user_config(db)
    
    provider = payload.llm_provider or db_config.llm_provider
    api_key = payload.api_key
    if not api_key and db_config.api_key:
        api_key = decode_api_key(db_config.api_key)
        
    model_name = payload.model_name or db_config.model_name

    if not provider:
        raise HTTPException(status_code=400, detail="LLM provider is not configured.")
    if not api_key and provider != "ollama":
        raise HTTPException(status_code=400, detail="API Key is missing.")
    
    try:
        llm = get_llm(
            provider=provider,
            api_key=api_key,
            model_name=model_name
        )
        response = llm.invoke([HumanMessage(content="Hello! Please reply with a short greeting.")])
        return {"success": True, "message": "Test successful", "response": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM test failed: {str(e)}")
