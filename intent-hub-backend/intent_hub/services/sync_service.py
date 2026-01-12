"""同步服务 - 处理索引同步业务逻辑"""
from typing import Dict, Any
from intent_hub.utils.logger import logger

from intent_hub.core.components import ComponentManager


class SyncService:
    """同步服务类 - 处理索引同步的核心业务逻辑"""
    
    def __init__(self, component_manager: ComponentManager):
        """初始化同步服务
        
        Args:
            component_manager: 组件管理器实例
        """
        self.component_manager = component_manager
    
    def reindex(self, force_full: bool = False) -> Dict[str, Any]:
        """重新索引：支持全量和增量两种模式
        
        Args:
            force_full: 如果为True，则执行全量重建（清空后重新创建）
            
        Returns:
            包含同步结果的字典
        """
        self.component_manager.ensure_ready()
        
        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager
        
        # 1. 重新加载路由配置文件（热加载）
        route_manager.reload()
        
        # 2. 获取配置文件中的路由
        config_routes = route_manager.get_all_routes()
        config_route_ids = {route.id for route in config_routes}
        
        if force_full:
            return self._full_reindex(config_routes, encoder, qdrant_client)
        else:
            return self._incremental_reindex(
                config_routes, config_route_ids, encoder, qdrant_client, route_manager
            )
    
    def _full_reindex(
        self,
        config_routes: list,
        encoder,
        qdrant_client
    ) -> Dict[str, Any]:
        """全量重建模式：清空后重新创建"""
        logger.info("执行全量重建模式")
        qdrant_client.delete_all()
        
        total_points = 0
        for route in config_routes:
            embeddings = encoder.encode(route.utterances)
            qdrant_client.upsert_route_utterances(
                route_id=route.id,
                route_name=route.name,
                utterances=route.utterances,
                embeddings=embeddings,
                score_threshold=route.score_threshold
            )
            total_points += len(route.utterances)
        
        return {
            "message": "全量重新索引完成",
            "mode": "full",
            "routes_count": len(config_routes),
            "total_points": total_points
        }
    
    def _incremental_reindex(
        self,
        config_routes: list,
        config_route_ids: set,
        encoder,
        qdrant_client,
        route_manager
    ) -> Dict[str, Any]:
        """增量更新模式：只更新变化的路由"""
        logger.info("执行增量更新模式")
        
        # 3. 获取Qdrant中现有的路由ID集合
        existing_route_ids = qdrant_client.get_existing_route_ids()
        
        # 4. 计算需要删除的路由（在Qdrant中存在但配置文件中不存在）
        routes_to_delete = existing_route_ids - config_route_ids
        deleted_count = 0
        for route_id in routes_to_delete:
            logger.info(f"删除不再存在的路由: {route_id}")
            qdrant_client.delete_route(route_id)
            deleted_count += 1
        
        # 5. 增量更新配置文件中的路由
        updated_count = 0
        skipped_count = 0
        new_count = 0
        total_points = 0
        
        for route in config_routes:
            route_hash = route_manager.compute_route_hash(route)
            is_new_route = route.id not in existing_route_ids
            
            if is_new_route:
                # 新路由：直接插入
                logger.info(f"新增路由: {route.name} (ID: {route.id})")
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold
                )
                total_points += len(route.utterances)
                new_count += 1
            else:
                # 现有路由：检查是否需要更新
                # 由于无法直接从Qdrant获取路由的哈希值，我们采用保守策略：
                # 先删除旧向量点，再插入新的（确保一致性）
                # 这样可以处理utterances变化、名称变化、阈值变化等情况
                logger.info(f"更新路由: {route.name} (ID: {route.id})")
                # 先删除旧的向量点
                qdrant_client.delete_route(route.id)
                # 重新编码并插入新的向量点
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold
                )
                total_points += len(route.utterances)
                updated_count += 1
        
        return {
            "message": "增量重新索引完成",
            "mode": "incremental",
            "routes_count": len(config_routes),
            "new_routes": new_count,
            "updated_routes": updated_count,
            "deleted_routes": deleted_count,
            "skipped_routes": skipped_count,
            "total_points": total_points
        }

