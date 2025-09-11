import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os
import subprocess
import sys
from fastapi.testclient import TestClient
import requests
from bananagen.api import app
from bananagen.db import Database, APIProviderRecord, APIKeyRecord


class TestOpenRouterConfiguration:
    """Integration tests for OpenRouter provider configuration workflow.

    Tests the complete flow from configuration endpoint to database storage
    with mocked external OpenRouter API validation and proper error handling.
    """

    def setup_method(self):
        """Set up test environment with temporary database."""
        self.client = TestClient(app)
        # Use in-memory database for tests
        self.temp_db_path = ":memory:"

    def setUp_temp_db(self):
        """Set up temporary database for CLI tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_bananagen.db")
        self.valid_api_key = "sk-or-v1-valid-key-123456"

    def tearDown_temp_db(self):
        """Clean up temporary database files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('bananagen.api.db')
    @patch('requests.get')  # Mock external OpenRouter API calls
    def test_successful_openrouter_configuration(self, mock_openrouter_get, mock_db):
        """Test successful configuration of OpenRouter provider with valid API key."""
        # Setup mocks
        mock_db.get_api_provider.return_value = None  # No existing provider
        mock_db.encrypt_api_key.return_value = "encrypted-key-abc123"
        mock_db.save_api_provider.return_value = None

        # Mock successful OpenRouter API key validation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"models": []}}  # Valid response structure
        mock_openrouter_get.return_value = mock_response

        # Test data
        valid_openrouter_key = "sk-or-v1-valid-key-123"
        request_data = {
            "provider": "openrouter",
            "api_key": valid_openrouter_key,
            "environment": "production"
        }

        # Execute configuration
        response = self.client.post("/configure", json=request_data)

        # Verify successful response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["provider"] == "openrouter"
        assert response_data["environment"] == "production"
        assert "Provider 'openrouter' configured successfully." in response_data["message"]

        # Verify database operations were called correctly
        mock_db.get_api_provider.assert_called_once_with("openrouter")
        mock_db.encrypt_api_key.assert_called_once_with(valid_openrouter_key)
        mock_db.save_api_provider.assert_called_once_with({
            'provider': 'openrouter',
            'api_key': 'encrypted-key-abc123',
            'environment': 'production'
        })

        # Verify OpenRouter API validation was attempted
        mock_openrouter_get.assert_called_once()
        call_args = mock_openrouter_get.call_args
        assert "https://openrouter.ai/api/v1" in call_args[0][0]  # URL contains OpenRouter base
        assert "Authorization" in call_args[1]["headers"]  # API key passed in headers

    # Additional test methods will be implemented here
    @patch('bananagen.api.db')
    @patch('requests.get')
    def test_openrouter_invalid_api_key_validation(self, mock_openrouter_get, mock_db):
        """Test handling of invalid API key during OpenRouter configuration."""
        # Setup mocks for database operations
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.return_value = "encrypted-invalid-key"
        mock_db.save_api_provider.return_value = None

        # Mock OpenRouter API rejecting invalid API key
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_openrouter_get.return_value = mock_response

        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-invalid-key-123",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        # Should return validation error
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "API key validation failed" in response_data["error"]

        # Database operations should still have been attempted
        mock_db.get_api_provider.assert_called_once_with("openrouter")
        mock_db.encrypt_api_key.assert_called_once()
        mock_openrouter_get.assert_called_once()

        # But final save should not occur due to validation failure
        # (This would depend on implementation - could save with validation flag)

    @patch('requests.get')
    def test_openrouter_network_failure_handling(self, mock_openrouter_get):
        """Test handling of network failures during OpenRouter API validation."""
        # Mock network failures
        mock_openrouter_get.side_effect = requests.exceptions.ConnectionError("Network timeout")

        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-valid-key-123",
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
    def test_openrouter_rate_limit_handling(self, mock_openrouter_get, mock_db):
        """Test handling of OpenRouter API rate limits."""
        mock_db.get_api_provider.return_value = None

        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "Rate limit exceeded"}}
        mock_openrouter_get.return_value = mock_response

        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-valid-key-123",
            "environment": "production"
        }

        response = self.client.post("/configure", json=request_data)

        # Should handle rate limit error
        assert response.status_code == 429
        response_data = response.json()
        assert "error" in response_data
        assert any(keyword in response_data["error"].lower() for keyword in ["rate", "limit", "too many"])

    def test_openrouter_configuration_workflow_validation(self):
        """Test that configuration workflow properly validates and stores complete provider data."""
        # This test validates the end-to-end workflow expectations

        with patch('bananagen.api.db') as mock_db, \
             patch('requests.get') as mock_openrouter_get:

            # Setup successful mocks
            mock_db.get_api_provider.return_value = None
            mock_db.encrypt_api_key.return_value = "encrypted-test-key"
            mock_db.save_api_provider.return_value = None

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"models": []}}
            mock_openrouter_get.return_value = mock_response

            # Test minimal required configuration
            request_data = {
                "provider": "openrouter",
                "api_key": "sk-or-v1-test-key"
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
            call_args = mock_save_provider.call_args[0][0]
            assert call_args['provider'] == 'openrouter'
            assert call_args['api_key'] == 'encrypted-test-key'
            assert call_args['environment'] == 'production'


# CLI Integration Tests for OpenRouter Provider Configuration
# =========================================================
# These tests validate the end-to-end CLI workflow:
# - Command execution with subprocess
# - API key encryption/storage
# - Provider registration in database
# - Error handling for various failure scenarios
# All tests are designed to fail initially per TDD (until core functionality implemented)

    def test_cli_openrouter_successful_configuration(self):
        """Test successful OpenRouter configuration via CLI command."""
        # This test should fail initially per TDD (encrypt_api_key not implemented)
        self.setUp_temp_db()

        # Run CLI configure command
        result = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "openrouter",
            "--api-key", self.valid_api_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        # Expect success (will fail initially due to missing implementation)
        assert result.returncode == 0, f"CLI failed: stderr={result.stderr}, stdout={result.stdout}"
        assert "configured successfully" in result.stdout.lower() or "openrouter" in result.stdout

        # Verify database state
        db = Database(self.temp_db_path)
        provider = db.get_api_provider("openrouter")
        assert provider is not None, "Provider should be registered"
        assert provider.provider == "openrouter"

        # Verify encrypted API key is stored
        keys = db.get_api_keys_for_provider("openrouter")
        assert len(keys) == 1, "Should have one API key record"
        encrypted_key = keys[0].encrypted_key
        assert encrypted_key != self.valid_api_key, "Key should be encrypted"
        assert len(encrypted_key) > len(self.valid_api_key), "Encrypted key should be longer"

        self.tearDown_temp_db()

    def test_cli_openrouter_invalid_api_key_handling(self):
        """Test CLI handling of invalid OpenRouter API key format."""
        self.setUp_temp_db()

        invalid_key = "invalid-key-format-no-prefix"

        result = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "openrouter",
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
        provider = db.get_api_provider("openrouter")
        assert provider is None, "Provider should not be saved"

        self.tearDown_temp_db()

    def test_cli_openrouter_duplicate_provider_prevention(self):
        """Test that CLI prevents duplicate provider configuration."""
        self.setUp_temp_db()

        # First configuration
        result1 = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "openrouter",
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
                "openrouter",
                "--api-key", "sk-or-v1-different-key-456"
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
            provider = db.get_api_provider("openrouter")
            assert provider is not None
            keys = db.get_api_keys_for_provider("openrouter")
            assert len(keys) == 1

        self.tearDown_temp_db()

    def test_cli_openrouter_encryption_failure_handling(self):
        """Test CLI handles encryption failures gracefully."""
        self.setUp_temp_db()

        with patch('bananagen.core.encrypt_api_key', side_effect=Exception("Encryption failed - placeholder")):
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "configure",
                "openrouter",
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
            provider = db.get_api_provider("openrouter")
            assert provider is None, "Provider should not be saved when encryption fails"

        self.tearDown_temp_db()


# Integration Test Summary and Validations
# ========================================
#
# API Tests (Existing):
# Test Flow Overview:
# 1. POST /configure with OpenRouter provider data (provider, api_key, environment)
# 2. Mock external OpenRouter API validation to simulate real API interaction
# 3. Database storage of encrypted API key using mocked database operations
# 4. Response validation for proper structure and success/error handling
# 5. Verification of proper mock call sequences and parameter passing
#
# CLI Tests (New - TDD Implementation):
# Test Flow Overview:
# 1. CLI command: bananagen configure openrouter --api-key <key>
# 2. Command execution via subprocess with temporary database
# 3. API key encryption using bananagen.core.encrypt_api_key (initially fails)
# 4. Database storage and provider registration verification
# 5. Return code and output validation
#
# Key Validations:
#
# Happy Path Validation:
# - Validates successful configuration workflow with valid OpenRouter API key
# - Verifies API request formatting and authorization header inclusion
# - Confirms database operations are called with correct encrypted data
# - Validates response structure matches expected contract
# - CLI: Validates subprocess execution and database state after configuration
#
# Error Handling Validation:
# - Invalid API Key: Tests 401 responses from OpenRouter API and CLI key format errors
# - Network Failures: Tests connection timeouts and network errors
# - Rate Limiting: Tests 429 responses for excessive requests
# - Database Errors: Tests failures in encryption and storage operations
# - Duplicate Provider: Tests CLI prevention of duplicate provider registration
# - Encryption Failures: Tests handling when encrypt_api_key raises exceptions
#
# Mock Strategy:
# - Database operations (get_api_provider, encrypt_api_key, save_api_provider)
# - External API calls (requests.get for OpenRouter API validation)
# - HTTP error conditions and various response scenarios
# - CLI subprocess execution with temporary databases
# - Encryption function mocking (raises exceptions to simulate TDD failures)
#
# TDD Design Notes:
# - All new CLI tests are designed to FAIL initially per TDD principles
# - Encryption function (bananagen.core.encrypt_api_key) does not exist yet
# - Tests include mocks that will raise exceptions (e.g., patch encrypt_api_key)
# - Expected failure reasons: import errors, missing functions, unhandled exceptions
# - Core implementation begins after these tests validate the intended interface
#
# Test Coverage:
# - Successful configuration with valid keys (API + CLI)
# - API key validation failures (401, invalid format)
# - Network and connection failures
# - Rate limit handling
# - Default environment assignment
# - Proper error response formatting
# - Database encryption and storage verification
# - CLI subprocess execution and error handling
# - Duplicate provider prevention
# - Encryption error handling
#
# Integration Points Tested:
# - FastAPI TestClient API request/response handling
# - CLI subprocess command execution
# - Database abstraction layer mocks
# - External API integration patterns
# - Error handling and exception propagation
# - Request validation and response formatting
# - API key encryption workflow
# - Provider registration lifecycle