"""路由管理相关API"""

from flask import jsonify, request
from pydantic import ValidationError

from intent_hub.core.components import get_component_manager
from intent_hub.models import ErrorResponse, GenerateUtterancesRequest, RouteConfig
from intent_hub.services.route_service import RouteService
from intent_hub.utils.error_handler import handle_errors, validate_request


@handle_errors
def get_routes():
    """获取所有路由列表"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    routes = route_service.get_all_routes()

    return jsonify([route.dict() for route in routes]), 200


@handle_errors
def search_routes():
    """搜索路由（通过名称、描述或例句）"""
    # 获取查询参数
    query = request.args.get("q", "").strip()

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    routes = route_service.search_routes(query)

    return jsonify([route.dict() for route in routes]), 200


@handle_errors
@validate_request(RouteConfig)
def create_route(route: RouteConfig):
    """新增路由配置（含向量生成）"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    created_route = route_service.create_route(route)

    return jsonify(created_route.dict()), 201


@handle_errors
def update_route(route_id: int):
    """修改指定路由"""
    # 手动验证请求数据（因为需要先获取route_id参数）
    data = request.get_json()
    if not data:
        return jsonify(
            ErrorResponse(error="请求参数错误", detail="请求体不能为空").dict()
        ), 400

    try:
        route = RouteConfig(**data)
    except ValidationError as e:
        return jsonify(
            ErrorResponse(
                error="请求参数错误", detail=f"缺少必需的参数或参数格式错误: {str(e)}"
            ).dict()
        ), 400

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        updated_route = route_service.update_route(route_id, route)
        return jsonify(updated_route.dict()), 200
    except ValueError as e:
        return jsonify(ErrorResponse(error="路由不存在", detail=str(e)).dict()), 404


@handle_errors
def delete_route(route_id: int):
    """删除指定路由"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        route_service.delete_route(route_id)
        return jsonify({"message": f"路由 {route_id} 已删除"}), 200
    except ValueError as e:
        return jsonify(ErrorResponse(error="路由不存在", detail=str(e)).dict()), 404


@handle_errors
@validate_request(GenerateUtterancesRequest)
def generate_utterances(req: GenerateUtterancesRequest):
    """根据Agent信息生成提问列表（不自动持久化）"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        updated_route = route_service.generate_utterances(req)
        return jsonify(updated_route.dict()), 200
    except Exception as e:
        return jsonify(ErrorResponse(error="生成提问失败", detail=str(e)).dict()), 500
