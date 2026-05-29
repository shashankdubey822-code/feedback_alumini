from typing import Dict, Any
from backend.utils.logger import get_section_logger
from backend.utils.supabase_db import execute_one
from backend.agents.base import BaseAgent, SupervisorAgent

logger = get_section_logger('analysis_orchestrator')

# ----------------- SUBAGENTS ----------------- #

class SentimentAnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Sentiment Analyzer Subagent", "Assigns a sentiment score and label using NLP.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing SentimentAnalyzerAgent")
        # Pseudo NLP processing
        payload['analysis_data'] = payload.get('analysis_data', {})
        payload['analysis_data']['sentiment_score'] = 0.8
        payload['analysis_data']['sentiment_label'] = 'Positive'
        return payload

class KeywordExtractionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Keyword Extraction Subagent", "Extracts key entities into keywords_json.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing KeywordExtractionAgent")
        payload['analysis_data']['keywords'] = ["interactive", "great session"]
        return payload

class ActionableInsightAgent(BaseAgent):
    def __init__(self):
        super().__init__("Actionable Insight Subagent", "Determines if feedback requires immediate faculty action.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing ActionableInsightAgent")
        payload['analysis_data']['is_actionable'] = False
        return payload

class TopicModelingAgent(BaseAgent):
    def __init__(self):
        super().__init__("Topic Modeling Subagent", "Aggregates future topics to recommend.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing TopicModelingAgent")
        payload['analysis_data']['category'] = "Technology"
        return payload

class CertificateTemplateAgent(BaseAgent):
    def __init__(self):
        super().__init__("Certificate Template Mapper Subagent", "Selects Google Slides template.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing CertificateTemplateAgent")
        payload['certificate_data'] = {'template_id': 'default_template'}
        return payload

class CertificateGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Certificate Generator Subagent", "Triggers GAS to inject student name.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing CertificateGeneratorAgent")
        payload['certificate_data']['status'] = 'COMPLETED'
        payload['certificate_data']['url'] = 'https://docs.google.com/presentation/d/fake_cert/edit'
        return payload

class EmailNotificationAgent(BaseAgent):
    def __init__(self):
        super().__init__("Email Notification Subagent", "Emails generated certificate to student.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing EmailNotificationAgent")
        # Emailing logic
        return payload

class DashboardSyncerAgent(BaseAgent):
    def __init__(self):
        super().__init__("Dashboard Analytics Syncer Subagent", "Updates AnalyticsEngine.")
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing DashboardSyncerAgent")
        response_id = payload.get('response_id')
        if response_id:
            try:
                from backend.services.analytics_engine import analytics_engine
                analytics_engine.refresh_single_record(response_id)
            except Exception as e:
                logger.error(f"Dashboard sync failed: {e}")
        return payload

# ----------------- SUPERVISOR ----------------- #

class AnalysisOrchestratorSupervisor(SupervisorAgent):
    def __init__(self):
        super().__init__("Analysis & Action Supervisor", "Manages AI analytics, generation, and notifications.")
        
        self.register_subagent(SentimentAnalyzerAgent())
        self.register_subagent(KeywordExtractionAgent())
        self.register_subagent(ActionableInsightAgent())
        self.register_subagent(TopicModelingAgent())
        self.register_subagent(CertificateTemplateAgent())
        self.register_subagent(CertificateGeneratorAgent())
        self.register_subagent(EmailNotificationAgent())
        self.register_subagent(DashboardSyncerAgent())

    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Analysis Orchestrator: Processing payload via {len(self.subagents)} subagents...")
        
        state = payload
        for agent in self.subagents:
            state = agent.execute(state)
            if 'error' in state: break
            
        # Finally, save analysis to DB
        response_id = payload.get('response_id')
        if response_id and 'analysis_data' in payload:
            try:
                import json
                a_data = payload['analysis_data']
                k_json = json.dumps({
                    'keywords': a_data.get('keywords', []),
                    'is_actionable': a_data.get('is_actionable', False),
                    'category': a_data.get('category', 'Other')
                })
                
                execute_one("""
                    INSERT INTO feedback_analysis (response_id, sentiment_label, sentiment_score, keywords_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (response_id) DO UPDATE SET
                        sentiment_label = EXCLUDED.sentiment_label,
                        sentiment_score = EXCLUDED.sentiment_score,
                        keywords_json = EXCLUDED.keywords_json
                """, (response_id, a_data.get('sentiment_label'), a_data.get('sentiment_score'), k_json))
                logger.info(f"Saved analysis for response {response_id}")
            except Exception as e:
                logger.error(f"Failed to save analysis: {e}")
                
        return state
