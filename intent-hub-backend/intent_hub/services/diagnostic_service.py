import numpy as np
import json
import os
from typing import List, Dict, Any, Optional
from intent_hub.core.components import ComponentManager
from intent_hub.models import (
    DiagnosticResult,
    RouteOverlap,
    ConflictPoint,
    RouteConfig,
    RepairSuggestion,
)
from intent_hub.utils.logger import logger

try:
    from scipy.spatial.distance import directed_hausdorff  # type: ignore
except Exception:  # pragma: no cover
    directed_hausdorff = None

try:
    import umap  # type: ignore
except Exception:  # pragma: no cover
    umap = None

class DiagnosticService:
    """诊断服务 - 处理语义重叠检测逻辑"""

    CACHE_FILE = "diagnostics_cache.json"

    def __init__(self, component_manager: ComponentManager):
        self.component_manager = component_manager
        # 获取基础目录以确保存储位置一致
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_path = os.path.join(self.base_dir, self.CACHE_FILE)

    def _load_cache(self) -> Dict[str, Any]:
        """从文件加载诊断缓存"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载诊断缓存失败: {e}")
        return {}

    def _save_cache(self, cache_data: Dict[str, Any]):
        """将诊断数据保存到缓存文件"""
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存诊断缓存失败: {e}")

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
            
            # B. 计算 Hausdorff 距离
            h_dist = None
            if directed_hausdorff is not None:
                # Hausdorff 距离越小表示越重叠
                h_dist = max(
                    directed_hausdorff(current_vectors, other_vectors)[0],
                    directed_hausdorff(other_vectors, current_vectors)[0]
                )

            # C. 查找当前路由中哪些点非常接近对方路由的质心
            conflicting_points = []
            for p in current_points:
                sim = self._cosine_similarity(np.array(p["vector"]), centroid_other)
                if sim >= threshold:
                    conflicting_points.append(ConflictPoint(
                        utterance=p["payload"].get("utterance", ""),
                        similarity=sim
                    ))

            # 如果质心太接近，或者有具体的冲突点，或者 Hausdorff 距离非常小，则记录重叠
            # 注意：Hausdorff 距离的阈值需要根据具体向量维度和分布调整，这里先记录数据
            if centroid_sim >= threshold or conflicting_points:
                overlaps.append(RouteOverlap(
                    target_route_id=other_route.id,
                    target_route_name=other_route.name,
                    overlap_score=centroid_sim,
                    hausdorff_distance=float(h_dist) if h_dist is not None else None,
                    conflicting_utterances=conflicting_points
                ))

        # 按相似度降序排序
        overlaps.sort(key=lambda x: x.overlap_score, reverse=True)

        return DiagnosticResult(
            route_id=route_id,
            route_name=current_route.name,
            overlaps=overlaps
        )

    def analyze_all_overlaps(self, threshold: float = 0.9, use_cache: bool = True) -> List[DiagnosticResult]:
        """对所有路由进行全局重叠检测"""
        if use_cache:
            cache = self._load_cache()
            if cache:
                logger.info("从缓存中读取诊断结果")
                # 过滤出有重叠的结果
                results = []
                for r_id_str, r_data in cache.items():
                    res = DiagnosticResult(**r_data)
                    if res.overlaps:
                        results.append(res)
                return results

        # 如果不使用缓存，则重新计算
        self.component_manager.ensure_ready()
        all_routes = self.component_manager.route_manager.get_all_routes()
        
        results = []
        cache_to_save = {}
        for route in all_routes:
            result = self.analyze_route_overlap(route.id, threshold)
            cache_to_save[str(route.id)] = result.dict()
            if result.overlaps:
                results.append(result)
        
        # 保存到缓存
        self._save_cache(cache_to_save)
        return results

    def update_route_diagnostics(self, route_id: int, threshold: float = 0.9):
        """增量更新指定路由的诊断信息"""
        logger.info(f"增量更新路由 ID {route_id} 的诊断信息")
        cache = self._load_cache()
        
        # 1. 计算当前路由的最新诊断结果
        current_result = self.analyze_route_overlap(route_id, threshold)
        cache[str(route_id)] = current_result.dict()

        # 2. 更新其他路由中关于当前路由的重叠信息
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager
        qdrant_client = self.component_manager.qdrant_client
        
        current_points = qdrant_client.get_route_vectors(route_id)
        if current_points:
            current_vectors = [np.array(p["vector"]) for p in current_points]
            centroid_current = np.mean(current_vectors, axis=0)
            
            for other_id_str, other_data in cache.items():
                other_id = int(other_id_str)
                if other_id == route_id:
                    continue
                
                # 获取对方路由的向量，计算它与当前修改路由的重叠情况
                other_points = qdrant_client.get_route_vectors(other_id)
                if not other_points:
                    continue
                    
                other_vectors = [np.array(p["vector"]) for p in other_points]
                centroid_other = np.mean(other_vectors, axis=0)
                
                # 计算两者的相似度
                centroid_sim = self._cosine_similarity(centroid_other, centroid_current)
                
                # 计算 Hausdorff
                h_dist = None
                if directed_hausdorff is not None:
                    h_dist = max(
                        directed_hausdorff(other_vectors, current_vectors)[0],
                        directed_hausdorff(current_vectors, other_vectors)[0]
                    )
                
                # 检查 other_points 中是否有靠近 current 质心的点
                conflicting_points = []
                for p in other_points:
                    sim = self._cosine_similarity(np.array(p["vector"]), centroid_current)
                    if sim >= threshold:
                        conflicting_points.append(ConflictPoint(
                            utterance=p["payload"].get("utterance", ""),
                            similarity=sim
                        ))
                
                # 更新 other_data 中的 overlaps 列表
                # 先移除旧的关于 route_id 的记录
                other_res = DiagnosticResult(**other_data)
                other_res.overlaps = [o for o in other_res.overlaps if o.target_route_id != route_id]
                
                # 如果存在重叠，添加新记录
                if centroid_sim >= threshold or conflicting_points:
                    other_res.overlaps.append(RouteOverlap(
                        target_route_id=route_id,
                        target_route_name=current_result.route_name,
                        overlap_score=centroid_sim,
                        hausdorff_distance=float(h_dist) if h_dist is not None else None,
                        conflicting_utterances=conflicting_points
                    ))
                    # 重新排序
                    other_res.overlaps.sort(key=lambda x: x.overlap_score, reverse=True)
                
                # 更新缓存中的数据
                cache[other_id_str] = other_res.dict()

        # 3. 保存更新后的缓存
        self._save_cache(cache)

    def remove_route_from_cache(self, route_id: int):
        """从诊断缓存中移除指定路由"""
        logger.info(f"从诊断缓存中移除路由 ID {route_id}")
        cache = self._load_cache()
        
        # 1. 移除该路由自身的记录
        cache.pop(str(route_id), None)
        
        # 2. 从其他路由的 overlaps 列表中移除该路由
        for other_id_str, other_data in cache.items():
            if "overlaps" in other_data:
                other_data["overlaps"] = [
                    o for o in other_data["overlaps"] 
                    if o.get("target_route_id") != route_id
                ]
        
        # 3. 保存更新后的缓存
        self._save_cache(cache)

    def build_umap_projection(self, n_neighbors: int = 15, min_dist: float = 0.1, seed: int = 42) -> Dict[str, Any]:
        """对 Qdrant 中所有点进行 UMAP 降维，返回 2D 坐标（用于可视化）

        Returns:
            {
              "points": [
                {"x": float, "y": float, "route_id": int, "route_name": str, "utterance": str}
              ],
              "meta": {"n_points": int, "n_neighbors": int, "min_dist": float}
            }
        """
        self.component_manager.ensure_ready()
        qdrant_client = self.component_manager.qdrant_client

        if umap is None:
            raise RuntimeError("未安装 umap-learn，无法进行 UMAP 降维")

        all_points = qdrant_client.scroll_all_points(with_vectors=True)
        if not all_points:
            return {"points": [], "meta": {"n_points": 0, "n_neighbors": n_neighbors, "min_dist": min_dist}}

        vectors = []
        payloads = []
        for p in all_points:
            v = p.get("vector")
            pl = p.get("payload") or {}
            if v is None:
                continue
            # 只保留有 route_id 的点（避免脏数据影响可视化）
            if pl.get("route_id") is None:
                continue
            vectors.append(np.array(v, dtype=np.float32))
            payloads.append(pl)

        if not vectors:
            return {"points": [], "meta": {"n_points": 0, "n_neighbors": n_neighbors, "min_dist": min_dist}}

        X = np.vstack(vectors)
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            metric="cosine",
            random_state=seed,
        )

        Y = reducer.fit_transform(X)

        out_points = []
        for (x, y), pl in zip(Y, payloads):
            out_points.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "route_id": int(pl.get("route_id")),
                    "route_name": str(pl.get("route_name") or ""),
                    "utterance": str(pl.get("utterance") or ""),
                }
            )

        return {
            "points": out_points,
            "meta": {"n_points": len(out_points), "n_neighbors": n_neighbors, "min_dist": min_dist},
        }

    def get_repair_suggestions(
        self, source_route_id: int, target_route_id: int
    ) -> RepairSuggestion:
        """使用 LLM 为冲突的两个路由生成修复建议"""
        from intent_hub.services.llm_factory import LLMFactory
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from pydantic import Field, BaseModel

        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        route_a = route_manager.get_route(source_route_id)
        route_b = route_manager.get_route(target_route_id)

        if not route_a or not route_b:
            raise ValueError("指定的路由不存在")

        # 获取冲突示例
        overlap_info = self.analyze_route_overlap(source_route_id)
        target_overlap = next(
            (o for o in overlap_info.overlaps if o.target_route_id == target_route_id),
            None,
        )
        conflict_examples = (
            [c.utterance for c in target_overlap.conflicting_utterances]
            if target_overlap
            else []
        )

        llm = LLMFactory.create_llm(temperature=0.7)

        from intent_hub.config import Config
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    Config.AGENT_REPAIR_PROMPT,
                ),
            ]
        )

        chain = prompt | llm | JsonOutputParser()

        try:
            result = chain.invoke(
                {
                    "name_a": route_a.name,
                    "desc_a": route_a.description,
                    "utterances_a": route_a.utterances[:10],  # 限制数量
                    "name_b": route_b.name,
                    "desc_b": route_b.description,
                    "conflicts": conflict_examples[:5],
                }
            )

            return RepairSuggestion(
                route_id=source_route_id,
                route_name=route_a.name,
                new_utterances=result.get("new_utterances", []),
                negative_samples=result.get("negative_samples", []),
                rationalization=result.get("rationalization", ""),
            )
        except Exception as e:
            logger.error(f"LLM 生成修复建议失败: {str(e)}")
            raise RuntimeError(f"修复建议生成失败: {str(e)}")

    def apply_repair(self, route_id: int, utterances: List[str]) -> bool:
        """应用修复建议，更新 Qdrant 中的数据"""
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager
        qdrant_client = self.component_manager.qdrant_client

        route = route_manager.get_route(route_id)
        if not route:
            raise ValueError(f"路由ID {route_id} 不存在")

        # 1. 更新 route_manager (内存/文件)
        route.utterances = utterances
        route_manager.update_route(route.id, route)

        # 2. 更新 Qdrant
        # 这里最简单的做法是删除该路由旧的所有点，重新插入
        qdrant_client.delete_route(route_id)

        # 重新编码并插入
        encoder = self.component_manager.encoder
        vectors = encoder.encode(utterances)

        # 使用封装好的 upsert_route_utterances 方法
        qdrant_client.upsert_route_utterances(
            route_id=route_id,
            route_name=route.name,
            utterances=utterances,
            embeddings=vectors.tolist() if hasattr(vectors, "tolist") else vectors,
            score_threshold=route.score_threshold,
        )

        # 触发增量诊断更新
        try:
            self.update_route_diagnostics(route_id)
        except Exception as e:
            logger.error(f"修复后增量诊断更新失败: {e}")

        return True
