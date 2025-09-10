# Bananagen

A CLI tool that produces ready-to-use image assets by driving the Nano Banana (Gemini 2.5 Flash) model with intelligent caching, batch processing, and comprehensive API support.

## Features

- 🚀 **Fast Placeholder Generation** - Create temporary images instantly without API calls
- 🎨 **AI-Powered Image Generation** - Use Google Gemini 2.5 Flash for high-quality image creation
- 📦 **Batch Processing** - Process multiple images concurrently with configurable rate limiting
- 🔍 **Smart Scanning** - Automatically scan and replace placeholder images in your project files
- 📊 **Comprehensive API** - RESTful API with async processing and status tracking
- 🗂️ **Intelligent Caching** - SHA256-based caching prevents duplicate generations
- 🛡️ **Validation & Error Handling** - Pydantic models with comprehensive input validation
- 🚦 **Rate Limiting** - Built-in protection against API rate limits with exponential backoff
- 📝 **Structured Logging** - JSON-formatted logs with rich metadata
- 🔄 **Async Processing** - Non-blocking operations for better performance

## Installation

### Prerequisites

- Python 3.10+
- Optional: Google Gemini API key for real image generation

### Install from PyPI

```bash
pip install bananagen
```

### Install with Poetry

```bash
# Clone the repository
git clone https://github.com/your-username/bananagen.git
cd bananagen

# Install dependencies
poetry install

# Or add to existing project
poetry add bananagen
```

### Dependencies

The following packages are automatically installed:

- `click>=8.1.7` - Command-line interface
- `pillow>=10.0.0` - Image processing
- `aiohttp>=3.8.0` - Async HTTP client
- `fastapi>=0.104.0` - REST API framework
- `pydantic>=2.0.0` - Data validation
- `uvicorn>=0.24.0` - ASGI server
- `google-generativeai>=0.3.0` - Gemini API client

### Environment Setup

Set your API key for real image generation:

```bash
export NANO_BANANA_API_KEY=your_gemini_api_key_here
# or
export GEMINI_API_KEY=your_gemini_api_key_here
```

Configure logging level:

```bash
export BANANAGEN_LOG_LEVEL=DEBUG  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Quick Start

### 1. Generate a Simple Image

```bash
# Generate a placeholder (instant, no API calls)
bananagen placeholder --width 512 --height 512 --out my_image.png

# Generate with Gemini AI
bananagen generate --prompt "A beautiful sunset over mountains" --out sunset.png
```

### 2. Batch Processing

Create a jobs file:

```bash
echo '[{
  "prompt": "A cat wearing sunglasses",
  "width": 512,
  "height": 512,
  "output_path": "./assets/cat.png"
}, {
  "prompt": "A dog playing fetch",
  "width": 512,
  "height": 512,
  "output_path": "./assets/dog.png"
}]' > image_jobs.json

# Process batch
bananagen batch --list image_jobs.json --concurrency 2
```

### 3. Scan and Replace Placeholders

```bash
# Scan your website for placeholder patterns
bananagen scan --root ./website --pattern "*placeholder*" --replace
```

### 4. API Server Mode

```bash
# Start the API server
bananagen serve --port 9090 --host 0.0.0.0
```

## CLI Usage Examples

### Core Commands

#### Generate Images

```bash
# Basic generation
bananagen generate --prompt "A red apple" --out apple.png

# With dimensions
bananagen generate --prompt "A blue sky" --width 1024 --height 768 --out sky.png

# Use existing placeholder as template
bananagen placeholder --width 512 --height 512 --out template.png
bananagen generate --placeholder template.png --prompt "A city skyline" --out skyline.png

# Force re-generation (bypass cache)
bananagen generate --prompt "A sunset" --out sunset.png --force

# Use specific seed for reproducible results
bananagen generate --prompt "A forest" --out forest.png --seed 12345

# JSON output for scripting
bananagen generate --prompt "A car" --out car.png --json
# {"id": "uuid", "status": "processing", "out_path": "car.png", "created_at": "2025-01-01T12:00:00Z"}
```

#### Placeholder Creation

```bash
# Basic placeholder
bananagen placeholder --width 512 --height 512 --out placeholder.png

