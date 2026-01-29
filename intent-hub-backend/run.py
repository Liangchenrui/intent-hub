"""Intent Hub startup script."""
from intent_hub.app import init_app
from intent_hub.config import Config
from intent_hub.utils.logger import suppress_health_check_logs

if __name__ == "__main__":
    print("Initializing Intent Hub components...")
    try:
        app = init_app()
        print("Components initialized.")
    except Exception as e:
        print(f"Component initialization failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    suppress_health_check_logs()
    print(f"Starting Flask server: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )

