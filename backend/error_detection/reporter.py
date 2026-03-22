"""
Error Reporter — aggregates all page detectors and exposes results.
"""
from __future__ import annotations
import os
import logging
from typing import List, Dict, Any

from .base import DetectionResult, Severity
from .db_errors import DBErrorDetector
from .overview_errors import OverviewErrorDetector
from .insights_errors import InsightsErrorDetector
from .charts_errors import ChartsErrorDetector
from .nlp_errors import NLPErrorDetector
from .speakers_errors import SpeakersErrorDetector
from .upload_errors import UploadErrorDetector
from .webhook_errors import WebhookErrorDetector

logger = logging.getLogger("error_detection")


def run_all_checks(db_path: str, upload_dir: str = "data/uploads") -> Dict[str, Any]:
    """Run all detectors and return a structured report."""
    detectors = [
        DBErrorDetector(db_path),
        OverviewErrorDetector(db_path),
        InsightsErrorDetector(db_path),
        ChartsErrorDetector(db_path),
        NLPErrorDetector(db_path),
        SpeakersErrorDetector(db_path),
        UploadErrorDetector(upload_dir, db_path),
        WebhookErrorDetector(),
    ]

    all_results: List[DetectionResult] = []
    for detector in detectors:
        try:
            results = detector.run()
            all_results.extend(results)
        except Exception as e:
            logger.error(f"Detector {detector.__class__.__name__} crashed: {e}")
            all_results.append(DetectionResult(
                page=detector.page,
                check="detector_crash",
                severity=Severity.CRITICAL,
                message=f"Detector crashed: {e}",
                ok=False,
            ))

    # Summarize
    criticals = [r for r in all_results if r.severity == Severity.CRITICAL and not r.ok]
    warnings  = [r for r in all_results if r.severity == Severity.WARNING and not r.ok]
    oks       = [r for r in all_results if r.ok]

    # Log critical errors
    for r in criticals:
        logger.error(f"[{r.page.upper()}] {r.check}: {r.message}" + (f" — {r.detail}" if r.detail else ""))

    return {
        "summary": {
            "total":    len(all_results),
            "critical": len(criticals),
            "warnings": len(warnings),
            "ok":       len(oks),
            "healthy":  len(criticals) == 0,
        },
        "results": [r.to_dict() for r in all_results],
        "by_page": _group_by_page(all_results),
    }


def _group_by_page(results: List[DetectionResult]) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for r in results:
        grouped.setdefault(r.page, []).append(r.to_dict())
    return grouped
