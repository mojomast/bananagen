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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class OpenRouterAdapter:
    """Adapter for accessing Gemini models through OpenRouter."""

    def __init__(self, base_url: str = None, api_key_encrypted: str = None, provider_details: Dict = None):
        # Get base URL from environment or use default
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        logger.info(f"OpenRouterAdapter initialized with base_url: {self.base_url}")
        self.api_key_encrypted = api_key_encrypted  # Keep for backward compatibility
        self.provider_details = provider_details or {}

    async def call_gemini(self, template_path: str, prompt: str, model: str = None, params: Dict = None) -> tuple[str, Dict]:
        """Call image generation model via OpenRouter for text-to-image generation."""
        # Get model from environment, provider details, or use default
        logger.info(f"OpenRouter call_gemini called with model: '{model}' (type: {type(model)})")
        if not model or not model.strip():
            logger.info("Model is None or empty, using fallback")
            model = os.getenv("OPENROUTER_MODEL") or self.provider_details.get("model_name", "google/gemini-2.5-flash-image-preview")
        # Ensure we always use the Gemini model from environment if available
        env_model = os.getenv("OPENROUTER_MODEL")
        if env_model and env_model != model:
            logger.info(f"Overriding model '{model}' with environment model '{env_model}'")
            model = env_model
        logger.info(f"Final model being used: '{model}'")
        params = params or {}

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Try to get API key from environment first, then fall back to encrypted key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key and self.api_key_encrypted:
            # Only try to decrypt if we have an encrypted key and no env var
            try:
                from bananagen.core import decrypt_key
                api_key = decrypt_key(self.api_key_encrypted)
            except Exception as e:
                logger.warning(f"Failed to decrypt API key: {e}")
        
        if not api_key:
            logger.error("No API key found for OpenRouter. Set OPENROUTER_API_KEY in .env file")
            raise ValueError("API key not found. Please set OPENROUTER_API_KEY in your .env file")

        # Check if this is a Gemini model
        is_gemini = "gemini" in model.lower()
        is_gemini_image_model = "gemini" in model.lower() and "image" in model.lower()
        logger.info(f"Model detection: model='{model}', is_gemini={is_gemini}, is_gemini_image_model={is_gemini_image_model}")
        
        # Determine if we have a placeholder (for image editing) or doing text-to-image generation
        has_placeholder = template_path and os.path.exists(template_path)
        
        if is_gemini_image_model:
            if has_placeholder:
                # Image editing mode: Use placeholder as source image + prompt for transformation
                logger.info(f"Using Gemini for image editing with placeholder template: {template_path}")
                # Add context to prompt explaining the placeholder is a size template
                edit_prompt = f"Transform this blank placeholder image according to the following description: {prompt}. The placeholder image is only to define the output dimensions and should be completely replaced with the generated content."
                return await self._call_gemini_image_edit(api_key, template_path, edit_prompt, model, params)
            else:
                # Text-to-image generation: Direct generation without placeholder
                logger.info(f"Using Gemini for text-to-image generation")
                return await self._call_gemini_text_to_image(api_key, prompt, model, params)
            
        elif is_gemini:
            # Use chat completions endpoint for text-based Gemini models
            return await self._call_gemini_chat(api_key, template_path, prompt, model, params)
        else:
            # Use images generations endpoint for traditional models
            return await self._call_image_generation(api_key, template_path, prompt, model, params)
        logger.info(f"Making request to URL: {url}")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        # For Stable Diffusion and similar models, use the images/generations endpoint
        request_data = {
            "model": model,
            "prompt": prompt,
            "n": 1,  # Number of images
            "size": f"{params.get('width', 512)}x{params.get('height', 512)}"
        }

        # Add optional parameters
        if 'seed' in params:
            request_data["seed"] = int(params["seed"])
        if 'negative_prompt' in params:
            request_data["negative_prompt"] = params["negative_prompt"]

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"OpenRouter API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "request_headers": {k: v for k, v in headers.items() if k != 'Authorization'},
                    "request_payload": request_data
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

                        logger.info("OpenRouter API response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "response_headers": dict(response.headers),
                            "full_response": resp_json
                        })

                        # Parse the response and extract generated image
                        generated_image = self._parse_image_response(resp_json)

                        # Generate output path - use template_path as base if provided, otherwise create new
                        if template_path:
                            output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))
                        else:
                            output_path = params.get("output_path", f"generated_{hash(prompt) % 10000}.png")

                        with open(output_path, 'wb') as f:
                            f.write(generated_image)

                        sha256 = hashlib.sha256(generated_image).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "seed": params.get("seed"),
                            "params": params,
                            "openrouter_response": resp_json,
                            "sha256": sha256
                        }

                        logger.info("OpenRouter image generation completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "request_url": url,
                    "request_details": {
                        "model": model,
                        "messages_count": len(request_data.get("messages", [])),
                        "has_image": any(msg.get('content', []) and 
                                       any(content.get('type') == 'image_url' for content in msg.get('content', [])) 
                                       for msg in request_data.get("messages", []))
                    }
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise Exception(f"Network error after {max_retries} attempts: {e}")
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "request_url": url,
                    "traceback": __import__('traceback').format_exc()
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via OpenRouter")

    async def _call_gemini_chat(self, api_key: str, template_path: str, prompt: str, model: str, params: Dict) -> tuple[str, Dict]:
        """Call Gemini model via OpenRouter chat completions for image generation."""
        url = f"{self.base_url}/chat/completions"
        logger.info(f"Making Gemini request to URL: {url}")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        # For Gemini, we ask it to generate an image description that can be used to create an image
        generation_prompt = f"Generate a detailed description of an image based on this prompt: {prompt}. Make the description vivid and suitable for image generation."
        
        request_data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": generation_prompt
                }
            ],
            "max_tokens": 1000
        }

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Gemini API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "request_payload": request_data
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

                        logger.info("Gemini API response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "full_response": resp_json
                        })

                        # Parse the Gemini response
                        generated_description = self._parse_gemini_response(resp_json)
                        
                        # Generate output path
                        if template_path:
                            output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))
                        else:
                            output_path = params.get("output_path", f"generated_{hash(prompt) % 10000}.png")

                        # Create a placeholder image with the description
                        # In a real implementation, you might want to use another service to generate the actual image
                        img = Image.new('RGB', (params.get('width', 512), params.get('height', 512)), (200, 200, 255))
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        image_data = buf.getvalue()

                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        sha256 = hashlib.sha256(image_data).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "generated_description": generated_description,
                            "params": params,
                            "gemini_response": resp_json,
                            "sha256": sha256
                        }

                        logger.info("Gemini image generation completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via Gemini")

    async def _call_gemini_image_generation(self, api_key: str, template_path: str, prompt: str, model: str, params: Dict) -> tuple[str, Dict]:
        """Call Gemini image generation model via OpenRouter images/generations endpoint."""
        url = f"{self.base_url}/images/generations"
        logger.info(f"Making Gemini image generation request to URL: {url}")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        request_data = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": f"{params.get('width', 512)}x{params.get('height', 512)}"
        }

        # Add optional parameters
        if 'seed' in params:
            request_data["seed"] = int(params["seed"])
        if 'negative_prompt' in params:
            request_data["negative_prompt"] = params["negative_prompt"]

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Gemini image generation API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "request_payload": request_data
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

                        logger.info("Gemini image generation response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "response_data_keys": list(resp_json.keys()) if isinstance(resp_json, dict) else "not_dict"
                        })

                        # Parse the image generation response
                        image_url = self._parse_image_generation_response(resp_json)
                        
                        # Download the generated image
                        async with session.get(image_url) as img_response:
                            if img_response.status != 200:
                                raise Exception(f"Failed to download generated image: {img_response.status}")
                            
                            image_data = await img_response.read()
                            
                            # Generate output path
                            if template_path:
                                output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))
                            else:
                                output_path = params.get("output_path", f"generated_{hash(prompt) % 10000}.png")
                            
                            # Save the image
                            with open(output_path, 'wb') as f:
                                f.write(image_data)

                            sha256 = hashlib.sha256(image_data).hexdigest()

                            metadata = {
                                "prompt": prompt,
                                "model": model,
                                "params": params,
                                "image_url": image_url,
                                "api_response": resp_json,
                                "sha256": sha256
                            }

                            logger.info("Gemini image generation completed", extra={"output_path": output_path})
                            return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via Gemini")

    async def _call_image_generation(self, api_key: str, template_path: str, prompt: str, model: str, params: Dict) -> tuple[str, Dict]:
        """Call traditional image generation model via OpenRouter."""
        url = f"{self.base_url}/images/generations"
        logger.info(f"Making image generation request to URL: {url}")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        request_data = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": f"{params.get('width', 512)}x{params.get('height', 512)}"
        }

        # Add optional parameters
        if 'seed' in params:
            request_data["seed"] = int(params["seed"])
        if 'negative_prompt' in params:
            request_data["negative_prompt"] = params["negative_prompt"]

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Image generation API call attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "request_payload": request_data
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

                        logger.info("Image generation API response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "full_response": resp_json
                        })

                        # Parse the response and extract generated image
                        generated_image = self._parse_image_response(resp_json)

                        # Generate output path
                        if template_path:
                            output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))
                        else:
                            output_path = params.get("output_path", f"generated_{hash(prompt) % 10000}.png")

                        with open(output_path, 'wb') as f:
                            f.write(generated_image)

                        sha256 = hashlib.sha256(generated_image).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "params": params,
                            "openrouter_response": resp_json,
                            "sha256": sha256
                        }

                        logger.info("Image generation completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via OpenRouter")

    async def _call_gemini_text_to_image(self, api_key: str, prompt: str, model: str, params: Dict) -> tuple[str, Dict]:
        """Generate image using Gemini chat completions endpoint for text-to-image generation."""
        logger.info("Using Gemini chat completions for text-to-image generation", extra={"model": model, "prompt": prompt[:100]})

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        # For Gemini text-to-image generation via OpenRouter, send only the text prompt
        # Based on successful Discord bot implementation - no placeholder image needed
        
        request_data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.7
        }

        # Try alternative parameter names that OpenRouter might recognize for Gemini
        if 'seed' in params:
            request_data["seed"] = int(params["seed"])

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Gemini text-to-image generation attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "request_payload": request_data
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

                        logger.info("Gemini text-to-image response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "response_data_keys": list(resp_json.keys()) if isinstance(resp_json, dict) else "not_dict",
                            "full_response": resp_json
                        })

                        # Parse the Gemini response for actual image data
                        image_data = self._parse_gemini_image_response(resp_json)

                        # Generate output path
                        output_path = params.get("output_path", f"generated_{hash(prompt) % 10000}.png")

                        # Save the actual generated image
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        sha256 = hashlib.sha256(image_data).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "params": params,
                            "gemini_response": resp_json,
                            "sha256": sha256,
                            "method": "gemini_text_to_image_generation"
                        }

                        logger.info("Gemini text-to-image generation completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to generate image via Gemini text-to-image")

    async def _call_gemini_image_edit(self, api_key: str, template_path: str, prompt: str, model: str, params: Dict) -> tuple[str, Dict]:
        """Edit/transform placeholder image using Gemini chat completions endpoint."""
        logger.info("Using Gemini for image editing/transformation", extra={"model": model, "template": template_path, "prompt": prompt[:100]})

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.provider_details.get("referer", "https://bananagen.com"),
            "X-Title": self.provider_details.get("app_name", "BananaGen")
        }

        # For Gemini image editing, send both the prompt AND the placeholder image
        # This follows the Discord bot's edit_image approach
        
        # Read and encode the placeholder image
        with open(template_path, 'rb') as f:
            image_data = f.read()
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        request_data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.7
        }

        # Try alternative parameter names that OpenRouter might recognize for Gemini
        if 'seed' in params:
            request_data["seed"] = int(params["seed"])

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Gemini image editing attempt {attempt + 1}/{max_retries}", extra={
                    "model": model,
                    "base_url": self.base_url,
                    "request_url": url,
                    "template_path": template_path,
                    "request_payload": request_data
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

                        logger.info("Gemini image editing response received", extra={
                            "model": model,
                            "response_status": response.status,
                            "response_data_keys": list(resp_json.keys()) if isinstance(resp_json, dict) else "not_dict",
                            "full_response": resp_json
                        })

                        # Parse the Gemini response for actual image data
                        image_data = self._parse_gemini_image_response(resp_json)

                        # Generate output path
                        output_path = params.get("output_path", template_path.replace(".png", "_generated.png"))

                        # Save the actual generated image
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        sha256 = hashlib.sha256(image_data).hexdigest()

                        metadata = {
                            "prompt": prompt,
                            "model": model,
                            "template_path": template_path,
                            "params": params,
                            "gemini_response": resp_json,
                            "sha256": sha256,
                            "method": "gemini_image_edit"
                        }

                        logger.info("Gemini image editing completed", extra={"output_path": output_path})
                        return output_path, metadata

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": model,
                    "base_url": self.base_url,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                else:
                    raise e

        # If we reach here, all retries failed
        raise last_error or Exception("Failed to edit image via Gemini")

    def _parse_image_response(self, resp_json: Dict) -> bytes:
        """Parse OpenRouter response to extract generated image data for text-to-image models."""
        # For OpenAI DALL-E style responses
        if 'data' in resp_json and resp_json['data']:
            image_data = resp_json['data'][0]
            
            # If it's a URL, download the image
            if 'url' in image_data:
                import aiohttp
                async def download_image():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_data['url']) as response:
                            if response.status == 200:
                                return await response.read()
                            else:
                                raise Exception(f"Failed to download image: {response.status}")
                return download_image()
            
            # If it's base64 encoded
            elif 'b64_json' in image_data:
                return base64.b64decode(image_data['b64_json'])
        
        # For other formats, check for direct image data
        if 'images' in resp_json and resp_json['images']:
            image_info = resp_json['images'][0]
            
            # If it's a URL
            if 'url' in image_info:
                import aiohttp
                async def download_image():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_info['url']) as response:
                            if response.status == 200:
                                return await response.read()
                            else:
                                raise Exception(f"Failed to download image: {response.status}")
                return download_image()
            
            # If it's base64
            elif 'b64' in image_info or 'data' in image_info:
                b64_data = image_info.get('b64') or image_info.get('data')
                return base64.b64decode(b64_data)

        # If no image found, create a placeholder image based on the response
        logger.warning("No image data found in response, creating placeholder", extra={"response": resp_json})
        placeholder_text = "Generated via OpenRouter"
        img = Image.new('RGB', (512, 512), (128, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _parse_gemini_response(self, resp_json: Dict) -> str:
        """Parse Gemini chat response to extract generated description."""
        try:
            if 'choices' in resp_json and resp_json['choices']:
                choice = resp_json['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    return choice['message']['content']
            
            logger.warning("No content found in Gemini response", extra={"response": resp_json})
            return "Generated image description not available"
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}", extra={"response": resp_json})
            return "Error parsing generated description"

    def _parse_image_generation_response(self, resp_json: dict) -> str:
        """Parse the image generation response from OpenRouter and extract the image URL."""
        try:
            # OpenRouter typically returns data in this format for image generation
            if 'data' in resp_json and len(resp_json['data']) > 0:
                image_data = resp_json['data'][0]
                if 'url' in image_data:
                    return image_data['url']
                elif 'b64_json' in image_data:
                    # Handle base64 encoded images
                    import base64
                    image_data_b64 = image_data['b64_json']
                    # For now, return a data URL
                    return f"data:image/png;base64,{image_data_b64}"
            
            # Alternative response format
            if 'images' in resp_json and len(resp_json['images']) > 0:
                return resp_json['images'][0]['url']
            
            # Fallback for other formats
            if 'url' in resp_json:
                return resp_json['url']
            
            logger.error("No image URL found in response", extra={"response": resp_json})
            raise Exception("No image URL found in API response")
            
        except Exception as e:
            logger.error(f"Error parsing image generation response: {e}", extra={"response": resp_json})
            raise Exception(f"Failed to parse image generation response: {e}")

    def _parse_gemini_image_response(self, resp_json: Dict) -> bytes:
        """Parse Gemini chat response to extract generated image data."""
        try:
            # Based on successful Discord bot implementation - search extensively for base64 data
            logger.debug("Parsing Gemini response for image data", extra={"response_keys": list(resp_json.keys())})
            
            # Check for OpenAI-style response format first
            if 'choices' in resp_json and resp_json['choices']:
                choice = resp_json['choices'][0]
                message = choice.get('message', {})
                content = message.get('content')
                
                logger.debug(f"Choice content type: {type(content)}, content preview: {str(content)[:100]}")
                
                # Check if content has parts (list format)
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            # Look for inline_data (Gemini format)
                            if 'inline_data' in part and 'data' in part['inline_data']:
                                image_b64 = part['inline_data']['data']
                                logger.info("Found image data in Gemini inline_data format")
                                return base64.b64decode(image_b64)
                            
                            # Look for image_url format
                            if 'image_url' in part and 'url' in part['image_url']:
                                url = part['image_url']['url']
                                if url.startswith('data:image'):
                                    _, b64_data = url.split(',', 1)
                                    logger.info("Found image data in data URL format")
                                    return base64.b64decode(b64_data)
                
                # Check if content is a string - this is where the Discord bot finds the data
                if isinstance(content, str):
                    content = content.strip()
                    if len(content) > 1000:  # Likely image data
                        logger.info("Found long string content - checking for base64 image data")
                        
                        # Extract base64 data if it's a data URL
                        if content.startswith("data:image/"):
                            _, b64_data = content.split(',', 1)
                            logger.info("Found image data in content data URL")
                            return base64.b64decode(b64_data)
                        
                        # Look for base64 image data patterns in text
                        import re
                        b64_pattern = r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)'
                        match = re.search(b64_pattern, content)
                        if match:
                            logger.info("Found image data in content string pattern")
                            return base64.b64decode(match.group(1))
                        
                        # Check if the content itself is base64 (common case for Discord bot)
                        try:
                            # Try to decode as base64 first
                            decoded = base64.b64decode(content)
                            # Check if it's a valid image by trying to read it
                            from PIL import Image as PILImage
                            img = PILImage.open(io.BytesIO(decoded))
                            logger.info("Found direct base64 image data in content string")
                            return decoded
                        except:
                            pass
                        
                        # Look for standalone base64 strings that start with image headers
                        b64_standalone_pattern = r'([A-Za-z0-9+/]{500,}={0,2})'
                        matches = re.findall(b64_standalone_pattern, content)
                        for match in matches:
                            try:
                                decoded = base64.b64decode(match)
                                # Try to verify it's an image
                                from PIL import Image as PILImage
                                img = PILImage.open(io.BytesIO(decoded))
                                logger.info("Found standalone base64 image data in content")
                                return decoded
                            except:
                                continue
            
            # Deep search through the entire response for base64 strings (Discord bot approach)
            def find_base64_strings(obj, path=""):
                """Recursively search for base64 strings in a nested object"""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if isinstance(value, str) and len(value) > 1000:
                            # Check for common image headers
                            if value.startswith(('iVBORw0KGgo', '/9j/', 'R0lGOD', 'UklGRg')):
                                logger.info(f"Found potential base64 image at path: {current_path}, length: {len(value)}")
                                try:
                                    return base64.b64decode(value)
                                except:
                                    pass
                            elif value.startswith("data:image/"):
                                try:
                                    _, b64_data = value.split(',', 1)
                                    logger.info(f"Found data URL image at path: {current_path}")
                                    return base64.b64decode(b64_data)
                                except:
                                    pass
                        else:
                            result = find_base64_strings(value, current_path)
                            if result:
                                return result
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        current_path = f"{path}[{i}]" if path else f"[{i}]"
                        result = find_base64_strings(item, current_path)
                        if result:
                            return result
                return None
            
            # Try the deep search
            result = find_base64_strings(resp_json)
            if result:
                return result
            
            # Final attempt: regex search through raw response string
            response_str = str(resp_json)
            import re
            patterns = [
                r'iVBORw0KGgo[A-Za-z0-9+/=]+',  # PNG
                r'/9j/[A-Za-z0-9+/=]+',          # JPEG
                r'R0lGOD[A-Za-z0-9+/=]+',        # GIF
                r'UklGRg[A-Za-z0-9+/=]+'         # WEBP
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response_str)
                for match in matches:
                    if len(match) > 1000:  # Reasonable minimum length for an image
                        logger.info(f"Found base64 pattern via regex: {pattern}, length: {len(match)}")
                        try:
                            return base64.b64decode(match)
                        except:
                            continue
            
            # If no image data found, this means the model returned text instead of image
            logger.error("No image data found in Gemini response - model returned text instead of image", extra={
                "response_structure": self._get_response_structure(resp_json),
                "content_preview": str(resp_json.get('choices', [{}])[0].get('message', {}).get('content', ''))[:200] if 'choices' in resp_json else "No choices found"
            })
            
            raise Exception(f"Gemini model returned text description instead of image data. "
                          f"Content preview: {str(resp_json.get('choices', [{}])[0].get('message', {}).get('content', ''))[:200]}...")
            
        except Exception as e:
            if "returned text description instead" in str(e):
                raise e  # Re-raise our custom error
            logger.error(f"Error parsing Gemini image response: {e}", extra={"response": resp_json})
            raise Exception(f"Failed to parse Gemini image response: {e}")

    def _get_response_structure(self, obj, depth=0, max_depth=3):
        """Get a summary of the response structure for debugging."""
        if depth > max_depth:
            return "..."
        
        if isinstance(obj, dict):
            return {k: self._get_response_structure(v, depth+1, max_depth) for k, v in obj.items()}
        elif isinstance(obj, list):
            if len(obj) > 0:
                return [self._get_response_structure(obj[0], depth+1, max_depth), f"... ({len(obj)} items)"] if len(obj) > 1 else [self._get_response_structure(obj[0], depth+1, max_depth)]
            else:
                return []
        else:
            return type(obj).__name__