# Transparent background
bananagen placeholder --width 512 --height 512 --transparent --out transparent.png

# Custom color
bananagen placeholder --width 512 --height 512 --color "#ff0000" --out red_placeholder.png
```

#### Batch Processing

```bash
# Process jobs from JSON file
bananagen batch --list jobs.json --concurrency 3 --rate-limit 2.0

# JSON output for monitoring
bananagen batch --list jobs.json --json

# Concurrency and rate limiting
bananagen batch --list jobs.json --concurrency 5 --rate-limit 1.0
```

#### File Scanning

```bash
# Dry run scan
bananagen scan --root ./project --pattern "*placeholder*"

# Replace placeholders with generated images
bananagen scan --root ./project --pattern "*placeholder*" --replace

# Custom pattern scanning
bananagen scan --root ./src --pattern "*__asset__*"
```

#### API Server

```bash
# Start with default settings
bananagen serve

# Custom host and port
bananagen serve --host 127.0.0.1 --port 8080
```

#### Job Status

```bash
# Check specific job
bananagen status abc123-def456-ghi789

# JSON output
bananagen status abc123-def456-ghi789 --json
```

### Advanced CLI Options

#### Logging Control

```bash
# Set logging level
bananagen --log-level DEBUG generate --prompt "test" --out test.png

# Structured JSON logging
export BANANAGEN_LOG_LEVEL=INFO
bananagen generate --prompt "test" --out test.png --json
```

## API Documentation

The Bananagen API provides RESTful endpoints for all CLI functionality with async processing and comprehensive status tracking.

### API Endpoints

#### POST `/generate`

Generate a single image.

**Request Body:**
```json
{
  "prompt": "A beautiful landscape",
  "width": 512,
  "height": 512,
  "output_path": "./assets/landscape.png",
  "model": "gemini-2.5-flash",
  "template_path": null
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2025-01-01T12:00:00Z"
}
```

#### POST `/batch`

Process multiple images in batch.

**Request Body:**
```json
{
  "jobs": [
    {
      "prompt": "A red rose",
      "width": 512,
      "height": 512,
      "output_path": "./assets/rose.png"
    },
    {
      "prompt": "A blue sky",
      "width": 512,
      "height": 512,
      "output_path": "./assets/sky.png"
    }
  ]
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "queued",
  "created_at": "2025-01-01T12:00:00Z"
}
```

#### POST `/scan`

Scan and optionally replace placeholders.

**Request Body:**
```json
{
  "root": "./website",
  "pattern": "*__placeholder__*",
  "replace": true,
  "extract_from": ["readme", "manifest"]
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "status": "queued",
  "created_at": "2025-01-01T12:00:00Z"
}
```

#### GET `/status/{job_id}`

Check job status.

**Response (Generation):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "done",
  "created_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:00:30Z",
  "metadata": {
    "prompt": "A beautiful landscape",
    "model": "gemini-2.5-flash",
    "sha256": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
  },
  "error": null
}
```

**Response (Batch):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "done",
  "created_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:02:00Z",
  "results": [
    {
      "job_id": "job1",
      "success": true,
      "output_path": "./assets/rose.png",
      "metadata": {
        "prompt": "A red rose",
        "sha256": "b775a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae4"
      }
    }
  ],
  "error": null
}
```

### API Rate Limiting

The API implements rate limiting of **10 requests per minute per IP address**. Exceeding the limit returns a 429 status code:

```json
{
  "error": "Rate limit exceeded. Maximum 10 requests per minute."
}
```

### API Error Handling

The API includes comprehensive error handling with appropriate HTTP status codes:

- `422` - Validation error (invalid request data)
- `429` - Rate limit exceeded
- `404` - Job not found
- `500` - Internal server error

All error responses include detailed error information and validation messages.

## For Coding Agents

Bananagen is designed for integration with coding agents and automation tools.

### Agent Integration Patterns

#### 1. Placeholder-First Workflow

```bash
# 1. Quick placeholders for layout
bananagen placeholder --width 800 --height 600 --out ./temp/header_placeholder.png
bananagen placeholder --width 400 --height 300 --out ./temp/icon_placeholder.png

