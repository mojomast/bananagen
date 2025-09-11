from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from bananagen.db import Database
import uuid


@dataclass
class APIProvider:
    VALID_AUTH_TYPES = ("api_key", "bearer", "oauth")

    name: str
    endpoint: str
    model: str = ""
    base_url: str = ""
    settings: Optional[Dict[str, Any]] = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    id: Optional[str] = None

    def __post_init__(self):
        self._validate_keys()

    def _validate_keys(self):
        """Validate that required string keys are non-empty."""
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if not self.endpoint or not isinstance(self.endpoint, str):
            raise ValueError("endpoint must be a non-empty string")
        if not self.base_url or not isinstance(self.base_url, str):
            raise ValueError("base_url must be a non-empty string")
        if not self.model or not isinstance(self.model, str):
            raise ValueError("model must be a non-empty string")

    @classmethod
    def create(cls, db: Database, name: str, endpoint: str, model: str, base_url: str, settings: Optional[Dict[str, Any]] = None) -> 'APIProvider':
        """Create a new API provider."""
        provider = cls(
            name=name.strip(),
            endpoint=endpoint.strip(),
            model=model.strip(),
            base_url=base_url.strip(),
            settings=settings or {}
        )
        provider.save(db)
        return provider

    def save(self, db: Database):
        """Save the provider to the database."""
        from bananagen.db import APIProviderRecord
        record = APIProviderRecord(
            id=self.id or str(uuid.uuid4()),
            name=self.name,
            display_name=self.name,  # Use name as display_name for simplicity
            endpoint_url=self.endpoint,  # Map endpoint to endpoint_url
            auth_type="api_key",  # Default
            model_name=self.model,
            base_url=self.base_url,
            settings=self.settings,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
        db.save_api_provider(record)
        self.id = record.id

    @classmethod
    def load(cls, db: Database, provider_id: str) -> Optional['APIProvider']:
        """Load a provider from the database."""
        record = db.get_api_provider(provider_id)
        if not record:
            return None
        provider = cls(
            id=record.id,
            name=record.name,
            endpoint=record.endpoint_url,
            model=record.model_name or "",
            base_url=record.base_url or record.endpoint_url,  # Fallback to endpoint_url if no base_url
            settings=record.settings or {},
            is_active=record.is_active,
            created_at=record.created_at,
            updated_at=record.updated_at
        )
        provider._validate_keys()
        return provider

    @classmethod
    def list_active(cls, db: Database) -> List['APIProvider']:
        """List all active providers."""
        records = db.list_active_api_providers()
        providers = []
        for record in records:
            provider = cls(
                id=record.id,
                name=record.name,
                endpoint=record.endpoint_url,
                model=record.model_name or "",
                base_url=record.base_url or record.endpoint_url,
                settings=record.settings or {},
                is_active=record.is_active,
                created_at=record.created_at,
                updated_at=record.updated_at
            )
            try:
                provider._validate_keys()
                providers.append(provider)
            except ValueError:
                # Skip invalid providers
                pass
        return providers

    @classmethod
    def is_valid_auth_type(cls, auth_type: str) -> bool:
        return auth_type in cls.VALID_AUTH_TYPES