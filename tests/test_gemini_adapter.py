"""
Unit tests for bananagen.gemini_adapter module.

These tests MUST FAIL initially (TDD approach).
Tests include both mock mode and real API interface.
"""
import pytest
from pathlib import Path
import tempfile
import json
from unittest.mock import AsyncMock, patch

from bananagen.gemini_adapter import GeminiAdapter, GeminiResponse


class TestGeminiAdapter:
    """Test Gemini API adapter functionality."""
    
    @pytest.fixture
    def adapter(self):
        """Create GeminiAdapter instance for testing."""
        return GeminiAdapter(api_key="test_key", mock_mode=True)
    
    @pytest.fixture
    def real_adapter(self):
        """Create GeminiAdapter for real API testing (when not in mock mode)."""
        return GeminiAdapter(api_key="test_key", mock_mode=False)
    
    @pytest.mark.asyncio
    async def test_call_gemini_mock_mode(self, adapter):
        """Test Gemini call in mock mode returns fake response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.png"
            output_path = Path(tmpdir) / "output.png"
            
            # Create a dummy template file
            template_path.touch()
            
            response = await adapter.call_gemini(
                template_path=str(template_path),
                prompt="A beautiful sunset",
                output_path=str(output_path),
                model="gemini-2.5-flash"
            )
            
            # Verify mock response structure
            assert isinstance(response, GeminiResponse)
            assert response.success is True
            assert response.image_path == str(output_path)
            assert response.metadata is not None
            assert "prompt" in response.metadata
            assert "model" in response.metadata
            assert "mock" in response.metadata
            assert response.metadata["mock"] is True
            
            # Verify mock image file was created
            assert Path(output_path).exists()
    
    @pytest.mark.asyncio
    async def test_call_gemini_with_parameters(self, adapter):
        """Test Gemini call with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.png"
            output_path = Path(tmpdir) / "output.png"
            template_path.touch()
            
            params = {
                "temperature": 0.7,
                "max_output_tokens": 1024,
                "seed": 42
            }
            
            response = await adapter.call_gemini(
                template_path=str(template_path),
                prompt="Generate a cat image",
                output_path=str(output_path),
                params=params
            )
            
            assert response.success is True
            assert response.metadata["params"] == params
            assert response.metadata["seed"] == 42
    
    @pytest.mark.asyncio
    async def test_call_gemini_missing_template(self, adapter):
        """Test error handling when template file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "nonexistent.png"
            output_path = Path(tmpdir) / "output.png"
            
            response = await adapter.call_gemini(
                template_path=str(template_path),
                prompt="Test prompt",
                output_path=str(output_path)
            )
            
            assert response.success is False
            assert "error" in response.metadata
            assert "not found" in response.metadata["error"].lower()
    
    @pytest.mark.asyncio
    async def test_call_gemini_empty_prompt(self, adapter):
        """Test error handling for empty prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "template.png"
            output_path = Path(tmpdir) / "output.png"
            template_path.touch()
            
            response = await adapter.call_gemini(
                template_path=str(template_path),
                prompt="",  # Empty prompt
                output_path=str(output_path)
            )
            
            assert response.success is False
            assert "error" in response.metadata
            assert "prompt" in response.metadata["error"].lower()
    
    @pytest.mark.asyncio
    async def test_real_api_interface_structure(self, real_adapter):
        """Test that real API calls have proper structure (without making actual calls)."""
        # This tests the interface without making real API calls
        with patch('aiohttp.ClientSession.post') as mock_post:
            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Generated image data"}]
                        }
                    }
                ],
                "response_id": "test_response_123"
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with tempfile.TemporaryDirectory() as tmpdir:
                template_path = Path(tmpdir) / "template.png"
                output_path = Path(tmpdir) / "output.png"
                template_path.touch()
                
                response = await real_adapter.call_gemini(
                    template_path=str(template_path),
                    prompt="Test prompt",
                    output_path=str(output_path)
                )
                
                # Verify the API was called
                mock_post.assert_called_once()
                
                # Verify response structure
                assert hasattr(response, 'success')
                assert hasattr(response, 'image_path')
                assert hasattr(response, 'metadata')
    
    def test_gemini_response_dataclass(self):
        """Test GeminiResponse dataclass structure."""
        metadata = {
            "prompt": "test",
            "model": "gemini-2.5-flash",
            "timestamp": "2025-09-10T12:00:00Z"
        }
        
        response = GeminiResponse(
            success=True,
            image_path="/path/to/image.png",
            metadata=metadata
        )
        
        assert response.success is True
        assert response.image_path == "/path/to/image.png"
        assert response.metadata == metadata
        
        # Test JSON serialization
        response_dict = response.to_dict()
        assert "success" in response_dict
        assert "image_path" in response_dict
        assert "metadata" in response_dict
    
    def test_adapter_initialization(self):
        """Test GeminiAdapter initialization with different configurations."""
        # Mock mode
        adapter_mock = GeminiAdapter(api_key="test", mock_mode=True)
        assert adapter_mock.mock_mode is True
        assert adapter_mock.api_key == "test"
        
        # Real mode
        adapter_real = GeminiAdapter(api_key="real_key", mock_mode=False)
        assert adapter_real.mock_mode is False
        assert adapter_real.api_key == "real_key"
        
        # Default parameters
        adapter_default = GeminiAdapter(api_key="key")
        assert adapter_default.mock_mode is False  # Should default to False
