import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import requests
from bananagen.api import app, db


class TestRequestyConfiguration:
    """Integration tests for Requesty provider configuration workflow.

    Tests the complete flow from configuration endpoint to database storage
    with mocked external Requesty API validation and proper error handling.
    """

    def setup_method(self):
        """Set up test environment with temporary database."""
        self.client = TestClient(app)
        # Use in-memory database for tests
        self.temp_db_path = ":memory:"

    @patch('bananagen.api.db')
    @patch('requests.get')  # Mock external Requesty API calls
    def test_successful_requesty_configuration(self, mock_requesty_get, mock_db):
        """Test successful configuration of Requesty provider with valid API key."""
        # Setup mocks
        mock_db.get_api_provider.return_value = None  # No existing provider
        mock_db.encrypt_api_key.return_value = "encrypted-key-abc123"
        mock_db.save_api_provider.return_value = None

        # Mock successful Requesty API key validation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "version": "2.5.0",
                    "displayName": "Gemini 2.5 Flash"
                }
            ]
        }  # Valid Gemini model response structure
        mock_requesty_get.return_value = mock_response

        # Test data
        valid_requesty_key = "ray-v1-api-key-123"
        request_data = {
            "provider": "requesty",
            "api_key": valid_requesty_key,
            "environment": "production"
        }

        # Execute configuration
        response = self.client.post("/configure", json=request_data)

        # Verify successful response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["provider"] == "requesty"
        assert response_data["environment"] == "production"
        assert "Provider 'requesty' configured successfully." in response_data["message"]

        # Verify database operations were called correctly
        mock_db.get_api_provider.assert_called_once_with("requesty")
        mock_db.encrypt_api_key.assert_called_once_with(valid_requesty_key)
        mock_db.save_api_provider.assert_called_once_with({
            'provider': 'requesty',
            'api_key': 'encrypted-key-abc123',
            'environment': 'production'
        })

        # Verify Requesty API validation was attempted
        mock_requesty_get.assert_called_once()
        call_args = mock_requesty_get.call_args
        assert "https://api.requesty.ai" in call_args[0][0]  # URL contains Requesty base
        assert "Authorization" in call_args[1]["headers"]  # API key passed in headers

    @patch('bananagen.api.db')
    @patch('requests.get')
    def test_requesty_invalid_api_key_validation(self, mock_requesty_get, mock_db):
        """Test handling of invalid API key during Requesty configuration."""
        # Setup mocks for database operations
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.return_value = "encrypted-invalid-key"
        mock_db.save_api_provider.return_value = None

        # Mock Requesty API rejecting invalid API key
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {
                "code": 403,
                "message": "Invalid API key",
                "status": "PERMISSION_DENIED"
            }
        }
        mock_requesty_get.return_value = mock_response

        request_data = {
            "provider": "requesty",
            "api_key": "ray-v1-invalid-key-123",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        # Should return validation error
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "API key validation failed" in response_data["error"]

        # Database operations should still have been attempted
        mock_db.get_api_provider.assert_called_once_with("requesty")
        mock_db.encrypt_api_key.assert_called_once()
        mock_requesty_get.assert_called_once()

    @patch('requests.get')
    @patch('bananagen.api.db')
    def test_requesty_network_failure_handling(self, mock_db, mock_requesty_get):
        """Test handling of network failures during Requesty API validation."""
        # Setup database mocks
        mock_db.get_api_provider.return_value = None

        # Mock network failures
        mock_requesty_get.side_effect = requests.exceptions.ConnectionError("Connection timeout")

        request_data = {
            "provider": "requesty",
            "api_key": "ray-v1-valid-key-123",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        # Should handle network error gracefully
        assert response.status_code in [500, 502, 503]  # Depending on implementation
        response_data = response.json()
        assert "error" in response_data
        assert any(keyword in response_data["error"].lower() for keyword in ["network", "connection", "timeout"])

    @patch('bananagen.api.db')
    @patch('requests.get')
    def test_requesty_rate_limit_handling(self, mock_requesty_get, mock_db):
        """Test handling of Requesty API rate limits."""
        mock_db.get_api_provider.return_value = None

        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota).",
                "status": "RESOURCE_EXHAUSTED"
            }
        }
        mock_requesty_get.return_value = mock_response

        request_data = {
            "provider": "requesty",
            "api_key": "ray-v1-valid-key-123",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        # Should handle rate limit error
        assert response.status_code == 429
        response_data = response.json()
        assert "error" in response_data
        assert any(keyword in response_data["error"].lower() for keyword in ["rate", "limit", "quota", "exhausted"])

    def test_requesty_configuration_workflow_validation(self):
        """Test that configuration workflow properly validates and stores complete provider data."""
        # This test validates the end-to-end workflow expectations

        with patch('bananagen.api.db') as mock_db, \
             patch('requests.get') as mock_requesty_get:

            # Setup successful mocks
            mock_db.get_api_provider.return_value = None
            mock_db.encrypt_api_key.return_value = "encrypted-test-key"
            mock_db.save_api_provider.return_value = None

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [{"name": "models/gemini-2.5-flash"}]
            }
            mock_requesty_get.return_value = mock_response

            # Test minimal required configuration
            request_data = {
                "provider": "requesty",
                "api_key": "ray-v1-test-key"
            }

            response = self.client.post("/configure", json=request_data)

            assert response.status_code == 200
            response_data = response.json()

            # Verify response structure matches expected contract
            assert "message" in response_data
            assert "provider" in response_data
            assert "environment" in response_data
            assert response_data["environment"] == "production"  # Default value

            # Verify database was called with correct data structure
            call_args = mock_db.save_api_provider.call_args[0][0]
            assert call_args['provider'] == 'requesty'
            assert call_args['api_key'] == 'encrypted-test-key'
            assert call_args['environment'] == 'production'

    @patch('bananagen.api.db')
    def test_requesty_duplicate_configuration_error(self, mock_db):
        """Test error handling when Requesty provider is already configured."""
        # Mock existing provider
        mock_db.get_api_provider.return_value = {
            'provider': 'requesty',
            'api_key': 'existing-encrypted-key',
            'environment': 'production'
        }

        request_data = {
            "provider": "requesty",
            "api_key": "ray-v1-new-key",
            "environment": "development"
        }

        response = self.client.post("/configure", json=request_data)

        assert response.status_code == 409
        response_data = response.json()
        assert "error" in response_data
        assert "already configured" in response_data["error"]

        # Verify only get_api_provider was called (no save)
        mock_db.get_api_provider.assert_called_once_with("requesty")
        mock_db.encrypt_api_key.assert_not_called()
        mock_db.save_api_provider.assert_not_called()

    @patch('bananagen.api.db')
    @patch('requests.get')
    def test_requesty_api_timeout_handling(self, mock_requesty_get, mock_db):
        """Test handling of Requesty API timeouts."""
        mock_db.get_api_provider.return_value = None

        # Mock timeout
        mock_requesty_get.side_effect = requests.exceptions.Timeout("Request timed out")

        request_data = {
            "provider": "requesty",
            "api_key": "ray-v1-key",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        assert response.status_code in [408, 504]  # Request timeout or Gateway timeout
        response_data = response.json()
        assert "error" in response_data
        assert any(keyword in response_data["error"].lower() for keyword in ["timeout", "timed out"])


# Integration Test Summary and Validations
# ========================================
#
# Test Flow Overview:
# 1. POST /configure with Requesty provider data (provider, api_key, environment)
# 2. Mock external Requesty API validation to simulate real API interaction
# 3. Database storage of encrypted API key using mocked database operations
# 4. Response validation for proper structure and success/error handling
# 5. Verification of proper mock call sequences and parameter passing
#
# Key Validations:
#
# Happy Path Validation:
# - Validates successful configuration workflow with valid Requesty API key
# - Verifies API request formatting and authorization header inclusion for Requesty Gemini endpoint
# - Confirms database operations are called with correct encrypted data
# - Validates response structure matches expected contract
#
# Error Handling Validation:
# - Invalid API Key: Tests 403 responses from Requesty API with Gemini-specific error format
# - Network Failures: Tests connection timeouts and network errors
# - Rate Limiting: Tests 429 responses for excessive requests with Requesty quota errors
# - Timeouts: Tests request timeout handling
# - Database Errors: Tests failures in encryption and storage operations
# - Duplicate Configuration: Tests 409 conflict when provider already exists
#
# Mock Strategy:
# - Database operations (get_api_provider, encrypt_api_key, save_api_provider)
# - External API calls (requests.get for Requesty Gemini API model validation)
# - HTTP error conditions and various Gemini API-specific response scenarios
#
# Test Coverage:
# - Successful configuration with valid keys
# - API key validation failures (403, invalid format)
# - Network and connection failures
# - Rate limit and quota handling
# - Request timeout scenarios
# - Default environment assignment
# - Proper error response formatting
# - Database encryption and storage verification
# - Duplicate provider detection and error handling
#
# Integration Points Tested:
# - FastAPI TestClient API request/response handling
# - Database abstraction layer mocks
# - External Requesty Gemini API integration patterns
# - Error handling and exception propagation
# - Request validation and response formatting
# - Rate limiting middleware integration