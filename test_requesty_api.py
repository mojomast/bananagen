#!/usr/bin/env python3
"""Test script to verify Requesty API integration."""

import json
import requests
import tempfile
import os

def create_test_image():
    """Create a simple test image."""
    from PIL import Image
    import io

    # Create a simple 64x64 red square
    img = Image.new('RGB', (64, 64), color='red')
    temp_path = tempfile.mktemp(suffix='.png')
    img.save(temp_path)
    return temp_path

def test_requesty_generate():
    """Test the generate endpoint with Requesty provider."""
    # Create test image
    image_path = create_test_image()

    try:
        # Test data
        test_data = {
            "prompt": "Generate a blue square",
            "width": 64,
            "height": 64,
            "output_path": image_path.replace('.png', '_output.png'),
            "model": "google/gemini-1.5-flash",
            "template_path": image_path,
            "provider": "requesty"
        }

        print("Testing Requesty API integration...")
        print("Test data:", json.dumps(test_data, indent=2))

        # Make request to API
        response = requests.post("http://localhost:9090/generate", json=test_data, timeout=30)

        print(f"Response status: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 200:
            result = response.json()
            job_id = result.get('id')
            if job_id:
                # Check status
                status_response = requests.get(f"http://localhost:9090/status/{job_id}")
                print(f"Status response: {status_response.json()}")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        # Clean up
        if os.path.exists(image_path):
            os.unlink(image_path)

if __name__ == "__main__":
    test_requesty_generate()