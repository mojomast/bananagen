import pytest
from datetime import datetime
from bananagen.db import Database
from bananagen.models.api_provider import APIProvider
import tempfile
import os


@pytest.fixture
def test_db():
    """Create a test database in file."""
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db = Database(path)
    def cleanup():
        if os.path.exists(path):
            os.unlink(path)
    import atexit
    atexit.register(cleanup)
    return db


def test_api_provider_creation(test_db):
    """Test creating an API provider."""
    provider = APIProvider.create(
        db=test_db,
        name="OpenRouter",
        endpoint="https://api.openrouter.ai/v1/chat/completions",
        model="gpt-3.5-turbo",
        base_url="https://api.openrouter.ai"
    )
    assert provider.name == "OpenRouter"
    assert provider.endpoint == "https://api.openrouter.ai/v1/chat/completions"
    assert provider.model == "gpt-3.5-turbo"
    assert provider.base_url == "https://api.openrouter.ai"
    assert provider.settings == {}


def test_api_provider_validation():
    """Test validation of required fields."""
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        APIProvider(
            name="",
            endpoint="https://api.example.com",
            model="model1",
            base_url="https://api.example.com"
        )
    
    with pytest.raises(ValueError, match="endpoint must be a non-empty string"):
        APIProvider(
            name="Provider",
            endpoint="",
            model="model1",
            base_url="https://api.example.com"
        )


def test_save_and_load_provider(test_db):
    """Test saving and loading a provider from database."""
    provider = APIProvider(
        name="Test Provider",
        endpoint="https://api.test.com/v1/generate",
        model="test-model",
        base_url="https://api.test.com"
    )

    provider.save(test_db)
    assert provider.id is not None

    loaded = APIProvider.load(test_db, provider.id)
    assert loaded is not None
    assert loaded.name == provider.name
    assert loaded.endpoint == provider.endpoint
    assert loaded.model == provider.model
    assert loaded.base_url == provider.base_url
    assert loaded.settings == provider.settings


def test_list_active_providers(test_db):
    """Test listing active providers."""
    provider = APIProvider.create(
        db=test_db,
        name="Active Provider",
        endpoint="https://api.active.com",
        model="active-model",
        base_url="https://api.active.com"
    )

    active_providers = APIProvider.list_active(test_db)
    assert len(active_providers) >= 1
    assert any(p.name == "Active Provider" for p in active_providers)