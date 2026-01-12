"""统一错误处理工具"""
from functools import wraps
from flask import request, jsonify
from typing import Callable, Type, Optional
from pydantic import BaseModel, ValidationError

from intent_hub.utils.logger import logger
from intent_hub.models import ErrorResponse


def handle_errors(f: Callable) -> Callable:
    """统一错误处理装饰器
    
    自动捕获异常并返回标准错误响应
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"请求参数验证失败: {e}")
            return jsonify(ErrorResponse(
                error="请求参数错误",
                detail=f"参数验证失败: {str(e)}"
            ).dict()), 400
        except ValueError as e:
            logger.warning(f"请求参数错误: {e}")
            return jsonify(ErrorResponse(
                error="请求参数错误",
                detail=str(e)
            ).dict()), 400
        except RuntimeError as e:
            logger.error(f"运行时错误: {e}", exc_info=True)
            return jsonify(ErrorResponse(
                error="服务未就绪",
                detail=str(e)
            ).dict()), 503
        except Exception as e:
            logger.error(f"处理请求失败: {e}", exc_info=True)
            return jsonify(ErrorResponse(
                error="处理请求失败",
                detail=str(e)
            ).dict()), 500
    
    return decorated_function


def validate_request(model_class: Type[BaseModel], require_json: bool = True):
    """请求数据验证装饰器
    
    Args:
        model_class: Pydantic模型类
        require_json: 是否要求请求体为JSON格式
    
    Returns:
        装饰器函数
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查请求体
            data = request.get_json()
            if require_json and data is None:
                return jsonify(ErrorResponse(
                    error="请求参数错误",
                    detail="请求体不能为空"
                ).dict()), 400
            
            # 验证数据
            try:
                validated_data = model_class(**data) if data else None
            except ValidationError as e:
                logger.warning(f"请求参数验证失败: {e}")
                return jsonify(ErrorResponse(
                    error="请求参数错误",
                    detail=f"缺少必需的参数或参数格式错误: {str(e)}"
                ).dict()), 400
            
            # 将验证后的数据传递给原函数
            return f(validated_data, *args, **kwargs)
        
        return decorated_function
    return decorator

