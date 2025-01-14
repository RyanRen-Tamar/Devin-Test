# Lamta Task Generator Backend

Backend service for the Lamta Task Generator & Task Management Center. This service provides task generation, validation, and execution management capabilities using LangGraph architecture.

## Features

- Task creation and management
- Automatic subtask generation using LLM
- Task validation and feasibility checks
- Task execution scheduling
- Real-time status updates
- Error handling and logging

## Tech Stack

- FastAPI
- SQLAlchemy (PostgreSQL)
- LangGraph
- LangChain
- OpenAI GPT-4

## Project Structure

```
lamta-task-backend/
├─ src/
│  ├─ models/          # Database models / ORM files
│  ├─ routes/          # API routes
│  ├─ services/        # Business logic (task generator, validator, executor)
│  ├─ utils/           # Utility functions and components
├─ tests/              # Test cases
├─ requirements.txt    # Dependencies
└─ README.md
```

## Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the application:
```bash
uvicorn src.main:app --reload
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

- Follow PEP 8 style guide
- Write tests for new features
- Update documentation when making changes
- Use proper error handling and logging

## License

[MIT License](LICENSE)
