"""
Error Logger - Centralized error tracking and categorization
"""

import json
import os
from datetime import datetime
from enum import Enum

class ErrorCategory(Enum):
    """Error categories for classification"""
    DATABASE = "database"
    NLP_SERVICE = "nlp_service"
    DATA_INGESTION = "data_ingestion"
    SERVICE_CONNECTION = "service_connection"
    BACKGROUND_WORKER = "background_worker"
    GOOGLE_FORMS = "google_forms"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ErrorLogger:
    """Centralized error logging and diagnostics"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self.error_file = os.path.join(log_dir, "errors.jsonl")
        self.diagnostics_file = os.path.join(log_dir, "diagnostics.log")

        # Ensure logs directory exists
        os.makedirs(log_dir, exist_ok=True)

    def log_error(self, category: ErrorCategory, error_msg: str,
                  context: dict = None, traceback_str: str = None):
        """Log an error with full context"""
        error_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "category": category.value,
            "message": error_msg,
            "context": context or {},
            "traceback": traceback_str
        }

        # Append to JSON lines file
        with open(self.error_file, 'a') as f:
            f.write(json.dumps(error_record) + '\n')

        return error_record

    def get_error_summary(self, limit: int = 100) -> dict:
        """Get summary of recent errors by category"""
        category_counts = {}
        recent_errors = []

        if not os.path.exists(self.error_file):
            return {"summary": {}, "recent": []}

        with open(self.error_file, 'r') as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    error = json.loads(line)
                    cat = error.get("category", "unknown")
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    recent_errors.append(error)
                except:
                    continue

        return {
            "total_errors": len(recent_errors),
            "by_category": category_counts,
            "recent_errors": recent_errors[-10:]  # Last 10
        }

    def diagnose(self) -> dict:
        """Generate diagnostic report"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error_summary": self.get_error_summary()
        }
