"""配置管理模块"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """应用配置类"""

    # Flask配置
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = True

    # Qdrant配置
    # 1. 本地/自建: 填写 QDRANT_URL + QDRANT_COLLECTION
    # 2. Qdrant云端: 填写 QDRANT_URL + QDRANT_API_KEY + QDRANT_COLLECTION
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "intent_hub_routes"
    QDRANT_API_KEY: Optional[str] = None

    # Embedding模型配置
    # 1. 如果 HUGGINGFACE_ACCESS_TOKEN 不为空，尝试使用 HuggingFace Inference API
    # 2. 如果 Token 为空或验证失败，则从 hf-mirror 下载模型到本地
    HUGGINGFACE_ACCESS_TOKEN: Optional[str] = None  # HuggingFace Access Token (可选)
    HUGGINGFACE_PROVIDER: Optional[str] = (
        None  # 推理服务提供商 (可选，如 "nebius", "hf-inference" 等)
    )
    EMBEDDING_MODEL_NAME: str = "Qwen/Qwen3-Embedding-0.6B"  # 模型名称
    EMBEDDING_DEVICE: str = "cpu"  # 本地模型使用的设备 (cpu/cuda/mps)

    # 默认路由配置
    DEFAULT_ROUTE_ID: int = 0
    DEFAULT_ROUTE_NAME: str = "none"

    # 性能配置
    BATCH_SIZE: int = 32

    # 路由配置文件路径（相对于intent_hub包目录）
    ROUTES_CONFIG_PATH: str = "routes_config.json"
    # 系统设置文件路径
    SETTINGS_FILE_PATH: str = "settings.json"

    # 认证配置
    # API Keys（多个key用逗号分隔）
    API_KEYS: Optional[str] = None
    # 是否启用认证（默认启用）
    AUTH_ENABLED: bool = True

    # Telestar认证配置
    # Predict认证Key（如果为空则不启用认证，如果有值则启用认证并使用该值）
    PREDICT_AUTH_KEY: Optional[str] = None

    # 用户配置（请在 settings.json 中配置实际值）
    DEFAULT_USERNAME: str = "admin"
    DEFAULT_PASSWORD: str = "123456"

    # LLM配置（通用）
    LLM_PROVIDER: str = (
        "deepseek"  # 支持的provider: deepseek, openrouter, doubao, qwen, gemini
    )
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.7

    # DeepSeek LLM配置（向后兼容）
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 提示词配置
    UTTERANCE_GENERATION_PROMPT: str = """你是一个资深的用户意图分析专家。你的任务是为特定的 AI Agent 生成高质量的测试数据集（Utterances），用于后续的意图识别和路由分发系统训练。

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
   - 提取描述中的"核心动词" and "核心名词"，进行交叉组合。
   - 包含同义词替换（例如：从"预定"扩展到"帮我订一个"、"我想约一个"）。
   - 必须沿用参考示例的语气和专业深度，但不要重复原话。

3. **路由判别性**：
   - 生成的提问必须与该 Agent 的核心功能高度相关，避免产生可能导致路由误判到其他通用 Agent 的极其模糊的句子。

4. **格式要求**：
   - 仅输出生成的问题列表，不要包含任何解释性文字。

