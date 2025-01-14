from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base

class TaskStatus(str, enum.Enum):
    VERIFYING = "verifying"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    task_name = Column(String, index=True)
    task_description = Column(String)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.VERIFYING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subtasks = relationship("SubTask", back_populates="task")
    comments = relationship("TaskComment", back_populates="task")

class SubTask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    subtask_name = Column(String, index=True)
    subtask_desc = Column(String)
    execute_time = Column(DateTime)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.VERIFYING)
    execution_log = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="subtasks")
    calendar_events = relationship("CalendarEvent", back_populates="subtask")

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    subtask_id = Column(Integer, ForeignKey("subtasks.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    recurrence_rule = Column(String)
    status = Column(String)

    subtask = relationship("SubTask", back_populates="calendar_events")

class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    user_id = Column(Integer, index=True)
    comment_text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
