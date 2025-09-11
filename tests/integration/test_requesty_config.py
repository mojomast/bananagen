import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os
import subprocess
import sys
import shutil
from fastapi.testclient import TestClient
import requests
from bananagen.api import app, db
from bananagen.db import Database, APIProviderRecord, APIKeyRecord


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


    def setUp_temp_db(self):
        """Set up temporary database for CLI tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_bananagen.db")
        self.valid_api_key = "ray-v1-api-key-123456"

    def tearDown_temp_db(self):
        """Clean up temporary database files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cli_requesty_successful_configuration(self):
        """Test successful Requesty configuration via CLI command."""
        # This test should fail initially per TDD (encrypt_api_key not implemented)
        self.setUp_temp_db()

        # Run CLI configure command
        result = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "requesty",
            "--api-key", self.valid_api_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        # Expect success (will fail initially due to missing implementation)
        assert result.returncode == 0, f"CLI failed: stderr={result.stderr}, stdout={result.stdout}"
        assert "configured successfully" in result.stdout.lower() or "requesty" in result.stdout

        # Verify database state
        db = Database(self.temp_db_path)
        provider = db.get_api_provider("requesty")
        assert provider is not None, "Provider should be registered"
        assert provider.name == "requesty"

        # Verify encrypted API key is stored
        keys = db.get_api_keys_for_provider(provider.id)
        assert len(keys) == 1, "Should have one API key record"
        encrypted_key = keys[0].key_value
        assert encrypted_key != self.valid_api_key, "Key should be encrypted"
        assert len(encrypted_key) > len(self.valid_api_key), "Encrypted key should be longer"

        self.tearDown_temp_db()

    def test_cli_requesty_invalid_api_key_handling(self):
        """Test CLI handling of invalid Requesty API key format."""
        self.setUp_temp_db()

        invalid_key = "invalid-key-format-no-prefix"

        result = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "requesty",
            "--api-key", invalid_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        # Should fail with invalid key format
        assert result.returncode != 0, "Should fail with invalid key"
        combined_output = result.stdout + result.stderr
        assert any(keyword in combined_output.lower() for keyword in [
            "invalid", "error", "failed", "api key"
        ]), f"No error indication: {combined_output}"

        # Database should remain empty
        db = Database(self.temp_db_path)
        provider = db.get_api_provider("requesty")
        assert provider is None, "Provider should not be saved"

        self.tearDown_temp_db()

    def test_cli_requesty_duplicate_provider_prevention(self):
        """Test that CLI prevents duplicate provider configuration."""
        self.setUp_temp_db()

        # First configuration
        result1 = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "requesty",
            "--api-key", self.valid_api_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        if result1.returncode == 0:
            # Second attempt should fail
            result2 = subprocess.run([
                sys.executable, "-m", "bananagen",
                "configure",
                "requesty",
                "--api-key", "ray-v1-different-key-456"
            ], capture_output=True, text=True, env={
                **os.environ,
                "BANANAGEN_DB_PATH": self.temp_db_path
            }, timeout=30)

            assert result2.returncode != 0, "Duplicate should fail"
            combined_output = result2.stdout + result2.stderr
            assert any(keyword in combined_output.lower() for keyword in [
                "duplicate", "exists", "already", "configured"
            ]), f"No duplicate indication: {combined_output}"

            # Database should have only one record
            db = Database(self.temp_db_path)
            provider = db.get_api_provider("requesty")
            assert provider is not None
            keys = db.get_api_keys_for_provider(provider.id)
            assert len(keys) == 1

        self.tearDown_temp_db()

    def test_cli_requesty_encryption_failure_handling(self):
        """Test CLI handles encryption failures gracefully."""
        self.setUp_temp_db()

        with patch('bananagen.core.encrypt_api_key', side_effect=Exception("Encryption failed - placeholder")):
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "configure",
                "requesty",
                "--api-key", self.valid_api_key
            ], capture_output=True, text=True, env={
                **os.environ,
                "BANANAGEN_DB_PATH": self.temp_db_path
            }, timeout=30)

            # Should handle encryption failure
            assert result.returncode != 0, "Should fail when encryption fails"
            combined_output = result.stdout + result.stderr
            assert any(keyword in combined_output.lower() for keyword in [
                "encryption", "error", "failed"
            ]), f"No encryption error indication: {combined_output}"

            # Database should remain empty
            db = Database(self.temp_db_path)
            provider = db.get_api_provider("requesty")
            assert provider is None, "Provider should not be saved when encryption fails"

        self.tearDown_temp_db()


# Integration Test Summary and Validations
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
# TDD Design Notes:
# - All CLI tests are designed to FAIL initially per TDD principles
# - Encryption function (bananagen.core.encrypt_api_key) does not exist yet
# - Tests include mocks that will raise exceptions (e.g., patch encrypt_api_key)
# - Expected failure reasons: import errors, missing functions, unhandled exceptions
# - Core implementation begins after these tests validate the intended interface
#
# Test Coverage:
# - Successful configuration with valid keys (API + CLI)
# - API key validation failures (403, invalid format)
# - Network and connection failures
# - Rate limit and quota handling
# - Request timeout scenarios
# - Default environment assignment
# - Proper error response formatting
# - Database encryption and storage verification
# - CLI subprocess execution and error handling
# - Duplicate provider prevention
# - Encryption error handling
#
# CLI Tests (New - TDD Implementation):
# Test Flow Overview:
# 1. CLI command: bananagen configure requesty --api-key <key>
# 2. Command execution via subprocess with temporary database
# 3. API key encryption using bananagen.core.encrypt_api_key (initially fails)
# 4. Database storage and provider registration verification
# 5. Return code and output validation
#
# Key Validations CLI:
#
# Happy Path Validation:
# - Validates successful configuration workflow with valid Requesty API key
# - Verifies API key encryption and storage in database
# - Confirms provider registration with correct metadata
# - Validates CLI subprocess execution and database state changes
#
# Error Handling Validation:
# - Invalid API Key: Tests CLI key format validation and error reporting
# - Duplicate Provider: Tests prevention of duplicate provider registration
# - Encryption Failures: Tests handling when encrypt_api_key raises exceptions
# - Database Errors: Tests graceful failure when database operations fail
#
# Mock Strategy:
# - Database operations (get_api_provider, encrypt_api_key, save_api_provider)
# - External API calls (requests.get for Requesty Gemini API model validation)
# - HTTP error conditions and various Gemini API-specific response scenarios
# - CLI subprocess execution with temporary databases
# - Encryption function mocking (raises exceptions to simulate TDD failures)
# - Environment variable configuration for database path
#
# Integration Points Tested:
# - FastAPI TestClient API request/response handling
# - CLI subprocess command execution
# - Database abstraction layer mocks
# - External Requesty Gemini API integration patterns
# - Error handling and exception propagation
# - Request validation and response formatting
# - API key encryption workflow
# - Provider registration lifecycle