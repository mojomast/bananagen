# Agent Integration Guide for Bananagen

This document provides integration examples and best practices for coding agents (such as Roo, Claude Code, or similar tools) to work effectively with bananagen.

## Overview

Bananagen provides both CLI and HTTP API interfaces for image generation, making it easy for agents to:

- Generate placeholder images for web development
- Create final images using Gemini 2.5 Flash
- Process batches of images concurrently
- Scan and replace placeholders in project files

## CLI Integration

### Single Image Generation

```bash
# Generate a placeholder (fast, no API calls)
bananagen placeholder --width 512 --height 256 --out ./assets/placeholder.png

# Generate with Gemini (requires API key)
bananagen generate --prompt "A 2D pixel art banana mascot" --width 512 --height 512 --out ./assets/banana.png

# Generate with JSON output for status tracking
bananagen generate --prompt "A 2D pixel art banana mascot" --width 512 --height 512 --out ./assets/banana.png --json
```

### Batch Processing

```bash
# Process a JSON file with multiple jobs
echo '[
  {"prompt": "A red apple", "width": 512, "height": 512, "output_path": "./assets/apple.png"},
  {"prompt": "A yellow banana", "width": 512, "height": 512, "output_path": "./assets/banana.png"}
]' > jobs.json

bananagen batch --list jobs.json --concurrency 2 --json
```

### Placeholder Scanning

```bash
# Scan for placeholders (dry run)
bananagen scan --root ./site --pattern "*__placeholder__*"

# Scan and replace placeholders
bananagen scan --root ./site --pattern "*__placeholder__*" --replace
```

### Status Checking

```bash
# Check CLI status
bananagen status 123e4567-e89b-12d3-a456-426614174000 --json

# Or use API
curl http://localhost:9090/status/123e4567-e89b-12d3-a456-426614174000
```

## API Integration

### Starting the API Server

```bash
bananagen serve --port 9090 --host 0.0.0.0
```

### Single Image Generation

```python
import requests
import json

# Generate request
response = requests.post("http://localhost:9090/generate",
    json={
        "prompt": "A 2D pixel art banana mascot",
        "width": 512,
        "height": 512,
        "output_path": "./assets/banana.png"
    }
)

job_id = response.json()["id"]

# Check status
status_response = requests.get(f"http://localhost:9090/status/{job_id}")
print(f"Status: {status_response.json()['status']}")
```

### Batch Processing

```python
import requests

# Create batch
batch_response = requests.post("http://localhost:9090/batch",
    json={
        "jobs": [
            {
                "prompt": "A red apple on a table",
                "width": 512,
                "height": 512,
                "output_path": "./assets/apple.png"
            },
            {
                "prompt": "A yellow banana on a table",
                "width": 512,
                "height": 512,
                "output_path": "./assets/banana.png"
            }
        ]
    }
)

batch_id = batch_response.json()["id"]

# Monitor completion
while True:
    status = requests.get(f"http://localhost:9090/status/{batch_id}").json()
    if status["status"] in ["done", "error", "failed"]:
        break
    time.sleep(2)

print(f"Batch completed with status: {status['status']}")
```

### Placeholder Scanning

```python
import requests

# Scan for placeholders
scan_response = requests.post("http://localhost:9090/scan",
    json={
        "root": "./website",
        "pattern": "*__placeholder__*",
        "replace": False,  # Dry run first
        "extract_from": ["readme", "manifest"]
    }
)

results = scan_response.json()
print(f"Found {len(results['details'])} placeholders, {results['replaced']} could be replaced")

# If okay, do replacement
replacement_response = requests.post("http://localhost:9090/scan",
    json={
        "root": "./website",
        "pattern": "*__placeholder__*",
        "replace": True,
        "extract_from": ["readme", "manifest"]
    }
)
```

## Agent Integration Patterns

### For Roo / Similar Agents

When integrating with Roo, use these patterns:

#### 1. Placeholder-First Approach

