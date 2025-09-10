# Data Model: Add API Support for OpenRouter and Requesty Gemini 2.5 Flash

## Overview
This feature extends the existing SQLite database schema to support multiple AI API providers for image generation. The data model maintains backward compatibility while adding flexibility for provider management and configuration.

## Entities

### API Provider
Represents a supported AI API service for image generation.

**Fields**:
- `id`: UUID (primary key) - Unique identifier
- `name`: VARCHAR(50) NOT NULL - Provider name (e.g., 'gemini', 'openrouter', 'requesty')
- `display_name`: VARCHAR(100) NOT NULL - Human-readable name (e.g., 'Google Gemini', 'OpenRouter', 'Requesty')
- `endpoint_url`: VARCHAR(500) NOT NULL - Base API endpoint URL
- `auth_type`: VARCHAR(20) NOT NULL - Authentication method ('bearer', 'api_key', 'oauth')
- `model_name`: VARCHAR(100) - Default model to use (e.g., 'gemini-2.5-flash')
- `is_active`: BOOLEAN DEFAULT TRUE - Whether provider is enabled
- `created_at`: DATETIME DEFAULT CURRENT_TIMESTAMP
- `updated_at`: DATETIME DEFAULT CURRENT_TIMESTAMP

**Validation Rules**:
- `name` must be unique and lowercase
- `endpoint_url` must be valid URL format
- `auth_type` must be one of supported types

**Relationships**:
- One-to-many with API Key (a provider can have multiple keys for different users/environments)

### API Key
Stores encrypted API credentials for providers.

**Fields**:
- `id`: UUID (primary key) - Unique identifier
- `provider_id`: UUID NOT NULL (foreign key to api_providers.id)
- `key_value`: TEXT NOT NULL - Encrypted API key value
- `environment`: VARCHAR(50) DEFAULT 'default' - Environment identifier (dev, prod, etc.)
- `is_active`: BOOLEAN DEFAULT TRUE - Whether key is active
- `last_used_at`: DATETIME - Timestamp of last API call
- `created_at`: DATETIME DEFAULT CURRENT_TIMESTAMP
- `updated_at`: DATETIME DEFAULT CURRENT_TIMESTAMP

**Validation Rules**:
- `key_value` must not be empty
- `provider_id` must reference existing provider
- Encryption: Use Fernet symmetric encryption with project-specific key

**Relationships**:
- Many-to-one with API Provider

## Database Schema Changes

### New Tables

```sql
CREATE TABLE api_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    auth_type TEXT NOT NULL,
    model_name TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    key_value TEXT NOT NULL,
    environment TEXT DEFAULT 'default',
    is_active BOOLEAN DEFAULT 1,
    last_used_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES api_providers(id)
);

-- Indexes for performance
CREATE INDEX idx_api_providers_name ON api_providers(name);
CREATE INDEX idx_api_keys_provider_id ON api_keys(provider_id);
CREATE INDEX idx_api_keys_environment ON api_keys(environment);
```

### Migration Strategy
- Create new tables without affecting existing schema
- Populate with default Gemini provider data
- Existing functionality continues to work via backward compatibility
- New providers can be added via configuration

## State Transitions

### Provider States
- **Inactive**: `is_active = FALSE` - Provider disabled, no API calls allowed
- **Active**: `is_active = TRUE` - Provider available for use

### Key States
- **Inactive**: `is_active = FALSE` - Key disabled, authentication will fail
- **Active**: `is_active = TRUE` - Key available for authentication
- **Used**: `last_used_at` updated on successful API call

## Security Considerations
- API keys stored encrypted using Fernet (AES 128)
- Encryption key derived from project configuration
- Keys never logged or exposed in error messages
- Access control: Only authenticated users can manage keys
- Audit trail: Track key usage via `last_used_at`

## Integration Points
- **CLI Configuration**: Interactive setup updates these tables
- **Adapter Layer**: Queries active providers and keys for API calls
- **Error Handling**: Invalid keys marked inactive automatically
- **Monitoring**: Track usage patterns and provider reliability