# 2. Add to HTML
<img src="temp/header_placeholder.png" alt="Header image">
<img src="temp/icon_placeholder.png" alt="Icon">

# 3. Replace with final images
bananagen generate --prompt "Professional company header" --width 800 --height 600 --out ./assets/header_final.png
bananagen generate --prompt "Company logo concept" --width 400 --height 300 --out ./assets/icon_final.png
```

#### 2. JSON-Based Automation

```bash
# Script-friendly output
JOB_ID=$(bananagen generate --prompt "Product screenshot" --out product.png --json | jq -r '.id')

# Monitor completion
while [[ "$(bananagen status $JOB_ID --json | jq -r '.status')" == "processing" ]]; do
  sleep 1
done

echo "Image generation completed!"
```

#### 3. API Integration Script

```python
import requests
import time

# Generate image via API
response = requests.post("http://localhost:9090/generate", json={
    "prompt": "A futuristic city",
    "width": 1024,
    "height": 768,
    "output_path": "./assets/city.png"
})

if response.status_code == 200:
    job_id = response.json()["id"]

    # Monitor progress
    while True:
        status = requests.get(f"http://localhost:9090/status/{job_id}").json()
        if status["status"] in ["done", "error"]:
            break
        time.sleep(2)

    print(f"Job completed: {status['status']}")
```

### Environment Variables for Agents

```bash
# API Configuration
export NANO_BANANA_API_KEY=your_api_key
export GEMINI_API_KEY=your_api_key  # Alternative

# Logging Configuration
export BANANAGEN_LOG_LEVEL=DEBUG

# Custom Settings
export BANANAGEN_DEFAULT_MODEL="gemini-2.5-flash"
export BANANAGEN_DEFAULT_WIDTH=512
export BANANAGEN_DEFAULT_HEIGHT=512
```

## Advanced Features

### Intelligent Caching

Bananagen uses SHA256 hashing for intelligent caching:

```bash
# Same prompt and template = instant result from cache
bananagen generate --prompt "A sunset" --width 512 --height 512 --out sunset1.png
bananagen generate --prompt "A sunset" --width 512 --height 512 --out sunset2.png  # Uses cache
```

### Batch Processing with Concurrency

```bash
# Process 10 images with concurrency, rate limiting, and JSON output
bananagen batch --list large_batch.json --concurrency 5 --rate-limit 2.0 --json
```

### Error Handling and Retry

Features automatic retry with exponential backoff for network issues:

```
Attempt 1 failed, retrying in 1s...
Attempt 2 failed, retrying in 2s...
Attempt 3 failed, retrying in 4s...
```

### Validation and Security

Comprehensive input validation with Pydantic models:

- File path validation
- Image dimension limits (64-4096px)
- Prompt length restrictions
- File type restrictions (.png, .jpg, .jpeg)

## Troubleshooting

### Common Issues

1. **No API Key**: Set `NANO_BANANA_API_KEY` or `GEMINI_API_KEY`
2. **Port Conflicts**: Change API port with `--port` option
3. **Permission Errors**: Ensure write permissions for output directories
4. **Large Images**: Consider memory usage for images > 2000px

### Debug Mode

```bash
# Enable debug logging
export BANANAGEN_LOG_LEVEL=DEBUG

# Test CLI availability
bananagen --help

# Test API health
curl http://localhost:9090/status/health
```

### Mock Mode

Works without API key for testing:

```bash
env NANO_BANANA_API_KEY=mock_key bananagen generate --prompt "test" --out test.png
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

See LICENSE file for details.

## Changelog

### Recent Updates

- **Async API Processing** - Non-blocking image generation
- **Enhanced Validation** - Comprehensive Pydantic models
- **Rate Limiting** - Built-in API protection
- **Exponential Backoff** - Improved retry logic
- **Structured Logging** - JSON-formatted logs with metadata
- **Improved Caching** - SHA256-based intelligent caching
- **Batch Processing** - Concurrent job execution with monitoring