```bash
# 1. Create placeholders quickly (no API cost)
bananagen placeholder --width 512 --height 512 --out ./assets/header_image_placeholder.png
bananagen placeholder --width 256 --height 256 --out ./assets/icon_placeholder.png

# 2. Add placeholders to HTML
<!-- In HTML file -->
<img src="assets/header_image_placeholder.png" alt="Company header image">
<img src="assets/icon_placeholder.png" alt="Company icon">

# 3. Later, replace with actual images
bananagen generate --prompt "Professional company header with logo" --width 512 --height 512 --out ./assets/header_image_final.png
```

#### 2. Progressive Enhancement

```bash
# Generate in phases
# Phase 1: Fast placeholders
bananagen placeholder --width 1024 --height 768 --out ./temp/layout_placeholder.png
# → Use for layout testing immediately

# Phase 2: Generate final when ready
bananagen generate --template-path ./temp/layout_placeholder.png --prompt "Final polished version" --out ./assets/final_image.png
# → Replace placeholder with final image
```

#### 3. Batch Workflow for Multiple Assets

```bash
# Create job specification
cat > image_jobs.json << EOF
[
  {"prompt": "Product showcase image", "width": 800, "height": 600, "output_path": "./assets/product_showcase.png"},
  {"prompt": "Team photo placeholder", "width": 400, "height": 300, "output_path": "./assets/team_photo.png"},
  {"prompt": "Logo concept", "width": 256, "height": 256, "output_path": "./assets/logo.png"}
]
EOF

# Execute batch
bananagen batch --list image_jobs.json --concurrency 2 --rate-limit 2.0 --json
```

### For Claude Code / Similar Agents

#### Integration Script Pattern

```python
#!/usr/bin/env python3
"""
Integration script for Claude Code and bananagen
"""
import subprocess
import json
import sys

def run_bananagen_command(cmd_args):
    """Execute bananagen command and return parsed result."""
    result = subprocess.run(['bananagen'] + cmd_args,
                          capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Command failed: {' '.join(cmd_args)}")
        print(f"Error: {result.stderr}")
        return None

    # Try to parse as JSON first
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return result.stdout.strip()

def generate_image_workflow(prompt, output_path, width=512, height=512):
    """Complete image generation workflow."""
    print(f"Generating image: {prompt}")

    # Check if CLI is available
    result = run_bananagen_command(['generate', '--help'])
    if result is None:
        print("ERROR: bananagen CLI not available")
        return False

    # Start generation
    gen_result = run_bananagen_command([
        'generate',
        '--prompt', prompt,
        '--width', str(width),
        '--height', str(height),
        '--out', output_path,
        '--json'
    ])

    if not gen_result:
        return False

    job_id = gen_result.get('id')
    if not job_id:
        print("ERROR: No job ID returned")
        return False

    print(f"Job started with ID: {job_id}")

    # Monitor status (simplified)
    while True:
        status_result = run_bananagen_command(['status', job_id, '--json'])
        if status_result and status_result.get('status') in ['done', 'error']:
            break
        time.sleep(2)

    final_status = status_result.get('status', 'unknown')
    print(f"Job completed with status: {final_status}")
    return final_status == 'done'

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python bananagen_integration.py <prompt> <output_path> [width] [height]")
        sys.exit(1)

    prompt = sys.argv[1]
    output_path = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 512
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 512

    success = generate_image_workflow(prompt, output_path, width, height)
    sys.exit(0 if success else 1)
```

## Environment Variables

```bash
# Set Gemini API key (if using real API)
export NANO_BANANA_API_KEY=your_gemini_api_key_here

# Configure default settings
export BANANAGEN_DEFAULT_MODEL="gemini-2.5-flash"
export BANANAGEN_DEFAULT_WIDTH=512
export BANANAGEN_DEFAULT_HEIGHT=512
```

## Best Practices for Agents

### 1. Error Handling

Always check command return codes and handle failures gracefully:

```python
def safe_bananagen_call(cmd_args, max_retries=3):
    """Call bananagen with retries and error handling."""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(['bananagen'] + cmd_args,
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return result
        except subprocess.TimeoutExpired:
            print(f"Attempt {attempt + 1} timed out")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff

    print(f"All {max_retries} attempts failed")
    return None
```

