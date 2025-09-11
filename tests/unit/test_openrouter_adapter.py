import pytest
import asyncio
import base64
import io
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, AsyncMock
import aiohttp

from bananagen.adapters.openrouter_adapter import OpenRouterAdapter


@pytest.fixture
def temp_image():
    """Create a temporary image file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
        # Create a simple 1x1 RGBA image
        image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        f.write(image_data)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def adapter():
    """Create an OpenRouterAdapter instance."""
    return OpenRouterAdapter(
        base_url="https://openrouter.ai/api/v1",
        api_key_encrypted="encrypted_key_123",
        provider_details={"referer": "test.com", "app_name": "TestApp"}
    )


class TestOpenRouterAdapter:
    """Test OpenRouterAdapter class."""

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_success_with_image_url(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test successful call with image in response."""
        mock_decrypt_key.return_value = "fake_api_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "or-123",
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Here is your image"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}}
                        ]
                    }
                }
            ]
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('builtins.open', mock_open()), \
             patch('os.path.exists', return_value=True), \
             patch('bananagen.adapters.openrouter_adapter.hashlib.sha256') as mock_sha:

            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "abcd1234"
            mock_sha.return_value = mock_hash

            result_path, metadata = await adapter.call_gemini(
                template_path=temp_image,
                prompt="Generate a banana",
                model="google/gemini-1.5-flash"
            )

            assert result_path.endswith("_generated.png")
            assert metadata['model'] == "google/gemini-1.5-flash"
            assert metadata['prompt'] == "Generate a banana"
            assert metadata['openrouter_response_id'] == "or-123"
            assert metadata['sha256'] == "abcd1234"
            mock_decrypt_key.assert_called_once_with("encrypted_key_123")

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_success_with_base64_content(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test successful call with base64 image in content."""
        mock_decrypt_key.return_value = "fake_api_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 200
        # Mock base64 for a simple image
        base64_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        mock_response.json = AsyncMock(return_value={
            "id": "or-456",
            "choices": [
                {
                    "message": {
                        "content": base64_img  # Direct base64 string
                    }
                }
            ]
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('builtins.open', mock_open()), \
             patch('os.path.exists', return_value=True), \
             patch('bananagen.adapters.openrouter_adapter.hashlib.sha256') as mock_sha, \
             patch('bananagen.adapters.openrouter_adapter.base64.b64decode') as mock_b64decode:

            mock_b64decode.return_value = b"fake_image_data"
            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "efgh5678"
            mock_sha.return_value = mock_hash

            result_path, metadata = await adapter.call_gemini(
                template_path=temp_image,
                prompt="Test prompt",
                model="google/gemini-1.5-flash"
            )

            assert metadata['openrouter_response_id'] == "or-456"
            mock_b64decode.assert_called_once_with(base64_img)

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_authentication_failure(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test authentication failure."""
        mock_decrypt_key.return_value = "wrong_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Invalid API key")
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('os.path.exists', return_value=True):
            with pytest.raises(ValueError) as exc_info:
                await adapter.call_gemini(
                    template_path=temp_image,
                    prompt="Test"
                )

            assert "Authentication failed" in str(exc_info.value)

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_rate_limit(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test rate limit handling."""
        mock_decrypt_key.return_value = "fake_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.text = AsyncMock(return_value="Rate limit exceeded")
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('os.path.exists', return_value=True):
            with pytest.raises(Exception) as exc_info:
                with patch('asyncio.sleep'):  # Skip sleep for faster test
                    await adapter.call_gemini(
                        template_path=temp_image,
                        prompt="Test"
                    )

            assert "Rate limit exceeded" in str(exc_info.value)

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_api_error(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test API error handling."""
        mock_decrypt_key.return_value = "fake_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal server error")
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('os.path.exists', return_value=True):
            with pytest.raises(Exception) as exc_info:
                await adapter.call_gemini(
                    template_path=temp_image,
                    prompt="Test"
                )

            assert "API error 500" in str(exc_info.value)

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_no_api_key(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test when no API key is available."""
        mock_decrypt_key.return_value = None

        with patch('os.path.exists', return_value=True), \
             patch('os.getenv', return_value=None):
            with pytest.raises(ValueError) as exc_info:
                await adapter.call_gemini(
                    template_path=temp_image,
                    prompt="Test"
                )

            assert "API key not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_gemini_invalid_template_path(self, adapter):
        """Test invalid template path."""
        with pytest.raises(FileNotFoundError) as exc_info:
            await adapter.call_gemini(
                template_path="nonexistent.png",
                prompt="Test"
            )

        assert "Template file does not exist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_gemini_empty_prompt(self, adapter, temp_image):
        """Test empty prompt."""
        with patch('os.path.exists', return_value=True):
            with pytest.raises(ValueError) as exc_info:
                await adapter.call_gemini(
                    template_path=temp_image,
                    prompt=""
                )

            assert "Prompt cannot be empty" in str(exc_info.value)

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_fallback_to_placeholder(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test fallback to placeholder when no image in response."""
        mock_decrypt_key.return_value = "fake_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "or-fallback",
            "choices": [
                {
                    "message": {
                        "content": "No image generated"  # No image content
                    }
                }
            ]
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch('builtins.open', mock_open()), \
             patch('os.path.exists', return_value=True), \
             patch('bananagen.adapters.openrouter_adapter.hashlib.sha256') as mock_sha, \
             patch('bananagen.adapters.openrouter_adapter.Image') as mock_image_class:

            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "ijkl9999"
            mock_sha.return_value = mock_hash

            mock_image = MagicMock()
            mock_image_class.new.return_value = mock_image
            mock_img_instance = MagicMock()
            mock_img_instance.getvalue.return_value = b"placeholder_data"
            mock_img_instance.save.return_value = None
            mock_session_class.BytesIO.return_value = mock_img_instance

            result_path, metadata = await adapter.call_gemini(
                template_path=temp_image,
                prompt="Test"
            )

            assert metadata['openrouter_response_id'] == "or-fallback"
            # Verify fallback image creation
            mock_image_class.new.assert_called_once()

    @patch('bananagen.adapters.openrouter_adapter.decrypt_key')
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_call_gemini_with_params(self, mock_session_class, mock_decrypt_key, adapter, temp_image):
        """Test with additional parameters."""
        mock_decrypt_key.return_value = "fake_key"

        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "data:image/png;base64,iVBORw0KGgo="}}]
        })
        mock_session.post.return_value.__aenter__.return_value = mock_response

        params = {"seed": 42, "output_path": "/custom/path.png"}

        with patch('builtins.open', mock_open()), \
             patch('os.path.exists', return_value=True), \
             patch('bananagen.adapters.openrouter_adapter.hashlib.sha256') as mock_sha:

            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "mnop1234"
            mock_sha.return_value = mock_hash

            result_path, metadata = await adapter.call_gemini(
                template_path=temp_image,
                prompt="Test",
                params=params
            )

            assert metadata['seed'] == 42
            assert result_path == "/custom/path.png"  # Custom output path from params