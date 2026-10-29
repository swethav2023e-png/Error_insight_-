"""
Comprehensive Automated Test Suite for ErrorInsight.
Validates all 14 required areas using a temporary test SQLite database:
1. Application startup and database initialization
2. Health endpoint
3. Valid JSON upload (Format A and Format B)
4. Valid plain-text log upload
5. Invalid JSON and unsupported formats
6. Missing required fields
7. Error categorization and severity normalization
8. Database persistence across application restarts
9. History retrieval and filtering
10. Analytics calculations
11. API-key authentication
12. Duplicate submission handling
13. Integration between a simulated Log Parser client and ErrorInsight
14. Database failures and appropriate HTTP responses
"""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from app import create_app
from config import TestingConfig
from database.db import DatabaseError, SQLiteManager, get_db, set_db
from services.classifier_service import classify_category, normalize_severity
from services.parser_service import parse_json_data, parse_plaintext_log, ParseError


class ErrorInsightTestCase(unittest.TestCase):
    """Test case suite covering all core ErrorInsight capabilities."""

    def setUp(self):
        # Create a temporary database file for each test or test run
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)

        class CustomTestConfig(TestingConfig):
            DATABASE_PATH = self.temp_db_path
            API_KEY = "test-secret-api-key-42"
            TESTING = True

        self.config = CustomTestConfig
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        # Clean up temporary database file
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    # 1. Application startup and database initialization
    def test_01_app_startup_and_database_init(self):
        self.assertTrue(os.path.exists(self.temp_db_path))
        db = SQLiteManager(self.temp_db_path)
        health = db.check_health()
        self.assertTrue(health["connected"])
        self.assertEqual(health["record_count"], 0)

    # 2. Health endpoint
    def test_02_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "SQLite")
        self.assertEqual(data["stored_record_count"], 0)

    # 3. Valid JSON upload (Format A and Format B)
    def test_03_valid_json_upload_format_a_and_b(self):
        # Format A: Object with "errors" array
        format_a = {
            "errors": [
                {
                    "id": "A-1",
                    "timestamp": "2026-10-29 08:00:00",
                    "type": "Database",
                    "message": "Database connection failed",
                    "severity": "Critical"
                }
            ]
        }
        res_a = self.client.post(
            "/api/analyze",
            data=json.dumps(format_a),
            content_type="application/json"
        )
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.get_json()
        self.assertEqual(data_a["status"], "success")
        self.assertEqual(data_a["saved_to_database"], 1)
        self.assertEqual(data_a["analysis"]["total_errors"], 1)

        # Format B: Array of objects
        format_b = [
            {
                "timestamp": "2026-10-29 08:05:00",
                "message": "Connection timeout connecting to redis",
                "severity": "Warning"
            }
        ]
        res_b = self.client.post(
            "/api/analyze",
            data=json.dumps(format_b),
            content_type="application/json"
        )
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.get_json()
        self.assertEqual(data_b["status"], "success")
        self.assertEqual(data_b["saved_to_database"], 1)

    # 4. Valid plain-text log upload
    def test_04_valid_plaintext_log_upload(self):
        log_content = (
            "2026-10-29 09:00:15 [CRITICAL] Database connection refused on port 3306\n"
            "2026-10-29 09:01:22 [ERROR] Failed to authenticate user admin\n"
            "2026-10-29 09:02:45 [WARN] HTTP request timed out connecting to service\n"
        )
        data = {
            "file": (io.BytesIO(log_content.encode("utf-8")), "server.log")
        }
        response = self.client.post(
            "/api/analyze",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.get_json()
        self.assertEqual(res_json["saved_to_database"], 3)
        self.assertEqual(res_json["analysis"]["total_errors"], 3)

    # 5. Invalid JSON and unsupported formats
    def test_05_invalid_json_and_unsupported_formats(self):
        # Invalid JSON syntax
        bad_json = "{ 'errors': [ invalid json content... "
        response = self.client.post(
            "/api/analyze",
            data=bad_json,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

        # Empty plain-text file
        empty_data = {
            "file": (io.BytesIO(b"   \n  "), "empty.log")
        }
        res_empty = self.client.post(
            "/api/analyze",
            data=empty_data,
            content_type="multipart/form-data"
        )
        self.assertEqual(res_empty.status_code, 400)

    # 6. Missing required fields
    def test_06_missing_required_fields(self):
        # JSON error object without a message
        payload = {
            "errors": [
                {"id": 1, "timestamp": "2026-10-29 10:00:00", "severity": "Info"},
                {"id": 2, "timestamp": "2026-10-29 10:01:00", "severity": "Error", "message": ""}
            ]
        }
        response = self.client.post(
            "/api/logs",
            data=json.dumps(payload),
            headers={"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No valid error records found", response.get_json()["error"])

    # 7. Error categorization and severity normalization
    def test_07_categorization_and_severity_normalization(self):
        # Categorization tests
        self.assertEqual(classify_category("Database connection timeout"), "Database")
        self.assertEqual(classify_category("Invalid password hash or JWT token"), "Authentication")
        self.assertEqual(classify_category("Socket connection reset by peer"), "Network")
        self.assertEqual(classify_category("File not found: /etc/app.conf"), "File System")
        self.assertEqual(classify_category("Out of memory: Heap space exceeded"), "Memory")
        self.assertEqual(classify_category("NullPointerException in user service"), "Application")

        # Explicit category preservation
        self.assertEqual(classify_category("Something happened", explicit_type="Database"), "Database")
        self.assertEqual(classify_category("Unrelated message", explicit_type="Network"), "Network")

        # Severity normalization tests
        self.assertEqual(normalize_severity("FATAL"), "Critical")
        self.assertEqual(normalize_severity("CRITICAL"), "Critical")
        self.assertEqual(normalize_severity("EXCEPTION"), "Error")
        self.assertEqual(normalize_severity("ERROR"), "Error")
        self.assertEqual(normalize_severity("WARN"), "Warning")
        self.assertEqual(normalize_severity("WARNING"), "Warning")
        self.assertEqual(normalize_severity("INFORMATION"), "Info")
        self.assertEqual(normalize_severity("INFO"), "Info")
        self.assertEqual(normalize_severity("UNKNOWN_XYZ"), "Error")

    # 8. Database persistence across application restarts
    def test_08_database_persistence_across_restarts(self):
        # Insert record into app instance 1
        headers = {"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        payload = {
            "errors": [
                {
                    "id": "PERSIST-1",
                    "timestamp": "2026-10-29 12:00:00",
                    "type": "Database",
                    "message": "Persistent DB failure verification",
                    "severity": "Critical"
                }
            ]
        }
        res1 = self.client.post("/api/logs", data=json.dumps(payload), headers=headers)
        self.assertEqual(res1.status_code, 201)

        # "Restart" by instantiating a completely new Flask app using the same temp_db_path
        app2 = create_app(self.config)
        client2 = app2.test_client()

        # Query history from app2
        res2 = client2.get("/api/history")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["pagination"]["total_records"], 1)
        self.assertEqual(data2["records"][0]["message"], "Persistent DB failure verification")

    # 9. History retrieval and filtering
    def test_09_history_retrieval_and_filtering(self):
        headers = {"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        payload = {
            "errors": [
                {"id": "H-1", "timestamp": "2026-10-29 10:00:00", "type": "Database", "message": "SQL query failed", "severity": "Critical"},
                {"id": "H-2", "timestamp": "2026-10-29 10:05:00", "type": "Network", "message": "Socket closed", "severity": "Warning"},
                {"id": "H-3", "timestamp": "2026-10-29 10:10:00", "type": "Authentication", "message": "Login failed", "severity": "Error"},
            ]
        }
        self.client.post("/api/logs", data=json.dumps(payload), headers=headers)

        # Filter by severity
        res_crit = self.client.get("/api/history?severity=Critical")
        self.assertEqual(res_crit.status_code, 200)
        self.assertEqual(len(res_crit.get_json()["records"]), 1)
        self.assertEqual(res_crit.get_json()["records"][0]["category"], "Database")

        # Filter by category
        res_net = self.client.get("/api/history?category=Network")
        self.assertEqual(res_net.status_code, 200)
        self.assertEqual(len(res_net.get_json()["records"]), 1)

        # Search query
        res_search = self.client.get("/api/history?search=Login")
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.get_json()["records"]), 1)

    # 10. Analytics calculations
    def test_10_analytics_calculations(self):
        headers = {"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        payload = {
            "errors": [
                {"timestamp": "2026-10-29 10:00:00", "type": "Database", "message": "DB Deadlock", "severity": "Critical"},
                {"timestamp": "2026-10-29 10:01:00", "type": "Database", "message": "DB Deadlock", "severity": "Critical"},
                {"timestamp": "2026-10-29 10:02:00", "type": "Network", "message": "DNS Fail", "severity": "Warning"},
            ]
        }
        self.client.post("/api/logs", data=json.dumps(payload), headers=headers)

        res = self.client.get("/api/analytics")
        self.assertEqual(res.status_code, 200)
        analytics = res.get_json()["analytics"]
        self.assertEqual(analytics["total_errors"], 3)
        self.assertEqual(analytics["unique_categories"], 2)
        self.assertEqual(analytics["critical_count"], 2)
        self.assertEqual(analytics["warning_count"], 1)

        # Recurring errors: "DB Deadlock" should have count 2
        recurring = analytics["recurring_errors"]
        self.assertTrue(len(recurring) > 0)
        top = recurring[0]
        self.assertEqual(top["message"], "DB Deadlock")
        self.assertEqual(top["count"], 2)

    # 11. API-key authentication
    def test_11_api_key_authentication(self):
        payload = {"errors": [{"message": "Test Auth", "severity": "Error"}]}

        # Missing API Key
        res_no_key = self.client.post("/api/logs", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res_no_key.status_code, 401)

        # Invalid API Key
        res_bad_key = self.client.post(
            "/api/logs",
            data=json.dumps(payload),
            headers={"X-API-Key": "wrong-key-9999", "Content-Type": "application/json"}
        )
        self.assertEqual(res_bad_key.status_code, 401)

        # Valid API Key
        res_ok_key = self.client.post(
            "/api/logs",
            data=json.dumps(payload),
            headers={"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        )
        self.assertEqual(res_ok_key.status_code, 201)

    # 12. Duplicate submission handling
    def test_12_duplicate_submission_handling(self):
        headers = {"X-API-Key": self.config.API_KEY, "Content-Type": "application/json"}
        record = {
            "id": "DUP-1",
            "timestamp": "2026-10-29 11:00:00",
            "message": "Unique test message for idempotency",
            "severity": "Warning"
        }
        payload = {"errors": [record]}

        # First post -> accepted
        res1 = self.client.post("/api/logs", data=json.dumps(payload), headers=headers)
        self.assertEqual(res1.status_code, 201)
        self.assertEqual(res1.get_json()["accepted"], 1)
        self.assertEqual(res1.get_json()["duplicates"], 0)

        # Second post with identical id, timestamp, message -> detected as duplicate
        res2 = self.client.post("/api/logs", data=json.dumps(payload), headers=headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.get_json()["accepted"], 0)
        self.assertEqual(res2.get_json()["duplicates"], 1)

        # Verify DB total is still 1
        history = self.client.get("/api/history").get_json()
        self.assertEqual(history["pagination"]["total_records"], 1)

    # 13. Integration between simulated Log Parser client and ErrorInsight
    def test_13_simulated_log_parser_client_integration(self):
        # Simulate exact behavior of sample_parser_client.py
        headers = {
            "X-API-Key": self.config.API_KEY,
            "Content-Type": "application/json",
            "X-Source-Project": "Simulated_LogParser"
        }
        client_batch = {
            "errors": [
                {
                    "id": "CLIENT-SIM-1",
                    "timestamp": "2026-10-29 11:30:00",
                    "type": "Database",
                    "message": "Simulated Parser Client: DB connection refused",
                    "severity": "Critical"
                },
                {
                    "id": "CLIENT-SIM-2",
                    "timestamp": "2026-10-29 11:31:00",
                    "type": "Network",
                    "message": "Simulated Parser Client: Gateway 504 Timeout",
                    "severity": "Warning"
                }
            ]
        }
        response = self.client.post("/api/logs", data=json.dumps(client_batch), headers=headers)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["accepted"], 2)

        # Check single record retrieval by ID
        history = self.client.get("/api/history?source=Simulated_LogParser").get_json()
        first_id = history["records"][0]["id"]
        detail_res = self.client.get(f"/api/errors/{first_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.get_json()
        self.assertIn("recommendation", detail_data)
        self.assertIn("possible_causes", detail_data["recommendation"])

    # 14. Database failures and appropriate HTTP responses
    def test_14_database_failures_and_http_responses(self):
        # Test 404 for non-existent record
        res_404 = self.client.get("/api/errors/999999")
        self.assertEqual(res_404.status_code, 404)

        # Test health check failure when DB file path is invalid or corrupted
        broken_db = SQLiteManager("/non_existent_directory_error_insight/test.db")
        health = broken_db.check_health()
        self.assertFalse(health["connected"])

    # 15. Health score calculation and explainability breakdown
    def test_15_health_score_calculation_and_explainability(self):

        from services.analytics_service import calculate_health_score

        # Zero data case
        zero_score = calculate_health_score(0, {}, {})
        self.assertFalse(zero_score["has_sufficient_data"])
        self.assertIsNone(zero_score["score"])
        self.assertEqual(zero_score["status"], "Insufficient Data")

        # Healthy case
        healthy_score = calculate_health_score(
            total_events=100,
            severity_counts={"Critical": 0, "Error": 1, "Warning": 2, "Info": 97},
            component_counts={"Application": 100}
        )
        self.assertTrue(healthy_score["has_sufficient_data"])
        self.assertGreaterEqual(healthy_score["score"], 85)
        self.assertIn("deductions", healthy_score)
        self.assertIn("formula", healthy_score)

        # Critical failure burst case
        critical_score = calculate_health_score(
            total_events=20,
            severity_counts={"Critical": 8, "Error": 10, "Warning": 2, "Info": 0},
            component_counts={"Database": 18, "Network": 2},
            anomalies_count=2
        )
        self.assertEqual(critical_score["status"], "Critical")
        self.assertLess(critical_score["score"], 50)

    # 16. Component health and evidence-based risk ranking
    def test_16_component_health_and_risk_ranking(self):
        from services.analytics_service import calculate_component_health

        sample_records = [
            {"category": "Database", "severity": "Critical", "message": "Deadlock on table users"},
            {"category": "Database", "severity": "Critical", "message": "Connection refused port 5432"},
            {"category": "Database", "severity": "Error", "message": "Query failed timeout"},
            {"category": "Network", "severity": "Warning", "message": "Socket slow"},
            {"category": "Application", "severity": "Info", "message": "User login session active"}
        ]
        recurring = [{"category": "Database", "count": 2, "message": "Deadlock on table users"}]
        components = calculate_component_health(sample_records, recurring)

        self.assertEqual(len(components), 3)
        # Database has 2 Criticals so it must be ranked first with Critical risk level
        top_comp = components[0]
        self.assertEqual(top_comp["component"], "Database")
        self.assertEqual(top_comp["risk_level"], "Critical")
        self.assertGreater(len(top_comp["evidence"]), 0)

    # 17. Anomaly detection (Volume Spikes & Bursts)
    def test_17_anomaly_detection(self):
        from services.analytics_service import detect_anomalies

        records = [
            {"timestamp": "2026-10-29 08:15:00", "severity": "Critical", "category": "Database"},
            {"timestamp": "2026-10-29 08:30:00", "severity": "Critical", "category": "Database"},
            {"timestamp": "2026-10-29 09:00:00", "severity": "Info", "category": "Application"},
        ]
        timeline = [
            {"time": "2026-10-29 06", "count": 1},
            {"time": "2026-10-29 07", "count": 1},
            {"time": "2026-10-29 08", "count": 25},  # Volume spike
            {"time": "2026-10-29 09", "count": 2},
        ]
        anomalies = detect_anomalies(records, timeline, {"Database": 2, "Application": 1})
        self.assertGreater(len(anomalies), 0)
        types = [a["type"] for a in anomalies]
        self.assertIn("Volume Spike", types)

    # 18. Historical comparison logic
    def test_18_historical_comparison(self):
        from services.analytics_service import compare_with_history

        current = [
            {"message": "New database connection error", "category": "Database"}
        ]
        history = [
            {"message": "Old warning socket timeout", "category": "Network"},
            {"message": "Old database slow query", "category": "Database"},
            {"message": "New database connection error", "category": "Database"}
        ]

        # Baseline comparison
        comp = compare_with_history(current, history)
        self.assertTrue(comp["has_baseline"])
        self.assertIn("New database connection error", comp["new_signatures"])
        self.assertIn("Old warning socket timeout", comp["resolved_signatures"])

        # No baseline comparison
        no_base = compare_with_history(current, [])
        self.assertFalse(no_base["has_baseline"])

    # 19. Health report generation endpoint
    def test_19_health_report_generation(self):
        # Seed some data first
        seed_data = {
            "errors": [
                {
                    "timestamp": "2026-10-29 10:00:00",
                    "type": "Database",
                    "message": "Connection pool full",
                    "severity": "Critical"
                }
            ]
        }
        self.client.post("/api/analyze", data=json.dumps(seed_data), content_type="application/json")

        # Test JSON format
        res_json = self.client.get("/api/report")
        self.assertEqual(res_json.status_code, 200)
        json_data = res_json.get_json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("report", json_data)
        self.assertIn("overall_health_score", json_data["report"])
        self.assertIn("markdown", json_data["report"])

        # Test Markdown download
        res_md = self.client.get("/api/report?format=markdown&download=1")
        self.assertEqual(res_md.status_code, 200)
        self.assertIn(b"# LogHealth", res_md.data)
        self.assertIn("attachment", res_md.headers.get("Content-Disposition", ""))

    # 20. Empty and malformed inputs handling
    def test_20_empty_and_malformed_inputs_handling(self):
        # Empty JSON array
        res_empty = self.client.post("/api/analyze", data=json.dumps([]), content_type="application/json")
        self.assertEqual(res_empty.status_code, 400)

        # Empty body
        res_none = self.client.post("/api/analyze", data="", content_type="application/json")
        self.assertEqual(res_none.status_code, 400)

        # Analytics endpoint with empty database produces neutral health score without crashing
        res_analytics = self.client.get("/api/analytics")
        self.assertEqual(res_analytics.status_code, 200)
        data = res_analytics.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIn("health_score", data["analytics"])


if __name__ == "__main__":
    unittest.main()

