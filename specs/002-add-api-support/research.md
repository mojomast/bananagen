# Research Findings: Add API Support for OpenRouter and Requesty Gemini 2.5 Flash

## OpenRouter API Integration

**Decision**: Use OpenRouter's REST API for image generation with Gemini 2.5 Flash model.

**Rationale**: 
- OpenRouter provides unified access to multiple AI providers including Google/Gemini
- Supports image generation capabilities
- Standard REST API with JSON request/response
- Handles authentication via API key
- Allows cost-effective access to Gemini models

**Alternatives Considered**:
- Direct Google AI Studio API: More complex authentication, potential rate limits
- Other aggregators: OpenRouter has good documentation and reliability

**Integration Approach**:
- Endpoint: `https://openrouter.ai/api/v1/images/generations`
- Authentication: Bearer token in Authorization header
- Request format: JSON with model, prompt, size parameters
- Response: JSON with generated image URL or base64 data

## Requesty API Integration

**Decision**: Assume Requesty is a custom or specific provider with similar API structure to OpenRouter.

**Rationale**: 
- Maintain consistency with existing adapter pattern
- Support extensible architecture for future providers
- Use similar authentication and request patterns

**Alternatives Considered**:
- If Requesty is not a real provider, consider Anthropic Claude or other image-capable models
- Direct integration vs unified adapter approach

**Integration Approach**:
- Research needed: Confirm Requesty API endpoints and authentication
- Assume REST API with JSON format
- Implement as separate adapter class

## Interactive Setup Script/Option

**Decision**: Add `--configure` flag to CLI with interactive prompts for API keys.

**Rationale**: 
- User-friendly configuration without editing config files
- Secure input handling (no echo for sensitive data)
- Optional: Can still use environment variables or config files
- Follows existing CLI patterns in Bananagen

**Alternatives Considered**:
- Web-based configuration UI: Overkill for CLI tool
- Config file only: Less user-friendly
- Environment variables only: Harder for new users

**Implementation Approach**:
- Use Python's `getpass` for secure key input
- Store in SQLite or config file with encryption
- Validate keys before saving
- Provide `--list-providers` to show configured providers

## Multi-Provider Architecture

**Decision**: Extend existing `gemini_adapter.py` to support multiple providers via strategy pattern.

**Rationale**: 
- Maintains backward compatibility
- Clean separation of concerns
- Easy to add new providers
- Consistent error handling and logging

**Alternatives Considered**:
- Separate modules for each provider: Code duplication
- Single monolithic adapter: Harder to maintain
- Plugin system: Over-engineering for 2-3 providers

**Integration Approach**:
- Base `ProviderAdapter` class with common interface
- Specific implementations: `GeminiAdapter`, `OpenRouterAdapter`, `RequestyAdapter`
- Factory pattern for provider selection
- Shared utilities for HTTP requests, error handling

## Best Practices for API Integration

**Decision**: Implement exponential backoff, rate limiting, and comprehensive error handling.

**Rationale**: 
- Robust handling of API failures and rate limits
- Good user experience with clear error messages
- Follows existing async patterns in Bananagen

**Alternatives Considered**:
- Simple retry: May not handle rate limits well
- No retry: Poor reliability

**Implementation Approach**:
- Use `aiohttp` with timeout and retry logic
- Structured logging for API calls
- Graceful degradation when providers unavailable

## Configuration Management

**Decision**: Store API keys in SQLite database with optional encryption.

**Rationale**: 
- Consistent with existing metadata storage
- Secure storage with encryption option
- Easy retrieval and management

**Alternatives Considered**:
- Environment variables: Not persistent
- Config files: Less secure, harder to manage multiple keys

**Implementation Approach**:
- New table in existing DB: `api_providers`
- Fields: provider_name, api_key (encrypted), endpoint_url
- CLI commands: `bananagen configure --provider openrouter`
