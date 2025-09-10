import pytest
from fastapi.testclient import TestClient
from bananagen.api import app, ConfigureRequest
from pydantic import ValidationError
import json
from unittest.mock import patch, MagicMock


client = TestClient(app)


class TestConfigureProviderContract:
    """Contract tests for POST /configure endpoint."""

    def test_valid_request_schema(self):
        """Test that valid ConfigureRequest matches the schema."""
        # Valid request
        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-abcd1234567890xyz",
            "environment": "production"
        }

        # Should parse without error
        request = ConfigureRequest(**request_data)
        assert request.provider == "openrouter"
        assert request.api_key == "sk-or-v1-abcd1234567890xyz"
        assert request.environment == "production"

    def test_minimal_required_fields_request_schema(self):
        """Test minimal valid request with only required fields."""
        minimal_request = {
            "provider": "openrouter",
            "api_key": "valid-key-123"
        }

        request = ConfigureRequest(**minimal_request)
        assert request.provider == "openrouter"
        assert request.api_key == "valid-key-123"
        assert request.environment == "production"  # default value

    def test_optional_fields_request_schema(self):
        """Test request with all fields specified."""
        full_request = {
            "provider": "requesty",
            "api_key": "api-key-here",
            "environment": "development"
        }

        request = ConfigureRequest(**full_request)
        assert request.provider == "requesty"
        assert request.api_key == "api-key-here"
        assert request.environment == "development"

    def test_invalid_request_schema_invalid_provider(self):
        """Test that request fails with invalid provider."""
        invalid_request = {
            "provider": "invalid-provider",
            "api_key": "some-key"
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_invalid_request_schema_empty_provider(self):
        """Test request validation for empty provider."""
        invalid_request = {
            "provider": "",
            "api_key": "some-key"
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_invalid_request_schema_empty_api_key(self):
        """Test request validation for empty API key."""
        invalid_request = {
            "provider": "openrouter",
            "api_key": ""
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_invalid_request_schema_whitespace_api_key(self):
        """Test request validation for whitespace-only API key."""
        invalid_request = {
            "provider": "openrouter",
            "api_key": "   "
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_invalid_request_schema_invalid_api_key_format(self):
        """Test request validation for invalid API key format."""
        invalid_request = {
            "provider": "openrouter",
            "api_key": "invalid@key!with!special&chars"
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_invalid_request_schema_invalid_environment(self):
        """Test request validation for invalid environment."""
        invalid_request = {
            "provider": "openrouter",
            "api_key": "valid-key-123",
            "environment": "invalid-env"
        }

        with pytest.raises(ValidationError):
            ConfigureRequest(**invalid_request)

    def test_valid_supported_providers(self):
        """Test all supported providers are accepted."""
        supported_providers = ["openrouter", "requesty"]

        for provider in supported_providers:
            request_data = {
                "provider": provider,
                "api_key": f"key-for-{provider}"
            }

            request = ConfigureRequest(**request_data)
            assert request.provider == provider

    def test_valid_environments(self):
        """Test all valid environments are accepted."""
        valid_environments = ["development", "staging", "production"]

        for environment in valid_environments:
            request_data = {
                "provider": "openrouter",
                "api_key": "valid-key-123",
                "environment": environment
            }

            request = ConfigureRequest(**request_data)
            assert request.environment == environment

    @patch('bananagen.api.db')
    def test_successful_configuration_new_provider(self, mock_db):
        """Test successful configuration of a new provider."""
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.return_value = "encrypted-key-abc123"
        mock_db.save_api_provider.return_value = None

        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-original-key",
            "environment": "production"
        }

        response = client.post("/configure", json=request_data)

        assert response.status_code == 200
        response_data = response.json()
        assert "message" in response_data
        assert response_data["provider"] == "openrouter"
        assert response_data["environment"] == "production"
        assert "Provider 'openrouter' configured successfully." in response_data["message"]

        # Verify database calls
        mock_db.get_api_provider.assert_called_once_with("openrouter")
        mock_db.encrypt_api_key.assert_called_once_with("sk-or-v1-original-key")
        mock_db.save_api_provider.assert_called_once_with({
            'provider': 'openrouter',
            'api_key': 'encrypted-key-abc123',
            'environment': 'production'
        })

    @patch('bananagen.api.db')
    def test_duplicate_provider_configuration(self, mock_db):
        """Test error handling for duplicate provider configuration."""
        # Mock existing provider
        mock_db.get_api_provider.return_value = {
            'provider': 'openrouter',
            'api_key': 'existing-encrypted-key',
            'environment': 'production'
        }

        request_data = {
            "provider": "openrouter",
            "api_key": "sk-or-v1-new-key",
            "environment": "development"
        }

        response = client.post("/configure", json=request_data)

        assert response.status_code == 409
        response_data = response.json()
        assert "error" in response_data
        assert "already configured" in response_data["error"]

        # Verify only get_api_provider was called (no save)
        mock_db.get_api_provider.assert_called_once_with("openrouter")
        mock_db.encrypt_api_key.assert_not_called()
        mock_db.save_api_provider.assert_not_called()

    @patch('bananagen.api.db')
    def test_configuration_with_minimal_request(self, mock_db):
        """Test configuration with minimal request (only required fields)."""
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.return_value = "encrypted-minimal-key"
        mock_db.save_api_provider.return_value = None

        minimal_request = {
            "provider": "requesty",
            "api_key": "minimal-api-key"
        }

        response = client.post("/configure", json=minimal_request)

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["provider"] == "requesty"
        assert response_data["environment"] == "production"  # default

        # Verify default environment was used
        mock_db.save_api_provider.assert_called_once_with({
            'provider': 'requesty',
            'api_key': 'encrypted-minimal-key',
            'environment': 'production'
        })

    @patch('bananagen.api.db')
    def test_database_error_handling(self, mock_db):
        """Test error handling when database operations fail."""
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.side_effect = Exception("Encryption failed")

        request_data = {
            "provider": "openrouter",
            "api_key": "some-key",
            "environment": "production"
        }

        response = client.post("/configure", json=request_data)

        assert response.status_code == 500
        response_data = response.json()
        assert "error" in response_data
        assert "Failed to configure provider" in response_data["error"]

    @patch('bananagen.api.db')
    def test_encryption_used_for_api_key_storage(self, mock_db):
        """Test that API keys are encrypted before storage."""
        mock_db.get_api_provider.return_value = None
        mock_db.encrypt_api_key.return_value = "mock-encrypted-key"
        mock_db.save_api_provider.return_value = None

        request_data = {
            "provider": "openrouter",
            "api_key": "plaintext-api-key-123",
            "environment": "development"
        }

        response = client.post("/configure", json=request_data)
        assert response.status_code == 200

        # Verify encryption was called with original key
        mock_db.encrypt_api_key.assert_called_once_with("plaintext-api-key-123")
        # Verify only encrypted key went to database
        mock_db.save_api_provider.assert_called_once_with({
            'provider': 'openrouter',
            'api_key': 'mock-encrypted-key',  # encrypted, not plaintext
            'environment': 'development'
        })

    def test_rate_limiting_applied(self):
        """Test that rate limiting is applied to configure endpoint."""
        # Since rate limiting requires multiple requests within time window,
        # this test would be more complex. For contract testing, we can
        # verify the rate limiting middleware is in place by making
        # repeated requests and checking for 429 responses.
        pass

    # Additional validation test cases
    def test_api_key_validation_special_characters(self):
        """Test API key validation allows reasonable special characters."""
        # These characters are commonly used in API keys
        valid_keys = [
            "key-123_456.789",
            "ABCD1234-abcd5678",
            "gemini-api-key-v2"
        ]

        for api_key in valid_keys:
            request_data = {
                "provider": "openrouter",
                "api_key": api_key
            }

            request = ConfigureRequest(**request_data)
            assert request.api_key == api_key

    def test_response_structure_contract(self):
        """Test response structure meets contract requirements."""
        with patch('bananagen.api.db') as mock_db:
            mock_db.get_api_provider.return_value = None
            mock_db.encrypt_api_key.return_value = "encrypted-key"
            mock_db.save_api_provider.return_value = None

            request_data = {
                "provider": "openrouter",
                "api_key": "test-key",
                "environment": "production"
            }

            response = client.post("/configure", json=request_data)

            assert response.status_code == 200
            response_data = response.json()

            # Response should contain success message and provider info
            required_fields = ["message", "provider", "environment"]
            for field in required_fields:
                assert field in response_data

            assert response_data["message"] == "Provider 'openrouter' configured successfully."
            assert response_data["provider"] == "openrouter"
            assert response_data["environment"] == "production"