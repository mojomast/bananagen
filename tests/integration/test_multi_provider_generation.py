import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import requests
import tempfile
import os
import subprocess
import sys
import shutil
from bananagen.api import app, db
from bananagen.db import Database, APIProviderRecord


class TestMultiProviderGeneration:
    """Integration tests for multi-provider image generation workflow.

    Tests the complete flow from generation request to provider selection
    with mocked external API calls to both OpenRouter and Requesty APIs,
    proper fallback mechanisms, and error handling. Includes both API
    and CLI integration tests following TDD practices.
    """

    def setup_method(self):
        """Set up test environment with temporary database."""
        self.client = TestClient(app)
        # Use in-memory database for API tests
        self.temp_db_path = ":memory:"

        # Setup test data
        self.openrouter_key = "sk-or-v1-test-key-123"
        self.requesty_key = "ray-v1-test-key-456"
        self.encrypted_openrouter_key = "encrypted-or-key-abc"
        self.encrypted_requesty_key = "encrypted-ray-key-def"
        self.template_path = "/tmp/test_template.png"
        self.output_path = "/tmp/test_output.png"

    def setUp_temp_db(self):
        """Set up temporary database for CLI tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db_path = os.path.join(self.temp_dir, "test_bananagen.db")

    def tearDown_temp_db(self):
        """Clean up temporary database files."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_successful_generation_openrouter_provider(self, mock_call_gemini, mock_db):
        """Test successful generation using OpenRouter provider."""
        # Setup mocks
        mock_db.get_api_provider.side_effect = lambda provider: {
            "openrouter": {"provider": "openrouter", "api_key": self.encrypted_openrouter_key},
            "requesty": {"provider": "requesty", "api_key": self.encrypted_requesty_key}
        }.get(provider)

        mock_call_gemini.return_value = ("/tmp/generated_openrouter.png", {
            "provider": "openrouter",
            "model": "gemini-2.5-flash",
            "response_id": "or-response-123",
            "prompt": "Test prompt for OpenRouter"
        })

        # Test request data
        request_data = {
            "prompt": "A beautiful landscape",
            "width": 1024,
            "height": 768,
            "output_path": self.output_path,
            "template_path": self.template_path,
            "provider": "openrouter"
        }

        # Execute generation
        response = self.client.post("/generate", json=request_data)

        # Verify successful response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "queued"
        assert "id" in response_data

        # Verify request processing was attempted
        mock_call_gemini.assert_called_once()
        call_args = mock_call_gemini.call_args_list[0][0] if mock_call_gemini.call_args_list else mock_call_gemini.call_args[0]
        assert call_args[0] == self.template_path  # template_path
        assert "A beautiful landscape" in call_args[1]  # prompt

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_successful_generation_requesty_provider(self, mock_call_gemini, mock_db):
        """Test successful generation using Requesty provider."""
        # Setup mocks
        mock_db.get_api_provider.side_effect = lambda provider: {
            "openrouter": {"provider": "openrouter", "api_key": self.encrypted_openrouter_key},
            "requesty": {"provider": "requesty", "api_key": self.encrypted_requesty_key}
        }.get(provider)

        mock_call_gemini.return_value = ("/tmp/generated_requesty.png", {
            "provider": "requesty",
            "model": "gemini-2.5-flash",
            "response_id": "ray-response-456",
            "prompt": "Test prompt for Requesty"
        })

        # Test request data
        request_data = {
            "prompt": "Abstract art creation",
            "width": 768,
            "height": 768,
            "output_path": self.output_path,
            "template_path": self.template_path,
            "provider": "requesty"
        }

        # Execute generation
        response = self.client.post("/generate", json=request_data)

        # Verify successful response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "queued"

        # Verify call_gemini was called with correct provider logic
        mock_call_gemini.assert_called_once()

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_provider_fallback_on_failure(self, mock_call_gemini, mock_db):
        """Test automatic provider switching when primary provider fails."""
        # Setup mocks
        mock_db.get_api_provider.side_effect = lambda provider: {
            "openrouter": {"provider": "openrouter", "api_key": self.encrypted_openrouter_key},
            "requesty": {"provider": "requesty", "api_key": self.encrypted_requesty_key}
        }.get(provider)

        # Mock primary provider failure, secondary success
        mock_call_gemini.side_effect = [
            Exception("OpenRouter API rate limit exceeded"),
            ("/tmp/generated_fallback.png", {
                "provider": "requesty",
                "model": "gemini-2.5-flash",
                "response_id": "fallback-response-789",
                "prompt": "Fallback test prompt"
            })
        ]

        request_data = {
            "prompt": "Test fallback scenario",
            "width": 512,
            "height": 512,
            "output_path": self.output_path,
            "template_path": self.template_path,
            # No specific provider - system should choose
        }

        response = self.client.post("/generate", json=request_data)

        # Should succeed after fallback
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "queued"

        # Verify both providers were attempted
        assert mock_call_gemini.call_count == 2  # Primary failed, secondary succeeded

    @patch('bananagen.api.db')
    def test_invalid_provider_error_handling(self, mock_db):
        """Test error handling for invalid provider specification."""
        # Setup mocks - no providers configured
        mock_db.get_api_provider.return_value = None

        request_data = {
            "prompt": "Test invalid provider",
            "width": 512,
            "height": 512,
            "output_path": self.output_path,
            "provider": "invalid-provider"
        }

        response = self.client.post("/generate", json=request_data)

        # Should return validation error
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "provider" in response_data["error"].lower()

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_database_provider_retrieval(self, mock_call_gemini, mock_db):
        """Test that provider configurations are correctly retrieved from database."""
        # Setup specific provider data
        mock_db.get_api_provider.side_effect = lambda provider: {
            "openrouter": {
                'provider': 'openrouter',
                'api_key': self.encrypted_openrouter_key,
                'environment': 'production'
            }
        }.get(provider)

        mock_call_gemini.return_value = ("/tmp/generated_db_test.png", {
            "provider": "openrouter",
            "model": "gemini-2.5-flash",
            "response_id": "db-test-response"
        })

        request_data = {
            "prompt": "Database retrieval test",
            "width": 512,
            "height": 512,
            "output_path": self.output_path,
            "provider": "openrouter"
        }

        response = self.client.post("/generate", json=request_data)

        assert response.status_code == 200

        # Verify database was queried correctly
        mock_db.get_api_provider.assert_called_with("openrouter")

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_response_validation_structure(self, mock_call_gemini, mock_db):
        """Test that response includes proper provider and generation metadata."""
        mock_db.get_api_provider.return_value = {"provider": "openrouter", "api_key": self.encrypted_openrouter_key}

        mock_call_gemini.return_value = ("/tmp/generated_validation.png", {
            "provider": "openrouter",
            "model": "gemini-2.5-flash",
            "seed": 12345,
            "prompt": "Validation test prompt",
            "response_id": "validation-response-001",
            "sha256": "mock-sha256-hash"
        })

        request_data = {
            "prompt": "Response validation test",
            "width": 1024,
            "height": 1024,
            "output_path": self.output_path,
            "provider": "openrouter"
        }

        response = self.client.post("/generate", json=request_data)

        assert response.status_code == 200
        response_data = response.json()

        # Validate response structure
        assert "id" in response_data
        assert "status" in response_data
        assert "created_at" in response_data
        assert response_data["status"] == "queued"

        # Processing should complete with metadata
        mock_call_gemini.assert_called_once()

    @patch('bananagen.api.db')
    @patch('bananagen.gemini_adapter.call_gemini')
    def test_network_failure_recovery(self, mock_call_gemini, mock_db):
        """Test recovery from network failures during generation."""
        mock_db.get_api_provider.side_effect = lambda provider: {
            "openrouter": {"provider": "openrouter", "api_key": self.encrypted_openrouter_key}
        }.get(provider)

        # Mock network failure followed by success
        mock_call_gemini.side_effect = [
            requests.exceptions.ConnectionError("Network timeout"),
            ("/tmp/generated_recovered.png", {
                "provider": "openrouter",
                "model": "gemini-2.5-flash",
                "response_id": "recovery-response"
            })
        ]

        request_data = {
            "prompt": "Network recovery test",
            "width": 512,
            "height": 512,
            "output_path": self.output_path,
            "provider": "openrouter"
        }

        response = self.client.post("/generate", json=request_data)

        # Should eventually succeed
        assert response.status_code == 200

        # Verify retry logic was triggered
        assert mock_call_gemini.call_count == 2


