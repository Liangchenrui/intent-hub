"""同步服务 - 处理索引同步业务逻辑"""

from typing import Any, Dict

from intent_hub.core.components import ComponentManager
from intent_hub.utils.logger import logger


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
        self, config_routes: list, encoder, qdrant_client
    ) -> Dict[str, Any]:
        """全量重建模式：清空后重新创建"""
        logger.info("执行全量重建模式")
        qdrant_client.delete_all()

        total_points = 0
        total_negative_points = 0
        failed_routes = []
        for route in config_routes:
            try:
                # 处理正例向量
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold,
                )
                total_points += len(route.utterances)

                # 处理负例向量
                negative_samples = getattr(route, "negative_samples", [])
                if negative_samples:
                    negative_embeddings = encoder.encode(negative_samples)
                    negative_threshold = getattr(route, "negative_threshold", 0.95)
                    qdrant_client.upsert_route_negative_samples(
                        route_id=route.id,
                        route_name=route.name,
                        negative_samples=negative_samples,
                        embeddings=negative_embeddings,
                        negative_threshold=negative_threshold,
                    )
                    total_negative_points += len(negative_samples)
                else:
                    # 确保删除可能存在的旧负例向量
                    qdrant_client.delete_route_negative_samples(route.id)
            except Exception as e:
                logger.error(
                    f"处理路由 {route.name} (ID: {route.id}) 时失败: {e}", exc_info=True
                )
                failed_routes.append(
                    {"route_id": route.id, "route_name": route.name, "error": str(e)}
                )

        # 全量同步后同步启动全量诊断，确保数据一致性
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService

            diag_service = DiagnosticService(self.component_manager)
            diag_service.analyze_all_overlaps(use_cache=False)
            logger.info("全量同步后已同步完成全量诊断")
        except Exception as e:
            logger.error(f"全量同步后启动全量诊断失败: {e}")

        result = {
            "message": "全量重新索引完成"
            if not failed_routes
            else f"全量重新索引完成，但有 {len(failed_routes)} 个路由失败",
            "mode": "full",
            "routes_count": len(config_routes),
            "total_points": total_points,
            "total_negative_points": total_negative_points,
            "success_count": len(config_routes) - len(failed_routes),
            "failed_count": len(failed_routes),
        }
        if failed_routes:
            result["failed_routes"] = failed_routes
            logger.warning(
                f"全量重新索引完成，但有 {len(failed_routes)} 个路由失败: {[r['route_name'] for r in failed_routes]}"
            )
        return result

    def _incremental_reindex(
        self,
        config_routes: list,
        config_route_ids: set,
        encoder,
        qdrant_client,
        route_manager,
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
            qdrant_client.delete_route_negative_samples(route_id)
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
                # 处理正例向量
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold,
                )
                total_points += len(route.utterances)

                # 处理负例向量
                negative_samples = getattr(route, "negative_samples", [])
                if negative_samples:
                    negative_embeddings = encoder.encode(negative_samples)
                    negative_threshold = getattr(route, "negative_threshold", 0.95)
                    qdrant_client.upsert_route_negative_samples(
                        route_id=route.id,
                        route_name=route.name,
                        negative_samples=negative_samples,
                        embeddings=negative_embeddings,
                        negative_threshold=negative_threshold,
                    )

                new_count += 1
            else:
                # 现有路由：检查是否需要更新
                # 由于无法直接从Qdrant获取路由的哈希值，我们采用保守策略：
                # 先删除旧向量点，再插入新的（确保一致性）
                # 这样可以处理utterances变化、名称变化、阈值变化等情况
                logger.info(f"更新路由: {route.name} (ID: {route.id})")
                # 先删除旧的向量点（包括正例和负例）
                qdrant_client.delete_route(route.id)
                qdrant_client.delete_route_negative_samples(route.id)

                # 重新编码并插入新的正例向量点
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold,
                )
                total_points += len(route.utterances)

                # 处理负例向量
                negative_samples = getattr(route, "negative_samples", [])
                if negative_samples:
                    negative_embeddings = encoder.encode(negative_samples)
                    negative_threshold = getattr(route, "negative_threshold", 0.95)
                    qdrant_client.upsert_route_negative_samples(
                        route_id=route.id,
                        route_name=route.name,
                        negative_samples=negative_samples,
                        embeddings=negative_embeddings,
                        negative_threshold=negative_threshold,
                    )

                updated_count += 1

        # 处理被删除的路由缓存清理
        if routes_to_delete:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                for rid in routes_to_delete:
                    diag_service.remove_route_from_cache(rid)
            except Exception as e:
                logger.error(f"清理已删除路由的诊断缓存失败: {e}")

        # 增量同步后，如果有任何变化，同步启动全量诊断确保最新
        if new_count > 0 or updated_count > 0 or deleted_count > 0:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                diag_service.analyze_all_overlaps(use_cache=False)
                logger.info("增量同步后已同步完成全量诊断")
            except Exception as e:
                logger.error(f"增量同步后同步启动全量诊断失败: {e}")

        return {
            "message": "增量重新索引完成",
            "mode": "incremental",
            "routes_count": len(config_routes),
            "new_routes": new_count,
            "updated_routes": updated_count,
            "deleted_routes": deleted_count,
            "skipped_routes": skipped_count,
            "total_points": total_points,
        }

    def sync_route(self, route_id: int) -> Dict[str, Any]:
        """同步单个路由到向量数据库

        Args:
            route_id: 要同步的路由ID

        Returns:
            包含同步结果的字典

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 重新加载路由配置文件（热加载）
        route_manager.reload()

        # 获取路由配置
        route = route_manager.get_route(route_id)
        if not route:
            raise ValueError(f"路由ID {route_id} 不存在")

        logger.info(f"开始同步单个路由: {route.name} (ID: {route_id})")

        # 先删除旧的向量点（包括正例和负例）
        qdrant_client.delete_route(route_id)
        qdrant_client.delete_route_negative_samples(route_id)

        # 重新编码并插入新的正例向量点
        embeddings = encoder.encode(route.utterances)
        qdrant_client.upsert_route_utterances(
            route_id=route.id,
            route_name=route.name,
            utterances=route.utterances,
            embeddings=embeddings,
            score_threshold=route.score_threshold,
        )
        total_points = len(route.utterances)

        # 处理负例向量
        negative_samples = getattr(route, "negative_samples", [])
        total_negative_points = 0
        if negative_samples:
            negative_embeddings = encoder.encode(negative_samples)
            negative_threshold = getattr(route, "negative_threshold", 0.95)
            qdrant_client.upsert_route_negative_samples(
                route_id=route.id,
                route_name=route.name,
                negative_samples=negative_samples,
                embeddings=negative_embeddings,
                negative_threshold=negative_threshold,
            )
            total_negative_points = len(negative_samples)

        logger.info(
            f"成功同步路由 {route.name} (ID: {route_id})，共 {total_points} 个正例向量点，{total_negative_points} 个负例向量点"
        )

        return {
            "message": f"路由 {route.name} 同步完成",
            "route_id": route_id,
            "route_name": route.name,
            "total_points": total_points,
            "total_negative_points": total_negative_points,
        }

    def sync_routes(self, route_ids: list) -> Dict[str, Any]:
        """同步多个路由到向量数据库

        Args:
            route_ids: 要同步的路由ID列表

        Returns:
            包含同步结果的字典
        """
        self.component_manager.ensure_ready()

        results = []
        for route_id in route_ids:
            try:
                result = self.sync_route(route_id)
                results.append(result)
            except Exception as e:
                logger.error(f"同步路由 {route_id} 失败: {e}")
                results.append({"route_id": route_id, "error": str(e)})

        return {
            "message": f"已同步 {len([r for r in results if 'error' not in r])} 个路由",
            "results": results,
        }
