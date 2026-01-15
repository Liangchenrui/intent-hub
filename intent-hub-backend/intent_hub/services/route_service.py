"""路由服务 - 处理路由CRUD业务逻辑"""

from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from intent_hub.core.components import ComponentManager
from intent_hub.models import GenerateUtterancesRequest, RouteConfig
from intent_hub.services.llm_factory import LLMFactory
from intent_hub.utils.logger import logger


class UtteranceList(BaseModel):
    utterances: List[str] = Field(description="生成的提问列表")


class RouteService:
    """路由服务类 - 处理路由的CRUD操作"""

    def __init__(self, component_manager: ComponentManager):
        """初始化路由服务

        Args:
            component_manager: 组件管理器实例
        """
        self.component_manager = component_manager

    def get_all_routes(self) -> List[RouteConfig]:
        """获取所有路由配置

        Returns:
            路由配置列表
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        routes = route_manager.get_all_routes()
        logger.info(f"获取路由列表: 共 {len(routes)} 个路由")
        logger.debug(
            f"路由详情: {[{'id': r.id, 'name': r.name, 'utterances_count': len(r.utterances)} for r in routes]}"
        )
        return routes

    def search_routes(self, query: str) -> List[RouteConfig]:
        """搜索路由配置

        Args:
            query: 搜索关键词，会在名称、描述和例句中搜索

        Returns:
            匹配的路由配置列表
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        routes = route_manager.search_routes(query)
        logger.info(f"搜索路由 '{query}': 找到 {len(routes)} 个匹配的路由")
        logger.debug(f"匹配的路由: {[{'id': r.id, 'name': r.name} for r in routes]}")
        return routes

    def create_route(self, route: RouteConfig) -> RouteConfig:
        """创建或更新路由（含向量生成）

        Args:
            route: 路由配置

        Returns:
            创建或更新后的路由配置

        Raises:
            ValueError: 如果ID不为0且路由不存在
        """
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        if route.id == 0:
            routes = route_manager.get_all_routes()
            valid_ids = [r.id for r in routes if r.id != 0]

            if not valid_ids:
                new_id = 1
            else:
                new_id = max(valid_ids) + 1

            route.id = new_id
            logger.info(
                f"模式：检测到前端传入ID为0，将其视为[创建]，自动分配新ID: {route.id}"
            )
        else:
            if not route_manager.get_route(route.id):
                raise ValueError(
                    f"路由ID {route.id} 不存在，无法更新。如果想创建新路由，请将ID设为0"
                )
            logger.info(f"模式：更新现有路由 (ID: {route.id})")

        route_manager.add_route(route)
        
        # 1. 处理正例向量
        embeddings = encoder.encode(route.utterances)
        qdrant_client.upsert_route_utterances(
            route_id=route.id,
            route_name=route.name,
            utterances=route.utterances,
            embeddings=embeddings,
            score_threshold=route.score_threshold,
        )

        # 2. 处理负例向量
        if route.negative_samples:
            # 先删除旧的负例向量
            qdrant_client.delete_route_negative_samples(route.id)
            
            # 生成负例向量并插入
            negative_embeddings = encoder.encode(route.negative_samples)
            negative_threshold = getattr(route, 'negative_threshold', 0.95)
            qdrant_client.upsert_route_negative_samples(
                route_id=route.id,
                route_name=route.name,
                negative_samples=route.negative_samples,
                embeddings=negative_embeddings,
                negative_threshold=negative_threshold,
            )
            logger.info(
                f"成功处理路由 {route.name} 的 {len(route.negative_samples)} 个负例"
            )
        else:
            # 如果没有负例，删除可能存在的旧负例向量
            qdrant_client.delete_route_negative_samples(route.id)

        logger.info(f"成功处理路由: {route.name} (ID: {route.id})")

        # 同步触发增量诊断更新，确保数据一致性
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService
            diagnostic_service = DiagnosticService(self.component_manager)
            diagnostic_service.update_route_diagnostics(route.id)
            logger.info(f"已同步完成路由 ID {route.id} 的增量诊断更新")
        except Exception as e:
            logger.error(f"同步增量诊断失败: {e}")

        return route

    def update_route(self, route_id: int, route: RouteConfig) -> RouteConfig:
        """更新指定路由

        Args:
            route_id: 路由ID
            route: 新的路由配置

        Returns:
            更新后的路由配置

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 获取旧配置用于比较
        old_route = route_manager.get_route(route_id)
        if not old_route:
            raise ValueError(f"路由ID {route_id} 不存在")

        # 检查是否需要更新向量索引（语料、名称或阈值变化时需要）
        utterances_changed = set(old_route.utterances) != set(route.utterances)
        name_changed = old_route.name != route.name
        threshold_changed = old_route.score_threshold != route.score_threshold
        negative_samples_changed = (
            set(getattr(old_route, 'negative_samples', [])) 
            != set(getattr(route, 'negative_samples', []))
        )
        negative_threshold_changed = (
            getattr(old_route, 'negative_threshold', 0.95)
            != getattr(route, 'negative_threshold', 0.95)
        )
        needs_vector_update = (
            utterances_changed 
            or name_changed 
            or threshold_changed 
            or negative_samples_changed 
            or negative_threshold_changed
        )

        if not route_manager.update_route(route_id, route):
            raise ValueError(f"路由ID {route_id} 不存在")

        if needs_vector_update:
            logger.info(
                f"检测到路由 ID {route_id} 关键配置已变化 "
                f"(语料:{utterances_changed}, 名称:{name_changed}, 阈值:{threshold_changed}, "
                f"负例:{negative_samples_changed}, 负例阈值:{negative_threshold_changed})，"
                f"正在更新向量索引..."
            )

            # 如果名称变了，旧的 ID (基于名称生成的 UUID) 会失效，需要先删除旧点
            if name_changed:
                logger.info(f"路由名称从 '{old_route.name}' 变更为 '{route.name}'，清理旧向量点")
                qdrant_client.delete_route(route_id)

            # 1. 更新正例向量
            embeddings = encoder.encode(route.utterances)
            qdrant_client.upsert_route_utterances(
                route_id=route_id,
                route_name=route.name,
                utterances=route.utterances,
                embeddings=embeddings,
                score_threshold=route.score_threshold,
            )

            # 2. 更新负例向量
            negative_samples = getattr(route, 'negative_samples', [])
            if negative_samples:
                # 先删除旧的负例向量
                qdrant_client.delete_route_negative_samples(route_id)
                
                # 生成负例向量并插入
                negative_embeddings = encoder.encode(negative_samples)
                negative_threshold = getattr(route, 'negative_threshold', 0.95)
                qdrant_client.upsert_route_negative_samples(
                    route_id=route_id,
                    route_name=route.name,
                    negative_samples=negative_samples,
                    embeddings=negative_embeddings,
                    negative_threshold=negative_threshold,
                )
                logger.info(
                    f"成功更新路由 {route.name} 的 {len(negative_samples)} 个负例"
                )
            else:
                # 如果没有负例，删除可能存在的旧负例向量
                qdrant_client.delete_route_negative_samples(route_id)

            # 同步触发增量诊断更新
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diagnostic_service = DiagnosticService(self.component_manager)
                diagnostic_service.update_route_diagnostics(route_id)
                logger.info(f"已同步完成路由 ID {route_id} 的增量诊断更新")
            except Exception as e:
                logger.error(f"同步增量诊断失败: {e}")
        else:
            logger.info(f"路由 ID {route_id} 关键配置未变化，跳过向量和诊断更新")

        logger.info(f"成功更新路由: {route.name} (ID: {route_id})")

        return route

    def delete_route(self, route_id: int) -> None:
        """删除指定路由

        Args:
            route_id: 路由ID

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()

        route_manager = self.component_manager.route_manager
        qdrant_client = self.component_manager.qdrant_client

        if not route_manager.delete_route(route_id):
            raise ValueError(f"路由ID {route_id} 不存在")

        # 从Qdrant中删除路由的所有向量（包括正例和负例）
        try:
            qdrant_client.delete_route(route_id)
            qdrant_client.delete_route_negative_samples(route_id)
            logger.info(f"成功从Qdrant删除路由 {route_id} 的所有向量点")
        except Exception as e:
            logger.error(f"从Qdrant删除路由向量失败: {e}")

        # 从诊断缓存中移除
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService
            diagnostic_service = DiagnosticService(self.component_manager)
            diagnostic_service.remove_route_from_cache(route_id)
        except Exception as e:
            logger.error(f"从诊断缓存中移除路由失败: {e}")

        logger.info(f"成功删除路由: ID {route_id} (已重排JSON ID)")

    def generate_utterances(self, req: GenerateUtterancesRequest) -> RouteConfig:
        """根据 Agent 信息生成提问列表（不执行持久化，由前端决定是否保存）

        Args:
            req: 生成请求

        Returns:
            生成的路由配置（包含示例utterances在最前面 + 新生成的utterances）
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        example_utterances = req.utterances if req.utterances is not None else []
        new_utterances = self._generate_utterances_with_llm(req, example_utterances)
        final_utterances = example_utterances + new_utterances

        logger.info(
            f"成功为路由 ID {req.id} 生成 {len(new_utterances)} 个新提问，总计 {len(final_utterances)} 个"
        )

        existing_route = route_manager.get_route(req.id) if req.id != 0 else None

        if existing_route:
            return RouteConfig(
                id=req.id,
                name=req.name if req.name else existing_route.name,
                description=req.description
                if req.description
                else existing_route.description,
                utterances=final_utterances,
                negative_samples=getattr(existing_route, 'negative_samples', []),
                score_threshold=existing_route.score_threshold,
                negative_threshold=getattr(existing_route, 'negative_threshold', 0.95),
            )
        else:
            return RouteConfig(
                id=req.id,
                name=req.name,
                description=req.description,
                utterances=final_utterances,
                negative_samples=[],
                score_threshold=0.75,  # 默认阈值
                negative_threshold=0.95,  # 默认负例阈值
            )

    def _generate_utterances_with_llm(
        self, req: GenerateUtterancesRequest, example_utterances: List[str]
    ) -> List[str]:
        """使用LangChain和配置的LLM生成提问

        Args:
            req: 生成请求
            example_utterances: 示例utterances列表（用于参考风格，不会包含在返回结果中）

        Returns:
            新生成的utterances列表（不包含示例）
        """
        llm = LLMFactory.create_llm()

        parser = PydanticOutputParser(pydantic_object=UtteranceList)

        reference_utterances_text = ""
        if example_utterances and len(example_utterances) > 0:
            utterances_list = "\n".join([f"- {utt}" for utt in example_utterances])
            reference_utterances_text = f"\n参考示例（请参照这些示例的风格和范围，生成新的句子，但绝对不能重复这些示例）:\n{utterances_list}\n"

        from intent_hub.config import Config
        prompt = PromptTemplate(
            template=Config.UTTERANCE_GENERATION_PROMPT,
            input_variables=["name", "description", "count", "reference_utterances"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        prompt_variables = {
            "name": req.name,
            "description": req.description,
            "count": req.count,
            "reference_utterances": reference_utterances_text,
        }

        chain = prompt | llm | parser

        try:
            result = chain.invoke(prompt_variables)
            generated_utterances = result.utterances

            reference_set = set(example_utterances) if example_utterances else set()
            new_utterances = []
            for utt in generated_utterances:
                if utt not in reference_set:
                    new_utterances.append(utt)

            if len(new_utterances) > req.count:
                new_utterances = new_utterances[: req.count]

            return new_utterances
        except Exception as e:
            logger.error(f"LLM生成提问失败: {e}")
            raise RuntimeError(f"大模型生成提问失败: {str(e)}")
