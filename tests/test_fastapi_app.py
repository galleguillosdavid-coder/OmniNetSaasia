"""
Tests for the FastAPI application (docs/Auditorias/3.md §245-285).
Verifies route preservation, Pydantic schema validation, and Zero NetLoss safety.
"""

import warnings
import unittest
from unittest.mock import patch, MagicMock

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastapi.testclient import TestClient

from netopt.fastapi_app import create_app
from main import get_dashboard_html


class TestFastAPIApp(unittest.TestCase):
    """Verifies FastAPI REST API endpoints and compatibility with OmniNet."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(dashboard_html_provider=get_dashboard_html)
        cls.client = TestClient(cls.app)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["version"], "2.9.6")
        self.assertEqual(data["service"], "OmniNet AI Agent Pro")

    def test_dashboard_html_endpoint(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<!DOCTYPE html>", resp.text)
        self.assertIn("OmniNet", resp.text)

    def test_system_status_endpoint(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["version"], "2.9.6")
        self.assertIn("platform", data)
        self.assertIn("admin_elevated", data)

    def test_subagents_list_endpoint(self):
        resp = self.client.get("/api/subagents")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 10)

    def test_chat_endpoint_valid_and_validation_error(self):
        # Valid chat request
        resp = self.client.post("/api/chat", json={
            "message": "Hola, ¿cómo optimizar mi conexión?",
            "history": [],
            "language_mode": "simple"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("reply", data)

        # Invalid chat request (empty message -> Pydantic 422 Unprocessable Entity)
        err_resp = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(err_resp.status_code, 422)

    def test_optimize_endpoint_dry_run_safety(self):
        resp = self.client.post("/api/optimize", json={"execute": False, "profile": "balanced"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["applied"])
        self.assertIn("plan_id", data)

    def test_subagent_run_endpoint_dry_run(self):
        resp = self.client.post("/api/subagents/run", json={"id": "redes", "execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("subagent"), "network")

    def test_payload_too_large_rejection(self):
        # Header indicating content > 1MB
        headers = {"content-length": str(1024 * 1024 + 10)}
        resp = self.client.post("/api/chat", json={"message": "test"}, headers=headers)
        self.assertEqual(resp.status_code, 413)


if __name__ == "__main__":
    unittest.main()