### 2. Status Polling

Implement intelligent status polling with exponential backoff:

```python
def poll_status(job_id, max_attempts=30):
    """Poll job status with smart delays."""
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"http://localhost:9090/status/{job_id}", timeout=10)
            status_data = response.json()

            if status_data['status'] in ['done', 'failed', 'error']:
                return status_data

            # Wait before next poll, increasing delay
            delay = min(2 ** attempt, 30)  # Cap at 30 seconds
            time.sleep(delay)

        except Exception as e:
            print(f"Status check failed: {e}")
            time.sleep(5)

    return None
```

### 3. Concurrent Processing

Leverage batch processing for multiple images:

```python
def process_multiple_images(job_list):
    """Process multiple images efficiently."""
    # Group jobs that can be processed concurrently
    concurrent_jobs = [job for job in job_list if job.get('priority') == 'high']
    sequential_jobs = [job for job in job_list if job.get('priority') != 'high']

    # Process high-priority jobs in batch
    if concurrent_jobs:
        batch_result = requests.post("http://localhost:9090/batch",
                                   json={"jobs": concurrent_jobs})

        # Monitor batch completion
        batch_id = batch_result.json()['id']
        poll_status(batch_id)

    # Process remaining jobs sequentially
    for job in sequential_jobs:
        response = requests.post("http://localhost:9090/generate", json=job)
        job_id = response.json()['id']
        poll_status(job_id)
```

### 4. File Management

Handle temporary files and cleanup properly:

```python
def with_temporary_files(func):
    """Decorator to handle temporary file cleanup."""
    import tempfile
    import atexit

    def wrapper(*args, **kwargs):
        temp_files = []

        def cleanup():
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass

        atexit.register(cleanup)

        # Store temp files for cleanup
        result = func(*args, temp_files=temp_files, **kwargs)

        # Immediate cleanup of known temp files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except OSError:
                pass

        return result

    return wrapper
```

### 5. Placeholder Strategy

Use placeholders for fast iteration:

```python
def placeholder_replacement_workflow():
    """Workflow: placeholders first, then replace with final images."""

    # Phase 1: Quick placeholders for layout
    placeholder_files = []
    for spec in image_specs:
        placeholder_path = f"./temp/placeholder_{spec['name']}.png"
        generate_placeholder(spec['width'], spec['height'], placeholder_path)
        placeholder_files.append(placeholder_path)

        # Insert placeholder into HTML/template
        update_template_with_placeholder(spec['name'], placeholder_path)

    # Phase 2: Replace with final images when ready
    for spec in image_specs:
        if user_approves_generation(spec):
            final_path = f"./assets/final_{spec['name']}.png"
            generate_with_gemini(spec['prompt'], final_path, spec['width'], spec['height'])

            # Replace placeholder in HTML/template
            replace_placeholder_in_template(spec['name'], placeholder_path, final_path)

            # Clean up placeholder
            os.unlink(placeholder_path)
```

## Troubleshooting

### Common Issues

1. **API Key Missing**: Ensure `NANO_BANANA_API_KEY` is set for real generation
2. **Port Conflicts**: Default API port is 9090; change if needed
3. **Timeout Issues**: Increase timeout for large batch jobs
4. **File Permissions**: Ensure write permissions for output directories
5. **Memory Usage**: Large images may require significant memory

### Debug Commands

```bash
# Test CLI availability
bananagen --help

# Test API health
curl http://localhost:9090/status/health || echo "API not running"

# Check database status
ls -la bananagen.db

# Test with mock mode
env NANO_BANANA_API_KEY=mock_key bananagen generate --prompt "test" --out test.png
```

### Logging

Enable debug logging for troubleshooting:

```bash
# Set logging level
export BANANAGEN_LOG_LEVEL=DEBUG

# Or in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

This integration guide provides a comprehensive set of patterns and best practices for agents to effectively use bananagen in their workflows.