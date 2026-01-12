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
        embeddings = encoder.encode(route.utterances)
        qdrant_client.upsert_route_utterances(
            route_id=route.id,
            route_name=route.name,
            utterances=route.utterances,
            embeddings=embeddings,
            score_threshold=route.score_threshold,
        )

        logger.info(f"成功处理路由: {route.name} (ID: {route.id})")
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

        if not route_manager.update_route(route_id, route):
            raise ValueError(f"路由ID {route_id} 不存在")
        embeddings = encoder.encode(route.utterances)
        qdrant_client.upsert_route_utterances(
            route_id=route_id,
            route_name=route.name,
            utterances=route.utterances,
            embeddings=embeddings,
            score_threshold=route.score_threshold,
        )

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

        if not route_manager.delete_route(route_id):
            raise ValueError(f"路由ID {route_id} 不存在")

        logger.info(f"成功删除路由: ID {route_id} (已重排JSON ID)")

    def generate_and_update_utterances(
        self, req: GenerateUtterancesRequest
    ) -> RouteConfig:
        """生成并更新路由提问

        Args:
            req: 生成请求

        Returns:
            更新后的路由配置（包含示例utterances在最前面 + 新生成的utterances）
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        example_utterances = req.utterances if req.utterances is not None else []
        new_utterances = self._generate_utterances_with_llm(req, example_utterances)
        final_utterances = example_utterances + new_utterances

        existing_route = route_manager.get_route(req.id) if req.id != 0 else None

        if existing_route:
            updated_route = RouteConfig(
                id=req.id,
                name=req.name if req.name else existing_route.name,
                description=req.description
                if req.description
                else existing_route.description,
                utterances=final_utterances,
                score_threshold=existing_route.score_threshold,
            )
            return self.update_route(req.id, updated_route)
        else:
            logger.info("路由 ID 为 0，仅生成提问内容，不执行持久化")
            return RouteConfig(
                id=req.id,
                name=req.name,
                description=req.description,
                utterances=final_utterances,
                score_threshold=0.75,  # 默认阈值
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

        prompt = PromptTemplate(
            template="""你是一个资深的用户意图分析专家。你的任务是为特定的 AI Agent 生成高质量的测试数据集（Utterances），用于后续的意图识别和路由分发系统训练。

### Agent 背景信息
- **Agent 名称**: {name}
- **功能描述**: {description}
- **参考示例（请参照这些示例的风格和范围，生成新的句子，但绝对不能重复这些示例）**: {reference_utterances}

### 生成要求
你需要生成 {count} 条**全新的**用户提问（必须与参考示例不同），请严格遵守以下准则：

1. **分布控制**：
   - **关键词/短语 (30%)**: 极其简短，如"查天气"、"翻译一下"、"写代码"。这类词对路由最关键。
   - **简单指令 (40%)**: 直接的命令句，如"帮我写个请假条"、"帮我分析这行代码"。
   - **真实口语 (30%)**: 包含语气词、不规范表达或略显随意的口语，模拟真实用户输入。

2. **多样性与覆盖面**：
   - 提取描述中的"核心动词"和"核心名词"，进行交叉组合。
   - 包含同义词替换（例如：从"预定"扩展到"帮我订一个"、"我想约一个"）。
   - 必须沿用参考示例的语气和专业深度，但不要重复原话。

3. **路由判别性**：
   - 生成的提问必须与该 Agent 的核心功能高度相关，避免产生可能导致路由误判到其他通用 Agent 的极其模糊的句子。

4. **格式要求**：
   - 仅输出生成的问题列表，不要包含任何解释性文字。

{format_instructions}""",
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
