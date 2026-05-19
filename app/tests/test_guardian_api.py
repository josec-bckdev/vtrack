"""
Tests for guardian endpoints — now served under /monitor/guardian/*.

Kept as a separate file so the guardian-specific contract tests remain
distinct from the broader monitoring router tests in test_monitoring.py.
"""

import pytest
from unittest.mock import patch, AsyncMock


class TestGuardianStatusEndpoint:

    def test_guardian_status_returns_200(self, test_client):
        response = test_client.get("/monitor/guardian")
        assert response.status_code == 200

    def test_guardian_status_has_morning_slot(self, test_client):
        response = test_client.get("/monitor/guardian")
        assert "morning" in response.json()

    def test_guardian_status_has_afternoon_slot(self, test_client):
        response = test_client.get("/monitor/guardian")
        assert "afternoon" in response.json()

    def test_guardian_status_morning_has_task_running_field(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "task_running" in data["morning"]

    def test_guardian_status_afternoon_has_task_running_field(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "task_running" in data["afternoon"]

    def test_guardian_status_task_running_is_bool(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert isinstance(data["morning"]["task_running"], bool)
        assert isinstance(data["afternoon"]["task_running"], bool)

    def test_guardian_status_morning_has_last_outcome(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "last_outcome" in data["morning"]

    def test_guardian_status_morning_has_completed_at(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "completed_at" in data["morning"]


class TestGuardianActivateEndpoint:

    def test_activate_morning_slot_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            response = test_client.post("/monitor/guardian/activate?slot=morning")
        assert response.status_code == 200

    def test_activate_afternoon_slot_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            response = test_client.post("/monitor/guardian/activate?slot=afternoon")
        assert response.status_code == 200

    def test_activate_invalid_slot_returns_400(self, test_client):
        response = test_client.post("/monitor/guardian/activate?slot=midnight")
        assert response.status_code == 400

    def test_activate_missing_slot_returns_422(self, test_client):
        response = test_client.post("/monitor/guardian/activate")
        assert response.status_code == 422

    def test_activate_response_contains_slot_name(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            data = test_client.post("/monitor/guardian/activate?slot=morning").json()
        assert "slot" in data

    def test_activate_already_running_returns_409(self, test_client):
        with patch("app.main.scheduler.activate_guardian",
                   new_callable=AsyncMock,
                   side_effect=RuntimeError("morning guardian already active")):
            response = test_client.post("/monitor/guardian/activate?slot=morning")
        assert response.status_code == 409
