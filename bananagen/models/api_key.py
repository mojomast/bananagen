from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class APIKey:
    VALID_ENVIRONMENTS = ("development", "staging", "production")

    id: Optional[int] = None
    provider_id: int
    key_value: str
    environment: str = "production"
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.environment not in self.VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid environment '{self.environment}'. Must be one of {self.VALID_ENVIRONMENTS}")

    @classmethod
    def is_valid_environment(cls, environment: str) -> bool:
        return environment in cls.VALID_ENVIRONMENTS