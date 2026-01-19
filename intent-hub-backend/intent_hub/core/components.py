"""核心组件管理 - 统一管理所有组件的初始化和依赖注入"""

from typing import Optional

from intent_hub.config import Config
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.utils.logger import logger


class ComponentManager:
    """组件管理器 - 统一管理所有核心组件的初始化"""

    def __init__(self):
        """初始化组件管理器"""
        self._encoder: Optional[QwenEmbeddingEncoder] = None
        self._qdrant_client: Optional[IntentHubQdrantClient] = None
        self._route_manager: Optional[RouteManager] = None
        self._initialized = False

    @property
    def encoder(self) -> QwenEmbeddingEncoder:
        """获取编码器实例"""
        if self._encoder is None:
            raise RuntimeError("编码器未初始化，请先调用 init_components()")
        return self._encoder

    @property
    def qdrant_client(self) -> IntentHubQdrantClient:
        """获取Qdrant客户端实例"""
        if self._qdrant_client is None:
            raise RuntimeError("Qdrant客户端未初始化，请先调用 init_components()")
        return self._qdrant_client

    @property
    def route_manager(self) -> RouteManager:
        """获取路由管理器实例"""
        if self._route_manager is None:
            raise RuntimeError("路由管理器未初始化，请先调用 init_components()")
        return self._route_manager

    def is_ready(self) -> bool:
        """检查所有组件是否已初始化"""
        return (
            self._encoder is not None
            and self._qdrant_client is not None
            and self._route_manager is not None
        )

    def reinit_components(self):
        """重新初始化所有组件"""
        self._initialized = False
        self._encoder = None
        self._qdrant_client = None
        self._route_manager = None
        self.init_components()

    def init_components(self, force: bool = False):
        """初始化所有组件

        Args:
            force: 是否强制重新初始化（即使已标记为已初始化）
        """
        if self._initialized and not force:
            logger.info("组件已初始化，跳过重复初始化")
            return

        # 尝试初始化编码器
        if self._encoder is None or force:
            try:
                logger.info("正在初始化编码器...")
                self._encoder = QwenEmbeddingEncoder(
                    model_name=Config.EMBEDDING_MODEL_NAME,
                    device=Config.EMBEDDING_DEVICE,
                    batch_size=Config.BATCH_SIZE,
                    huggingface_token=Config.HUGGINGFACE_ACCESS_TOKEN,
                    huggingface_provider=Config.HUGGINGFACE_PROVIDER,
                    huggingface_timeout=Config.HUGGINGFACE_TIMEOUT,
                )
                # 触发初始化以获取维度
                _ = self._encoder.dimensions
                mode = (
                    "HuggingFace Inference API"
                    if self._encoder.is_remote
                    else "本地模型"
                )
                logger.info(f"编码器初始化完成，模式: {mode}")
            except Exception as e:
                logger.error(f"编码器初始化失败: {e}")
                self._encoder = None

        # 尝试初始化Qdrant客户端
        if self._qdrant_client is None or force:
            try:
                logger.info("正在初始化Qdrant客户端...")
                dimensions = self._encoder.dimensions if self._encoder else 1024
                self._qdrant_client = IntentHubQdrantClient(
                    url=Config.QDRANT_URL,
                    collection_name=Config.QDRANT_COLLECTION,
                    dimensions=dimensions,
                    api_key=Config.QDRANT_API_KEY,
                )
                logger.info("Qdrant客户端初始化完成")
            except Exception as e:
                logger.error(f"Qdrant客户端初始化失败: {e}")
                self._qdrant_client = None

        # 初始化路由管理器
        if self._route_manager is None or force:
            try:
                logger.info("正在初始化路由管理器...")
                self._route_manager = RouteManager()
                logger.info("路由管理器初始化完成")
            except Exception as e:
                logger.error(f"路由管理器初始化失败: {e}")
                self._route_manager = None

        # 同步路由数据到Qdrant
        if self._qdrant_client and self._encoder and self._route_manager:
            try:
                logger.info("检查Qdrant数据同步状态...")
                if not self._qdrant_client.has_data():
                    logger.info("Qdrant为空，开始同步路由数据...")
                    routes = self._route_manager.get_all_routes()
                    if routes:
                        total_points = 0
                        for route in routes:
                            embeddings = self._encoder.encode(route.utterances)
                            self._qdrant_client.upsert_route_utterances(
                                route_id=route.id,
                                route_name=route.name,
                                utterances=route.utterances,
                                embeddings=embeddings,
                                score_threshold=route.score_threshold,
                            )
                            total_points += len(route.utterances)
                        logger.info(
                            f"成功同步 {len(routes)} 个路由，共 {total_points} 个向量点到Qdrant"
                        )
                    else:
                        logger.warning("路由管理器中没有路由配置，Qdrant保持为空")
                else:
                    logger.info("Qdrant中已有数据，跳过同步")
            except Exception as e:
                logger.error(f"数据同步过程中出现错误: {e}")

        # 只有当所有关键组件都成功初始化后，才标记为已初始化
        if self.is_ready():
            self._initialized = True
            logger.info("所有组件初始化成功")
        else:
            self._initialized = False
            logger.info("部分组件初始化失败，下次调用将重试")

    def ensure_ready(self):
        """确保组件已初始化，如果未初始化则初始化"""
        if not self.is_ready():
            self.init_components()


# 全局组件管理器实例（单例模式）
_component_manager: Optional[ComponentManager] = None


def get_component_manager() -> ComponentManager:
    """获取全局组件管理器实例"""
    global _component_manager
    if _component_manager is None:
        _component_manager = ComponentManager()
    return _component_manager
