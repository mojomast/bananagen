# Quickstart: Add API Support for OpenRouter and Requesty Gemini 2.5 Flash

## Overview
This feature adds support for multiple AI providers (OpenRouter and Requesty) for image generation in Bananagen, in addition to the existing Gemini support. It includes an optional interactive setup for easy API configuration.

## Prerequisites
- Bananagen installed and configured
- API keys for desired providers (OpenRouter, Requesty)
- Internet connection for API calls

## Step 1: Configure API Providers

### Option A: Interactive Setup (Recommended)
```bash
# Configure OpenRouter
bananagen configure --provider openrouter

# Configure Requesty
bananagen configure --provider requesty
```

The interactive setup will:
- Prompt for your API key securely (input hidden)
- Ask for confirmation
- Validate the key format
- Store encrypted credentials

### Option B: Non-Interactive Setup
```bash
# Set environment variables
export OPENROUTER_API_KEY="your-openrouter-key"
export REQUESTY_API_KEY="your-requesty-key"

# Or pass directly (less secure)
bananagen configure --provider openrouter --api-key "your-key"
```

## Step 2: Generate Images with Different Providers

### Using OpenRouter
```bash
bananagen generate \
  --provider openrouter \
  --prompt "A futuristic cityscape at sunset" \
  --width 1024 \
  --height 768 \
  --out cityscape.png
```

### Using Requesty
```bash
bananagen generate \
  --provider requesty \
  --prompt "A serene mountain landscape" \
  --width 800 \
  --height 600 \
  --out mountains.png
```

### Using Default (Gemini)
```bash
bananagen generate \
  --prompt "A banana on a beach" \
  --out banana.png
```

## Step 3: Batch Processing with Providers

Create a batch file (`batch.json`):
```json
[
  {
    "provider": "openrouter",
    "prompt": "A robot painting a picture",
    "width": 1024,
    "height": 1024,
    "output": "robot-artist.png"
  },
  {
    "provider": "requesty",
    "prompt": "A underwater coral reef",
    "width": 800,
    "height": 600,
    "output": "coral-reef.png"
  }
]
```

Run the batch:
```bash
bananagen batch --file batch.json
```

## Step 4: Verify Configuration

Check configured providers:
```bash
bananagen configure --list
```

Expected output:
```
Configured Providers:
- gemini: Google Gemini 2.5 Flash (default)
- openrouter: OpenRouter API
- requesty: Requesty API
```

## Troubleshooting

### Provider Not Configured
```
Error: Provider 'openrouter' not configured. Run 'bananagen configure --provider openrouter' to set up API key.
```
**Solution**: Run the configure command for the missing provider.

### Invalid API Key
```
Error: API call failed - Invalid API key
```
**Solution**:
1. Reconfigure with correct key: `bananagen configure --provider <provider>`
2. Check key validity on provider's website
3. Ensure key has necessary permissions

### Network Issues
```
Error: API call failed - Connection timeout
```
**Solution**:
- Check internet connection
- Try again later (may be temporary provider issue)
- Switch to different provider if available

### Unsupported Provider
```
Error: Unsupported provider 'unknown'
```
**Solution**: Use one of the supported providers: `gemini`, `openrouter`, `requesty`

## Advanced Usage

### Environment-Specific Configuration
```bash
# Configure for development environment
bananagen configure --provider openrouter --env dev

# Configure for production
bananagen configure --provider openrouter --env prod
```

### Checking Provider Status
```bash
bananagen status --providers
```

Shows:
- Configured providers
- Last used timestamp
- Success/failure rates
- Rate limit status

## Next Steps
- Explore batch processing for multiple images
- Integrate with existing workflows
- Monitor usage and costs across providers
- Consider adding more providers in the future

## Support
If you encounter issues:
1. Check this quickstart guide
2. Verify API keys and network connectivity
3. Review error messages for specific guidance
4. Check provider documentation for API changes
