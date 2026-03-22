"""
Error Detection Base — Severity enum, DetectionResult, and base class.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING  = "WARNING"
    INFO     = "INFO"


@dataclass
class DetectionResult:
    page:     str
    check:    str
    severity: Severity
    message:  str
    detail:   Optional[str] = None
    ok:       bool = False

    def to_dict(self) -> dict:
        return {
            "page":     self.page,
            "check":    self.check,
            "severity": self.severity.value,
            "message":  self.message,
            "detail":   self.detail,
            "ok":       self.ok,
        }


class ErrorDetector:
    """Base class for all page-level error detectors."""

    page: str = "unknown"

    def run(self) -> List[DetectionResult]:
        raise NotImplementedError

    def _ok(self, check: str, message: str) -> DetectionResult:
        return DetectionResult(page=self.page, check=check, severity=Severity.INFO,
                               message=message, ok=True)

    def _warn(self, check: str, message: str, detail: str = None) -> DetectionResult:
        return DetectionResult(page=self.page, check=check, severity=Severity.WARNING,
                               message=message, detail=detail, ok=False)

    def _critical(self, check: str, message: str, detail: str = None) -> DetectionResult:
        return DetectionResult(page=self.page, check=check, severity=Severity.CRITICAL,
                               message=message, detail=detail, ok=False)
