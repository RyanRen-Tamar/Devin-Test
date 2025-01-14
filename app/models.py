from sqlalchemy import Column, String, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(Enum("verifying", "pending", "in_progress", "paused", "completed"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subtasks = relationship("SubTask", back_populates="task")

class SubTask(Base):
    __tablename__ = "subtasks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    title = Column(String, nullable=False)
    status = Column(Enum("verifying", "pending", "in_progress", "paused", "completed"))
    detail = Column(String)
    metrics = Column(JSON)
    task = relationship("Task", back_populates="subtasks")
    comments = relationship("TaskComment", back_populates="subtask")

class TaskComment(Base):
    __tablename__ = "task_comments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subtask_id = Column(String, ForeignKey("subtasks.id"))
    source = Column(String)  # "AI" or "Human"
    timestamp = Column(DateTime, default=datetime.utcnow)
    content = Column(String)
    subtask = relationship("SubTask", back_populates="comments")
