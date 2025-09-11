# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

Bananagen is a CLI tool for generating image assets using AI models (primarily Gemini 2.5 Flash). It creates placeholder images, processes them with AI prompts, supports batch workflows, and provides an HTTP API for programmatic access. The tool supports multiple AI providers (Gemini, OpenRouter, Requesty) through a strategy pattern adapter architecture.

## Commands

### Build and Test
```bash
# Run all tests
python -m pytest

# Run specific test category
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/contract/

# Run tests with coverage
python -m pytest --cov=bananagen

# Run a single test file
python -m pytest tests/test_cli.py

# Run with debug output
python -m pytest -v
```

### Development Commands
```bash
# Install dependencies (if Poetry is available)
poetry install

# Without Poetry, use pip
pip install -r requirements.txt

# Run the CLI directly
python -m bananagen --help

# Generate a placeholder image
python -m bananagen placeholder --width 512 --height 512 --out test.png

# Generate an AI image (requires API key)
python -m bananagen generate --prompt "A sunset" --out sunset.png

# Configure API providers interactively
python -m bananagen configure --provider openrouter

# Start the API server
python -m bananagen serve --port 9090

# Check job status
python -m bananagen status <job-id>
```

### Environment Setup
```bash
# Set API keys
$env:NANO_BANANA_API_KEY = "your_gemini_api_key"  # PowerShell
$env:GEMINI_API_KEY = "your_gemini_api_key"       # Alternative

# Set logging level
$env:BANANAGEN_LOG_LEVEL = "DEBUG"
```

## Architecture

### Core Modules

**CLI Layer** (`bananagen/cli.py`)
- Entry point for all commands using Click framework
- Commands: `generate`, `placeholder`, `batch`, `scan`, `serve`, `status`, `configure`
- Extensive validation for all inputs
- JSON output support for agent integration

**Core Logic** (`bananagen/core.py`)
- `generate_placeholder()`: Creates blank images with Pillow
- `generate_image()`: Orchestrates AI image generation
- SHA256-based caching to avoid duplicate generations

**API Adapters** (`bananagen/adapters/`)
- `openrouter_adapter.py`: OpenRouter AI integration
- `requesty_adapter.py`: Requesty AI integration
- `gemini_adapter.py`: Google Gemini integration (legacy location)
- Strategy pattern allows switching providers dynamically

**Database** (`bananagen/db.py`)
- SQLite for metadata storage and API configuration
- Encrypted API key storage using cryptography library
- Tracks generation history, job status, and provider settings

**Batch Processing** (`bananagen/batch_runner.py`)
- `BatchRunner`: Concurrent job execution with rate limiting
- Exponential backoff for retry logic
- Progress tracking and error handling

**File Scanning** (`bananagen/scanner.py`)
- `Scanner`: Finds placeholder patterns in project files
- Context extraction from HTML alt text, manifests, READMEs
- Dry-run mode for safety

**REST API** (`bananagen/api.py`)
- FastAPI-based HTTP server
- Endpoints: `/generate`, `/batch`, `/status/{id}`, `/scan`
- Async processing with background tasks
- Rate limiting (10 requests/minute per IP)

### Testing Structure

**Unit Tests** (`tests/unit/`)
- Test individual components in isolation
- Mock external dependencies
- Cover validation, error handling

**Integration Tests** (`tests/integration/`)
- End-to-end workflow testing
- Test provider configurations
- Multi-provider generation flows

**Contract Tests** (`tests/contract/`)
- Validate API request/response schemas
- Ensure OpenAPI compliance
- Test all HTTP endpoints

### Key Design Patterns

1. **Multi-Provider Support**: Strategy pattern with adapters for different AI APIs
2. **Async Processing**: All I/O operations use async/await for concurrency
3. **Caching**: SHA256 hashing prevents duplicate API calls for identical requests
4. **Validation**: Pydantic models ensure data integrity throughout
5. **Error Handling**: Exponential backoff with configurable retry limits
6. **Structured Logging**: JSON-formatted logs with rich metadata

## Common Development Tasks

### Adding a New AI Provider

1. Create adapter in `bananagen/adapters/new_provider_adapter.py`
2. Implement the adapter interface with `generate_image()` method
3. Add provider configuration to `models/api_provider.py`
4. Update CLI to support the new provider option
5. Add integration tests in `tests/integration/test_new_provider_config.py`

### Modifying CLI Commands

1. Edit command in `bananagen/cli.py`
2. Add validation callbacks for new parameters
3. Update tests in `tests/unit/test_cli.py`
4. Ensure JSON output format remains stable for agents

### Working with the Database

- Database file: `bananagen.db` (SQLite)
- Schema managed in `bananagen/db.py`
- API keys stored encrypted in `api_providers` table
- Generation history in `generations` table

## Important Files

- `pyproject.toml`: Project configuration and dependencies
- `bananagen/cli.py`: All CLI command definitions
- `bananagen/core.py`: Core generation logic
- `bananagen/api.py`: REST API endpoints
- `tests/unit/test_cli.py`: CLI test coverage
- `.github/copilot-instructions.md`: Additional context for AI assistants

## Tips for Development

1. **TDD Approach**: Tests are written first and should fail initially
2. **Mock Mode**: Set `NANO_BANANA_API_KEY=mock_key` for testing without real API
3. **JSON Output**: Use `--json` flag for stable, parseable output
4. **Validation**: All inputs validated with Click callbacks before processing
5. **Logging**: Use `--log-level DEBUG` to troubleshoot issues
6. **Provider Configuration**: Use `configure` command for interactive API setup

## Agent Integration

The tool is designed for seamless integration with coding agents:

```bash
# Quick placeholder for layout
python -m bananagen placeholder --width 800 --height 600 --out header.png

# Generate with AI (returns JSON with job ID)
python -m bananagen generate --prompt "Professional header" --out final.png --json

# Check status
python -m bananagen status <job-id> --json

# Batch processing
python -m bananagen batch --list jobs.json --json
```

All commands support `--json` flag for structured output suitable for parsing by automated tools.
