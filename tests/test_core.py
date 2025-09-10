"""
Unit tests for bananagen.core module.

These tests MUST FAIL initially (TDD approach).
Implementation should make these tests pass.
"""
import pytest
from pathlib import Path
import tempfile
from PIL import Image

from bananagen.core import generate_placeholder


class TestGeneratePlaceholder:
    """Test placeholder image generation functionality."""
    
    def test_generate_basic_placeholder(self):
        """Test generating a basic placeholder with width and height."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_placeholder.png"
            
            # This should create a 300x200 placeholder
            result = generate_placeholder(
                width=300,
                height=200,
                out_path=str(output_path)
            )
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify image dimensions
            with Image.open(output_path) as img:
                assert img.size == (300, 200)
                
            # Verify return value contains metadata
            assert result is not None
            assert "path" in result
            assert "width" in result
            assert "height" in result
            assert result["width"] == 300
            assert result["height"] == 200
    
    def test_generate_placeholder_with_color(self):
        """Test generating placeholder with custom color."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "colored_placeholder.png"
            
            result = generate_placeholder(
                width=100,
                height=100,
                color="#FF0000",  # Red
                out_path=str(output_path)
            )
            
            assert output_path.exists()
            
            # Verify the image has the right color
            with Image.open(output_path) as img:
                # Check pixel color (should be red)
                pixel = img.getpixel((50, 50))
                # RGB for red
                assert pixel == (255, 0, 0) or pixel == (255, 0, 0, 255)  # with or without alpha
    
    def test_generate_transparent_placeholder(self):
        """Test generating placeholder with transparent background."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "transparent_placeholder.png"
            
            result = generate_placeholder(
                width=50,
                height=50,
                transparent=True,
                out_path=str(output_path)
            )
            
            assert output_path.exists()
            
            # Verify image has alpha channel
            with Image.open(output_path) as img:
                assert img.mode in ['RGBA', 'LA']  # Has alpha channel
    
    def test_generate_placeholder_invalid_dimensions(self):
        """Test error handling for invalid dimensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "invalid_placeholder.png"
            
            # Should raise error for invalid dimensions
            with pytest.raises(ValueError):
                generate_placeholder(
                    width=0,
                    height=200,
                    out_path=str(output_path)
                )
            
            with pytest.raises(ValueError):
                generate_placeholder(
                    width=200,
                    height=-10,
                    out_path=str(output_path)
                )
    
    def test_generate_placeholder_directory_creation(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested path that doesn't exist
            output_path = Path(tmpdir) / "nested" / "dir" / "placeholder.png"
            
            result = generate_placeholder(
                width=100,
                height=100,
                out_path=str(output_path)
            )
            
            # Directory should be created and file should exist
            assert output_path.exists()
            assert output_path.parent.exists()
