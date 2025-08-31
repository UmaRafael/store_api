# store/middlewares/exception_handler.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from http import HTTPStatus
import logging

from store.core.exceptions import BaseException

logger = logging.getLogger(__name__)

async def base_exception_handler(request: Request, exc: BaseException) -> JSONResponse:
    """Handler para exceções personalizadas da aplicação."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler para erros de validação do Pydantic."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"] if loc != "body"),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation error",
                "details": {"errors": errors}
            }
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler para exceções genéricas não tratadas."""
    logger.exception("Unhandled exception occurred")
    
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "type": exc.__class__.__name__
            }
        }
    )

def setup_exception_handlers(app: FastAPI) -> None:
    """Configura os handlers de exceção para a aplicação."""
    app.add_exception_handler(BaseException, base_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
