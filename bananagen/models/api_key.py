from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from bananagen.db import Database
from bananagen.core import encrypt_key, decrypt_key
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class APIKey:
    VALID_ENVIRONMENTS = ("development", "staging", "production")

    provider_id: str  # Foreign key to API Provider
    encrypted_key: str
    id: Optional[str] = None
    description: Optional[str] = None
    environment: str = "production"
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.environment not in self.VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid environment '{self.environment}'. Must be one of {self.VALID_ENVIRONMENTS}")
        if not self.encrypted_key:
            raise ValueError("encrypted_key cannot be empty")
        if not self.provider_id:
            raise ValueError("provider_id cannot be empty")

    @classmethod
    def create(cls, db: Database, provider_id: str, plain_key: str, description: Optional[str] = None, environment: str = "production") -> 'APIKey':
        """Create a new API key with encryption."""
        encrypted_key = encrypt_key(plain_key)
        api_key = cls(
            provider_id=provider_id,
            encrypted_key=encrypted_key,
            description=description,
            environment=environment
        )
        api_key.save(db)
        return api_key

    @classmethod
    def load(cls, db: Database, key_id: str) -> Optional['APIKey']:
        """Load an API key from the database."""
        from bananagen.db import APIKeyRecord
        record = db.get_api_key(key_id)
        if not record:
            return None
        api_key = cls(
            id=record.id,
            provider_id=record.provider_id,
            encrypted_key=record.key_value,
            description=record.description,
            environment=record.environment,
            is_active=record.is_active,
            last_used_at=record.last_used_at,
            created_at=record.created_at,
            updated_at=record.updated_at
        )
        return api_key

    def save(self, db: Database):
        """Save the API key to the database."""
        from bananagen.db import APIKeyRecord
        record = APIKeyRecord(
            id=self.id or str(uuid.uuid4()),
            provider_id=self.provider_id,
            key_value=self.encrypted_key,
            description=self.description,
            environment=self.environment,
            is_active=self.is_active,
            last_used_at=self.last_used_at,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
        db.save_api_key(record)
        self.id = record.id
        logger.info("API key saved", extra={"key_id": self.id, "provider_id": self.provider_id})

    def decrypt_key(self) -> str:
        """Decrypt the API key."""
        return decrypt_key(self.encrypted_key)

    @classmethod
    def is_valid_environment(cls, environment: str) -> bool:
        return environment in cls.VALID_ENVIRONMENTS

    def link_to_provider(self, provider_id: str):
        """Update the provider_id linkage."""
        self.provider_id = provider_id
        self.updated_at = datetime.now()

    def rotate_key(self, db: Database, new_plain_key: str):
        """Rotate the API key with a new value."""
        self.encrypted_key = encrypt_key(new_plain_key)
        self.updated_at = datetime.now()
        self.last_used_at = None  # Reset last used time on rotation
        self.save(db)
        logger.info("API key rotated", extra={"key_id": self.id})

    def deactivate(self, db: Database):
        """Deactivate the API key."""
        self.is_active = False
        self.updated_at = datetime.now()
        self.save(db)
        logger.info("API key deactivated", extra={"key_id": self.id})

    def reactivate(self, db: Database):
        """Reactivate the API key."""
        self.is_active = True
        self.updated_at = datetime.now()
        self.save(db)
        logger.info("API key reactivated", extra={"key_id": self.id})