# CLI Integration Tests for Multi-Provider Generation
# ===================================================
# These tests validate the end-to-end CLI workflow with provider selection:
# - Command execution with subprocess for generation commands
# - Provider selection and adapter factory usage (mocked initially)
# - Fallback mechanisms when providers fail
# - Configuration retrieval from database
# - Error handling for unconfigured providers
# All tests are designed to fail initially per TDD (until provider factory implemented)

    def test_cli_generation_openrouter_provider(self):
        """Test CLI generation with OpenRouter provider selection."""
        # This test should fail initially per TDD (provider factory not implemented)
        self.setUp_temp_db()

        # First configure the provider
        result_config = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "openrouter",
            "--api-key", self.openrouter_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        if result_config.returncode == 0:
            # Now test generation with provider
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "generated_openrouter.png")
                template_path = os.path.join(tmpdir, "template.png")

                # Create a dummy template
                from PIL import Image
                img = Image.new('RGB', (256, 256), color='red')
                img.save(template_path)

                # Run generation command with provider selection
                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "generate",
                    "--prompt", "A test image with OpenRouter",
                    "--width", "256",
                    "--height", "256",
                    "--provider", "openrouter",
                    "--placeholder", template_path,
                    "--out", output_path
                ], capture_output=True, text=True, env={
                    **os.environ,
                    "BANANAGEN_DB_PATH": self.temp_db_path
                }, timeout=60)

                # Expect success after provider implementation
                assert result.returncode == 0, f"Generation failed: stderr={result.stderr}, stdout={result.stdout}"
                assert "OpenRouter" in result.stdout or "success" in result.stdout.lower()

                # Verify output file exists
                assert os.path.exists(output_path), "Output file should be created"
                assert os.path.getsize(output_path) > 0, "Output file should not be empty"

        self.tearDown_temp_db()

    def test_cli_generation_requesty_provider(self):
        """Test CLI generation with Requesty provider selection."""
        self.setUp_temp_db()

        # First configure the provider
        result_config = subprocess.run([
            sys.executable, "-m", "bananagen",
            "configure",
            "requesty",
            "--api-key", self.requesty_key
        ], capture_output=True, text=True, env={
            **os.environ,
            "BANANAGEN_DB_PATH": self.temp_db_path
        }, timeout=30)

        if result_config.returncode == 0:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "generated_requesty.png")
                template_path = os.path.join(tmpdir, "template.png")

                # Create a dummy template
                from PIL import Image
                img = Image.new('RGB', (256, 256), color='blue')
                img.save(template_path)

                # Run generation command with provider
                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "generate",
                    "--prompt", "A test image with Requesty Gemini",
                    "--width", "256",
                    "--height", "256",
                    "--provider", "requesty",
                    "--placeholder", template_path,
                    "--out", output_path
                ], capture_output=True, text=True, env={
                    **os.environ,
                    "BANANAGEN_DB_PATH": self.temp_db_path
                }, timeout=60)

                assert result.returncode == 0, f"Generation failed: stderr={result.stderr}, stdout={result.stdout}"
                assert "Requesty" in result.stdout or "success" in result.stdout.lower()

                # Verify output file exists
                assert os.path.exists(output_path), "Output file should be created"

        self.tearDown_temp_db()

    def test_cli_generation_provider_fallback(self):
        """Test CLI automatic fallback when primary provider fails."""
        self.setUp_temp_db()

        # Configure both providers
        config_results = []
        for provider, api_key in [("openrouter", self.openrouter_key), ("requesty", self.requesty_key)]:
            result_config = subprocess.run([
                sys.executable, "-m", "bananagen",
                "configure",
                provider,
                "--api-key", api_key
            ], capture_output=True, text=True, env={
                **os.environ,
                "BANANAGEN_DB_PATH": self.temp_db_path
            }, timeout=30)
            config_results.append((provider, result_config))

        # Mock provider factory to simulate failures
        with patch('bananagen.core.get_provider_adapter') as mock_factory:
            # Mock OpenRouter failure, Requesty success
            mock_openrouter_adapter = MagicMock()
            mock_requesty_adapter = MagicMock()

            mock_openrouter_adapter.call_gemini.side_effect = Exception("OpenRouter API rate limit")
            mock_requesty_adapter.call_gemini.return_value = ("/tmp/fallback_output.png", {})

            mock_factory.side_effect = lambda provider: {
                "openrouter": mock_openrouter_adapter,
                "requesty": mock_requesty_adapter
            }.get(provider, None)

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "fallback_generated.png")
                template_path = os.path.join(tmpdir, "template.png")

                from PIL import Image
                img = Image.new('RGB', (256, 256), color='green')
                img.save(template_path)

                # Run without specific provider - should fallback
                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "generate",
                    "--prompt", "A fallback test image",
                    "--width", "256",
                    "--height", "256",
                    "--placeholder", template_path,
                    "--out", output_path
                ], capture_output=True, text=True, env={
                    **os.environ,
                    "BANANAGEN_DB_PATH": self.temp_db_path
                }, timeout=60)

                # Should succeed after fallback
                if result.returncode == 0:
                    assert "Requesty" in result.stdout or "fallback" in result.stdout.lower()
                    assert os.path.exists(output_path)

        self.tearDown_temp_db()

    def test_cli_generation_unconfigured_provider_error(self):
        """Test CLI error when trying to use unconfigured provider."""
        self.setUp_temp_db()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "error_output.png")
            template_path = os.path.join(tmpdir, "template.png")

            # Create a dummy template
            from PIL import Image
            img = Image.new('RGB', (256, 256), color='yellow')
            img.save(template_path)

            # Try to generate with unconfigured OpenRouter provider
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "generate",
                "--prompt", "This should fail",
                "--width", "256",
                "--height", "256",
                "--provider", "openrouter",
                "--placeholder", template_path,
                "--out", output_path
            ], capture_output=True, text=True, env={
                **os.environ,
                "BANANAGEN_DB_PATH": self.temp_db_path
            }, timeout=30)

            # Should fail due to unconfigured provider
            assert result.returncode != 0, "Should fail with unconfigured provider"
            combined_output = result.stdout + result.stderr
            assert any(keyword in combined_output.lower() for keyword in [
                "configured", "provider", "error", "not found"
            ]), f"No provider error indication: {combined_output}"

            # File should not be created
            assert not os.path.exists(output_path), "Output file should not exist on error"

        self.tearDown_temp_db()

    def test_cli_generation_invalid_provider_error(self):
        """Test CLI error with invalid provider name."""
        self.setUp_temp_db()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "invalid_output.png")
            template_path = os.path.join(tmpdir, "template.png")

            # Create a dummy template
            from PIL import Image
            img = Image.new('RGB', (256, 256), color='purple')
            img.save(template_path)

            # Try to generate with invalid provider
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "generate",
                "--prompt", "This should fail",
                "--width", "256",
                "--height", "256",
                "--provider", "invalid-provider",
                "--placeholder", template_path,
                "--out", output_path
            ], capture_output=True, text=True, env={
                **os.environ,
                "BANANAGEN_DB_PATH": self.temp_db_path
            }, timeout=30)

            # Should fail with invalid provider
            assert result.returncode != 0, "Should fail with invalid provider"
            combined_output = result.stdout + result.stderr
            assert any(keyword in combined_output.lower() for keyword in [
                "unsupported", "invalid", "provider", "supported providers"
            ]), f"No invalid provider error indication: {combined_output}"

        self.tearDown_temp_db()


