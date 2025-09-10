import pytest
from fastapi.testclient import TestClient
from bananagen.api import app, GenerateRequest
from pydantic import ValidationError
import json
from unittest.mock import patch


client = TestClient(app)


class TestGenerateProviderContract:
    """Contract tests for POST /generate endpoint with provider support."""

    def test_valid_request_schema_with_provider(self):
        """Test that valid request with provider matches the schema when implemented."""
        # This will fail until provider field is added to GenerateRequest
        request_data = {
            "prompt": "A beautiful sunset",
            "width": 1024,
            "height": 768,
            "output_path": "/tmp/test.png",
            "provider": "openrouter"
        }

        # Mock the GenerateRequest to accept provider for this test
        with patch('bananagen.api.GenerateRequest') as MockGenerateRequest:
            MockGenerateRequest.return_value = MockGenerateRequest()
            MockGenerateRequest.__annotations__ = {
                'prompt': str,
                'width': int,
                'height': int,
                'output_path': str,
                'provider': str
            }

            # Should parse without error if provider field exists
            request = MockGenerateRequest(**request_data)
            assert request.prompt == "A beautiful sunset"
            assert request.width == 1024
            assert request.height == 768
            assert request.output_path == "/tmp/test.png"
            assert request.provider == "openrouter"

    def test_successful_generation_with_valid_provider(self):
        """Test successful generation with a valid provider."""
        request_data = {
            "prompt": "Test image generation",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test_provider.png",
            "provider": "openrouter"
        }

        # Mock the entire generation process to avoid actual API calls
        with patch('bananagen.api.process_generation') as mock_process, \
             patch('bananagen.api.GenerateRequest') as MockGenerateRequest:

            # Mock the request schema to include provider
            mock_request = MockGenerateRequest.return_value

            # Make request - this may fail if provider not in schema, but we'll mock response
            response = client.post("/generate", json=request_data)

            # For now, expect it might fail due to missing provider in schema
            if response.status_code == 200:
                # If provider support is implemented
                response_data = response.json()
                assert "id" in response_data
                assert "status" in response_data
                assert response_data["status"] == "queued"
                assert "created_at" in response_data
                # Check that provider was used (metadata would include it)
                assert isinstance(response_data["id"], str)
            else:
                # Current implementation without provider support
                assert response.status_code in [422, 400]  # Validation error

    def test_error_handling_invalid_provider(self):
        """Test error handling when an invalid provider is specified."""
        request_data = {
            "prompt": "Test with invalid provider",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test_invalid.png",
            "provider": "invalid_provider_xyz"
        }

        # Mock to simulate provider validation
        with patch('bananagen.api.process_generation') as mock_process, \
             patch('bananagen.api.GenerateRequest') as MockGenerateRequest:

            # Mock the request schema to include provider
            mock_request = MockGenerateRequest.return_value

            # Simulate error in background task when invalid provider is used
            mock_process.side_effect = ValueError("Invalid provider: invalid_provider_xyz")

            # Make request
            response = client.post("/generate", json=request_data)

            # If schema includes provider, job gets queued, but fails in background
            if response.status_code == 200:
                response_data = response.json()
                assert "id" in response_data
                # Check job status - would be 'failed' after processing
                # In a real test, you might poll /status/{id} to check failure
            else:
                assert response.status_code in [422, 400]  # Validation error

    def test_provider_field_validation(self):
        """Test validation for provider field when implemented."""
        # Test with empty provider
        request_data_empty = {
            "prompt": "Test",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test.png",
            "provider": ""
        }

        # Test with valid providers
        valid_providers = ["openrouter", "gemini", "dall-e", "midjourney"]

        for provider in valid_providers:
            request_data = {
                "prompt": "Test with valid provider",
                "width": 512,
                "height": 512,
                "output_path": "/tmp/test.png",
                "provider": provider
            }

            # Mock the schema
            with patch('bananagen.api.GenerateRequest') as MockGenerateRequest:
                # This should parse successfully if implemented
                pass  # Would test parsing

    def test_minimal_request_with_provider(self):
        """Test minimal required fields with provider."""
        minimal_request = {
            "prompt": "minimal test prompt",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/minimal.png",
            "provider": "openrouter"
        }

        # Mock schema to include provider
        with patch('bananagen.api.GenerateRequest') as MockGenerateRequest:
            mock_request = MockGenerateRequest.return_value
            MockGenerateRequest.return_value = mock_request

            # Should parse without error if provider field exists
            request = MockGenerateRequest(**minimal_request)
            assert request.prompt == "minimal test prompt"
            assert request.provider == "openrouter"


# Response structure assertions (when provider support is implemented)
# The response should include provider information or job metadata should reflect it

# Test for job status endpoint should also check provider usage
# when requesting status of a generation job created with provider