"""
Flask application configuration
Handles environment-based settings
"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Database (Supabase PostgreSQL via psycopg2)
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    DB_POOL_MIN  = int(os.getenv('DB_POOL_MIN', 2))
    DB_POOL_MAX  = int(os.getenv('DB_POOL_MAX', 10))

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # API
    API_TITLE = 'Alumni Feedback System API'
    API_VERSION = 'v1'
    API_DOCUMENTATION_URL = '/api/docs'

    # Webhook settings
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'webhook-secret-key')
    WEBHOOK_TIMEOUT = 30

    # Form settings
    FORM_PASSWORD = os.getenv('FORM_PASSWORD', '')
    MAX_SUBMISSION_SIZE = 1024 * 1024  # 1MB

    # Analytics
    DEFAULT_DATE_FORMAT = '%Y-%m-%d'
    DEFAULT_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/app.log'

    # NLP and Text Processing
    STOPWORDS_LANGUAGE = 'english'
    MIN_WORD_LENGTH = 3
    MAX_KEYWORDS = 10

    # Data Quality
    DATA_QUALITY_THRESHOLD = 80  # Minimum acceptable quality score

    # Supabase Settings
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', '')
    SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET', 'wiki-pages')
    DATABASE_URL = os.getenv('DATABASE_URL', '')

    # Gemini Settings
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

    # Groq Settings
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

    # Additional AI fallback settings
    HF_API_KEY = os.getenv('HF_API_KEY', os.getenv('HF_TOKEN', ''))
    COHERE_API_KEY = os.getenv('COHERE_API_KEY', '')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')

    # Google Apps Script Settings
    # Set APPS_SCRIPT_URL and APPS_SCRIPT_SECRET as secrets in Hugging Face / Render.
    # Do NOT hardcode these values here.
    APPS_SCRIPT_URL = os.getenv('APPS_SCRIPT_URL', '')
    APPS_SCRIPT_SECRET = os.getenv('APPS_SCRIPT_SECRET', '')



class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True
    LOG_LEVEL = 'DEBUG'
    SESSION_COOKIE_SECURE = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'WARNING'
    SESSION_COOKIE_SECURE = True


def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')

    config_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
    }

    return config_map.get(env, DevelopmentConfig)
