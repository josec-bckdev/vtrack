"""
Tests for the /monitor router.

The monitoring router consolidates all observability endpoints:
  GET  /monitor/health             — liveness probe
  GET  /monitor/status             — combined app snapshot
  GET  /monitor/guardian           — per-slot guardian state + outcome
  POST /monitor/guardian/activate  — trigger guardian for a slot
"""

import pytest
from unittest.mock import patch, AsyncMock


# =============================================================================
# /monitor/health
# =============================================================================

class TestMonitorHealth:

    def test_returns_200(self, test_client):
        response = test_client.get("/monitor/health")
        assert response.status_code == 200

    def test_returns_ok_status(self, test_client):
        response = test_client.get("/monitor/health")
        assert response.json()["status"] == "ok"


# =============================================================================
# /monitor/status
# =============================================================================

class TestMonitorStatus:

    def test_returns_200(self, test_client):
        response = test_client.get("/monitor/status")
        assert response.status_code == 200

    def test_has_collection_running_field(self, test_client):
        data = test_client.get("/monitor/status").json()
        assert "collection_running" in data

    def test_has_scheduler_running_field(self, test_client):
        data = test_client.get("/monitor/status").json()
        assert "scheduler_running" in data

    def test_has_guardian_field(self, test_client):
        data = test_client.get("/monitor/status").json()
        assert "guardian" in data

    def test_guardian_has_morning_and_afternoon(self, test_client):
        data = test_client.get("/monitor/status").json()
        assert "morning" in data["guardian"]
        assert "afternoon" in data["guardian"]


# =============================================================================
# /monitor/guardian
# =============================================================================

class TestMonitorGuardian:

    def test_returns_200(self, test_client):
        response = test_client.get("/monitor/guardian")
        assert response.status_code == 200

    def test_has_morning_and_afternoon_slots(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "morning" in data
        assert "afternoon" in data

    def test_morning_has_task_running(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "task_running" in data["morning"]

    def test_morning_has_last_outcome(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "last_outcome" in data["morning"]

    def test_morning_has_completed_at(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "completed_at" in data["morning"]

    def test_afternoon_has_last_outcome(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert "last_outcome" in data["afternoon"]

    def test_initial_last_outcome_is_none(self, test_client):
        data = test_client.get("/monitor/guardian").json()
        assert data["morning"]["last_outcome"] is None
        assert data["afternoon"]["last_outcome"] is None


# =============================================================================
# /monitor/guardian/activate
# =============================================================================

class TestMonitorGuardianActivate:

    def test_activate_morning_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            response = test_client.post("/monitor/guardian/activate?slot=morning")
        assert response.status_code == 200

    def test_activate_afternoon_returns_200(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            response = test_client.post("/monitor/guardian/activate?slot=afternoon")
        assert response.status_code == 200

    def test_activate_invalid_slot_returns_400(self, test_client):
        response = test_client.post("/monitor/guardian/activate?slot=midnight")
        assert response.status_code == 400

    def test_activate_missing_slot_returns_422(self, test_client):
        response = test_client.post("/monitor/guardian/activate")
        assert response.status_code == 422

    def test_activate_response_has_slot_field(self, test_client):
        with patch("app.main.scheduler.activate_guardian", new_callable=AsyncMock):
            data = test_client.post("/monitor/guardian/activate?slot=morning").json()
        assert "slot" in data

    def test_activate_already_running_returns_409(self, test_client):
        with patch("app.main.scheduler.activate_guardian",
                   new_callable=AsyncMock,
                   side_effect=RuntimeError("morning guardian already active")):
            response = test_client.post("/monitor/guardian/activate?slot=morning")
        assert response.status_code == 409


# =============================================================================
# /metrics  (Prometheus)
# =============================================================================

class TestPrometheusMetrics:

    def test_metrics_endpoint_returns_200(self, test_client):
        response = test_client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type_is_plaintext(self, test_client):
        response = test_client.get("/metrics")
        assert response.headers["content-type"].startswith("text/plain")

    def test_metrics_body_contains_prometheus_type_lines(self, test_client):
        response = test_client.get("/metrics")
        assert "# TYPE" in response.text

    def test_metrics_exposes_http_request_counter(self, test_client):
        test_client.get("/monitor/health")
        response = test_client.get("/metrics")
        assert "http_requests_total" in response.text
