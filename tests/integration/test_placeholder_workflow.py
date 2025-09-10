import pytest
import tempfile
import os
import subprocess
import sys
from pathlib import Path


class TestPlaceholderWorkflow:
    """Integration tests for placeholder generation workflow.

    Tests the complete workflow from CLI command to file creation.
    """

    def test_placeholder_cli_creates_image_file(self):
        """Test that bananagen placeholder command creates a valid image file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_placeholder.png")

            # Run CLI command
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "512",
                "--height", "256",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Placeholder saved" in result.stdout

            # Check file was created
            assert os.path.exists(output_path), "Output file was not created"
            assert os.path.getsize(output_path) > 0, "Output file is empty"

    def test_placeholder_cli_with_transparent_background(self):
        """Test placeholder generation with transparent background."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "transparent_placeholder.png")

            # Run CLI command with transparent flag
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "300",
                "--height", "200",
                "--transparent",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Placeholder saved" in result.stdout

            # Check file was created
            assert os.path.exists(output_path), "Output file was not created"
            assert os.path.getsize(output_path) > 0, "Output file is empty"

    def test_placeholder_cli_with_custom_color(self):
        """Test placeholder generation with custom background color."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "colored_placeholder.png")

            # Run CLI command with custom color
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "400",
                "--height", "300",
                "--color", "#ff0000",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"
            assert "Placeholder saved" in result.stdout

            # Check file was created
            assert os.path.exists(output_path), "Output file was not created"
            assert os.path.getsize(output_path) > 0, "Output file is empty"

    def test_placeholder_cli_validates_dimensions(self):
        """Test that CLI validates image dimensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with zero width
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "0",
                "--height", "512",
                "--out", os.path.join(tmpdir, "invalid.png")
            ], capture_output=True, text=True, cwd=tmpdir)

            # Should fail with validation error
            assert result.returncode != 0, "Command should fail with invalid dimensions"

            # Test with negative height
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "512",
                "--height", "-100",
                "--out", os.path.join(tmpdir, "invalid.png")
            ], capture_output=True, text=True, cwd=tmpdir)

            # Should fail with validation error
            assert result.returncode != 0, "Command should fail with negative dimensions"

    def test_placeholder_cli_creates_correct_path_structure(self):
        """Test that CLI handles directory creation for output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directory structure
            nested_dir = os.path.join(tmpdir, "images", "placeholders")
            output_path = os.path.join(nested_dir, "deep_nested.png")

            # Run CLI command (should create intermediate directories)
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "128",
                "--height", "128",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"

            # Check directories were created
            assert os.path.exists(nested_dir), "Nested directories were not created"
            assert os.path.exists(output_path), "Output file was not created"
            assert os.path.getsize(output_path) > 0, "Output file is empty"

    def test_placeholder_cli_handles_relative_paths(self):
        """Test placeholder generation with relative paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            relative_path = os.path.join("relative", "path", "output.png")
            output_path = os.path.join(tmpdir, relative_path)

            # Change to temporary directory to test relative paths
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Run CLI command with relative path
                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "placeholder",
                    "--width", "256",
                    "--height", "256",
                    "--out", relative_path
                ], capture_output=True, text=True, cwd=tmpdir)

                # Check command succeeded
                assert result.returncode == 0, f"Command failed: {result.stderr}"
                assert os.path.exists(output_path), "Output file was not created"

            finally:
                os.chdir(original_cwd)

    def test_placeholder_cli_requires_all_parameters(self):
        """Test that CLI requires mandatory parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test missing --width
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--height", "512",
                "--out", os.path.join(tmpdir, "test.png")
            ], capture_output=True, text=True, cwd=tmpdir)

            # Should fail due to missing required parameter
            assert result.returncode != 0, "Command should fail when width is missing"

            # Test missing --height
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "512",
                "--out", os.path.join(tmpdir, "test.png")
            ], capture_output=True, text=True, cwd=tmpdir)

            # Should fail due to missing required parameter
            assert result.returncode != 0, "Command should fail when height is missing"

            # Test missing --out
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "512",
                "--height", "512"
            ], capture_output=True, text=True, cwd=tmpdir)

            # Should fail due to missing required parameter
            assert result.returncode != 0, "Command should fail when out path is missing"

    def test_placeholder_cli_multiple_runs_overwrite(self):
        """Test that multiple runs to the same path overwrite the file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "overwrite_test.png")

            # First run
            result1 = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "100",
                "--height", "100",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            assert result1.returncode == 0
            size1 = os.path.getsize(output_path)

            # Second run with different dimensions
            result2 = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "200",
                "--height", "200",
                "--out", output_path
            ], capture_output=True, text=True, cwd=tmpdir)

            assert result2.returncode == 0
            size2 = os.path.getsize(output_path)

            # File should be overwritten (different size expected due to different dimensions)
            assert size2 != size1, "File was not overwritten with different content"

    def test_placeholder_cli_help_display(self):
        """Test that CLI help shows placeholder command details."""
        result = subprocess.run([
            sys.executable, "-m", "bananagen", "placeholder", "--help"
        ], capture_output=True, text=True)

        # Should show help successfully
        assert result.returncode == 0
        assert "width" in result.stdout
        assert "height" in result.stdout
        assert "color" in result.stdout
        assert "transparent" in result.stdout
        assert "Generate placeholder images" in result.stdout

    def test_placeholder_different_formats_mentioned(self):
        """Note: This test is for when PNG isn't the only supported format."""
        # Placeholder test for future image format support
        # For now, just verify PNG format works
        with tempfile.TemporaryDirectory() as tmpdir:
            png_path = os.path.join(tmpdir, "test.png")
            jpg_path = os.path.join(tmpdir, "test.jpg")

            # Test PNG
            result_png = subprocess.run([
                sys.executable, "-m", "bananagen",
                "placeholder",
                "--width", "64",
                "--height", "64",
                "--out", png_path
            ], capture_output=True, text=True, cwd=tmpdir)

            # PNG should work
            assert result_png.returncode == 0
            assert os.path.exists(png_path)