from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging
from typing import Union

logger = logging.getLogger(__name__)

async def error_handler(request: Request, exc: Union[HTTPException, Exception]) -> JSONResponse:
    """Global error handler for the application."""
    if isinstance(exc, HTTPException):
        error_detail = exc.detail if hasattr(exc, 'detail') else str(exc)
        status_code = exc.status_code if hasattr(exc, 'status_code') else status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.warning(f"HTTP Exception: {error_detail}")
        return JSONResponse(
            status_code=status_code,
            content={"error": error_detail}
        )
    
    # Log unexpected errors but don't expose internal details to client
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "An unexpected error occurred. Please try again later."}
    )