{format_instructions}"""

    AGENT_REPAIR_PROMPT: str = """你是一个 NLU 专家。
    当前存在两个意图在语义上发生了重叠，导致模型难以区分。
    你的任务是分析意图“{name_a}”，找出其中容易与意图“{name_b}”混淆的语句并建议删除或修改，同时提供一些更具区分性的新语句。

    意图 1 (目标分析对象): {name_a}
    描述 1: {desc_a}
    现有例句 1: {utterances_a}

    意图 2 (冲突对照对象): {name_b}
    描述 2: {desc_b}

    具体的冲突对（显示“{name_a}”中的句子与“{name_b}”中的哪些句子过于接近）: {conflicts}

    请按以下 JSON 格式回复：
    {{
      "conflicting_utterances": ["从 '现有例句 1' 中选出最应该被删除或修改的句子"],
      "new_utterances": ["生成 3-5 个新例句，这些句子应具有更强的 {name_a} 的特征词，且明显区别于 {name_b}"],
      "negative_samples": ["生成 2-3 个负面约束例句，即：如果用户这么说，虽然语义接近 {name_a}，但实际不属于 {name_a}"],
      "rationalization": "给出修改理由。注意：在理由中请直接使用意图的具体名称（即“{name_a}”和“{name_b}”），绝对禁止使用“意图A”、“意图B”、“Agent A”或“Agent B”这类代称。"
    }}
    不要输出任何其他文本。"""

    @classmethod
    def get_settings_path(cls) -> Path:
        """获取设置文件的绝对路径"""
        base_dir = Path(__file__).parent
        return base_dir / cls.SETTINGS_FILE_PATH

    @classmethod
    def load(cls):
        """从文件加载配置"""
        path = cls.get_settings_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    for key, value in settings.items():
                        if hasattr(cls, key) and not key.startswith("_"):
                            setattr(cls, key, value)
                # 处理向后兼容：如果LLM_PROVIDER=deepseek且新配置为空，使用旧配置
                cls._apply_backward_compatibility()
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    @classmethod
    def _apply_backward_compatibility(cls):
        """处理向后兼容性：如果使用deepseek且新配置为空，使用旧配置"""
        if cls.LLM_PROVIDER == "deepseek":
            if cls.LLM_API_KEY is None and cls.DEEPSEEK_API_KEY:
                cls.LLM_API_KEY = cls.DEEPSEEK_API_KEY
            if cls.LLM_BASE_URL is None and cls.DEEPSEEK_BASE_URL:
                cls.LLM_BASE_URL = cls.DEEPSEEK_BASE_URL
            if cls.LLM_MODEL is None and cls.DEEPSEEK_MODEL:
                cls.LLM_MODEL = cls.DEEPSEEK_MODEL

    @classmethod
    def save(cls, settings_dict: Dict[str, Any]):
        """保存配置到文件并更新类属性"""
        # 过滤并更新
        update_data = {}
        for key, value in settings_dict.items():
            if (
                hasattr(cls, key)
                and not key.startswith("_")
                and not callable(getattr(cls, key))
            ):
                setattr(cls, key, value)
                update_data[key] = value

        # 写入文件
        path = cls.get_settings_path()
        try:
            existing_settings = {}
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    existing_settings = json.load(f)

            existing_settings.update(update_data)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing_settings, f, indent=4, ensure_ascii=False)
            # 保存后应用向后兼容性
            cls._apply_backward_compatibility()
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            raise e

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """获取可供前端配置的项"""
        return {
            # Qdrant配置
            "QDRANT_URL": cls.QDRANT_URL,
            "QDRANT_COLLECTION": cls.QDRANT_COLLECTION,
            "QDRANT_API_KEY": cls.QDRANT_API_KEY,
            # Embedding模型配置
            "HUGGINGFACE_ACCESS_TOKEN": cls.HUGGINGFACE_ACCESS_TOKEN,
            "HUGGINGFACE_PROVIDER": cls.HUGGINGFACE_PROVIDER,
            "EMBEDDING_MODEL_NAME": cls.EMBEDDING_MODEL_NAME,
            "EMBEDDING_DEVICE": cls.EMBEDDING_DEVICE,
            # LLM配置（通用）
            "LLM_PROVIDER": cls.LLM_PROVIDER,
            "LLM_API_KEY": cls.LLM_API_KEY,
            "LLM_BASE_URL": cls.LLM_BASE_URL,
            "LLM_MODEL": cls.LLM_MODEL,
            "LLM_TEMPERATURE": cls.LLM_TEMPERATURE,
            # DeepSeek配置（向后兼容）
            "DEEPSEEK_API_KEY": cls.DEEPSEEK_API_KEY,
            "DEEPSEEK_BASE_URL": cls.DEEPSEEK_BASE_URL,
            "DEEPSEEK_MODEL": cls.DEEPSEEK_MODEL,
            # 提示词配置
            "UTTERANCE_GENERATION_PROMPT": cls.UTTERANCE_GENERATION_PROMPT,
            "AGENT_REPAIR_PROMPT": cls.AGENT_REPAIR_PROMPT,
            # 认证配置
            "AUTH_ENABLED": cls.AUTH_ENABLED,
            "PREDICT_AUTH_KEY": cls.PREDICT_AUTH_KEY,
            # 其他配置
            "BATCH_SIZE": cls.BATCH_SIZE,
            "DEFAULT_ROUTE_ID": cls.DEFAULT_ROUTE_ID,
            "DEFAULT_ROUTE_NAME": cls.DEFAULT_ROUTE_NAME,
        }


# 初始加载（load方法内部已调用_apply_backward_compatibility）
Config.load()
