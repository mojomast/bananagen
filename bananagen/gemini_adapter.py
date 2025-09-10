import os
from PIL import Image

def call_gemini(template_path: str, prompt: str, model: str = "nano-banana-2.5-flash", params: dict = None):
    """Call Gemini to generate image from template and prompt."""
    api_key = os.getenv("NANO_BANANA_API_KEY")
    if not api_key:
        # Mock mode
        return mock_generate(template_path, prompt, params)
    else:
        # Real implementation later
        raise NotImplementedError("Real Gemini API not implemented yet")

def mock_generate(template_path: str, prompt: str, params: dict = None):
    """Mock generation for testing."""
    # Load template
    template = Image.open(template_path)
    width, height = template.size
    
    # Create a fake generated image (e.g., add some color)
    generated = Image.new("RGB", (width, height), (255, 0, 0))  # red for mock
    
    # Save to a temp path or something
    out_path = template_path.replace(".png", "_generated.png")
    generated.save(out_path)
    
    metadata = {
        "prompt": prompt,
        "model": "mock",
        "seed": params.get("seed", 12345) if params else 12345,
        "params": params or {},
        "gemini_response_id": "mock-id",
        "sha256": "mock-sha256"
    }
    
    return out_path, metadata
