from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models

# Projects
async def create_project(db: AsyncSession, title: str, research_direction: str = None, target_journal: str = None):
    db_obj = models.Project(
        title=title,
        research_direction=research_direction,
        target_journal=target_journal
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_projects(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(models.Project).offset(skip).limit(limit))
    return result.scalars().all()

async def get_project(db: AsyncSession, project_id: str):
    result = await db.execute(select(models.Project).filter(models.Project.id == project_id))
    return result.scalars().first()

# Conversations
async def create_conversation(db: AsyncSession, project_id: str, role: str, content: str, agent_type: str = None, metadata: dict = None):
    db_obj = models.Conversation(
        project_id=project_id,
        role=role,
        content=content,
        agent_type=agent_type,
        metadata_=metadata
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_project_conversations(db: AsyncSession, project_id: str):
    result = await db.execute(
        select(models.Conversation)
        .filter(models.Conversation.project_id == project_id)
        .order_by(models.Conversation.created_at.asc())
    )
    return result.scalars().all()

# User Config
async def get_user_config(db: AsyncSession):
    result = await db.execute(select(models.UserConfig).limit(1))
    db_obj = result.scalars().first()
    if not db_obj:
        # Default initialization
        db_obj = models.UserConfig(
            llm_provider="openai",
            model_name="gpt-4o",
            embedding_model="BAAI/bge-m3"
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
    return db_obj

async def update_user_config(db: AsyncSession, provider: str = None, api_key: str = None, model_name: str = None, embedding_model: str = None):
    db_obj = await get_user_config(db)
    if provider is not None:
        db_obj.llm_provider = provider
    if api_key is not None:
        db_obj.api_key = api_key
    if model_name is not None:
        db_obj.model_name = model_name
    if embedding_model is not None:
        db_obj.embedding_model = embedding_model
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
