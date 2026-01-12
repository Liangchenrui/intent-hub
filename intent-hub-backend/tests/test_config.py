"""配置模块测试示例"""
import pytest
from intent_hub.config import Config


def test_config_defaults():
    """测试配置默认值"""
    assert Config.DEFAULT_ROUTE_ID == 0
    assert Config.DEFAULT_ROUTE_NAME == "none"
    assert Config.BATCH_SIZE == 32


def test_config_env_override(monkeypatch):
    """测试环境变量覆盖"""
    monkeypatch.setenv("FLASK_PORT", "8080")
    # 注意：由于Config是类属性，需要重新导入或使用不同的测试策略
    # 这里仅作为示例
    pass

