"""
E2E Test Suite for Dashboard RAG Mode Restoration (Milestone 4).

Covers:
- Tier 1: Feature Coverage (Standard RAG vs Dashboard RAG routing, direct tool execution).
- Tier 2: Boundary & Corner Cases (Multiline SQL stripping, empty inputs, bad SQL syntax, forbidden DDL/DML, schema fallback, observation truncation).
- Tier 3: Cross-Feature Combinations (Combined Schema + SQL + Vector search workflows, ReAct multi-tool iteration).
- Tier 4: Real-World Application Scenarios (Synthesizing student ratings, feedback response counts, event summaries).
"""

import sys
import os
import json
import re
from unittest.mock import patch, MagicMock

import pytest

# Ensure root workspace directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.services.agent_tools import (
    get_schema_info,
    execute_readonly_sql,
    semantic_vector_search,
    _STATIC_SCHEMA,
    MAX_TOOL_OUTPUT_CHARS,
    MAX_RESULT_ROWS,
)
from backend.services.wiki_service import WikiService


# ==============================================================================
# TIER 1: FEATURE COVERAGE
# ==============================================================================

class TestTier1FeatureCoverage:
    """Tier 1: Basic functionality & routing between standard RAG and Dashboard RAG."""

    def test_tier1_standard_rag_routing(self):
        """Verify query_wiki routes to Standard RAG when session_id does not start with 'dashboard_rag_'."""
        wiki_service = WikiService()
        with patch.object(wiki_service, 'list_wiki_pages', return_value=[]), \
             patch('backend.services.rag_service.RAGService') as MockRAG, \
             patch('backend.services.wiki_service.ChatGroq') as MockGroq:
            
            mock_rag_inst = MockRAG.return_value
            mock_rag_inst.search_similar_feedback.return_value = []

            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content="Final Answer: Standard RAG answer")
            MockGroq.return_value = mock_llm

            wiki_service.groq_key = "fake_groq_key"
            res = wiki_service.query_wiki("What guest lectures occurred?", session_id="standard_session_123")

            assert "answer" in res
            assert res["answer"] == "Standard RAG answer"
            mock_rag_inst.search_similar_feedback.assert_called_once()

    def test_tier1_dashboard_rag_routing(self):
        """Verify query_wiki routes to Dashboard RAG when session_id starts with 'dashboard_rag_'."""
        wiki_service = WikiService()
        with patch('backend.services.wiki_service.get_schema_info') as mock_schema, \
             patch('backend.services.rag_service.RAGService') as MockRAG, \
             patch('backend.services.wiki_service.ChatGroq') as MockGroq:
            
            mock_schema.return_value = "Database Tables: students, events"
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = MagicMock(content="Final Answer: Dashboard RAG active")
            MockGroq.return_value = mock_llm

            wiki_service.groq_key = "fake_groq_key"
            res = wiki_service.query_wiki("Show total students", session_id="dashboard_rag_session_456")

            assert "answer" in res
            assert res["answer"] == "Dashboard RAG active"
            mock_schema.assert_called_once()
            MockRAG.assert_not_called()

    def test_tier1_execute_readonly_sql_valid_query(self):
        """Verify execute_readonly_sql runs a valid SELECT statement and formats JSON response."""
        mock_rows = [
            {"id": 1, "name": "Alice", "department": "Computer Science"},
            {"id": 2, "name": "Bob", "department": "Information Technology"}
        ]
        with patch('backend.services.agent_tools.execute_all', return_value=mock_rows) as mock_exec:
            res = execute_readonly_sql("SELECT id, name, department FROM students;")
            mock_exec.assert_called_once_with("SELECT id, name, department FROM students")
            parsed = json.loads(res)
            assert len(parsed) == 2
            assert parsed[0]["name"] == "Alice"
            assert parsed[1]["department"] == "Information Technology"

    def test_tier1_semantic_vector_search_valid_query(self):
        """Verify semantic_vector_search queries RAGService and formats response snippets."""
        mock_results = [
            {
                "similarity": 0.92,
                "alumni_speaker_name": "Dr. Smith",
                "name_of_student": "Jane Doe",
                "session_rating": 5,
                "aspect_most_valuable": "Practical AI coding demos",
                "improvements_suggestions": "More Q&A time",
                "future_topics": "Deep Learning with PyTorch"
            }
        ]
        with patch('backend.services.agent_tools.RAGService') as MockRAG:
            mock_rag_inst = MockRAG.return_value
            mock_rag_inst.search_similar_feedback.return_value = mock_results

            res = semantic_vector_search("AI coding demos", top_k=3)
            assert "Semantic Search Results for 'AI coding demos':" in res
            assert "Speaker: Dr. Smith" in res
            assert "Student: Jane Doe" in res
            assert "Session Rating: 5/5" in res
            assert "Aspect Most Valuable: Practical AI coding demos" in res

    def test_tier1_get_schema_info_success(self):
        """Verify get_schema_info returns dynamic database table schemas when information_schema query succeeds."""
        mock_info_schema_rows = [
            {"table_name": "events", "column_name": "id", "data_type": "bigint"},
            {"table_name": "events", "column_name": "name", "data_type": "text"},
            {"table_name": "students", "column_name": "id", "data_type": "bigint"},
            {"table_name": "students", "column_name": "email", "data_type": "text"},
        ]
        with patch('backend.services.agent_tools.execute_all', return_value=mock_info_schema_rows):
            schema = get_schema_info()
            assert "Database Tables and Columns:" in schema
            assert "Table: events" in schema
            assert "- id (bigint)" in schema
            assert "Table: students" in schema
            assert "- email (text)" in schema


