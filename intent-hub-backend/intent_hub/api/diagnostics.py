from flask import jsonify, request
from intent_hub.core.components import get_component_manager
from intent_hub.services.diagnostic_service import DiagnosticService
from intent_hub.utils.error_handler import handle_errors

@handle_errors
def analyze_overlap(route_id):
    """分析指定路由与其他路由的重叠情况"""
    threshold = request.args.get("threshold", 0.85, type=float)
    
    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    
    result = diagnostic_service.analyze_route_overlap(route_id, threshold)
    return jsonify(result.dict()), 200

@handle_errors
def analyze_all_overlaps():
    """全局分析所有路由的重叠情况"""
    threshold = request.args.get("threshold", 0.85, type=float)
    
    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)
    
    results = diagnostic_service.analyze_all_overlaps(threshold)
    return jsonify([r.dict() for r in results]), 200


@handle_errors
def umap_points():
    """返回用于可视化的 UMAP 2D 点云"""
    n_neighbors = request.args.get("n_neighbors", 15, type=int)
    min_dist = request.args.get("min_dist", 0.1, type=float)
    seed = request.args.get("seed", 42, type=int)

    component_manager = get_component_manager()
    diagnostic_service = DiagnosticService(component_manager)

    data = diagnostic_service.build_umap_projection(
        n_neighbors=n_neighbors, min_dist=min_dist, seed=seed
    )
    return jsonify(data), 200
