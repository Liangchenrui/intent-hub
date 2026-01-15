"""路由管理相关API"""

from typing import List

from flask import jsonify, request
from pydantic import BaseModel, Field, ValidationError

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


class AddNegativeSamplesRequest(BaseModel):
    """添加负例样本请求模型"""

    negative_samples: List[str] = Field(..., description="负例语句列表")
    negative_threshold: float = Field(
        default=0.95,
        description="负例相似度阈值",
        ge=0.0,
        le=1.0,
    )


@handle_errors
def add_negative_samples(route_id: int):
    """为路由添加负例样本"""
    data = request.get_json()
    if not data:
        return jsonify(
            ErrorResponse(error="请求参数错误", detail="请求体不能为空").dict()
        ), 400

    try:
        req = AddNegativeSamplesRequest(**data)
    except ValidationError as e:
        return jsonify(
            ErrorResponse(
                error="请求参数错误", detail=f"参数格式错误: {str(e)}"
            ).dict()
        ), 400

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify(ErrorResponse(error="路由不存在", detail=f"路由ID {route_id} 不存在").dict()), 404

    # 合并负例样本
    existing_negative_samples = getattr(route, 'negative_samples', [])
    new_negative_samples = list(set(existing_negative_samples + req.negative_samples))
    
    # 更新路由配置
    route.negative_samples = new_negative_samples
    route.negative_threshold = req.negative_threshold
    route_manager.add_route(route)

    # 同步负例向量到Qdrant
    encoder = component_manager.encoder
    qdrant_client = component_manager.qdrant_client
    
    if new_negative_samples:
        negative_embeddings = encoder.encode(new_negative_samples)
        qdrant_client.upsert_route_negative_samples(
            route_id=route_id,
            route_name=route.name,
            negative_samples=new_negative_samples,
            embeddings=negative_embeddings,
            negative_threshold=req.negative_threshold,
        )

    return jsonify({
        "message": f"成功为路由 {route_id} 添加 {len(req.negative_samples)} 个负例样本",
        "route_id": route_id,
        "total_negative_samples": len(new_negative_samples)
    }), 200


@handle_errors
def delete_negative_samples(route_id: int):
    """删除路由的所有负例样本"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify(ErrorResponse(error="路由不存在", detail=f"路由ID {route_id} 不存在").dict()), 404

    # 删除负例向量
    qdrant_client = component_manager.qdrant_client
    qdrant_client.delete_route_negative_samples(route_id)

    # 更新路由配置
    route.negative_samples = []
    route_manager.add_route(route)

    return jsonify({
        "message": f"成功删除路由 {route_id} 的所有负例样本",
        "route_id": route_id
    }), 200
