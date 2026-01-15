"""Flask应用主文件"""

from flask import Flask

# 导入API处理函数
from intent_hub.api import (
    auth,
    diagnostics,
    health,
    prediction,
    reindex,
    routes,
    settings,
)
from intent_hub.auth import require_auth
from intent_hub.config import Config
from intent_hub.core.components import get_component_manager

# 初始化Flask应用
app = Flask(__name__)


# 注册路由
@app.route("/health", methods=["GET"])
def health_check():
    """健康检查接口（免鉴权）"""
    return health.health_check()


@app.route("/auth/login", methods=["POST"])
def login():
    """登录接口（免鉴权）"""
    return auth.login()


@app.route("/predict", methods=["POST"])
def predict():
    """路由预测接口（使用Telestar认证）"""
    return prediction.predict()


@app.route("/routes", methods=["GET"])
@require_auth
def get_routes():
    """获取所有路由列表"""
    return routes.get_routes()


@app.route("/routes/search", methods=["GET"])
@require_auth
def search_routes():
    """搜索路由接口"""
    return routes.search_routes()


@app.route("/routes", methods=["POST"])
@require_auth
def create_route():
    """新增路由配置"""
    return routes.create_route()


@app.route("/routes/<int:route_id>", methods=["PUT"])
@require_auth
def update_route(route_id: int):
    """修改指定路由"""
    return routes.update_route(route_id)


@app.route("/routes/<int:route_id>", methods=["DELETE"])
@require_auth
def delete_route(route_id: int):
    """删除指定路由"""
    return routes.delete_route(route_id)


@app.route("/routes/generate-utterances", methods=["POST"])
@require_auth
def generate_utterances():
    """根据Agent信息自动生成提问"""
    return routes.generate_utterances()


@app.route("/routes/<int:route_id>/negative-samples", methods=["POST"])
@require_auth
def add_negative_samples(route_id: int):
    """为路由添加负例样本"""
    return routes.add_negative_samples(route_id)


@app.route("/routes/<int:route_id>/negative-samples", methods=["DELETE"])
@require_auth
def delete_negative_samples(route_id: int):
    """删除路由的所有负例样本"""
    return routes.delete_negative_samples(route_id)


@app.route("/reindex", methods=["POST"])
@require_auth
def reindex_route():
    """重新索引接口"""
    return reindex.reindex()


@app.route("/diagnostics/overlap", methods=["GET"])
@require_auth
def analyze_all_overlaps():
    """全局分析所有路由的重叠情况"""
    return diagnostics.analyze_all_overlaps()


@app.route("/diagnostics/overlap/<int:route_id>", methods=["GET"])
@require_auth
def analyze_overlap(route_id: int):
    """分析指定路由与其他路由的重叠情况"""
    return diagnostics.analyze_overlap(route_id)


@app.route("/diagnostics/umap", methods=["GET"])
@require_auth
def diagnostics_umap():
    """UMAP 可视化点云数据"""
    return diagnostics.umap_points()


@app.route("/diagnostics/repair", methods=["POST"])
@require_auth
def get_repair_suggestions():
    """获取 LLM 修复建议"""
    return diagnostics.get_repair_suggestions()


@app.route("/diagnostics/apply-repair", methods=["POST"])
@require_auth
def apply_repair():
    """应用修复建议"""
    return diagnostics.apply_repair()


@app.route("/settings", methods=["GET"])
@require_auth
def get_settings():
    """获取系统配置"""
    return settings.get_settings()


@app.route("/settings", methods=["POST"])
@require_auth
def update_settings():
    """更新系统配置"""
    return settings.update_settings()


def init_app():
    """初始化应用（包括组件初始化）"""
    component_manager = get_component_manager()
    component_manager.init_components()

    # 启动全量诊断（异步），避免阻塞启动过程
    try:
        from intent_hub.services.diagnostic_service import DiagnosticService
        from intent_hub.utils.logger import logger
        diagnostic_service = DiagnosticService(component_manager)
        diagnostic_service.run_async_diagnostics("full")
        logger.info("系统启动：已异步启动后台全量重叠诊断")
    except Exception as e:
        from intent_hub.utils.logger import logger
        logger.error(f"系统启动时启动全量诊断失败: {e}")

    return app


if __name__ == "__main__":
    # 初始化组件
    component_manager = get_component_manager()
    component_manager.init_components()

    # 启动全量诊断（异步）
    try:
        from intent_hub.services.diagnostic_service import DiagnosticService
        from intent_hub.utils.logger import logger
        diagnostic_service = DiagnosticService(component_manager)
        diagnostic_service.run_async_diagnostics("full")
        logger.info("系统手动启动：已异步启动后台全量重叠诊断")
    except Exception as e:
        from intent_hub.utils.logger import logger
        logger.error(f"系统手动启动时启动全量诊断失败: {e}")

    # 启动Flask应用
    app.run(host=Config.FLASK_HOST, port=Config.FLASK_PORT, debug=Config.FLASK_DEBUG)
