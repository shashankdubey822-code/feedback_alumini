"""
Alumni Feedback System Backend
Main Flask application entry point with blueprint registration
"""

import os
import sys
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.config import get_config
from backend.utils.logger import setup_logger
from backend.routes.api import api_bp
from backend.routes.webhook import webhook_bp
from backend.routes.health import health_bp


def create_app(config=None):
    """Application factory for Flask app"""

    # Create Flask app
    app = Flask(__name__)

    # Load configuration
    if config is None:
        app.config.from_object(get_config())
    else:
        app.config.from_object(config)

    # Setup logging
    logger = setup_logger(app)
    logger.info(f"Application starting in {app.config.get('FLASK_ENV', 'development')} mode")

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
    app.register_blueprint(webhook_bp)

    # Serve static frontend files
    @app.route('/')
    def serve_index():
        """Serve main index.html"""
        frontend_path = os.path.join(os.path.dirname(__file__), 'frontend')
        if os.path.exists(frontend_path):
            return send_from_directory(frontend_path, 'index.html')
        return jsonify({'message': 'Alumni Feedback System API v1.0.0'}), 200

    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files (CSS, JS, etc.)"""
        frontend_path = os.path.join(os.path.dirname(__file__), 'frontend')
        return send_from_directory(frontend_path, path)

    # Error handlers
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
        from flask import request
        logger.debug(f"{request.method} {request.path} from {request.remote_addr}")

    @app.after_request
    def log_response(response):
        """Log response"""
        from flask import request
        logger.info(f"{request.method} {request.path} - {response.status_code}")
        return response

    # CLI commands for database management
    @app.cli.command('init-db')
    def init_db():
        """Initialize the database"""
        logger.info("Initializing database...")
        try:
            import sqlite3
            db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard_data'"
            )

            if not cursor.fetchone():
                logger.info("Creating dashboard_data table...")
                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS dashboard_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp_original TEXT,
                        timestamp_normalized TEXT,
                        name_of_student TEXT,
                        name_normalized TEXT,
                        department_original TEXT,
                        department_cleaned TEXT,
                        roll_no_original TEXT,
                        roll_no_cleaned TEXT,
                        date_of_lecture TEXT,
                        alumni_speaker_name TEXT,
                        session_help_understanding TEXT,
                        session_rating INTEGER,
                        session_technical_clarity INTEGER,
                        aspect_most_valuable TEXT,
                        improvements_suggestions TEXT,
                        future_topics TEXT,
                        form_source TEXT,
                        data_quality_score REAL,
                        is_duplicate_flag INTEGER DEFAULT 0,
                        record_status TEXT,
                        cleaned_at TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logger.info("Database initialized successfully")
            else:
                logger.info("Database already exists")

            conn.close()

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            return 1

        return 0

    logger.info("Application initialized successfully")
    return app


# Application entry point for Hugging Face Spaces
if __name__ == '__main__':
    app = create_app()

    # Get port from environment or default to 7860 (HF Spaces default)
    port = int(os.getenv('PORT', 7860))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    logger = app.logger
    logger.info(f"Starting server on port {port}")

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=False,  # Disable reloader for HF Spaces
    )
