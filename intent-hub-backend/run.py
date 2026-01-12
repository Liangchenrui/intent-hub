"""Intent Hub 启动脚本"""
from intent_hub.app import init_app
from intent_hub.config import Config

if __name__ == '__main__':
    # 初始化应用（包括组件初始化）
    print("正在初始化Intent Hub组件...")
    try:
        app = init_app()
        print("组件初始化完成！")
    except Exception as e:
        print(f"组件初始化失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    # 启动Flask应用
    print(f"启动Flask服务: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )

