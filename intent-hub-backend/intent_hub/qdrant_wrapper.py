"""Qdrant客户端封装模块"""

import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    PointStruct,
    VectorParams,
)

from intent_hub.utils.logger import logger


class IntentHubQdrantClient:
    """Intent Hub专用的Qdrant客户端封装"""

    # Qdrant payload中的字段名
    ROUTE_ID_KEY = "route_id"
    ROUTE_NAME_KEY = "route_name"
    UTTERANCE_KEY = "utterance"
    SCORE_THRESHOLD_KEY = "score_threshold"

    def __init__(
        self,
        url: str,
        collection_name: str,
        dimensions: int,
        api_key: Optional[str] = None,
    ):
        """初始化Qdrant客户端

        Args:
            url: Qdrant服务地址
            collection_name: Collection名称
            dimensions: 向量维度
            api_key: API密钥（可选）
        """
        # 彻底清洗 URL：去除空格、结尾斜杠
        self.url = url.strip().rstrip("/") if url else ""
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.api_key = api_key

        try:
            # 针对 Qdrant Cloud 环境，如果检测到 SSL 错误，尝试在代码层级绕过代理
            import os

            # 内部使用的干净 URL
            clean_url = self.url

            # 如果是云端地址，强制清理环境中的代理设置，防止 httpcore/httpx 走代理
            if clean_url and ".qdrant.io" in clean_url:
                host_only = (
                    clean_url.replace("https://", "")
                    .replace("http://", "")
                    .split(":")[0]
                ).strip()

                # 记录并打印以便调试
                no_proxy = os.environ.get("NO_PROXY", "")
                if host_only not in no_proxy:
                    os.environ["NO_PROXY"] = (
                        f"{no_proxy},{host_only}" if no_proxy else host_only
                    )
                    logger.info(f"已将 {host_only} 加入 NO_PROXY")

            # 根据配置决定使用 url 还是 host 模式
            if clean_url and (
                clean_url.startswith("http://")
                or clean_url.startswith("https://")
                or clean_url.startswith("grpc://")
            ):
                # 智能修复：如果是 Qdrant Cloud 地址且带了 6333 端口，云端通常使用 443
                if ".cloud.qdrant.io" in clean_url and ":6333" in clean_url:
                    logger.warning(
                        "检测到 Qdrant Cloud 地址使用了 6333 端口，尝试自动修正为标准 HTTPS (443)..."
                    )
                    clean_url = clean_url.replace(":6333", "")

                self.client = QdrantClient(url=clean_url, api_key=api_key, timeout=30)
                logger.info(f"Qdrant客户端以 URL 模式初始化: {clean_url}")
            else:
                # Host 模式初始化
                self.client = QdrantClient(
                    host=clean_url if clean_url else None,
                    api_key=api_key,
                    https=True
                    if (api_key and clean_url and ".qdrant.io" in clean_url)
                    else None,
                    timeout=30,
                )
                logger.info(
                    f"Qdrant客户端以 Host 模式初始化: {clean_url if clean_url else 'default'}"
                )
        except Exception as e:
            if "SSL" in str(e) or "EOF" in str(e):
                logger.error(
                    "Qdrant 连接发生 SSL 错误。请检查: 1. 端口是否正确(云端通常为443) 2. 环境中是否有代理(HTTP_PROXY)干扰连接。"
                )
            logger.error(f"Qdrant客户端初始化失败: {e}", exc_info=True)
            raise

        self._ensure_collection()

    def _ensure_collection(self):
        """确保Collection存在，不存在则创建"""
        try:
            if not self.client.collection_exists(self.collection_name):
                logger.info(f"创建Collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimensions, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Collection创建成功: {self.collection_name}")
            else:
                logger.info(f"Collection已存在: {self.collection_name}")
        except Exception as e:
            logger.error(f"Collection初始化失败: {e}", exc_info=True)
            raise

    def upsert_route_utterances(
        self,
        route_id: int,
        route_name: str,
        utterances: List[str],
        embeddings: List[List[float]],
        score_threshold: float,
    ):
        """插入或更新路由的utterances向量

        Args:
            route_id: 路由ID
            route_name: 路由名称
            utterances: 示例语句列表
            embeddings: 对应的向量列表
            score_threshold: 相似度阈值
        """
        if len(utterances) != len(embeddings):
            raise ValueError("utterances和embeddings长度不匹配")

        points = []
        for utterance, embedding in zip(utterances, embeddings):
            # 使用确定性UUID生成point ID
            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, f"{route_id}:{route_name}:{utterance}")
            )

            payload = {
                self.ROUTE_ID_KEY: route_id,
                self.ROUTE_NAME_KEY: route_name,
                self.UTTERANCE_KEY: utterance,
                self.SCORE_THRESHOLD_KEY: score_threshold,
            }

            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"成功更新路由 {route_name} 的 {len(points)} 个向量点")
        except Exception as e:
            logger.error(f"更新向量点失败: {e}", exc_info=True)
            raise

    def delete_route(self, route_id: int):
        """删除指定路由的所有向量点

        Args:
            route_id: 路由ID
        """
        try:
            # 注意：Qdrant的FieldCondition需要匹配数值类型，这里使用MatchValue
            from qdrant_client.models import MatchValue

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                        )
                    ]
                ),
            )
            logger.info(f"成功删除路由ID {route_id} 的所有向量点")
        except Exception as e:
            logger.error(f"删除路由向量点失败: {e}", exc_info=True)
            raise

    def search(self, query_vector: List[float], top_k: int = 1) -> List[Dict[str, Any]]:
        """搜索最相似的向量

        Args:
            query_vector: 查询向量
            top_k: 返回Top K结果

        Returns:
            搜索结果列表，每个结果包含score和payload
        """
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                with_payload=True,
            )

            search_results = []
            for point in results.points:
                search_results.append(
                    {
                        "score": point.score,
                        "payload": {
                            self.ROUTE_ID_KEY: point.payload.get(self.ROUTE_ID_KEY),
                            self.ROUTE_NAME_KEY: point.payload.get(self.ROUTE_NAME_KEY),
                            self.UTTERANCE_KEY: point.payload.get(self.UTTERANCE_KEY),
                            self.SCORE_THRESHOLD_KEY: point.payload.get(
                                self.SCORE_THRESHOLD_KEY
                            ),
                        },
                    }
                )

            return search_results
        except Exception as e:
            logger.error(f"向量搜索失败: {e}", exc_info=True)
            raise

    def delete_all(self):
        """清空Collection中的所有向量点"""
        try:
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()
            logger.info(f"成功清空Collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"清空Collection失败: {e}", exc_info=True)
            raise

    def is_ready(self) -> bool:
        """检查Qdrant服务是否可用"""
        try:
            return self.client.collection_exists(self.collection_name)
        except Exception:
            return False

    def has_data(self) -> bool:
        """检查Collection中是否有数据"""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count > 0
        except Exception as e:
            logger.error(f"检查Collection数据失败: {e}", exc_info=True)
            return False

    def get_existing_route_ids(self) -> set[int]:
        """获取Qdrant中所有现有的路由ID集合

        Returns:
            路由ID集合
        """
        try:
            route_ids = set()
            # 使用scroll方法遍历所有点，提取唯一的route_id
            offset = None
            batch_size = 100

            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, next_offset = result

                if not points:  # 没有更多点了
                    break

                # 从payload中提取route_id
                for point in points:
                    route_id = point.payload.get(self.ROUTE_ID_KEY)
                    if route_id is not None:
                        route_ids.add(route_id)

                offset = next_offset
                if next_offset is None:  # 没有更多数据了
                    break

            logger.info(
                f"从Qdrant获取到 {len(route_ids)} 个现有路由ID: {sorted(route_ids)}"
            )
            return route_ids
        except Exception as e:
            logger.error(f"获取现有路由ID失败: {e}", exc_info=True)
            raise