# ==============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# ==============================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Boundary, formatting, invalid input, and safety enforcement cases."""

    def test_tier2_multiline_sql_stripping(self):
        """Verify execute_readonly_sql correctly strips multiline markdown code fences without truncating lines."""
        multiline_sql = """```sql
        SELECT e.name, COUNT(r.id) AS total_responses
        FROM events e
        JOIN feedback_responses r ON e.id = r.event_id
        GROUP BY e.name
        ORDER BY total_responses DESC
        ```"""
        mock_rows = [{"name": "AI Workshop", "total_responses": 42}]
        with patch('backend.services.agent_tools.execute_all', return_value=mock_rows) as mock_exec:
            res = execute_readonly_sql(multiline_sql)
            expected_cleaned = "SELECT e.name, COUNT(r.id) AS total_responses\n        FROM events e\n        JOIN feedback_responses r ON e.id = r.event_id\n        GROUP BY e.name\n        ORDER BY total_responses DESC"
            mock_exec.assert_called_once_with(expected_cleaned)
            assert "AI Workshop" in res

    def test_tier2_empty_and_invalid_sql_inputs(self):
        """Verify execute_readonly_sql handles None, empty string, and whitespace gracefully."""
        assert execute_readonly_sql(None) == "Error: Empty or invalid SQL query provided."
        assert execute_readonly_sql("") == "Error: Empty or invalid SQL query provided."
        assert execute_readonly_sql("   ") == "Error: SQL query is empty after stripping formatting."
        assert execute_readonly_sql("```sql   ```") == "Error: SQL query is empty after stripping formatting."

    def test_tier2_bad_sql_syntax_handling(self):
        """Verify execute_readonly_sql handles database execution errors gracefully."""
        with patch('backend.services.agent_tools.execute_all', side_effect=Exception("relation 'non_existent_table' does not exist")):
            res = execute_readonly_sql("SELECT * FROM non_existent_table;")
            assert "Database error: relation 'non_existent_table' does not exist" in res

    def test_tier2_forbidden_ddl_dml_sql(self):
        """Verify execute_readonly_sql blocks DDL, DML, and multi-statement queries."""
        # Mutation rejection
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("DELETE FROM students WHERE id = 1;")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("INSERT INTO events (name) VALUES ('Test');")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("UPDATE students SET name = 'Hacked';")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("DROP TABLE feedback_responses;")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("ALTER TABLE students ADD COLUMN secret text;")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("TRUNCATE TABLE wiki_pages;")
        assert "Forbidden DDL/mutation statement" in execute_readonly_sql("CREATE TABLE evil (id int);")

        # Multi-statement rejection
        assert "Only single SQL statements are allowed" in execute_readonly_sql("SELECT 1; SELECT 2;")

        # Non-SELECT statement rejection
        assert "Only read-only SELECT or WITH ... SELECT queries are allowed." in execute_readonly_sql("SHOW tables;")

    def test_tier2_missing_table_schema_fallback(self):
        """Verify get_schema_info falls back to static schema if information_schema query fails or returns empty."""
        with patch('backend.services.agent_tools.execute_all', side_effect=Exception("DB Connection failed")):
            schema = get_schema_info()
            assert schema == _STATIC_SCHEMA.strip()
            assert "1. students:" in schema
            assert "2. events:" in schema

        with patch('backend.services.agent_tools.execute_all', return_value=[]):
            schema = get_schema_info()
            assert schema == _STATIC_SCHEMA.strip()

    def test_tier2_vector_search_empty_and_error(self):
        """Verify semantic_vector_search handles empty query and exceptions gracefully."""
        assert "Error: Empty query provided" in semantic_vector_search(None)
        assert "Error: Empty query provided" in semantic_vector_search("")
        assert "Error: Query is empty after cleaning." in semantic_vector_search('""')

        with patch('backend.services.agent_tools.RAGService', side_effect=Exception("Vector index uninitialized")):
            assert "Vector search error: Vector index uninitialized" in semantic_vector_search("Machine Learning")

    def test_tier2_react_observation_truncation(self):
        """Verify ReAct loop in query_wiki truncates tool observations longer than 1500 chars."""
        wiki_service = WikiService()
        wiki_service.groq_key = "fake_key"

        long_observation = "A" * 2000
        llm_responses = [
            MagicMock(content="Action: execute_readonly_sql\nAction Input: SELECT * FROM long_table;"),
            MagicMock(content="Final Answer: Done processing long table.")
        ]

        with patch('backend.services.wiki_service.get_schema_info', return_value="Schema"), \
             patch('backend.services.wiki_service.execute_readonly_sql', return_value=long_observation) as mock_sql, \
             patch('backend.services.wiki_service.ChatGroq') as MockGroq:
            
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = llm_responses
            MockGroq.return_value = mock_llm

            res = wiki_service.query_wiki("Get long table", session_id="dashboard_rag_test")
            assert res["answer"] == "Done processing long table."
            
            # Check the second invoke call to ensure truncated observation was passed to LLM
            second_call_messages = mock_llm.invoke.call_args_list[1][0][0]
            last_message_content = second_call_messages[-1].content
            assert "Observation: " in last_message_content
            assert "... [Observation truncated to 1500 characters]" in last_message_content
            assert len(last_message_content) < 1600


