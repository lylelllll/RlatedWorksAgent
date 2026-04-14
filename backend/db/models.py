import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

def utcnow():
    return datetime.now(timezone.utc)

class UserConfig(Base):
    __tablename__ = "user_config"

    id = Column(Integer, primary_key=True, index=True)
    llm_provider = Column(String, nullable=True)        # openai/anthropic/ollama
    api_key = Column(String, nullable=True)             # 加密存储
    model_name = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)      # UUID
    title = Column(String, nullable=False)
    research_direction = Column(String, nullable=True)
    target_journal = Column(String, nullable=True)
    stage = Column(String, default="EXPLORE")               # EXPLORE/IDEA/WRITING/REVIEW/DONE
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # 关系
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    paper_versions = relationship("PaperVersion", back_populates="project", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="project", cascade="all, delete-orphan")
    papers = relationship("Paper", back_populates="project", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="project", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)                # user/assistant/system
    content = Column(String, nullable=False)
    agent_type = Column(String, nullable=True)          # supervisor/writer/critic等
    metadata_ = Column("metadata", JSON, nullable=True) # 防止冲突
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="conversations")


class PaperVersion(Base):
    __tablename__ = "paper_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)             # {intro: "...", related: "...", method: "..."}
    change_summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="paper_versions")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    section = Column(String, nullable=True)
    feedback_text = Column(String, nullable=False)
    agent_action = Column(String, nullable=True)        # 记录agent如何响应
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="feedbacks")


class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    title = Column(String, nullable=True)
    authors = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    abstract = Column(String, nullable=True)
    paper_category = Column(String, nullable=True)      # JOURNAL/INTEREST/DOMAIN
    file_path = Column(String, nullable=True)
    chunk_count = Column(Integer, default=0)
    indexed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="papers")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(String, nullable=False)         # preference/style/feedback_pattern
    content = Column(String, nullable=False)
    importance = Column(Float, default=1.0)
    created_at = Column(DateTime, default=utcnow)

    project = relationship("Project", back_populates="memories")
