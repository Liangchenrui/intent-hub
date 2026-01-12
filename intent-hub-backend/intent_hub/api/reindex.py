"""重新索引相关API"""

from flask import jsonify, request

from intent_hub.core.components import get_component_manager
from intent_hub.services.sync_service import SyncService
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def reindex():
    """增量重新索引：只更新变化的路由

    支持可选参数：
    - force_full: 如果为true，则执行全量重建（清空后重新创建）
    """
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    # 获取请求参数
    data = request.get_json() or {}
    force_full = data.get("force_full", False)

    sync_service = SyncService(component_manager)
    result = sync_service.reindex(force_full=force_full)

    return jsonify(result), 200