# ==============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# ==============================================================================

class TestTier3CrossFeatureCombinations:
    """Tier 3: Multi-tool ReAct loop sequences and cross-feature capabilities."""

    def test_tier3_combined_schema_sql_vector_sequence(self):
        """Verify sequential execution of get_schema_info, execute_readonly_sql, and semantic_vector_search."""
        # 1. Inspect Schema
        with patch('backend.services.agent_tools.execute_all', return_value=[{"table_name": "events", "column_name": "speaker_name", "data_type": "text"}]):
            schema_res = get_schema_info()
            assert "Table: events" in schema_res

        # 2. Run SQL Query
        sql_rows = [{"speaker_name": "Prof. Alan Turing", "event_id": 101}]
        with patch('backend.services.agent_tools.execute_all', return_value=sql_rows):
            sql_res = execute_readonly_sql("SELECT speaker_name, event_id FROM events WHERE id = 101;")
            assert "Prof. Alan Turing" in sql_res

        # 3. Vector Search
        mock_vec_results = [{
            "similarity": 0.88,
            "alumni_speaker_name": "Prof. Alan Turing",
            "name_of_student": "Student A",
            "session_rating": 5,
            "aspect_most_valuable": "Computing Machinery",
            "improvements_suggestions": "None",
            "future_topics": "AI Ethics"
        }]
        with patch('backend.services.agent_tools.RAGService') as MockRAG:
            MockRAG.return_value.search_similar_feedback.return_value = mock_vec_results
            vec_res = semantic_vector_search("Computing Machinery")
            assert "Prof. Alan Turing" in vec_res
            assert "Computing Machinery" in vec_res

    def test_tier3_react_multi_step_tool_loop(self):
        """Verify ReAct loop in query_wiki handles multiple tool steps before returning Final Answer."""
        wiki_service = WikiService()
        wiki_service.groq_key = "fake_groq_key"

        llm_step1 = MagicMock(content="Action: get_schema_info\nAction Input: ")
        llm_step2 = MagicMock(content="Action: execute_readonly_sql\nAction Input: SELECT COUNT(*) FROM feedback_responses;")
        llm_step3 = MagicMock(content="Final Answer: There are 150 feedback responses recorded.")

        with patch('backend.services.wiki_service.get_schema_info', return_value="Schema: feedback_responses") as mock_schema, \
             patch('backend.services.wiki_service.execute_readonly_sql', return_value='[{"count": 150}]') as mock_sql, \
             patch('backend.services.wiki_service.ChatGroq') as MockGroq:
            
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = [llm_step1, llm_step2, llm_step3]
            MockGroq.return_value = mock_llm

            res = wiki_service.query_wiki("How many feedback responses do we have?", session_id="dashboard_rag_multi_step")
            
            assert res["answer"] == "There are 150 feedback responses recorded."
            assert mock_schema.call_count == 1
            mock_sql.assert_called_once_with("SELECT COUNT(*) FROM feedback_responses;")
            assert mock_llm.invoke.call_count == 3

    def test_tier3_vector_search_with_secondary_filters(self):
        """Verify semantic_vector_search applies optional python secondary filters (dept, year, semester)."""
        mock_results = [
            {"similarity": 0.9, "department": "Computer Science", "year": 2025, "alumni_speaker_name": "Dr. A"},
            {"similarity": 0.8, "department": "Electrical Engineering", "year": 2024, "alumni_speaker_name": "Dr. B"}
        ]
        with patch('backend.services.agent_tools.RAGService') as MockRAG:
            MockRAG.return_value.search_similar_feedback.return_value = mock_results
            
            # Filter matching CS dept
            res_cs = semantic_vector_search("lecture", filter_dept="Computer Science")
            assert "Dr. A" in res_cs
            assert "Dr. B" not in res_cs

            # Filter matching non-existent year falls back to all results to avoid empty response
            res_fallback = semantic_vector_search("lecture", filter_year=1999)
            assert "Dr. A" in res_fallback
            assert "Dr. B" in res_fallback


