"""Qdrant客户端封装模块"""

import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    PayloadSchemaType,
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
    IS_NEGATIVE_KEY = "is_negative"  # 标识是否为负例向量
    NEGATIVE_THRESHOLD_KEY = "negative_threshold"  # 负例阈值

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

            # 如果是特定的外部地址，强制清理环境中的代理设置，防止 httpcore/httpx 走代理
            if clean_url and (
                ".qdrant.io" in clean_url or "free4inno.com" in clean_url
            ):
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

                self.client = QdrantClient(url=clean_url, api_key=api_key, timeout=600)
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

            # 确保关键字段有索引 (针对 Qdrant Cloud 的性能或强制要求)
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self.ROUTE_ID_KEY,
                    field_schema=PayloadSchemaType.INTEGER,
                )
                logger.info(f"已确保字段 {self.ROUTE_ID_KEY} 的索引存在")
            except Exception as e:
                # 如果索引已存在，忽略错误
                if (
                    "already exists" not in str(e).lower()
                    and "duplicate" not in str(e).lower()
                ):
                    logger.warning(f"创建 {self.ROUTE_ID_KEY} 索引时出现警告: {e}")

            # 为 is_negative 字段创建索引（用于负例向量过滤）
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self.IS_NEGATIVE_KEY,
                    field_schema=PayloadSchemaType.BOOL,
                )
                logger.info(f"已确保字段 {self.IS_NEGATIVE_KEY} 的索引存在")
            except Exception as e:
                # 如果索引已存在，忽略错误
                if (
                    "already exists" not in str(e).lower()
                    and "duplicate" not in str(e).lower()
                ):
                    logger.warning(f"创建 {self.IS_NEGATIVE_KEY} 索引时出现警告: {e}")

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

    def get_route_vectors(self, route_id: int) -> List[Dict[str, Any]]:
        """获取指定路由的所有向量点和载荷（排除负例向量）

        Args:
            route_id: 路由ID

        Returns:
            包含vector和payload的列表（仅包含正例向量）
        """
        try:
            from qdrant_client.models import MatchValue

            results = []
            offset = None
            batch_size = 100

            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                            )
                        ],
                        # 排除负例向量：is_negative 不为 True
                        must_not=[
                            FieldCondition(
                                key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                            )
                        ],
                    ),
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                points, next_offset = result
                for point in points:
                    # 双重检查：确保不是负例向量（兼容旧数据，如果 is_negative 字段不存在，也认为是正例）
                    payload = point.payload or {}
                    is_negative = payload.get(self.IS_NEGATIVE_KEY, False)
                    if not is_negative:
                        results.append({"vector": point.vector, "payload": payload})

                if next_offset is None:
                    break
                offset = next_offset

            return results
        except Exception as e:
            logger.error(f"获取路由 {route_id} 的向量失败: {e}", exc_info=True)
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

    def scroll_all_points(
        self, with_vectors: bool = True, exclude_negative: bool = True
    ) -> List[Dict[str, Any]]:
        """遍历 collection 中所有点（用于可视化/诊断等离线分析场景）

        Args:
            with_vectors: 是否返回向量
            exclude_negative: 是否排除负例向量，默认为 True（诊断时应该排除负例）

        Returns:
            列表元素结构: {"id": str|int, "vector": [...](可选), "payload": {...}}
        """
        try:
            from qdrant_client.models import MatchValue

            results: List[Dict[str, Any]] = []
            offset = None
            batch_size = 200

            # 构建过滤条件
            scroll_filter = None
            if exclude_negative:
                scroll_filter = Filter(
                    must_not=[
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        )
                    ]
                )

            while True:
                scroll_params = {
                    "collection_name": self.collection_name,
                    "limit": batch_size,
                    "offset": offset,
                    "with_payload": True,
                    "with_vectors": with_vectors,
                }
                if scroll_filter:
                    scroll_params["scroll_filter"] = scroll_filter

                points, next_offset = self.client.scroll(**scroll_params)

                for p in points:
                    # 双重检查：确保不是负例向量（如果 exclude_negative 为 True）
                    payload = p.payload or {}
                    if exclude_negative and payload.get(self.IS_NEGATIVE_KEY, False):
                        continue

                    item: Dict[str, Any] = {"id": p.id, "payload": payload}
                    if with_vectors:
                        item["vector"] = p.vector
                    results.append(item)

                if next_offset is None:
                    break
                offset = next_offset

            return results
        except Exception as e:
            logger.error(f"遍历所有向量点失败: {e}", exc_info=True)
            raise

    def upsert_route_negative_samples(
        self,
        route_id: int,
        route_name: str,
        negative_samples: List[str],
        embeddings: List[List[float]],
        negative_threshold: float,
    ):
        """插入或更新路由的负例向量

        Args:
            route_id: 路由ID
            route_name: 路由名称
            negative_samples: 负例语句列表
            embeddings: 对应的向量列表
            negative_threshold: 负例相似度阈值
        """
        if len(negative_samples) != len(embeddings):
            raise ValueError("negative_samples和embeddings长度不匹配")

        points = []
        for negative_sample, embedding in zip(negative_samples, embeddings):
            # 使用确定性UUID生成point ID，添加negative前缀以区分
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"negative:{route_id}:{route_name}:{negative_sample}",
                )
            )

            payload = {
                self.ROUTE_ID_KEY: route_id,
                self.ROUTE_NAME_KEY: route_name,
                self.UTTERANCE_KEY: negative_sample,
                self.IS_NEGATIVE_KEY: True,  # 标识为负例
                self.NEGATIVE_THRESHOLD_KEY: negative_threshold,
            }

            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"成功更新路由 {route_name} 的 {len(points)} 个负例向量点")
        except Exception as e:
            logger.error(f"更新负例向量点失败: {e}", exc_info=True)
            raise

    def search_negative_samples(
        self, query_vector: List[float], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索与查询向量最相似的负例向量

        Args:
            query_vector: 查询向量
            top_k: 返回Top K结果

        Returns:
            搜索结果列表，每个结果包含score和payload
        """
        try:
            from qdrant_client.models import MatchValue

            # 只搜索负例向量
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        )
                    ]
                ),
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
                            self.NEGATIVE_THRESHOLD_KEY: point.payload.get(
                                self.NEGATIVE_THRESHOLD_KEY, 0.95
                            ),
                        },
                    }
                )

            return search_results
        except Exception as e:
            logger.error(f"负例向量搜索失败: {e}", exc_info=True)
            raise

    def delete_route_negative_samples(self, route_id: int):
        """删除指定路由的所有负例向量点

        Args:
            route_id: 路由ID
        """
        try:
            from qdrant_client.models import MatchValue

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                        ),
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        ),
                    ]
                ),
            )
            logger.info(f"成功删除路由ID {route_id} 的所有负例向量点")
        except Exception as e:
            logger.error(f"删除负例向量点失败: {e}", exc_info=True)
            raise
