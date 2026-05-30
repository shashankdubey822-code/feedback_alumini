"""
Error Detection System — per-page error detectors for DataLens.
"""
from .base import ErrorDetector, DetectionResult, Severity
from .reporter import run_all_checks

__all__ = ["ErrorDetector", "DetectionResult", "Severity", "run_all_checks"]
