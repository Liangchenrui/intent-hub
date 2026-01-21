"""系统设置相关API"""

from flask import jsonify, request

from intent_hub.config import Config
from intent_hub.utils.error_handler import handle_errors


@handle_errors
def get_settings():
    """获取系统配置项"""
    return jsonify(Config.to_dict()), 200


@handle_errors
def update_settings():
    """更新系统配置项"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体不能为空"}), 400

    try:
        Config.save(data)
        # 更新配置后，重新初始化核心组件
        from intent_hub.core.components import get_component_manager

        get_component_manager().reinit_components()
        return jsonify(
            {"message": "配置更新成功，组件已重新加载", "settings": Config.to_dict()}
        ), 200
    except Exception as e:
        return jsonify({"error": "配置保存失败", "detail": str(e)}), 500
