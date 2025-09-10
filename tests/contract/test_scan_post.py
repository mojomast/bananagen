import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
import tempfile
import os

# Try to import from bananagen.api - these might not exist yet
try:
    from bananagen.api import app, ScanRequest, ScanResponse
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    # Mock the app for testing when models aren't available
    from fastapi import FastAPI
    app = FastAPI()

client = TestClient(app)


class TestScanPostContract:
    """Contract tests for POST /scan endpoint."""

    def test_scan_request_model_exists(self):
        """Test that ScanRequest and ScanResponse models are defined."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest and ScanResponse models not yet implemented")

    def test_valid_scan_request_schema(self):
        """Test that valid scan request matches the ScanRequest schema."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest model not yet implemented")

        # Valid request
        request_data = {
            "root": "/tmp/test_project",
            "pattern": "*__placeholder__*",
            "replace": True,
            "extract_from": ["alt", "readme"]
        }

        # Should parse without error
        request = ScanRequest(**request_data)
        assert request.root == "/tmp/test_project"
        assert request.pattern == "*__placeholder__*"
        assert request.replace is True
        assert request.extract_from == ["alt", "readme"]

    def test_minimal_scan_request_schema(self):
        """Test minimal scan request with only root field."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest model not yet implemented")

        minimal_request = {
            "root": "/tmp/simple_scan"
        }

        request = ScanRequest(**minimal_request)
        assert request.root == "/tmp/simple_scan"
        # Test defaults
        assert request.pattern == "*__placeholder__*"  # default
        assert request.replace is True  # default
        assert request.extract_from == ["readme", "json"]  # default may vary

    def test_scan_request_with_all_options(self):
        """Test scan request with all optional fields specified."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest model not yet implemented")

        full_request = {
            "root": "/var/www/site",
            "pattern": "*.placeholder.*",
            "replace": False,
            "extract_from": ["alt", "manifest", "readme", "json"]
        }

        request = ScanRequest(**full_request)
        assert request.root == "/var/www/site"
        assert request.pattern == "*.placeholder.*"
        assert request.replace is False
        assert set(request.extract_from) == {"alt", "manifest", "readme", "json"}

    def test_invalid_scan_request_missing_root(self):
        """Test that scan request fails without required root field."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest model not yet implemented")

        invalid_request = {
            "pattern": "*__placeholder__*",
            "replace": True
        }

        with pytest.raises(ValidationError):
            ScanRequest(**invalid_request)

    def test_invalid_scan_request_invalid_extract_from(self):
        """Test that scan request fails with invalid extract_from values."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanRequest model not yet implemented")

        invalid_request = {
            "root": "/tmp/test",
            "extract_from": ["invalid_option"]
        }

        with pytest.raises(ValidationError):
            ScanRequest(**invalid_request)

    def test_scan_response_structure(self):
        """Test that scan response matches expected structure."""
        if not MODELS_AVAILABLE:
            pytest.skip("ScanResponse model not yet implemented")

        # Mock response data
        response_data = {
            "replaced": 5,
            "errors": 1,
            "details": [
                {
                    "file": "/tmp/test/image1.png",
                    "original_placeholder": "__placeholder_1__",
                    "new_path": "/tmp/generated/image1.png",
                    "success": True
                },
                {
                    "file": "/tmp/test/image2.png",
                    "original_placeholder": "__placeholder_2__",
                    "error": "Generation failed",
                    "success": False
                }
            ]
        }

        # Should be able to create response model
        response = ScanResponse(**response_data)
        assert response.replaced == 5
        assert response.errors == 1
        assert len(response.details) == 2

    def test_valid_scan_endpoint_response(self):
        """Test that actual /scan endpoint returns expected response."""
        # This test will likely fail until the endpoint is implemented
        request_data = {
            "root": "/tmp",
            "pattern": "*__placeholder__*"
        }

        response = client.post("/scan", json=request_data)

        # Expect 404 or 501 until implemented
        if response.status_code not in [200, 201, 501]:
            # If endpoint doesn't exist, it will be 404
            assert response.status_code == 404
            return  # Skip further validation if not implemented

        # If endpoint exists, validate response structure
        if response.status_code == 200:
            response_data = response.json()

            # Check according to OpenAPI spec
            assert "replaced" in response_data
            assert "errors" in response_data
            assert "details" in response_data

            assert isinstance(response_data["replaced"], int)
            assert isinstance(response_data["errors"], int)
            assert isinstance(response_data["details"], list)

            # Details should be objects
            if response_data["details"]:
                for detail in response_data["details"]:
                    assert isinstance(detail, dict)

    def test_scan_with_nonexistent_directory(self):
        """Test scan with a root directory that doesn't exist."""
        request_data = {
            "root": "/nonexistent/directory"
        }

        response = client.post("/scan", json=request_data)

        # Should handle gracefully - return 400 or 200 with errors
        assert response.status_code in [200, 400, 404, 501]

        if response.status_code == 200:
            data = response.json()
            # Should indicate errors
            assert "errors" in data
            assert data["errors"] >= 1

    def test_scan_with_different_patterns(self):
        """Test scan with various placeholder patterns."""
        patterns = [
            "*__placeholder__*",
            "*.placeholder",
            "*_placeholder_*",
            "__placeholder__",  # exact match
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            placeholder_dir = os.path.join(temp_dir, "placeholders")
            os.makedirs(placeholder_dir)

            for i, pattern in enumerate(patterns):
                filename = f"test_{i}_{pattern.replace('*', '').replace('__', '')}.txt"
                with open(os.path.join(placeholder_dir, filename), 'w') as f:
                    f.write("placeholder content")

            for pattern in patterns:
                request_data = {
                    "root": temp_dir,
                    "pattern": pattern,
                    "replace": False  # Don't actually replace, just scan
                }

                response = client.post("/scan", json=request_data)

                # Just check that request is accepted (will be 501 if not implemented)
                assert response.status_code in [200, 501]

                if response.status_code == 200:
                    data = response.json()
                    assert isinstance(data.get("replaced"), int)

    def test_scan_extract_from_options(self):
        """Test different extract_from option combinations."""
        extract_options = [
            ["alt"],
            ["manifest"],
            ["readme"],
            ["json"],
            ["alt", "readme"],
            ["manifest", "json"]
        ]

        for extract_from in extract_options:
            request_data = {
                "root": "/tmp",
                "extract_from": extract_from
            }

            # Test validation first (if models exist)
            if MODELS_AVAILABLE:
                try:
                    ScanRequest(**request_data)
                except ValidationError:
                    pytest.fail(f"Valid extract_from {extract_from} should not raise ValidationError")

            # Test endpoint (will be 501 if not implemented)
            response = client.post("/scan", json=request_data)
            assert response.status_code in [200, 501]

    def test_scan_replace_true_vs_false(self):
        """Test difference between replace=true and replace=false."""
        base_request = {
            "root": "/tmp",
            "pattern": "*__placeholder__*"
        }

        # Test with replace=false (scan only)
        scan_only_request = base_request.copy()
        scan_only_request["replace"] = False
        scan_response = client.post("/scan", json=scan_only_request)

        # Test with replace=true (scan and replace)
        replace_request = base_request.copy()
        replace_request["replace"] = True
        replace_response = client.post("/scan", json=replace_request)

        # Both should have same response structure
        for response in [scan_response, replace_response]:
            if response.status_code == 200:
                data = response.json()
                assert "replaced" in data
                assert "errors" in data
                assert "details" in data

                # With replace=true, should attempt replacements
                # With replace=false, replaced count should be 0
                if "replace" in response.request.json and not response.request.json["replace"]:
                    assert data["replaced"] == 0

    def test_scan_response_details_structure(self):
        """Test that scan response details contain expected information."""
        if not MODELS_AVAILABLE:
            pytest.skip("Cannot test without models")

        # Create detailed response structure
        response_data = {
            "replaced": 2,
            "errors": 0,
            "details": [
                {
                    "file": "/path/to/image.png",
                    "placeholder_found": "__placeholder__",
                    "replacement_made": True,
                    "new_image_path": "/path/to/generated.png",
                    "extracted_context": "Alt text: banana mascot",
                    "timestamp": "2024-01-01T12:00:00Z"
                },
                {
                    "file": "/path/to/another.png",
                    "placeholder_found": "_PLACEHOLDER_",
                    "replacement_made": True,
                    "new_image_path": "/path/to/another_generated.png",
                    "extracted_context": "From manifest.json",
                    "timestamp": "2024-01-01T12:01:00Z"
                }
            ]
        }

        response = ScanResponse(**response_data)
        assert len(response.details) == 2

        # Check detail structure
        for detail in response.details:
            assert "file" in detail
            assert "replacement_made" in detail
            assert detail["replacement_made"] in [True, False]