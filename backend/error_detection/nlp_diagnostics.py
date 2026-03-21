"""
NLP Diagnostics - Checks NLP service status and background worker
"""

import subprocess
import sys
from typing import Tuple, Dict

class NLPDiagnostics:
    """Diagnose NLP service and background worker issues"""

    def check_nlp_dependencies(self) -> Dict[str, dict]:
        """Check if all NLP dependencies are installed"""
        dependencies = {
            'nltk': 'Natural Language Toolkit',
            'textblob': 'TextBlob for sentiment',
            'transformers': 'HuggingFace Transformers (for DistilBERT)',
            'torch': 'PyTorch (for transformers)',
        }

        results = {}
        for pkg, desc in dependencies.items():
            try:
                __import__(pkg)
                results[pkg] = {
                    "status": "installed",
                    "description": desc
                }
            except ImportError:
                results[pkg] = {
                    "status": "missing",
                    "description": desc,
                    "fix": f"pip install {pkg}"
                }

        return results

    def check_nlp_service_creation(self) -> Tuple[bool, str, str]:
        """Try to instantiate NLP service"""
        try:
            from backend.services.nlp_service import NLPService
            nlp = NLPService()

            # Test basic methods
            test_text = "This is a great session!"
            sentiment = nlp.analyze_sentiment(test_text)
            keywords = nlp.extract_keywords(test_text)

            if sentiment and keywords is not None:
                return True, "NLP service working", json.dumps({
                    "sample_sentiment": sentiment,
                    "sample_keywords": keywords
                })
            else:
                return False, "NLP service returned empty results", ""

        except Exception as e:
            return False, f"Failed to create NLP service: {str(e)}", str(e)

    def check_model_loading(self) -> Dict[str, dict]:
        """Check if ML models can be loaded"""
        results = {}

        # Check TextBlob
        try:
            from textblob import TextBlob
            tb = TextBlob("test")
            results['textblob'] = {
                "status": "loaded",
                "polarity": tb.sentiment.polarity
            }
        except Exception as e:
            results['textblob'] = {
                "status": "failed",
                "error": str(e)
            }

        # Check NLTK data
        try:
            import nltk
            nltk.data.find('tokenizers/punkt_tab')
            nltk.data.find('corpora/stopwords')
            results['nltk_data'] = {
                "status": "available"
            }
        except Exception as e:
            results['nltk_data'] = {
                "status": "missing",
                "error": str(e),
                "fix": "nltk.download('punkt_tab'); nltk.download('stopwords')"
            }

        # Check transformers/DistilBERT
        try:
            from transformers import pipeline
            # Don't actually load model, just check if transformers works
            results['transformers'] = {
                "status": "available",
                "note": "DistilBERT can be loaded on demand"
            }
        except Exception as e:
            results['transformers'] = {
                "status": "failed",
                "error": str(e)
            }

        return results

    def check_background_worker_status(self) -> Dict:
        """Check if background worker thread is running"""
        return {
            "check": "background_worker",
            "status": "requires_runtime_inspection",
            "note": "Cannot detect thread status from bootstrap",
            "common_issues": [
                "Worker thread crashed due to model loading errors",
                "Database locked by worker process",
                "Worker waiting for dl_worker column to be created"
            ]
        }

    def full_diagnostics(self) -> Dict:
        """Run comprehensive NLP diagnostics"""
        import json

        deps_ok, deps_msg = True, "All dependencies present"
        dependencies = self.check_nlp_dependencies()
        if any(dep['status'] == 'missing' for dep in dependencies.values()):
            deps_ok = False
            deps_msg = "Some dependencies are missing"

        service_ok, service_msg, service_detail = self.check_nlp_service_creation()
        models = self.check_model_loading()
        worker = self.check_background_worker_status()

        return {
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "overall_status": "OK" if (deps_ok and service_ok) else "WARNING",
            "dependencies": {
                "summary": deps_msg,
                "details": dependencies
            },
            "service": {
                "status": "OK" if service_ok else "FAILED",
                "message": service_msg,
                "detail": service_detail
            },
            "models": models,
            "background_worker": worker,
            "recommendations": [
                "If NLP section is empty, check if background worker is processing data",
                "Review logs/app.log for worker thread errors",
                "Ensure database column 'dl_processed' exists",
                "Check if transformers model downloads are completing"
            ]
        }
