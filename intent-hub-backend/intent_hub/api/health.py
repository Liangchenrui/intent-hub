"""健康检查API"""

from flask import jsonify

from intent_hub.config import Config
from intent_hub.core.components import get_component_manager
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def health_check():
    """健康检查接口（免鉴权）"""
    component_manager = get_component_manager()

    qdrant_ready = False
    encoder_ready = False
    route_manager_ready = False

    if component_manager.is_ready():
        qdrant_ready = component_manager.qdrant_client.is_ready()
        encoder_ready = True
        route_manager_ready = True

    return jsonify(
        {
            "status": "ok",
            "qdrant_ready": qdrant_ready,
            "encoder_ready": encoder_ready,
            "route_manager_ready": route_manager_ready,
            "auth_enabled": Config.AUTH_ENABLED,
        }
    ), 200