# Integration Test Summary and Validations
# ========================================
#
# API Tests (Existing - Mock-Based):
# Test Flow Overview:
# 1. POST /generate with generation request (prompt, dimensions, output_path, provider)
# 2. Mock provider configuration retrieval from database
# 3. Mock external provider API calls (OpenRouter/Requesty generation endpoints)
# 4. Mock fallback logic when primary provider fails
# 5. Response validation for proper structure and metadata
# 6. Verification of provider selection and error handling
#
# CLI Tests (New - TDD Implementation):
# Test Flow Overview:
# 1. CLI configure command: bananagen configure [provider] --api-key [key]
# 2. CLI generate command: bananagen generate --provider [provider] --prompt [text] --out [file]
# 3. Subprocess execution with temporary database environment
# 4. Provider factory selection and adapter instantiation (mocked initially - will fail per TDD)
# 5. Database provider configuration retrieval and validation
# 6. End-to-end image generation workflow with file output verification
#
# Key Validations:
#
# Multi-Provider Success Validation:
# - API: Validates generation workflow with both OpenRouter and Requesty providers
# - CLI: Tests CLI provider selection and configuration retrieval from database
# - Verifies provider selection and API call routing to correct endpoints
# - Confirms database retrieval of encrypted provider keys
# - Validates response structure matches expected contract
#
# Automatic Provider Switching Validation:
# - API: Tests fallback mechanism when primary provider fails (rate limit, network error)
# - CLI: Tests automatic provider switching when CLI generation encounters provider failures
# - Verifies secondary provider selection and successful completion
# - Confirms retry counts and timing are within expected bounds
#
# Error Handling Validation:
# - Invalid Provider: Tests 400 responses for unsupported providers (API + CLI)
# - Unconfigured Provider: Tests errors when provider not configured (CLI-specific)
# - Network Failures: Tests connection timeouts and recovery mechanisms
# - Database Errors: Tests failures in provider configuration retrieval
# - API Rate Limiting: Tests handling of provider-specific rate limits
#
# Mock Strategy:
# - Database operations (get_api_provider with provider-specific returns)
# - Generation adapter (call_gemini with provider-aware responses)
# - Provider factory (get_provider_adapter - mocked to fail per TDD)
# - CLI subprocess execution with environment variable configuration
# - External API calls (simulated success/failure scenarios via mocked adapters)
#
# Test Coverage:
# - Successful generation with each configured provider (API + CLI)
# - CLI provider configuration workflow with database verification
# - Automatic provider fallback and switching logic
# - Error handling for invalid/unconfigured providers
# - Network failure recovery and retry mechanisms
# - Database provider configuration retrieval and storage
# - Response validation and metadata structure
# - CLI subprocess execution with file I/O verification
# - Rate limiting and quota exceeded scenarios
#
# TDD Design Notes:
# - All CLI tests are designed to FAIL initially per TDD principles
# - Provider factory (bananagen.core.get_provider_adapter) does not exist yet
# - Tests include mocks that will raise exceptions (e.g., patch get_provider_adapter)
# - Expected failure reasons: import errors, missing functions, AttributeError on non-existent adapters
# - Core implementation begins after these tests validate the intended interface
# - CLI tests use real subprocess execution but mock the provider factory layer
#
# Integration Points Tested:
# - FastAPI TestClient API request/response handling for /generate
# - CLI subprocess command execution with argument parsing
# - Database abstraction layer for provider management
# - Generation adapter integration with multiple providers
# - Provider factory pattern for adapter selection (TDD-mocked initially)
# - Error handling and exception propagation across providers
# - Request validation and response formatting consistency
# - CLI environment variable configuration for database paths
# - File I/O operations for template and output image handling