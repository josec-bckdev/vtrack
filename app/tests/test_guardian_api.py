"""
Tests for /guardian/status and /guardian/activate API endpoints.

These are integration tests that verify the guardian endpoints behave correctly
through the full FastAPI request/response cycle.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGuardianStatusEndpoint:

    def test_guardian_status_returns_200(self, test_client):
        response = test_client.get("/guardian/status")
        assert response.status_code == 200

    def test_guardian_status_has_morning_slot(self, test_client):
        response = test_client.get("/guardian/status")
        data = response.json()
        assert "morning" in data

    def test_guardian_status_has_afternoon_slot(self, test_client):
        response = test_client.get("/guardian/status")
        data = response.json()
        assert "afternoon" in data

    def test_guardian_status_morning_has_task_running_field(self, test_client):
        response = test_client.get("/guardian/status")
        data = response.json()
        assert "task_running" in data["morning"]

    def test_guardian_status_afternoon_has_task_running_field(self, test_client):
        response = test_client.get("/guardian/status")
        data = response.json()
        assert "task_running" in data["afternoon"]

    def test_guardian_status_task_running_is_bool(self, test_client):
        response = test_client.get("/guardian/status")
        data = response.json()
        assert isinstance(data["morning"]["task_running"], bool)
        assert isinstance(data["afternoon"]["task_running"], bool)


class TestGuardianActivateEndpoint:

    def test_activate_morning_slot_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock) as mock_activate:
            mock_activate.return_value = None
            response = test_client.post("/guardian/activate?slot=morning")
        assert response.status_code == 200

    def test_activate_afternoon_slot_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock) as mock_activate:
            mock_activate.return_value = None
            response = test_client.post("/guardian/activate?slot=afternoon")
        assert response.status_code == 200

    def test_activate_invalid_slot_returns_400(self, test_client):
        response = test_client.post("/guardian/activate?slot=midnight")
        assert response.status_code == 400

    def test_activate_missing_slot_returns_422(self, test_client):
        response = test_client.post("/guardian/activate")
        assert response.status_code == 422

    def test_activate_response_contains_slot_name(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            response = test_client.post("/guardian/activate?slot=morning")
        data = response.json()
        assert "slot" in data or "morning" in str(data)

    def test_activate_already_running_returns_409(self, test_client):
        with patch("app.main.scheduler.activate_guardian",
                   new_callable=AsyncMock,
                   side_effect=RuntimeError("morning guardian already active")):
            response = test_client.post("/guardian/activate?slot=morning")
        assert response.status_code == 409
