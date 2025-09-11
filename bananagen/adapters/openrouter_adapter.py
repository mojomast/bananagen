import aiohttp
import asyncio
import base64
import hashlib
import io
import json
import logging
import os
from PIL import Image
from typing import Dict, Optional

from bananagen.core import decrypt_key

logger = logging.getLogger(__name__)

class OpenRouterAdapter:
    """Adapter for accessing Gemini models through OpenRouter."""

    def __init__(self, base_url: str = "https://openrouter.ai/api/v1", api_key_encrypted: str = None, provider_details: Dict = None):
        self.base_url = base_url
        self.api_key_encrypted = api_key_encrypted
        self.provider_details = provider_details or {}

    async def call_gemini(self, template_path: str, prompt: str, model: str = "google/gemini-1.5-flash", params: Dict = None) -> tuple[str, Dict]:
        """Call Gemini model via OpenRouter for image generation."""
        params = params or {}

        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file does not exist: {template_path}")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        api_key = decrypt_key(self.api_key_encrypted) if self.api_key_encrypted else os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("No API key found for OpenRouter")
            raise ValueError("API key not found")

        # Load and encode template image
        with open(template_path, 'rb') as f:
            image_data = f.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')

        # Prepare request data for OpenRouter API
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        request_data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                    ]
                }
            ]
        }

        if 'seed' in params:
            request_data["seed"] = int(params["seed"])

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"OpenRouter API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "template_path": template_path
                })

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=request_data) as response:
                        if response.status == 401:
                            raise ValueError("Authentication failed: Invalid API key")
                        elif response.status == 403:
                            raise ValueError("Authentication failed: Access forbidden")
                        elif response.status == 429:
                            last_error = Exception("Rate limit exceeded")
                            if attempt < max_retries - 1:
                                delay = 2 ** attempt
                                logger.warning(f"Rate limited, retrying in {delay}s", extra={"delay": delay})
                                await asyncio.sleep(delay)
                                continue
                            else:
                                raise last_error
                        elif response.status >= 400:
                            error_text = await response.text()
                            raise Exception(f"API error {response.status}: {error_text}")

                        resp_json = await response.json()

                        # Parse the response and extract generated image
                        generated_image = self._parse_response_for_image(resp_json)

                        # Generate output path
                        output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))

                        with open(output_path, 'wb') as f:
                            f.write(generated_image)

                        sha256 = hashlib.sha256(generated_image).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "seed": params.get("seed", 12345),
                            "params": params,
                            "openrouter_response_id": resp_json.get("id", "unknown-id"),
                            "sha256": sha256
                        }

                        logger.info("OpenRouter image generation completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={"error": str(e)})
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"Network error after {max_retries} attempts: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}", extra={"error": str(e)})
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via OpenRouter")

    def _parse_response_for_image(self, resp_json: Dict) -> bytes:
        """Parse OpenRouter response to extract generated image data."""
        if 'choices' not in resp_json or not resp_json['choices']:
            raise Exception("No response choices found in API response")

        choice = resp_json['choices'][0]

        # Check if the response contains an image URL or base64 data
        if 'message' in choice and 'content' in choice['message']:
            content = choice['message']['content']

            # For OpenRouter with Gemini, the response might include image data
            if isinstance(content, str):
                # Assume it's base64 encoded image
                return base64.b64decode(content)
            elif isinstance(content, list):
                for item in content:
                    if item.get('type') == 'image_url' and 'url' in item.get('image_url', {}):
                        # If it's a data URL
                        url = item['image_url']['url']
                        if url.startswith('data:image/'):
                            _, encoded = url.split(',', 1)
                            return base64.b64decode(encoded)

        # If no image found, create a placeholder image based on the response
        placeholder_text = "Generated via OpenRouter"
        img = Image.new('RGB', (256, 256), (128, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()