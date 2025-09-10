from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class APIProvider:
    VALID_AUTH_TYPES = ("api_key", "bearer", "oauth")

    id: Optional[int] = None
    name: str
    display_name: str
    endpoint_url: str
    auth_type: str = "api_key"
    model_name: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.auth_type not in self.VALID_AUTH_TYPES:
            raise ValueError(f"Invalid auth_type '{self.auth_type}'. Must be one of {self.VALID_AUTH_TYPES}")

    @classmethod
    def is_valid_auth_type(cls, auth_type: str) -> bool:
        return auth_type in cls.VALID_AUTH_TYPES

  