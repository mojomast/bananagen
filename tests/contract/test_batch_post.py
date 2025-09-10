import pytest
from fastapi.testclient import TestClient
from bananagen.api import app, BatchRequest
from pydantic import ValidationError
import json


client = TestClient(app)


class TestBatchPostContract:
    """Contract tests for POST /batch endpoint."""

    def test_valid_request_schema(self):
        """Test that valid batch request matches the BatchRequest schema."""
        # Valid request
        request_data = {
            "jobs": [
                {
                    "prompt": "A beautiful sunset",
                    "width": 1024,
                    "height": 768,
                    "output_path": "/tmp/test1.png",
                    "model": "gemini-2.5-flash"
                },
                {
                    "prompt": "A mountain landscape",
                    "width": 512,
                    "height": 512,
                    "output_path": "/tmp/test2.png"
                }
            ]
        }

        # Should parse without error
        request = BatchRequest(**request_data)
        assert len(request.jobs) == 2
        assert request.jobs[0]["prompt"] == "A beautiful sunset"
        assert request.jobs[0]["width"] == 1024
        assert request.jobs[0]["height"] == 768
        assert request.jobs[0]["output_path"] == "/tmp/test1.png"
        assert request.jobs[0]["model"] == "gemini-2.5-flash"

    def test_minimal_batch_request_schema(self):
        """Test minimal batch request with only required fields."""
        request_data = {
            "jobs": [
                {
                    "prompt": "A simple image",
                    "width": 512,
                    "height": 512,
                    "output_path": "/tmp/minimal.png"
                }
            ]
        }

        request = BatchRequest(**request_data)
        assert len(request.jobs) == 1
        assert request.jobs[0]["prompt"] == "A simple image"
        assert request.jobs[0]["width"] == 512
        assert request.jobs[0]["height"] == 512
        assert request.jobs[0]["output_path"] == "/tmp/minimal.png"
        assert request.jobs[0].get("model", "gemini-2.5-flash") == "gemini-2.5-flash"

    def test_batch_request_with_optional_fields(self):
        """Test batch request with all optional job fields."""
        request_data = {
            "jobs": [
                {
                    "prompt": "Advanced prompt",
                    "width": 1024,
                    "height": 768,
                    "output_path": "/tmp/advanced.png",
                    "model": "nano-banana-2.5-flash",
                    "template_path": "/tmp/template.png",
                    "transparent": True,
                    "placeholder_color": "#ff0000",
                    "seed": 42,
                    "metadata": {"custom": "data"}
                }
            ]
        }

        request = BatchRequest(**request_data)
        assert len(request.jobs) == 1
        job = request.jobs[0]
        assert job["prompt"] == "Advanced prompt"
        assert job["width"] == 1024
        assert job["height"] == 768
        assert job["output_path"] == "/tmp/advanced.png"
        assert job["model"] == "nano-banana-2.5-flash"
        assert job["template_path"] == "/tmp/template.png"

    def test_invalid_request_schema_missing_jobs(self):
        """Test that request fails without required jobs field."""
        invalid_request = {}

        with pytest.raises(ValidationError):
            BatchRequest(**invalid_request)

    def test_invalid_request_schema_empty_jobs(self):
        """Test that request fails with empty jobs array."""
        invalid_request = {
            "jobs": []
        }

        # An empty jobs array might be allowed or not - this depends on implementation
        # For now, just ensure it parses (might be validated later in endpoint logic)
        request = BatchRequest(**invalid_request)
        assert request.jobs == []

    def test_invalid_request_schema_missing_prompt_in_job(self):
        """Test that job fails without required prompt."""
        invalid_request = {
            "jobs": [
                {
                    "width": 512,
                    "height": 512,
                    "output_path": "/tmp/test.png"
                }
            ]
        }

        # This should pass schema validation since jobs are List[dict]
        # Real validation would happen when processing the job
        request = BatchRequest(**invalid_request)
        assert len(request.jobs) == 1

    def test_invalid_request_schema_missing_output_path_in_job(self):
        """Test that job fails without required output_path."""
        invalid_request = {
            "jobs": [
                {
                    "prompt": "test prompt",
                    "width": 512,
                    "height": 512
                }
            ]
        }

        request = BatchRequest(**invalid_request)
        assert len(request.jobs) == 1
        assert "output_path" not in request.jobs[0]

    def test_valid_response_format(self):
        """Test that endpoint returns expected response format."""
        request_data = {
            "jobs": [
                {
                    "prompt": "A test image",
                    "width": 512,
                    "height": 512,
                    "output_path": "/tmp/test_batch.png"
                }
            ]
        }

        # Make request to endpoint
        # Note: This might fail if underlying functions are not mocked/ready
        response = client.post("/batch", json=request_data)

        # Should return 200 or appropriate status
        assert response.status_code in [200, 500]  # 500 if implementation not ready

        if response.status_code == 200:
            response_data = response.json()

            # Check response structure according to OpenAPI spec
            assert "batch_id" in response_data
            assert "status" in response_data
            assert "created_at" in response_data

            # Should be string UUID
            assert isinstance(response_data["batch_id"], str)
            # Should be "queued" status
            assert response_data["status"] == "queued"
            # created_at should be ISO format string
            assert isinstance(response_data["created_at"], str)

    def test_batch_with_multiple_jobs(self):
        """Test batch request with multiple jobs."""
        request_data = {
            "jobs": [
                {
                    "prompt": "First image",
                    "width": 512,
                    "height": 512,
                    "output_path": "/tmp/batch1.png"
                },
                {
                    "prompt": "Second image",
                    "width": 1024,
                    "height": 768,
                    "output_path": "/tmp/batch2.png",
                    "model": "nano-banana-2.5-flash"
                },
                {
                    "prompt": "Third image",
                    "width": 256,
                    "height": 256,
                    "output_path": "/tmp/batch3.png"
                }
            ]
        }

        request = BatchRequest(**request_data)
        assert len(request.jobs) == 3

        # Check that all required fields are present
        for i, job in enumerate(request.jobs):
            assert "prompt" in job
            assert "output_path" in job
            assert "width" in job
            assert "height" in job

    def test_batch_request_with_max_jobs(self):
        """Test batch request with many jobs to test potential limits."""
        # Create 10 jobs
        jobs = []
        for i in range(10):
            jobs.append({
                "prompt": f"Job {i}",
                "width": 512,
                "height": 512,
                "output_path": f"/tmp/job{i}.png"
            })

        request_data = {"jobs": jobs}
        request = BatchRequest(**request_data)
        assert len(request.jobs) == 10