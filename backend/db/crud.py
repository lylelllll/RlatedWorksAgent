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
