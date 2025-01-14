from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Task, SubTask
from app.database import get_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_langgraph_error(task_id: str, error_details: dict):
    """
    Handle errors that occur during LangGraph operations
    
    Args:
        task_id: The ID of the task where the error occurred
        error_details: Dictionary containing error information
    """
    # Log the error
    logger.error(f"LangGraph error for task {task_id}: {error_details}")
    
    try:
        # If we have a task_id, update its status
        if task_id:
            db = Session()  # You should properly initialize this with your SessionLocal
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = "failed"
                db.commit()
    except Exception as e:
        logger.error(f"Error while handling LangGraph error: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()

    # Return error response
    return {
        "status": "error",
        "task_id": task_id,
        "error": error_details.get("error", "Unknown error occurred"),
        "timestamp": datetime.utcnow().isoformat()
    }

def setup_error_handlers(app):
    """
    Set up global error handlers for the FastAPI application
    
    Args:
        app: FastAPI application instance
    """
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        error_details = {
            "error": str(exc),
            "path": request.url.path
        }
        
        # Log the error
        logger.error(f"Global error: {error_details}")
        
        # Handle specific error types
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail}
            )
            
        # Handle unexpected errors
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred"}
        )
