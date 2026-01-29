"""Unified error handling utilities."""
from functools import wraps
from flask import request, jsonify
from typing import Callable, Type
from pydantic import BaseModel, ValidationError

from intent_hub.utils.logger import logger
from intent_hub.models import ErrorResponse


def handle_errors(f: Callable) -> Callable:
    """Unified error handler decorator; catches exceptions and returns standard error response."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Request validation failed: {e}")
            return jsonify(ErrorResponse(
                error="Invalid request",
                detail=f"Validation failed: {str(e)}"
            ).dict()), 400
        except ValueError as e:
            logger.warning(f"Request parameter error: {e}")
            return jsonify(ErrorResponse(
                error="Invalid request",
                detail=str(e)
            ).dict()), 400
        except RuntimeError as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
            return jsonify(ErrorResponse(
                error="Service not ready",
                detail=str(e)
            ).dict()), 503
        except Exception as e:
            logger.error(f"Request handling failed: {e}", exc_info=True)
            return jsonify(ErrorResponse(
                error="Request failed",
                detail=str(e)
            ).dict()), 500

    return decorated_function


def validate_request(model_class: Type[BaseModel], require_json: bool = True):
    """Request body validation decorator."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if require_json and data is None:
                return jsonify(ErrorResponse(
                    error="Invalid request",
                    detail="Request body must not be empty"
                ).dict()), 400

            try:
                validated_data = model_class(**data) if data else None
            except ValidationError as e:
                logger.warning(f"Request validation failed: {e}")
                return jsonify(ErrorResponse(
                    error="Invalid request",
                    detail=f"Missing or invalid parameters: {str(e)}"
                ).dict()), 400

            return f(validated_data, *args, **kwargs)

        return decorated_function
    return decorator

