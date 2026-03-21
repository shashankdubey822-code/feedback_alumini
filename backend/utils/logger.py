"""
Logging configuration and utilities
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(app=None, name=None, log_file=None, log_level=None):
    """
    Setup application logger with file and console handlers

    Args:
        app: Flask application instance (optional)
        name: Logger name, defaults to __name__
        log_file: Log file path
        log_level: Logging level
    """
    logger = logging.getLogger(name or __name__)

    # Get config from app if provided
    if app:
        log_file = log_file or app.config.get('LOG_FILE', 'logs/app.log')
        log_level = log_level or app.config.get('LOG_LEVEL', 'INFO')
    else:
        log_file = log_file or 'logs/app.log'
        log_level = log_level or 'INFO'

    # Set log level
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Create logs directory if needed
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create formatters
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (with rotation)
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name):
    """Get or create a named logger"""
    return logging.getLogger(name)


def log_endpoint_access(func):
    """Decorator to log endpoint access"""
    import functools
    from flask import request

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(__name__)
        logger.info(f'{request.method} {request.path} - {request.remote_addr}')
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f'Error in {request.path}: {str(e)}', exc_info=True)
            raise

    return wrapper


def get_section_logger(section_name: str) -> logging.Logger:
    """
    Get a logger dedicated to a specific application section (nlp, db, api, etc).
    Logs to a cleanly isolated file: logs/{section_name}_errors.log
    """
    logger = logging.getLogger(section_name)
    logger.setLevel(logging.INFO)
    
    # Avoid attaching handlers multiple times on sequential calls
    if not logger.handlers:
        # Resolve project root dir
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"{section_name}_errors.log")
        
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False
        
    return logger
