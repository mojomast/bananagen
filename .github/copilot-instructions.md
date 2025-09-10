# Copilot Instructions for Bananagen

## Project Overview
Bananagen is a CLI tool for generating image assets using Gemini 2.5 Flash. It creates placeholders, processes them with AI prompts, supports batch workflows, and provides agent-friendly interfaces.

## Key Components
- `bananagen/` package: Core functionality
- CLI subcommands: generate, batch, scan, serve, configure
- SQLite database: Metadata storage and API provider configuration
- Optional HTTP API: For programmatic access
- Multi-provider support: Gemini, OpenRouter, Requesty APIs

## Development Guidelines
- Use Python 3.10+
- Follow TDD: Write tests first
- Use Click for CLI
- Async for concurrency
- Structured logging
- Dry-run for safety

## Common Patterns
- Placeholder generation: Use Pillow to create blank images
- Gemini calls: Async HTTP with aiohttp
- Multi-provider adapters: Strategy pattern for different AI APIs
- Metadata: Store in SQLite with UUIDs
- API configuration: Interactive setup with encrypted key storage
- Error handling: Exponential backoff for retries
- Agent integration: JSON APIs with stable schemas

## CLI Examples
```bash
bananagen generate --width 1024 --height 768 --prompt "A banana" --out banana.png
bananagen generate --provider openrouter --prompt "A robot" --out robot.png
bananagen configure --provider openrouter  # Interactive API setup
bananagen batch --list jobs.json
bananagen scan --root . --replace
```

## API Endpoints
- POST /generate: Queue image generation
- POST /batch: Queue batch jobs
- GET /status/{id}: Check status
- POST /scan: Scan and replace

## Testing
- Use pytest
- Mock Gemini API for unit tests
- Integration tests for full workflows
- Contract tests for API schemas

## Deployment
- Package with Poetry
- Cross-platform support
- Environment vars for API keys
- Safe defaults with confirmations
