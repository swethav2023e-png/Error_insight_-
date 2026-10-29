"""
LogHealth – Log Analytics and System Health Intelligence
Main Flask Application Entry Point and Application Factory.
"""

import logging
import os
from flask import Flask, jsonify, render_template

from config import Config, get_config
from database.db import SQLiteManager, set_db

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("LogHealth")



def create_app(config_class=None) -> Flask:
    """Application factory for ErrorInsight."""
    app = Flask(__name__)

    if config_class is None:
        config_class = get_config()

    app.config.from_object(config_class)

    # Initialize Database Manager
    db_manager = SQLiteManager(app.config["DATABASE_PATH"])
    try:
        db_manager.init_db()
        logger.info("Initialized database at %s", app.config["DATABASE_PATH"])
    except Exception as exc:
        logger.error("Database initialization warning: %s", exc)

    set_db(db_manager)

    # Register Blueprints
    from routes.api_routes import api_bp
    from routes.web_routes import web_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    # Global Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "status": "error",
            "error": "The requested resource was not found on this server."
        }), 404

    @app.errorhandler(413)
    def payload_too_large_error(error):
        return jsonify({
            "status": "error",
            "error": "File or payload exceeds maximum allowed size (16MB)."
        }), 413

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Internal Server Error")
        return jsonify({
            "status": "error",
            "error": "An internal server error occurred."
        }), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true")
    logger.info("Starting LogHealth on http://127.0.0.1:%s", port)
    app.run(host="127.0.0.1", port=port, debug=debug)

