"""Intent Hub - 基于向量相似度的静态路由系统"""

__version__ = "0.1.0"

from intent_hub.config import Config
from intent_hub.models import (
    RouteConfig,
    PredictRequest,
    PredictResponse,
    ErrorResponse,
    LoginRequest,
    LoginResponse
)
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.auth import get_auth_manager, require_auth

__all__ = [
    "Config",
    "RouteConfig",
    "PredictRequest",
    "PredictResponse",
    "ErrorResponse",
    "LoginRequest",
    "LoginResponse",
    "QwenEmbeddingEncoder",
    "IntentHubQdrantClient",
    "RouteManager",
    "get_auth_manager",
    "require_auth",
]

