import requests # Needed for exception handling and MockResponse
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
# Only importing the necessary constants and exception from the scraper module
from app.scraper import LOGIN_URL, URL_ACTUALIZA_VALORES, URL_OBTIENE_ESTADOS, ScraperError

# --- Mock Classes for HTTP Responses ---

class MockResponse:
    """Mock requests.Response object for simulating API responses."""
    def __init__(self, status_code, content: str = None, json_data: dict = None):
        self.status_code = status_code
        # Ensure content is always set, even if json_data is provided, for .text
        self.content = content
        self.json_data = json_data
        self.text = content if content is not None else str(json_data)
        
    def json(self):
        """Returns the JSON data if available."""
        if self.json_data is not None:
            return self.json_data
        # Use requests' own error for consistency in mocks
        raise requests.exceptions.JSONDecodeError("Mock response has no JSON data.")

    def raise_for_status(self):
        """Simulates raise_for_status behavior."""
        if self.status_code >= 400:
            # Raise requests' own error for consistency in mocks
            raise requests.exceptions.HTTPError(f"{self.status_code} error")
        return None

# --- Fixtures ---

# Use the official TestClient for FastAPI testing
# This is used globally by the tests in this file.
test_client = TestClient(app)

# --- Mock Handlers ---

def mock_successful_scrape(*args, **kwargs):
    """Mocks a successful login and data fetch sequence."""
    url = args[0]

    if url == LOGIN_URL:
        # 1. Successful login response (status 200, but content doesn't matter for the test)
        return MockResponse(200, content="Login Success HTML")
    
    elif url == URL_ACTUALIZA_VALORES:
        # 2. Mock successful actualizaValores
        mock_data = [
            ["1", "Ruta 01", "4.0", "-74.0", "img.png", "2025-10-01 10:00:00"]
        ]
        return MockResponse(200, json_data=mock_data)

    elif url == URL_OBTIENE_ESTADOS:
        # 3. Mock successful obtieneEstados (with the expected payload check, though we don't enforce it in the mock)
        mock_data = {"status_list": ["Active", "Inactive"]}
        return MockResponse(200, json_data=mock_data)

    return MockResponse(404, content="Not Found") # Default fallback

# --- Test Cases ---

def test_fetch_remote_data_success():
    """
    Test that the /fetch-remote-data endpoint calls the scraper and returns a successful response.
    """
    with patch('requests.Session.post', side_effect=mock_successful_scrape):
        response = test_client.post("/fetch-remote-data")
    
    assert response.status_code == 200
    data = response.json().get("data")
    
    assert "source" in data
    assert "valores_data" in data
    assert "estados_data" in data
    assert isinstance(data["valores_data"], list)
    assert isinstance(data["estados_data"], dict)


def test_fetch_remote_data_login_failure():
    """
    Test that a login failure (e.g., 401 response) results in a 503 error.
    """
    def mock_login_failure(*args, **kwargs):
        url = args[0]
        if url == LOGIN_URL:
            # Simulate unauthorized response during login (4xx error should raise an HTTPError)
            return MockResponse(401, content="Unauthorized")
        # Subsequent requests should not be reached if the login fails
        return MockResponse(200, json_data={})

    # Note: We patch 'requests.Session.post' because our scraper uses a session
    with patch('requests.Session.post', side_effect=mock_login_failure):
        response = test_client.post("/fetch-remote-data")
    
    # The endpoint catches the ScraperError (raised from HTTPError) and returns 503
    assert response.status_code == 503 # Service unavailable due to external scrape error
    assert "Login failed" in response.json()["detail"]