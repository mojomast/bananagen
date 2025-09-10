import pytest
from PIL import Image
from bananagen.core import generate_placeholder


def test_generate_placeholder_default():
    """Test default placeholder generation."""
    img = generate_placeholder(100, 100)
    assert isinstance(img, Image.Image)
    assert img.size == (100, 100)
    assert img.mode == "RGB"


def test_generate_placeholder_transparent():
    """Test transparent placeholder generation."""
    img = generate_placeholder(50, 50, transparent=True)
    assert isinstance(img, Image.Image)
    assert img.size == (50, 50)
    assert img.mode == "RGBA"


def test_generate_placeholder_custom_color():
    """Test placeholder with custom color."""
    img = generate_placeholder(80, 60, color="#ff0000")
    assert isinstance(img, Image.Image)
    assert img.size == (80, 60)
    assert img.mode == "RGB"
    # Check if color is approximately red
    pixels = list(img.getdata())
    # Assuming single color image, check first few pixels
    r, g, b = pixels[0]
    assert r == 255 and g == 0 and b == 0


def test_generate_placeholder_save_file():
    """Test saving placeholder to file."""
    import tempfile
    import os

    path = tempfile.mktemp(suffix=".png")

    try:
        img = generate_placeholder(64, 64, out_path=path)
        # Function should return image even when saving
        assert isinstance(img, Image.Image)

        # Check file exists
        assert os.path.exists(path)

        # Load and verify
        saved_img = Image.open(path)
        assert saved_img.size == (64, 64)
        assert saved_img.mode == "RGB"
        saved_img.close()  # Explicitly close to avoid lock
    finally:
        # Give some time for file handle to be released
        import time
        time.sleep(0.1)
        if os.path.exists(path):
            os.unlink(path)


def test_generate_placeholder_invalid_dimensions():
    """Test error handling for invalid dimensions."""
    with pytest.raises(ValueError):  # PIL raises ValueError for invalid size (0)
        generate_placeholder(0, 100)


def test_generate_placeholder_invalid_dimensions_negative():
    """Test error handling for negative dimensions."""
    with pytest.raises(ValueError):  # PIL raises ValueError for negative size
        generate_placeholder(-10, 100)
