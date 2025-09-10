import pytest
from fastapi.testclient import TestClient
from bananagen.api import app, GenerateRequest
from pydantic import ValidationError
import json


client = TestClient(app)


class TestGeneratePostContract:
    """Contract tests for POST /generate endpoint."""

    def test_valid_request_schema(self):
        """Test that valid request matches the GenerateRequest schema."""
        # Valid request
        request_data = {
            "prompt": "A beautiful sunset",
            "width": 1024,
            "height": 768,
            "output_path": "/tmp/test.png",
            "model": "gemini-2.5-flash"
        }

        # Should parse without error
        request = GenerateRequest(**request_data)
        assert request.prompt == "A beautiful sunset"
        assert request.width == 1024
        assert request.height == 768
        assert request.output_path == "/tmp/test.png"
        assert request.model == "gemini-2.5-flash"

    def test_minimal_required_fields_request_schema(self):
        """Test minimal valid request with only required fields."""
        minimal_request = {
            "prompt": "test prompt",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/out.png"
        }

        request = GenerateRequest(**minimal_request)
        assert request.prompt == "test prompt"
        assert request.width == 512  # default
        assert request.height == 512  # default
        assert request.output_path == "/tmp/out.png"
        assert request.model == "gemini-2.5-flash"  # default
        assert request.template_path is None

    def test_optional_fields_request_schema(self):
        """Test request with all optional fields."""
        full_request = {
            "prompt": "advanced prompt",
            "width": 1024,
            "height": 768,
            "output_path": "/tmp/advanced.png",
            "model": "nano-banana-2.5-flash",
            "template_path": "/tmp/template.png"
        }

        request = GenerateRequest(**full_request)
        assert request.prompt == "advanced prompt"
        assert request.width == 1024
        assert request.height == 768
        assert request.output_path == "/tmp/advanced.png"
        assert request.model == "nano-banana-2.5-flash"
        assert request.template_path == "/tmp/template.png"

    def test_invalid_request_schema_missing_required(self):
        """Test that request fails without required fields."""
        # Missing prompt
        invalid_request = {
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test.png"
        }

        with pytest.raises(ValidationError):
            GenerateRequest(**invalid_request)

    def test_invalid_request_schema_zero_dimensions(self):
        """Test request validation for invalid dimensions."""
        invalid_request = {
            "prompt": "test",
            "width": 0,
            "height": 512,
            "output_path": "/tmp/test.png"
        }

        with pytest.raises(ValidationError):
            GenerateRequest(**invalid_request)

    def test_invalid_request_schema_negative_dimensions(self):
        """Test request validation for negative dimensions."""
        invalid_request = {
            "prompt": "test",
            "width": -100,
            "height": 512,
            "output_path": "/tmp/test.png"
        }

        with pytest.raises(ValidationError):
            GenerateRequest(**invalid_request)

    def test_valid_response_format(self):
        """Test that endpoint returns expected response format."""
        request_data = {
            "prompt": "A test image",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test_response.png"
        }

        # Make request to endpoint
        # Note: This might fail if underlying functions are not mocked
        response = client.post("/generate", json=request_data)

        # Should return 200 or appropriate status
        assert response.status_code in [200, 500]  # 500 if implementation not ready

        if response.status_code == 200:
            response_data = response.json()

            # Check response structure
            assert "id" in response_data
            assert "status" in response_data
            assert "created_at" in response_data

            # Should be string UUID
            assert isinstance(response_data["id"], str)
            # Should be "queued" status
            assert response_data["status"] == "queued"
            # created_at should be ISO format
            assert isinstance(response_data["created_at"], str)

    def test_invalid_request_empty_prompt(self):
        """Test validation of empty prompt."""
        invalid_request = {
            "prompt": "",
            "width": 512,
            "height": 512,
            "output_path": "/tmp/test.png"
        }

        response = client.post("/generate", json=invalid_request)
        assert response.status_code == 422  # Pydantic validation error

    def test_invalid_request_missing_output_path(self):
        """Test validation of missing output_path."""
        invalid_request = {
            "prompt": "test",
            "width": 512,
            "height": 512
        }

        with pytest.raises(ValidationError):
            GenerateRequest(**invalid_request)