# ==============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==============================================================================

class TestTier4RealWorldScenarios:
    """Tier 4: Complex synthesis of analytics, student ratings, and feedback data."""

    def test_tier4_synthesize_student_ratings(self):
        """Test real-world scenario querying average session ratings per speaker."""
        sql_query = """
        SELECT e.speaker_name, COUNT(r.id) AS total_feedback, ROUND(AVG(r.session_rating), 2) AS avg_rating
        FROM events e
        JOIN feedback_responses r ON e.id = r.event_id
        GROUP BY e.speaker_name
        ORDER BY avg_rating DESC;
        """
        mock_sql_output = [
            {"speaker_name": "Dr. Sarah Connor", "total_feedback": 45, "avg_rating": "4.85"},
            {"speaker_name": "Prof. John Doe", "total_feedback": 30, "avg_rating": "4.20"}
        ]
        with patch('backend.services.agent_tools.execute_all', return_value=mock_sql_output):
            res = execute_readonly_sql(sql_query)
            parsed = json.loads(res)
            assert len(parsed) == 2
            assert parsed[0]["speaker_name"] == "Dr. Sarah Connor"
            assert float(parsed[0]["avg_rating"]) == 4.85

    def test_tier4_synthesize_feedback_counts_by_event(self):
        """Test real-world scenario counting feedback submissions per event."""
        sql_query = """
        SELECT e.id, e.name, e.speaker_name, COUNT(r.id) AS feedback_count
        FROM events e
        LEFT JOIN feedback_responses r ON e.id = r.event_id
        GROUP BY e.id, e.name, e.speaker_name
        ORDER BY feedback_count DESC;
        """
        mock_sql_output = [
            {"id": 10, "name": "Cloud Architecture Masterclass", "speaker_name": "Jane Smith", "feedback_count": 82},
            {"id": 11, "name": "Cybersecurity Trends", "speaker_name": "Robert Vance", "feedback_count": 15}
        ]
        with patch('backend.services.agent_tools.execute_all', return_value=mock_sql_output):
            res = execute_readonly_sql(sql_query)
            parsed = json.loads(res)
            assert parsed[0]["name"] == "Cloud Architecture Masterclass"
            assert parsed[0]["feedback_count"] == 82

    def test_tier4_synthesize_full_event_summary_in_dashboard_rag(self):
        """Test real-world end-to-end Dashboard RAG scenario synthesizing numerical ratings and qualitative feedback."""
        wiki_service = WikiService()
        wiki_service.groq_key = "fake_key"

        llm_step1 = MagicMock(content="Action: execute_readonly_sql\nAction Input: SELECT e.speaker_name, AVG(r.session_rating) as avg_rating FROM events e JOIN feedback_responses r ON e.id = r.event_id GROUP BY e.speaker_name;")
        llm_step2 = MagicMock(content="Action: semantic_vector_search\nAction Input: Dr. Sarah Connor improvement suggestions")
        llm_step3 = MagicMock(content="Final Answer: Dr. Sarah Connor achieved an average rating of 4.85 across 45 responses. Students praised the live AI demos and suggested extending the Q&A session.")

        mock_sql_res = '[{"speaker_name": "Dr. Sarah Connor", "avg_rating": 4.85}]'
        mock_vec_res = "Semantic Search Results for 'Dr. Sarah Connor improvement suggestions':\nResult 1: Speaker: Dr. Sarah Connor, Rating: 5/5, Aspect Most Valuable: Live AI Demos, Improvement Suggestions: Extend Q&A"

        with patch('backend.services.wiki_service.get_schema_info', return_value="Schema"), \
             patch('backend.services.wiki_service.execute_readonly_sql', return_value=mock_sql_res) as mock_sql, \
             patch('backend.services.wiki_service.semantic_vector_search', return_value=mock_vec_res) as mock_vec, \
             patch('backend.services.wiki_service.ChatGroq') as MockGroq:
            
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = [llm_step1, llm_step2, llm_step3]
            MockGroq.return_value = mock_llm

            res = wiki_service.query_wiki("Provide a summary of Dr. Sarah Connor's lecture performance.", session_id="dashboard_rag_summary_123")
            
            assert "Dr. Sarah Connor achieved an average rating of 4.85" in res["answer"]
            assert "Live AI demos" in res["answer"]
            mock_sql.assert_called_once()
            mock_vec.assert_called_once()
