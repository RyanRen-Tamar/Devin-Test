from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.models import Task, SubTask, TaskComment
from app.database import get_db
from app.langgraph_flow import create_task_flow
from app.task_generator import task_generator, validate_subtask
from app.error_handler import handle_langgraph_error

app = FastAPI()
task_flow = create_task_flow()

# Task Creation & Management
@app.post("/api/tasks/create")
async def create_task(task_data: dict, db: Session = Depends(get_db)):
    try:
        task_list, subtask_list = task_generator(task_data.get("description", ""))
        task = Task(
            title=task_data.get("title"),
            description=task_data.get("description"),
            status="verifying"
        )
        db.add(task)
        db.commit()
        return {"task_id": task.id, "status": "created"}
    except Exception as e:
        await handle_langgraph_error(None, {"error": str(e)})
        raise HTTPException(status_code=500, detail="Task creation failed")

@app.post("/api/tasks/{task_id}/publish")
async def publish_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "pending"
    db.commit()
    return {"status": "published"}

# Task Validation
@app.post("/api/tasks/{task_id}/sub_tasks/{sub_task_id}/verify")
async def verify_subtask(task_id: str, sub_task_id: str, db: Session = Depends(get_db)):
    subtask = db.query(SubTask).filter(
        SubTask.id == sub_task_id,
        SubTask.parent_task_id == task_id
    ).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="SubTask not found")
    
    try:
        result = await task_flow.arun({"subtask": subtask.detail})
        subtask.status = "verified" if result["status"] == "completed" else "failed"
        db.commit()
        return result
    except Exception as e:
        await handle_langgraph_error(task_id, {"error": str(e)})
        raise HTTPException(status_code=500, detail="Verification failed")

@app.post("/api/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "pending"
    db.commit()
    return {"status": "retry_initiated"}

# Task Execution
@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "in_progress"
    db.commit()
    return {"status": "execution_started"}

@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "paused"
    db.commit()
    return {"status": "paused"}

@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "completed"
    db.commit()
    return {"status": "completed"}

@app.post("/api/tasks/{task_id}/fail")
async def fail_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "failed"
    db.commit()
    return {"status": "failed"}

# Task Comments & Copy
@app.post("/api/tasks/{task_id}/copy")
async def copy_task(task_id: str, db: Session = Depends(get_db)):
    original_task = db.query(Task).filter(Task.id == task_id).first()
    if not original_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    new_task = Task(
        title=f"Copy of {original_task.title}",
        description=original_task.description,
        status="pending"
    )
    db.add(new_task)
    db.commit()
    return {"new_task_id": new_task.id}

@app.post("/api/tasks/{task_id}/sub_tasks/{sub_task_id}/comments")
async def add_comment(
    task_id: str,
    sub_task_id: str,
    comment_data: dict,
    db: Session = Depends(get_db)
):
    subtask = db.query(SubTask).filter(
        SubTask.id == sub_task_id,
        SubTask.parent_task_id == task_id
    ).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="SubTask not found")
    
    comment = TaskComment(
        subtask_id=sub_task_id,
        source=comment_data.get("source", "Human"),
        content=comment_data.get("content")
    )
    db.add(comment)
    db.commit()
    return {"comment_id": comment.id}

# Query Interfaces
@app.get("/api/tasks")
async def list_tasks(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    return query.all()

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"status": "deleted"}
