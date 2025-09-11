import pytest
from datetime import datetime
from bananagen.db import Database
from bananagen.models.api_key import APIKey
from bananagen.models.api_provider import APIProvider
from bananagen.core import encrypt_key, decrypt_key
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


@pytest.fixture
def test_provider(test_db):
    """Create a test API provider."""
    provider = APIProvider.create(
        db=test_db,
        name="Test Provider",
        endpoint="https://api.test.com",
        model="test-model",
        base_url="https://api.test.com"
    )
    return provider


def test_api_key_creation_with_encryption(test_db, test_provider):
    """Test creating an API key with encryption."""
    plain_key = "sk-test123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=plain_key,
        description="Test API key"
    )

    assert api_key.id is not None
    assert api_key.provider_id == test_provider.id
    assert api_key.description == "Test API key"
    assert api_key.is_active is True
    assert len(api_key.encrypted_key) > 0
    assert api_key.encrypted_key != plain_key  # Should be encrypted

    # Test decryption
    decrypted = api_key.decrypt_key()
    assert decrypted == plain_key


def test_api_key_validation():
    """Test validation of required fields."""
    with pytest.raises(ValueError, match="encrypted_key cannot be empty"):
        APIKey(
            id="test-id",
            provider_id="provider-123",
            encrypted_key="",  # Empty key should raise error
            environment="production"
        )

    with pytest.raises(ValueError, match="provider_id cannot be empty"):
        APIKey(
            id="test-id",
            provider_id="",  # Empty provider_id should raise error
            encrypted_key="encrypted-key",
            environment="production"
        )


def test_api_key_environment_validation():
    """Test environment validation."""
    with pytest.raises(ValueError, match="Invalid environment 'invalid'"):
        APIKey(
            id="test-id",
            provider_id="provider-123",
            encrypted_key="encrypted-key",
            environment="invalid"
        )

    # Valid environments should work
    api_key = APIKey(
        id="test-id",
        provider_id="provider-123",
        encrypted_key="encrypted-key",
        environment="staging"
    )
    assert api_key.environment == "staging"


def test_save_and_load_api_key(test_db, test_provider):
    """Test saving and loading an API key from database."""
    plain_key = "sk-test123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=plain_key,
        description="Test key"
    )

    loaded = APIKey.load(test_db, api_key.id)
    assert loaded is not None
    assert loaded.id == api_key.id
    assert loaded.provider_id == api_key.provider_id
    assert loaded.description == api_key.description
    assert loaded.is_active == api_key.is_active
    assert loaded.encrypted_key == api_key.encrypted_key

    # Test decryption of loaded key
    decrypted = loaded.decrypt_key()
    assert decrypted == plain_key


def test_api_key_rotation(test_db, test_provider):
    """Test API key rotation."""
    old_plain_key = "sk-old123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=old_plain_key,
        description="Key to rotate"
    )

    old_key = api_key.encrypted_key
    new_plain_key = "sk-new123456789"
    api_key.rotate_key(test_db, new_plain_key)

    # Key should be updated
    assert api_key.encrypted_key != old_key
    assert api_key.decrypt_key() == new_plain_key
    assert api_key.last_used_at is None  # Should be reset on rotation

    # Reload from database to verify persistence
    loaded = APIKey.load(test_db, api_key.id)
    assert loaded.decrypt_key() == new_plain_key


def test_api_key_deactivation(test_db, test_provider):
    """Test API key deactivation."""
    plain_key = "sk-test123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=plain_key
    )

    api_key.deactivate(test_db)
    assert api_key.is_active is False

    # Reload from database to verify persistence
    loaded = APIKey.load(test_db, api_key.id)
    assert loaded.is_active is False


def test_api_key_reactivation(test_db, test_provider):
    """Test API key reactivation."""
    plain_key = "sk-test123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=plain_key
    )

    api_key.deactivate(test_db)
    assert api_key.is_active is False

    api_key.reactivate(test_db)
    assert api_key.is_active is True

    # Reload from database to verify persistence
    loaded = APIKey.load(test_db, api_key.id)
    assert loaded.is_active is True


def test_link_to_provider(test_db, test_provider):
    """Test linking API key to a different provider."""
    plain_key = "sk-test123456789"
    api_key = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key=plain_key
    )

    # Create another provider
    new_provider = APIProvider.create(
        db=test_db,
        name="New Provider",
        endpoint="https://new-test.com",
        model="new-model",
        base_url="https://new-test.com"
    )

    old_provider_id = api_key.provider_id
    old_updated_at = api_key.updated_at

    api_key.link_to_provider(new_provider.id)

    assert api_key.provider_id == new_provider.id
    assert api_key.provider_id != old_provider_id
    assert api_key.updated_at != old_updated_at


def test_environment_filtering(test_db, test_provider):
    """Test that API keys are created with correct environment."""
    api_key_prod = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key="sk-prod123",
        environment="production"
    )

    api_key_staging = APIKey.create(
        db=test_db,
        provider_id=test_provider.id,
        plain_key="sk-staging123",
        environment="staging"
    )

    assert api_key_prod.environment == "production"
    assert api_key_staging.environment == "staging"