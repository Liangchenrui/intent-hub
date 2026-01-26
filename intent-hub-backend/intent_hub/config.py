"""配置管理模块"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from intent_hub.utils.logger import logger

# 获取项目根目录 (intenthub/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# 默认数据目录：优先使用环境变量，否则使用项目根目录下的 data 文件夹
DATA_DIR = Path(os.getenv("INTENT_HUB_DATA_DIR", str(PROJECT_ROOT / "data")))


class Config:
    """应用配置类"""

    # Flask配置
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", 5000))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    # Qdrant配置
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "intent_hub_routes")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")

    # Embedding模型配置
    HUGGINGFACE_ACCESS_TOKEN: Optional[str] = os.getenv("HUGGINGFACE_ACCESS_TOKEN")
    HUGGINGFACE_PROVIDER: Optional[str] = os.getenv("HUGGINGFACE_PROVIDER")
    HUGGINGFACE_TIMEOUT: int = int(os.getenv("HUGGINGFACE_TIMEOUT", 60))
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"
    )
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # 默认路由配置
    DEFAULT_ROUTE_ID: int = 0
    DEFAULT_ROUTE_NAME: str = "none"

    # 性能配置
    BATCH_SIZE: int = 32

    # 路由配置文件路径
    ROUTES_CONFIG_PATH: str = os.getenv(
        "ROUTES_CONFIG_PATH", str(DATA_DIR / "routes_config.json")
    )
    # 系统设置文件路径
    SETTINGS_FILE_PATH: str = os.getenv(
        "SETTINGS_FILE_PATH", str(DATA_DIR / "settings.json")
    )
    # 诊断缓存文件路径
    DIAGNOSTICS_CACHE_PATH: str = os.getenv(
        "DIAGNOSTICS_CACHE_PATH", str(DATA_DIR / "diagnostics_cache.json")
    )

    # 认证配置
    API_KEYS: Optional[str] = None
    AUTH_ENABLED: bool = True

    # Telestar认证配置
    PREDICT_AUTH_KEY: Optional[str] = None

    # 用户配置
    DEFAULT_USERNAME: str = "admin"
    DEFAULT_PASSWORD: str = "123456"

    # LLM配置
    LLM_PROVIDER: str = "deepseek"
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
    你的任务是分析意图"{name_a}"，找出其中容易与意图"{name_b}"混淆的语句并建议删除或修改，同时提供一些更具区分性的新语句。

    意图 1 (目标分析对象): {name_a}
    描述 1: {desc_a}
    现有例句 1: {utterances_a}

    意图 2 (冲突对照对象): {name_b}
    描述 2: {desc_b}

    具体的冲突对（显示"{name_a}"中的句子与"{name_b}"中的哪些句子过于接近）: {conflicts}

    请按以下 JSON 格式回复：
    {{
      "conflicting_utterances": ["从 '现有例句 1' 中选出最应该被删除或修改的句子"],
      "new_utterances": ["生成 3-5 个新例句，这些句子应具有更强的 {name_a} 的特征词，且明显区别于 {name_b}"],
      "negative_samples": ["生成 2-3 个负面约束例句，即：如果用户这么说，虽然语义接近 {name_a}，但实际不属于 {name_a}"],
      "rationalization": "给出修改理由。注意：在理由中请直接使用意图的具体名称（即"{name_a}"和"{name_b}"），绝对禁止使用"意图A"、"意图B"、"Agent A"或"Agent B"这类代称。"
    }}
    不要输出任何其他文本。"""

    # 诊断阈值配置
    REGION_THRESHOLD_SIGNIFICANT: float = 0.85  # 路由级冲突阈值（区域重叠：显著）
    INSTANCE_THRESHOLD_AMBIGUOUS: float = 0.92  # 语料级冲突阈值（向量冲突：模糊歧义）

    # --- settings.json -> dotenv 同步（用于容器重启时复用UI保存的配置） ---
    # 注意：环境变量优先级最高；如果你不希望同步生成 env 文件，可设置 INTENT_HUB_ENV_SYNC_ENABLED=false
    ENV_SYNC_ENABLED: bool = os.getenv(
        "INTENT_HUB_ENV_SYNC_ENABLED", "True"
    ).lower() in (
        "true",
        "1",
        "yes",
    )
    ENV_SYNC_PATH: str = os.getenv(
        "INTENT_HUB_ENV_SYNC_PATH", str(DATA_DIR / "env.runtime")
    )

    # 默认只同步“单行且关键”的配置，避免把包含大量换行的 prompt 写进 .env
    _DEFAULT_ENV_SYNC_KEYS: Sequence[str] = (
        # Qdrant
        "QDRANT_URL",
        "QDRANT_COLLECTION",
        "QDRANT_API_KEY",
        # Embedding
        "HUGGINGFACE_ACCESS_TOKEN",
        "HUGGINGFACE_PROVIDER",
        "HUGGINGFACE_TIMEOUT",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DEVICE",
        # LLM
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        # Auth
        "AUTH_ENABLED",
        "PREDICT_AUTH_KEY",
        "DEFAULT_USERNAME",
        "DEFAULT_PASSWORD",
        # Perf / routing defaults
        "BATCH_SIZE",
        "DEFAULT_ROUTE_ID",
        "DEFAULT_ROUTE_NAME",
        # Diagnostics thresholds
        "REGION_THRESHOLD_SIGNIFICANT",
        "INSTANCE_THRESHOLD_AMBIGUOUS",
    )

    @classmethod
    def get_settings_path(cls) -> Path:
        """获取设置文件的绝对路径"""
        return Path(cls.SETTINGS_FILE_PATH)

    @classmethod
    def load(cls):
        """从文件加载配置并应用环境变量覆盖"""
        # 1. 首先尝试从外部 data 目录下的 settings.json 加载
        path = cls.get_settings_path()

        # 确保数据目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    for key, value in settings.items():
                        if hasattr(cls, key) and not key.startswith("_"):
                            setattr(cls, key, value)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

        # 2. 环境变量覆盖 (最高优先级)
        for key in cls.to_dict().keys():
            env_val = os.getenv(key)
            if env_val is not None:
                # 获取当前值的类型进行转换
                curr_val = getattr(cls, key)
                try:
                    if isinstance(curr_val, bool):
                        setattr(cls, key, env_val.lower() in ("true", "1", "yes"))
                    elif isinstance(curr_val, int):
                        setattr(cls, key, int(env_val))
                    elif isinstance(curr_val, float):
                        setattr(cls, key, float(env_val))
                    else:
                        setattr(cls, key, env_val)
                except Exception as e:
                    print(f"转换环境变量 {key}={env_val} 失败: {e}")

        # 处理向后兼容
        cls._apply_backward_compatibility()

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
    def save(cls, settings_dict: Dict[str, Any]) -> bool:
        """保存配置到文件并更新类属性

        Args:
            settings_dict: 要保存的配置字典

        Returns:
            如果 QDRANT_COLLECTION 发生变化，返回 True；否则返回 False
        """
        # 检测 QDRANT_COLLECTION 是否发生变化
        old_collection = cls.QDRANT_COLLECTION
        collection_changed = False

        # 过滤并更新
        update_data = {}
        for key, value in settings_dict.items():
            if (
                hasattr(cls, key)
                and not key.startswith("_")
                and not callable(getattr(cls, key))
            ):
                # 检测 QDRANT_COLLECTION 变化
                if key == "QDRANT_COLLECTION" and value != old_collection:
                    collection_changed = True
                    logger.info(
                        f"检测到 QDRANT_COLLECTION 变化: {old_collection} -> {value}"
                    )

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

            # 将 settings.json 同步生成到 dotenv（用于 docker-compose 重启时加载）
            cls._sync_settings_to_env(existing_settings)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            raise e

        return collection_changed

    @classmethod
    def _get_env_sync_keys(cls) -> Sequence[str]:
        """获取需要同步到 dotenv 的 keys（可通过环境变量覆盖）"""
        raw = os.getenv("INTENT_HUB_ENV_SYNC_KEYS", "").strip()
        if not raw:
            return cls._DEFAULT_ENV_SYNC_KEYS
        # 允许逗号分隔
        return tuple(k.strip() for k in raw.split(",") if k.strip())

    @staticmethod
    def _dotenv_escape(value: str) -> str:
        """
        将值编码为 dotenv 兼容的单行字符串。
        - 对包含空格/特殊字符/换行的值使用双引号
        - 将换行转换为 \n，避免破坏 .env 行结构
        """
        v = value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "")
        needs_quotes = any(ch in v for ch in (" ", "#", "=", '"', "\t")) or "\\n" in v
        if needs_quotes:
            v = v.replace('"', '\\"')
            return f'"{v}"'
        return v

    @classmethod
    def _sync_settings_to_env(cls, settings: Dict[str, Any]) -> None:
        """把 settings.json 中的配置同步写入 dotenv 文件（默认 data/.env.runtime）"""
        if not cls.ENV_SYNC_ENABLED:
            return

        try:
            env_path = Path(cls.ENV_SYNC_PATH)
            env_path.parent.mkdir(parents=True, exist_ok=True)

            keys = cls._get_env_sync_keys()
            lines = [
                "# Auto-generated by Intent Hub (settings.json -> env sync).",
                "# Do NOT edit manually unless you know what you're doing.",
                "",
            ]

            for key in keys:
                # 只同步已存在且非 None 的值，避免用空值覆盖行为
                if key not in settings:
                    continue
                val = settings.get(key)
                if val is None:
                    continue

                if isinstance(val, bool):
                    s = "true" if val else "false"
                else:
                    s = str(val)
                lines.append(f"{key}={cls._dotenv_escape(s)}")

            lines.append("")
            env_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            # 同步失败不应影响主流程（settings.json 已成功保存）
            print(f"同步 env 文件失败: {e}")

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
            "HUGGINGFACE_TIMEOUT": cls.HUGGINGFACE_TIMEOUT,
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
            "DEFAULT_USERNAME": cls.DEFAULT_USERNAME,
            "DEFAULT_PASSWORD": cls.DEFAULT_PASSWORD,
            # 其他配置
            "BATCH_SIZE": cls.BATCH_SIZE,
            "DEFAULT_ROUTE_ID": cls.DEFAULT_ROUTE_ID,
            "DEFAULT_ROUTE_NAME": cls.DEFAULT_ROUTE_NAME,
            # 诊断阈值配置
            "REGION_THRESHOLD_SIGNIFICANT": cls.REGION_THRESHOLD_SIGNIFICANT,
            "INSTANCE_THRESHOLD_AMBIGUOUS": cls.INSTANCE_THRESHOLD_AMBIGUOUS,
        }


# 初始加载（load方法内部已调用_apply_backward_compatibility）
Config.load()
