"""
Alumni Feedback System Backend
Main Flask application entry point with blueprint registration
"""

import os
import sys
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import get_config
from backend.utils.logger import setup_logger
from backend.routes.api import api_bp, legacy_bp
from backend.routes.webhook import webhook_bp
from backend.routes.health import health_bp
from backend.routes.admin import admin_bp
from backend.routes.wiki import wiki_bp

from backend.utils.db_helper import initialize_database


def create_app(config=None):
    """Application factory for Flask app"""
    # Pre-import heavy ML libraries to avoid import lock deadlocks in background threads
    try:
        import torch
        import transformers
        import sentence_transformers
    except Exception as e:
        pass

    # Key: tell Flask where the frontend is
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')

    # Create Flask app with frontend/ as its template+static folder
    app = Flask(
        __name__,
        static_folder=frontend_dir,
        static_url_path='/static'
    )

    # Load configuration
    if config is None:
        app.config.from_object(get_config()())
    else:
        app.config.from_object(config)

    # Trust Hugging Face / Reverse Proxy headers for accurate request.host_url
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Setup logging
    logger = setup_logger(app)
    logger.info(f"Application starting in {app.config.get('FLASK_ENV', 'development')} mode")

    # Hugging Face Spaces set SPACE_ID; without PUBLIC_URL, embedded Google Form webhooks often point
    # at a wrong host (internal/http). See env.example for required secrets.
    if os.getenv('SPACE_ID') and not (os.getenv('PUBLIC_URL') or '').strip():
        logger.warning(
            'PUBLIC_URL is unset in a Hugging Face Space (SPACE_ID is set). '
            'Set PUBLIC_URL to your public https://…hf.space origin (no trailing slash) so '
            'new forms receive a reachable webhook URL. Then create a new event from the dashboard.'
        )

    # Initialize database on startup
    initialize_database(app, logger)

    # Start Deep Learning background thread
    from backend.services.dl_worker import start_dl_worker
    start_dl_worker(logger)

    # Start Certificate background job worker thread
    from backend.services.job_worker import start_job_worker
    start_job_worker(logger)

    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(legacy_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(wiki_bp)

    # Initialize Wiki folders and templates on startup
    try:
        from backend.services.wiki_service import WikiService
        WikiService().initialize_wiki()
        logger.info("Wiki directories and schemas initialized successfully on startup.")
    except Exception as e:
        logger.error(f"Startup Wiki initialization failed: {e}")


    # ─── Serve the single-page frontend ──────────────────────
    @app.route('/')
    def serve_index():
        """Serve main index.html from the frontend directory"""
        if os.path.exists(os.path.join(frontend_dir, 'index.html')):
            return send_from_directory(frontend_dir, 'index.html')
        return jsonify({'message': 'Alumni Feedback System API v1.0.0'}), 200

    # NOTE: /static/<path> is handled automatically by Flask since we set
    # static_folder=frontend_dir and static_url_path='/static'.
    # Flask will serve frontend/style.css at /static/style.css, etc.

    # ─── Error handlers ───────────────────────────────────────
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden'}), 403

    @app.before_request
    def log_request():
        """Log incoming requests"""
        from flask import request as req
        logger.debug(f"{req.method} {req.path} from {req.remote_addr}")

    @app.after_request
    def log_response(response):
        """Log response"""
        from flask import request as req
        logger.info(f"{req.method} {req.path} - {response.status_code}")
        return response

    logger.info("Application initialized successfully")
    return app


# ─── Entry point for Hugging Face Spaces ─────────────────────
# Build Trigger: 2026-03-21 03:00:18
if __name__ == '__main__':
    app = create_app()

    # Get port from environment or default to 7860 (HF Spaces default)
    port = int(os.getenv('PORT', 7860))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    logger = app.logger
    logger.info(f"Starting server on port {port}")

    # Trigger HF Space rebuild for Google Form fix
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False,  # Disable reloader for HF Spaces
    )
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False,  # Disable reloader for HF Spaces
        allow_unsafe_werkzeug=True  # Required for dev server with SocketIO
    )
