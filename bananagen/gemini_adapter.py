import os
import asyncio
import io
import hashlib
from PIL import Image
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

async def call_gemini(template_path: str, prompt: str, model: str = "nano-banana-2.5-flash", params: dict = None):
    """Call Gemini to generate image from template and prompt."""
    try:
        logger.info("Starting Gemini call", extra={
            "template_path": template_path,
            "prompt": prompt[:50] + '...' if len(prompt) > 50 else prompt,
            "model": model,
            "has_params": params is not None
        })

        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file does not exist: {template_path}")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        api_key = os.getenv("NANO_BANANA_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            logger.warning("No API key found, using mock mode", extra={"template_path": template_path})
            return await mock_generate(template_path, prompt, params)
        else:
            return await real_generate(template_path, prompt, model, params or {})

    except Exception as e:
        logger.error("Failed to call Gemini", extra={
            "template_path": template_path,
            "error": str(e),
            "error_type": type(e).__name__,
            "prompt": prompt[:30] + '...' if len(prompt) > 30 else prompt
        })
        raise

async def mock_generate(template_path: str, prompt: str, params: dict = None):
    """Mock generation for testing."""
    try:
        logger.info("Starting mock generation", extra={"template_path": template_path})

        # Simulate async processing
        await asyncio.sleep(0.1)

        try:
            # Load template
            template = Image.open(template_path)
            width, height = template.size
            logger.debug("Template loaded", extra={"width": width, "height": height})
        except FileNotFoundError:
            raise FileNotFoundError(f"Template file not found: {template_path}")
        except Exception as e:
            raise Exception(f"Failed to load template image: {e}")

        try:
            # Create a fake generated image (e.g., add some color)
            generated = Image.new("RGB", (width, height), (255, 0, 0))  # red for mock

            # Save to a temp path
            out_path = template_path.replace(".png", "_generated.png")
            generated.save(out_path)

            logger.info("Mock image generated", extra={"out_path": out_path})
        except Exception as e:
            raise Exception(f"Failed to save generated image: {e}")

        metadata = {
            "prompt": prompt,
            "model": "mock",
            "seed": params.get("seed", 12345) if params else 12345,
            "params": params or {},
            "gemini_response_id": "mock-id",
            "sha256": "mock-sha256"
        }

        return out_path, metadata

    except Exception as e:
        logger.error("Mock generation failed", extra={
            "template_path": template_path,
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise

async def real_generate(template_path: str, prompt: str, model: str = "nano-banana-2.5-flash", params: dict = None):
    """Real generation using Gemini API."""
    params = params or {}

    try:
        logger.info("Starting real generation", extra={"template_path": template_path, "model": model})

        try:
            # Load and prepare template
            template = Image.open(template_path)
            width, height = template.size
            template_bytes = io.BytesIO()
            template.save(template_bytes, format='PNG')
            template_bytes = template_bytes.getvalue()
            logger.debug("Template processed", extra={"width": width, "height": height, "bytes": len(template_bytes)})
        except FileNotFoundError:
            raise FileNotFoundError(f"Template file not found: {template_path}")
        except Exception as e:
            raise Exception(f"Failed to load template image: {e}")

        max_retries = 3
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Gemini API call attempt {attempt + 1}/{max_retries + 1}")

                def _call():
                    try:
                        # Initialize Gemini API if not already done
                        api_key = os.getenv("NANO_BANANA_API_KEY") or os.getenv("GEMINI_API_KEY")
                        if not api_key:
                            raise Exception("API key not found")

                        genai.configure(api_key=api_key)
                        m = genai.GenerativeModel(model="gemini-1.5-flash")
                        img_part = genai.Image.from_bytes(template_bytes)

                        # Prepare generation config
                        generation_config = None
                        if params and 'seed' in params and params['seed'] is not None:
                            generation_config = genai.types.GenerationConfig(
                                temperature=0.7,  # Default
                                candidate_count=1,
                                seed=int(params['seed'])
                            )

                        response = m.generate_content([img_part, prompt], generation_config=generation_config)
                        return response
                    except Exception as inner_e:
                        logger.error("Gemini API call error", extra={"error": str(inner_e)})
                        raise inner_e

                response = await asyncio.to_thread(_call)

                if hasattr(response, 'text'):
                    generated_text = response.text
                    logger.debug("Gemini response received", extra={"response_length": len(generated_text)})
                else:
                    generated_text = "No text response"
                    logger.warning("Gemini response missing text field")

                # Create image placeholder (simplified)
                try:
                    img = Image.new('RGB', (width, height), (255, 0, 255))
                    out_path = template_path.replace(".png", "_generated.png")
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes_data = img_bytes.getvalue()

                    # Write file safely
                    try:
                        with open(out_path, 'wb') as f:
                            f.write(img_bytes_data)
                        logger.info("Generated image saved", extra={"out_path": out_path})
                    except OSError as e:
                        raise Exception(f"Failed to save generated image: {e}")

                    # Calculate hash
                    sha256 = hashlib.sha256(img_bytes_data).hexdigest()

                    metadata = {
                        "prompt": prompt,
                        "model": model,
                        "seed": params.get("seed", 12345),
                        "params": params,
                        "gemini_response_id": getattr(response, 'response_id', "real-id"),
                        "sha256": sha256,
                        "response_text": generated_text[:100] + '...' if len(generated_text) > 100 else generated_text
                    }

                    logger.info("Real generation completed successfully", extra={"out_path": out_path})
                    return out_path, metadata

                except Exception as img_e:
                    logger.error("Failed to create output image", extra={
                        "error": str(img_e),
                        "template_path": template_path,
                        "width": width,
                        "height": height
                    })
                    raise Exception(f"Failed to create output image: {img_e}")

            except Exception as e:
                last_error = e
                logger.warning(f"Gemini API attempt {attempt + 1} failed", extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "attempt": attempt + 1,
                    "max_retries": max_retries
                })

                if attempt == max_retries:
                    break

                # Exponential backoff
                delay = 1 * (2 ** attempt)
                logger.info(f"Retrying Gemini API call in {delay}s")
                await asyncio.sleep(delay)

        # All retries failed
        error_msg = f"Gemini API call failed after {max_retries + 1} attempts: {str(last_error)}"
        logger.error("All Gemini API attempts failed", extra={"final_error": str(last_error)})
        raise Exception(error_msg)

    except Exception as e:
        logger.error("Real generation failed", extra={
            "template_path": template_path,
            "model": model,
            "error": str(e),
            "error_type": type(e).__name__
        })
        raise
