# Bananagen

A CLI tool for generating image assets using AI models with support for placeholders, batch processing, and multiple AI providers including Gemini, OpenRouter, and more.

## Features

- 🚀 **Fast Placeholder Generation** - Create temporary images instantly without API calls
- 🎨 **Multi-Provider AI Support** - Gemini, OpenRouter, and extensible adapter system
- 📦 **Batch Processing** - Process multiple images concurrently with rate limiting
- 🔍 **Smart Scanning** - Automatically scan and replace placeholder images in projects
- 📊 **HTTP API** - RESTful API with async processing and status tracking
- 🗂️ **Intelligent Caching** - SHA256-based caching prevents duplicate generations
- 🛡️ **Validation & Error Handling** - Comprehensive input validation and retry logic
- 📝 **Structured Logging** - JSON-formatted logs with rich metadata

## Installation

### Prerequisites

- Python 3.10+
- API key for your chosen provider (Gemini, OpenRouter, etc.)

### Install from PyPI

```bash
pip install bananagen
```

### Install with Poetry

```bash
git clone https://github.com/mojomast/bananagen.git
cd bananagen
poetry install
```

## Quick Start

### 1. Configure Your Provider

Create a `.env` file in your project root:

```bash
# For Gemini via Google AI Studio
GEMINI_API_KEY=your_gemini_api_key_here

# For OpenRouter (supports multiple models)
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=google/gemini-2.5-flash-image-preview

# Optional: Configure logging
BANANAGEN_LOG_LEVEL=INFO
```

### 2. Generate Images

```bash
# Generate a placeholder (instant, no API calls)
bananagen generate --width 512 --height 512 --prompt "placeholder" --out my_image.png

# Generate with AI
bananagen generate --prompt "A beautiful sunset over mountains" --out sunset.png

# Use specific provider
bananagen generate --provider openrouter --prompt "A futuristic city" --out city.png

# Batch processing
echo '[{"prompt": "A cat", "output_path": "cat.png"}, {"prompt": "A dog", "output_path": "dog.png"}]' > jobs.json
bananagen batch --list jobs.json
```

## CLI Commands

### Core Commands

```bash
# Generate single image
bananagen generate --prompt "Description" --out image.png [--width 512] [--height 512]

# Batch processing
bananagen batch --list jobs.json [--concurrency 2]

# Scan and replace placeholders
bananagen scan --root ./project [--replace]

# Start HTTP API server
bananagen serve [--port 8080] [--host 0.0.0.0]

# Configure API providers
bananagen configure --provider openrouter

# Check status
bananagen status <job_id>
```

### Provider Support

Bananagen supports multiple AI providers through an adapter system:

- **Gemini** - Google's multimodal AI (direct API)
- **OpenRouter** - Access to multiple models including Gemini, DALL-E, Stable Diffusion
- **Extensible** - Easy to add new providers

## API Documentation

### Start the Server

```bash
bananagen serve --port 8080
```

### Endpoints

#### POST `/generate`

Generate a single image.

```json
{
  "prompt": "A beautiful landscape",
  "width": 512,
  "height": 512,
  "output_path": "./landscape.png",
  "provider": "openrouter"
}
```

#### POST `/batch`

Process multiple images.

```json
{
  "jobs": [
    {"prompt": "A red rose", "output_path": "./rose.png"},
    {"prompt": "A blue sky", "output_path": "./sky.png"}
  ]
}
```

#### GET `/status/{job_id}`

Check job status and get results.

## Configuration

### Provider Setup

Use the interactive configuration tool:

```bash
bananagen configure --provider openrouter
```

This will:
1. Prompt for your API key
2. Test the connection
3. Save encrypted credentials
4. Set up default model preferences

### Environment Variables

```bash
# Primary configuration
GEMINI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-2.5-flash-image-preview

# Optional settings
BANANAGEN_LOG_LEVEL=INFO
BANANAGEN_DEFAULT_WIDTH=512
BANANAGEN_DEFAULT_HEIGHT=512
```

## Development

### Project Structure

```
bananagen/
├── bananagen/           # Core package
│   ├── adapters/        # Provider adapters
│   ├── cli.py          # Command-line interface
│   ├── core.py         # Core functionality
│   ├── api.py          # HTTP API
│   └── db.py           # Database operations
├── tests/              # Test suite
├── docs/               # Documentation
└── scripts/            # Utility scripts
```

### Running Tests

```bash
poetry run pytest
```

### Adding New Providers

1. Create adapter in `bananagen/adapters/`
2. Implement the `call_gemini` interface
3. Add provider configuration
4. Update CLI and API integration

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### Version 0.2.0
- Added OpenRouter adapter support
- Multi-provider configuration system
- Interactive provider setup
- Enhanced batch processing
- Improved error handling and retry logic

### Version 0.1.0
- Initial release with Gemini support
- CLI interface
- Placeholder generation
- Basic HTTP API
