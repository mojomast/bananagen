import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import openai
from PIL import Image
from typing import Dict, Optional
from dotenv import load_dotenv

from bananagen.gemini_adapter import mock_generate

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class RequestyAdapter:
    """Adapter for accessing Gemini models through Requesty."""

    def __init__(self, base_url: str = None, api_key_encrypted: str = None, provider_details: Dict = None):
        # Get base URL from environment or use default
        self.base_url = base_url or os.getenv("REQUESTY_BASE_URL", "https://router.requesty.ai/v1")
        logger.info(f"RequestyAdapter initialized with base_url: {self.base_url}")
        self.api_key_encrypted = api_key_encrypted  # Keep for backward compatibility
        self.provider_details = provider_details or {}

    async def call_gemini(self, template_path: str, prompt: str, model: str = None, params: Dict = None) -> tuple[str, Dict]:
        """Call Gemini model via Requesty for image generation using OpenAI client format."""
        # Get model from environment, provider details, or use default
        if not model:
            model = os.getenv("REQUESTY_MODEL") or self.provider_details.get("model_name", "coding/gemini-2.5-flash")
        
        params = params or {}

        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file does not exist: {template_path}")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Try to get API key from environment first, then fall back to encrypted key
        api_key = os.getenv("REQUESTY_API_KEY")
        if not api_key and self.api_key_encrypted:
            # Only try to decrypt if we have an encrypted key and no env var
            try:
                from bananagen.core import decrypt_key
                api_key = decrypt_key(self.api_key_encrypted)
            except Exception as e:
                logger.warning(f"Failed to decrypt API key: {e}")
        
        if not api_key:
            logger.error("No API key found for Requesty. Set REQUESTY_API_KEY in .env file")
            raise ValueError("API key not found. Please set REQUESTY_API_KEY in your .env file")

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Load and encode template image
                with open(template_path, 'rb') as f:
                    image_data = f.read()
                image_b64 = base64.b64encode(image_data).decode('utf-8')

                # Create the message with image and prompt
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Generate an image based on this template and prompt: {prompt}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ]

                logger.info(f"Requesty API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "template_path": template_path,
                    "prompt_preview": prompt[:50] + '...' if len(prompt) > 50 else prompt,
                    "base_url": self.base_url,
                    "request_payload": {
                        "model": model,
                        "messages": messages,
                        "max_tokens": params.get("max_tokens", 1000),
                        "temperature": params.get("temperature", 0.7)
                    }
                })

                # Initialize OpenAI client with Requesty configuration
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=self.base_url,
                    default_headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
                        "X-Title": self.provider_details.get("app_name", "BananaGen")
                    }
                )

                # Make the API call
                response = client.chat.completions.create(
                    model=model,
                    messages=messages
                )

                # Check if the response is successful
                if not response.choices:
                    raise Exception("No response choices found.")

                # For now, since this is a chat API, we'll create a simple generated image
                # In a real implementation, you'd parse the response for image generation instructions
                response_content = response.choices[0].message.content
                
                logger.info("Requesty API response received", extra={
                    "model": model,
                    "response_id": getattr(response, 'id', 'unknown'),
                    "response_preview": response_content[:100] + '...' if response_content and len(response_content) > 100 else response_content,
                    "response_model": getattr(response, 'model', 'unknown'),
                    "usage": getattr(response, 'usage', {}),
                    "finish_reason": getattr(response.choices[0], 'finish_reason', 'unknown') if response.choices else 'unknown',
                    "full_response": {
                        "id": getattr(response, 'id', 'unknown'),
                        "object": getattr(response, 'object', 'unknown'),
                        "created": getattr(response, 'created', 'unknown'),
                        "model": getattr(response, 'model', 'unknown'),
                        "choices": [{
                            "index": getattr(choice, 'index', 0),
                            "message": {
                                "role": getattr(choice.message, 'role', 'unknown'),
                                "content": response_content
                            },
                            "finish_reason": getattr(choice, 'finish_reason', 'unknown')
                        } for choice in response.choices] if response.choices else [],
                        "usage": {
                            "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0) if hasattr(response, 'usage') and response.usage else 0,
                            "completion_tokens": getattr(response.usage, 'completion_tokens', 0) if hasattr(response, 'usage') and response.usage else 0,
                            "total_tokens": getattr(response.usage, 'total_tokens', 0) if hasattr(response, 'usage') and response.usage else 0
                        } if hasattr(response, 'usage') and response.usage else {}
                    }
                })

                # Generate output path
                output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))

                # For now, create a placeholder image with the response text
                # This is a temporary solution - in production you'd want actual image generation
                generated_image = self._create_placeholder_with_text(template_path, response_content, params)

                with open(output_path, 'wb') as f:
                    f.write(generated_image)

                sha256 = hashlib.sha256(generated_image).hexdigest()

                metadata = {
                    "prompt": prompt,
                    "model": model,
                    "seed": params.get("seed", 12345),
                    "params": params,
                    "requesty_response_id": getattr(response, 'id', 'unknown-id'),
                    "sha256": sha256,
                    "api_response": response_content
                }

                logger.info("Requesty image generation completed", extra={"output_path": output_path})
                return output_path, metadata

            except openai.OpenAIError as e:
                last_error = e
                logger.warning(f"OpenAI API error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "request_details": {
                        "model": model,
                        "messages_count": len(messages) if 'messages' in locals() else 0,
                        "has_image": any(msg.get('content', []) and 
                                       any(content.get('type') == 'image_url' for content in msg.get('content', [])) 
                                       for msg in messages) if 'messages' in locals() else False
                    }
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"OpenAI API error after {max_retries} attempts: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}", extra={
                    "error": str(e), 
                    "error_type": type(e).__name__, 
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "traceback": __import__('traceback').format_exc()
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise e

        # If we reach here, all retries failed
        logger.warning("All retries failed, falling back to mock generation", extra={"last_error": str(last_error)})
        return await mock_generate(template_path, prompt, params)

    def _create_placeholder_with_text(self, template_path: str, response_text: str, params: Dict) -> bytes:
        """Create a placeholder image with the API response text."""
        try:
            # Load template to get dimensions
            template = Image.open(template_path)
            width, height = template.size
        except Exception:
            # Fallback dimensions if template can't be loaded
            width = params.get('width', 512)
            height = params.get('height', 512)

        # Create a colored placeholder image
        img = Image.new('RGB', (width, height), (64, 128, 192))  # Blue background
        
        # For now, just return the image bytes
        # In a real implementation, you might overlay text on the image
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _parse_response_for_image(self, resp_json: Dict) -> bytes:
        """Parse Requesty response to extract generated image data."""
        # This method is kept for backward compatibility but may not be used
        # with the new OpenAI client approach
        
        # For images/generations endpoint, look for data array
        if 'data' in resp_json and resp_json['data']:
            image_data = resp_json['data'][0]
            
            # Check for base64 encoded image
            if 'b64_json' in image_data:
                return base64.b64decode(image_data['b64_json'])
            elif 'url' in image_data:
                # If it's a URL, we might need to download it
                url = image_data['url']
                if url.startswith('data:image/'):
                    _, encoded = url.split(',', 1)
                    return base64.b64decode(encoded)
                else:
                    # For now, return placeholder if it's a remote URL
                    logger.warning("Requesty returned remote image URL, using placeholder", extra={"url": url})
        
        # If no image found, create a placeholder
        logger.warning("No image data found in Requesty response, using placeholder")
        placeholder_text = "Generated via Requesty"
        img = Image.new('RGB', (256, 256), (128, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()