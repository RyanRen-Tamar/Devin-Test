from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

# Add the project root to Python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base import get_db, engine
import src.models.task as task_models

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables
task_models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Lamta Task Generator",
    description="Task generation and management system",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "Welcome to Lamta Task Generator API"}

# Import and include routers
from src.routes import task
from src.utils.error_handler import error_handler

# Add exception handler
app.add_exception_handler(Exception, error_handler)

# Include routers
app.include_router(task.router)
