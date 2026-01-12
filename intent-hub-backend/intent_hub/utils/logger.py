"""自定义日志模块"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "intent_hub",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """设置并返回配置好的 logger 实例

    Args:
        name: logger 名称
        level: 日志级别
        log_file: 日志文件路径（可选，如果为 None 则只输出到控制台）
        format_string: 日志格式字符串（可选）

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 默认格式：时间戳 - 级别 - 模块 - 消息
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    
    # 控制台输出 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出 handler（如果指定了日志文件）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# 创建默认的 logger 实例
logger = setup_logger("intent_hub", logging.INFO)

