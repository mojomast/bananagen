# Contract tests for /generate endpoint
# These tests will fail until implementation is complete

import pytest
from bananagen.server import app  # Will fail until implemented
from fastapi.testclient import TestClient

client = TestClient(app)

def test_generate_endpoint():
    request_data = {
        "prompt": "A cozy cabin in snow",
        "width": 1024,
        "height": 768,
        "out_path": "./test_output.png"
    }
    response = client.post("/generate", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] in ["queued", "running", "done", "error"]
    assert "out_path" in data
    # This will fail until server is implemented
