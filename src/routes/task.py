from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.models.base import get_db
from src.models.task import Task, SubTask, TaskStatus
from src.services.task_generator import TaskGeneratorService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])
task_generator = TaskGeneratorService()

@router.post("/create")
async def create_task(
    task_data: dict,
    db: Session = Depends(get_db)
):
    """Create a new task and generate subtasks."""
    try:
        # Create main task
        new_task = Task(
            user_id=task_data["user_id"],
            task_name=task_data["task_name"],
            task_description=task_data["task_description"],
            status=TaskStatus.VERIFYING
        )
        db.add(new_task)
        db.flush()  # Get the task ID without committing

        # Generate subtasks using LangGraph
        generation_result = await task_generator.generate_task(task_data["task_description"])
        
        if not generation_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate subtasks: {generation_result.get('error')}"
            )

        # Create subtasks
        for subtask_data in generation_result["subtasks"]:
            subtask = SubTask(
                task_id=new_task.id,
                subtask_name=subtask_data["name"],
                subtask_desc=subtask_data["description"],
                execute_time=datetime.utcnow(),  # This should be calculated based on scheduling logic
                status=TaskStatus.VERIFYING
            )
            db.add(subtask)

        db.commit()
        return {
            "success": True,
            "task_id": new_task.id,
            "message": "Task created successfully with generated subtasks"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/validate")
async def validate_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Validate a task and its subtasks."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    try:
        # Implement validation logic here
        # This should check feasibility of all subtasks
        task.status = TaskStatus.PENDING
        db.commit()
        
        return {
            "success": True,
            "message": "Task validated successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/updateStatus")
async def update_task_status(
    task_id: int,
    new_status: TaskStatus,
    db: Session = Depends(get_db)
):
    """Update the status of a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    try:
        task.status = new_status
        task.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"Task status updated to {new_status}"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
