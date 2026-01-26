"""配置管理模块"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

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
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")

    # Qdrant配置
    QDRANT_URL: str = os.getenv("QDRANT_URL")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")

    # Embedding模型配置
    HUGGINGFACE_ACCESS_TOKEN: Optional[str] = os.getenv("HUGGINGFACE_ACCESS_TOKEN")
    HUGGINGFACE_PROVIDER: Optional[str] = os.getenv("HUGGINGFACE_PROVIDER")
    HUGGINGFACE_TIMEOUT: int = int(os.getenv("HUGGINGFACE_TIMEOUT", 60))
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME")
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
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")
    LLM_BASE_URL: Optional[str] = os.getenv("LLM_BASE_URL")
    LLM_MODEL: Optional[str] = os.getenv("LLM_MODEL")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", 0.7))

    # DeepSeek LLM配置（向后兼容）
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL")

    # 提示词配置
    UTTERANCE_GENERATION_PROMPT: str = os.getenv("UTTERANCE_GENERATION_PROMPT", "")
    AGENT_REPAIR_PROMPT: str = os.getenv("AGENT_REPAIR_PROMPT", "")

    # 诊断阈值配置
    REGION_THRESHOLD_SIGNIFICANT: float = float(os.getenv("REGION_THRESHOLD_SIGNIFICANT", 0.0))
    INSTANCE_THRESHOLD_AMBIGUOUS: float = float(os.getenv("INSTANCE_THRESHOLD_AMBIGUOUS", 0.0))

    @classmethod
    def get_settings_path(cls) -> Path:
        """获取设置文件的绝对路径"""
        return Path(cls.SETTINGS_FILE_PATH)

    @classmethod
    def load(cls):
        """从文件加载配置并应用优先级覆盖
        
        优先级顺序 (由低到高):
        1. 类属性默认值
        2. 环境变量 (Level 2: 基础设施配置)
        3. settings.json (Level 3: 用户真相 SSoT)
        """
        # 1. 环境变量覆盖
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

        # 2. 从 settings.json 加载 (最高优先级，覆盖环境变量)
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

        except Exception as e:
            print(f"保存配置文件失败: {e}")
            raise e

        return collection_changed

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
