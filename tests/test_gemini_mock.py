import pytest
from PIL import Image
from bananagen.gemini_adapter import mock_generate


@pytest.mark.asyncio
async def test_mock_generate_basic():
    """Test basic mock generation."""
    import tempfile
    import os
    
    # Create a temporary template image
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        template_path = f.name
    
    # Create a dummy template
    img = Image.new("RGB", (100, 50), color=(128, 128, 128))
    img.save(template_path)
    
    try:
        # Mock generate
        out_path, metadata = await mock_generate(template_path, "test prompt")
        
        # Verify output path
        assert out_path is not None
        assert os.path.exists(out_path)
        
        # Verify generated image
        gen_img = Image.open(out_path)
        assert gen_img.size == (100, 50)  # Should match template
        assert gen_img.mode == "RGB"
        
        # Verify metadata
        assert "prompt" in metadata
        assert metadata["prompt"] == "test prompt"
        assert "model" in metadata
        assert metadata["model"] == "mock"
        assert "seed" in metadata
        assert "params" in metadata
        assert "gemini_response_id" in metadata
        assert "sha256" in metadata
        
        # Verify SHA256 is a string (mock value)
        assert isinstance(metadata["sha256"], str)
        # Mock generates red image, check if first pixel is red
        pixels = list(gen_img.getdata())
        r, g, b = pixels[0]
        assert r == 255 and g == 0 and b == 0
        
    finally:
        # Cleanup
        for path in [template_path, out_path]:
            if os.path.exists(path or ""):
                os.unlink(path)


@pytest.mark.asyncio
async def test_mock_generate_with_params():
    """Test mock generation with custom params."""
    import tempfile
    import os
    
    # Create template
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        template_path = f.name
    
    img = Image.new("RGB", (64, 64), color=(0, 0, 0))
    img.save(template_path)
    
    try:
        # Generate with custom seed
        params = {"seed": 12345, "quality": "high"}
        out_path, metadata = await mock_generate(template_path, "another prompt", params)
        
        # Verify params are preserved
        assert metadata["params"] == params
        assert metadata["seed"] == 12345  # Overridden by params
        
        # Verify file created
        assert os.path.exists(out_path)
        
    finally:
        if os.path.exists(template_path):
            os.unlink(template_path)
        if os.path.exists(out_path or ""):
            os.unlink(out_path)


@pytest.mark.asyncio
async def test_mock_generate_default_params():
    """Test mock generation with no params provided."""
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        template_path = f.name
    
    img = Image.new("RGB", (32, 32), color=(255, 255, 255))
    img.save(template_path)
    
    try:
        # No params
        out_path, metadata = await mock_generate(template_path, "prompt", None)
        
        # Should use defaults
        assert metadata["seed"] == 12345
        assert metadata["params"] is None or metadata["params"] == {}
        
        assert os.path.exists(out_path)
        
    finally:
        if os.path.exists(template_path):
            os.unlink(template_path)
        if os.path.exists(out_path or ""):
            os.unlink(out_path)