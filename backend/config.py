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

    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'database/dashboard.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # SQLite timeout and connection settings
    SQLITE_TIMEOUT = 30.0  # 30 seconds timeout for locked database
    SQLITE_CHECK_SAME_THREAD = False  # Allow cross-thread access

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
    DATABASE_PATH = 'database/test_dashboard.db'
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
