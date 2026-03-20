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
from backend.routes.api import api_bp
from backend.routes.webhook import webhook_bp
from backend.routes.health import health_bp
from backend.routes.admin import admin_bp


def _initialize_database(app, logger):
    """Initialize database on application startup"""
    try:
        import sqlite3
        db_path = app.config.get('DATABASE_PATH', 'database/dashboard.db')

        # Create database directory if it doesn't exist (and if there is a directory specified)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists and has correct columns
        cursor.execute("PRAGMA table_info(dashboard_data)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # If table doesn't exist or is missing critical modern columns, recreate it
        if not columns or 'form_source' not in columns:
            logger.info("Initializing/Repairing dashboard_data table...")
            cursor.execute("DROP TABLE IF EXISTS dashboard_data")
            cursor.execute('''
                CREATE TABLE dashboard_data (
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
        
        # Ensure events table exists
        cursor.execute("PRAGMA table_info(events)")
        event_cols = [row[1] for row in cursor.fetchall()]
        if not event_cols:
            logger.info("Creating events table...")
            cursor.execute('''
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT NOT NULL,
                    venue_date TEXT NOT NULL,
                    form_id TEXT,
                    form_url TEXT,
                    form_edit_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        conn.commit()
        conn.close()
        logger.info("Database schema verified and ready")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")


def create_app(config=None):
    """Application factory for Flask app"""

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

    # Setup logging
    logger = setup_logger(app)
    logger.info(f"Application starting in {app.config.get('FLASK_ENV', 'development')} mode")

    # Initialize database on startup
    _initialize_database(app, logger)

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
    app.register_blueprint(admin_bp)

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

    # ─── Legacy bridge routes for Premium frontend ────────────
    @app.route('/api/data', methods=['GET'])
    def get_legacy_data():
        """Unified analytics payload for the Premium frontend (app.js)"""
        try:
            from backend.routes.api import get_consolidated_analytics
            return jsonify(get_consolidated_analytics(app)), 200
        except Exception as e:
            logger.error(f"Error in /api/data: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/filter', methods=['POST'])
    def get_legacy_filter():
        """Filtered analytics payload for the Premium frontend"""
        try:
            from backend.routes.api import get_consolidated_analytics
            body = request.get_json() or {}
            filters = body.get('filters', {})
            search = body.get('search', '')
            return jsonify(get_consolidated_analytics(app, filters=filters, search=search)), 200
        except Exception as e:
            logger.error(f"Error in /api/filter: {str(e)}")
            return jsonify({'error': str(e)}), 500

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
