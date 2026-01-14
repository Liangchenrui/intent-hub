import numpy as np
from typing import List, Dict, Any
from intent_hub.core.components import ComponentManager
from intent_hub.models import DiagnosticResult, RouteOverlap, ConflictPoint, RouteConfig
from intent_hub.utils.logger import logger

class DiagnosticService:
    """诊断服务 - 处理语义重叠检测逻辑"""

    def __init__(self, component_manager: ComponentManager):
        self.component_manager = component_manager

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def analyze_route_overlap(self, route_id: int, threshold: float = 0.9) -> DiagnosticResult:
        """分析指定路由与其他所有路由的语义重叠情况"""
        self.component_manager.ensure_ready()
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 1. 获取当前路由信息
        current_route = route_manager.get_route(route_id)
        if not current_route:
            raise ValueError(f"路由ID {route_id} 不存在")

        # 2. 获取当前路由的所有向量并计算质心
        current_points = qdrant_client.get_route_vectors(route_id)
        if not current_points:
            return DiagnosticResult(route_id=route_id, route_name=current_route.name, overlaps=[])

        current_vectors = [np.array(p["vector"]) for p in current_points]
        centroid_current = np.mean(current_vectors, axis=0)

        # 3. 获取所有其他路由
        all_routes = route_manager.get_all_routes()
        overlaps = []

        for other_route in all_routes:
            if other_route.id == route_id:
                continue

            # 获取对方路由的向量
            other_points = qdrant_client.get_route_vectors(other_route.id)
            if not other_points:
                continue

            other_vectors = [np.array(p["vector"]) for p in other_points]
            centroid_other = np.mean(other_vectors, axis=0)

            # A. 计算两个质心之间的相似度
            centroid_sim = self._cosine_similarity(centroid_current, centroid_other)
            
            # B. 查找当前路由中哪些点非常接近对方路由的质心
            conflicting_points = []
            for p in current_points:
                sim = self._cosine_similarity(np.array(p["vector"]), centroid_other)
                if sim >= threshold:
                    conflicting_points.append(ConflictPoint(
                        utterance=p["payload"].get("utterance", ""),
                        similarity=sim
                    ))

            # 如果质心太接近，或者有具体的冲突点，则记录重叠
            if centroid_sim >= threshold or conflicting_points:
                overlaps.append(RouteOverlap(
                    target_route_id=other_route.id,
                    target_route_name=other_route.name,
                    overlap_score=centroid_sim,
                    conflicting_utterances=conflicting_points
                ))

        # 按相似度降序排序
        overlaps.sort(key=lambda x: x.overlap_score, reverse=True)

        return DiagnosticResult(
            route_id=route_id,
            route_name=current_route.name,
            overlaps=overlaps
        )

    def analyze_all_overlaps(self, threshold: float = 0.9) -> List[DiagnosticResult]:
        """对所有路由进行全局重叠检测"""
        self.component_manager.ensure_ready()
        all_routes = self.component_manager.route_manager.get_all_routes()
        
        results = []
        for route in all_routes:
            result = self.analyze_route_overlap(route.id, threshold)
            if result.overlaps:
                results.append(result)
        
        return results
