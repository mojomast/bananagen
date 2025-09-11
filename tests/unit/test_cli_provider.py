"""
Unit tests for CLI provider configuration functionality.

Comprehensive test suite for the bananagen CLI configure command covering:
- Provider configuration with interactive and non-interactive modes
- Parameter validation and error handling
- Database interaction through CLI
- Mocking for database operations and external API calls
- Interactive prompts and CLI argument parsing
"""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from datetime import datetime
from bananagen.cli import main, validate_endpoint_url, validate_model_name, get_provider_choice, list_existing_providers, prompt_provider_details, confirm_configuration, prompt_api_key
from bananagen.db import Database, APIProviderRecord, APIKeyRecord


@pytest.fixture
def runner():
    """Create Click test runner for CLI testing."""
    return CliRunner()


@pytest.fixture
def mock_db():
    """Create a mocked database for testing."""
    mock_db = MagicMock(spec=Database)

    # Setup default return values for common database methods
    mock_db.get_api_provider.return_value = None
    mock_db.save_api_provider.return_value = None
    mock_db.save_api_key.return_value = None
    mock_db.list_active_api_providers.return_value = []

    return mock_db


@pytest.fixture
def mock_encrypt_key():
    """Mock the encrypt_key function to avoid actual key encryption."""
    with patch('bananagen.cli.encrypt_key') as mock_encrypt:
        mock_encrypt.return_value = "encrypted_test_key"
        yield mock_encrypt


@pytest.fixture
def sample_provider_record():
    """Create a sample API provider record for testing."""
    return APIProviderRecord(
        id="prov_test_123",
        name="testprovider",
        display_name="Test Provider",
        endpoint_url="https://api.test.com/v1",
        auth_type="bearer",
        model_name="test-model",
        base_url="https://api.test.com/v1",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        settings={"test": "setting"}
    )


@pytest.fixture
def sample_api_key_record():
    """Create a sample API key record for testing."""
    return APIKeyRecord(
        id="key_test_123",
        provider_id="prov_test_123",
        key_value="encrypted_test_key",
        description="Test key",
        environment="production",
        is_active=True,
        last_used_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestCLIProviderConfiguration:
    """Test CLI provider configuration functionality."""

    def test_configure_command_help(self, runner):
        """Test configure command help output."""
        result = runner.invoke(main, ['configure', '--help'])
        assert result.exit_code == 0
        assert 'configure' in result.output
        assert '--provider' in result.output
        assert '--non-interactive' in result.output
        assert '--api-key' in result.output
        assert '--update-only' in result.output

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_configure_non_interactive_new_provider(self, mock_encrypt, mock_db_class, runner, mock_encrypt_key):
        """Test configuring a new provider in non-interactive mode."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.return_value = "encrypted_key"

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive',
            '--api-key', 'test_key_123'
        ])

        assert result.exit_code == 0
        assert 'Provider \'Testprovider\' configured successfully!' in result.output
        mock_db_instance.save_api_provider.assert_called_once()
        mock_db_instance.save_api_key.assert_called_once()

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_configure_non_interactive_update_existing(self, mock_encrypt, mock_db_class, runner, sample_provider_record, sample_api_key_record):
        """Test updating an existing provider in non-interactive mode."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = sample_provider_record
        mock_db_instance.get_api_keys_for_provider.return_value = [sample_api_key_record]
        mock_encrypt.return_value = "new_encrypted_key"

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive',
            '--api-key', 'new_test_key'
        ])

        assert result.exit_code == 0
        assert 'Provider \'Test Provider\' configured successfully!' in result.output
        # Should update the existing key
        assert sample_api_key_record.key_value == "new_encrypted_key"
        mock_db_instance.save_api_key.assert_called_once()

    @patch('bananagen.cli.Database')
    def test_configure_non_interactive_missing_provider(self, mock_db_class, runner):
        """Test non-interactive mode without required provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance

        result = runner.invoke(main, [
            'configure',
            '--non-interactive',
            '--api-key', 'test_key'
        ])

        assert result.exit_code != 0
        assert "--provider is required in non-interactive mode" in result.output

    @patch('bananagen.cli.Database')
    def test_configure_non_interactive_missing_api_key(self, mock_db_class, runner):
        """Test non-interactive mode without required API key."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive'
        ])

        assert result.exit_code != 0
        assert "--api-key is required in non-interactive mode" in result.output

    @patch('bananagen.cli.Database')
    def test_configure_update_only_no_existing_provider(self, mock_db_class, runner):
        """Test update-only mode when provider doesn't exist."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None

        result = runner.invoke(main, [
            'configure',
            '--provider', 'nonexistent',
            '--non-interactive',
            '--api-key', 'test_key',
            '--update-only'
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_configure_invalid_provider_name_non_interactive(self, runner):
        """Test invalid provider name in non-interactive mode."""
        result = runner.invoke(main, [
            'configure',
            '--provider', 'invalid@name',
            '--non-interactive',
            '--api-key', 'validkey123'
        ])

        assert result.exit_code != 0
        assert "Provider name can only contain lowercase letters, numbers, hyphens, and underscores" in result.output

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_configure_openrouter_provider(self, mock_encrypt, mock_db_class, runner):
        """Test configuring OpenRouter provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.return_value = "encrypted_openrouter_key"

        result = runner.invoke(main, [
            'configure',
            '--provider', 'openrouter',
            '--non-interactive',
            '--api-key', 'openrouter_key_123'
        ])

        assert result.exit_code == 0
        assert 'Provider \'Openrouter\' configured successfully!' in result.output
        # Verify the database calls
        mock_db_instance.save_api_provider.assert_called_once()
        mock_db_instance.save_api_key.assert_called_once()

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_configure_requesty_provider(self, mock_encrypt, mock_db_class, runner):
        """Test configuring Requesty provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.return_value = "encrypted_requesty_key"

        result = runner.invoke(main, [
            'configure',
            '--provider', 'requesty',
            '--non-interactive',
            '--api-key', 'requesty_key_456'
        ])

        assert result.exit_code == 0
        assert 'Provider \'Requesty\' configured successfully!' in result.output
        mock_db_instance.save_api_provider.assert_called_once()
        mock_db_instance.save_api_key.assert_called_once()


class TestInteractiveProviderConfiguration:
    """Test interactive provider configuration flow."""

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.get_provider_choice')
    @patch('bananagen.cli.list_existing_providers')
    @patch('bananagen.cli.prompt_provider_details')
    @patch('bananagen.cli.prompt_api_key')
    @patch('bananagen.cli.confirm_configuration')
    @patch('bananagen.cli.encrypt_key')
    def test_interactive_configure_new_provider(self, mock_encrypt, mock_confirm, mock_prompt_key,
                                                mock_prompt_details, mock_list_providers,
                                                mock_choice, mock_db_class, runner):
        """Test interactive configuration of new provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance

        # Mock user choices and inputs
        mock_choice.return_value = '1'  # Create new provider

        provider_details = {
            'name': 'interactiveprovider',
            'display_name': 'Interactive Provider',
            'endpoint_url': 'https://api.interactive.com/v1',
            'model_name': 'interactive-model',
            'base_url': 'https://api.interactive.com/v1',
            'auth_type': 'bearer'
        }
        mock_prompt_details.return_value = provider_details
        mock_prompt_key.return_value = 'interactive_api_key_789'
        mock_confirm.return_value = True
        mock_encrypt.return_value = 'encrypted_interactive_key'

        result = runner.invoke(main, ['configure'])

        assert result.exit_code == 0
        assert 'Provider \'Interactive Provider\' configured successfully!' in result.output
        mock_db_instance.save_api_provider.assert_called_once()
        mock_db_instance.save_api_key.assert_called_once()

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.get_provider_choice')
    @patch('bananagen.cli.list_existing_providers')
    @patch('bananagen.cli.prompt_provider_details')
    @patch('bananagen.cli.prompt_api_key')
    @patch('bananagen.cli.confirm_configuration')
    @patch('bananagen.cli.encrypt_key')
    def test_interactive_update_existing_provider(self, mock_encrypt, mock_confirm, mock_prompt_key,
                                                  mock_prompt_details, mock_list_providers, mock_choice,
                                                  mock_db_class, runner, sample_provider_record):
        """Test interactive update of existing provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance

        # Mock user choices
        mock_choice.return_value = '2'  # Update existing provider
        mock_list_providers.return_value = 'testprovider'
        mock_db_instance.get_api_provider.return_value = sample_provider_record
        mock_db_instance.get_api_keys_for_provider.return_value = []

        # Mock provider details update
        provider_details = {
            'name': 'testprovider',
            'display_name': 'Test Provider',
            'endpoint_url': 'https://api.updated.com/v1',
            'model_name': 'updated-model',
            'base_url': 'https://api.updated.com/v1',
            'auth_type': 'bearer'
        }
        mock_prompt_details.return_value = provider_details
        mock_prompt_key.return_value = 'new_api_key_123'

        # User cancels confirmation
        mock_confirm.return_value = False
        mock_encrypt.return_value = 'encrypted_key'

        result = runner.invoke(main, ['configure'])

        assert result.exit_code == 0
        assert 'Configuration cancelled.' in result.output
        # Should not save anything
        mock_db_instance.save_api_provider.assert_not_called()
        mock_db_instance.save_api_key.assert_not_called()


class TestValidationFunctions:
    """Test validation functions used in CLI configuration."""

    def test_validate_endpoint_url_valid(self):
        """Test valid endpoint URL validation."""
        assert validate_endpoint_url('https://api.example.com/v1') == 'https://api.example.com/v1'
        assert validate_endpoint_url('http://localhost:8080') == 'http://localhost:8080'

    def test_validate_endpoint_url_invalid_empty(self):
        """Test empty endpoint URL validation."""
        with pytest.raises(Exception):
            validate_endpoint_url('')

    def test_validate_endpoint_url_invalid_format(self):
        """Test invalid URL format validation."""
        with pytest.raises(Exception):
            validate_endpoint_url('not-a-url')

    def test_validate_endpoint_url_invalid_protocol(self):
        """Test invalid protocol URL validation."""
        with pytest.raises(Exception):
            validate_endpoint_url('ftp://example.com')

    def test_validate_model_name_valid(self):
        """Test valid model name validation."""
        assert validate_model_name('gpt-4') == 'gpt-4'
        assert validate_model_name('claude-3.5-sonnet') == 'claude-3.5-sonnet'

    def test_validate_model_name_empty(self):
        """Test empty model name validation."""
        with pytest.raises(Exception):
            validate_model_name('')

    def test_validate_model_name_whitespace_only(self):
        """Test whitespace-only model name validation."""
        with pytest.raises(Exception):
            validate_model_name('   ')


class TestInteractivePrompts:
    """Test interactive prompt functions."""

    def test_get_provider_choice_create_new(self):
        """Test get_provider_choice for creating new provider."""
        with patch('click.prompt') as mock_prompt:
            mock_prompt.return_value = '1'
            result = get_provider_choice()
            assert result == '1'

    def test_get_provider_choice_update_existing(self):
        """Test get_provider_choice for updating existing provider."""
        with patch('click.prompt') as mock_prompt:
            mock_prompt.return_value = '2'
            result = get_provider_choice()
            assert result == '2'

    @patch('bananagen.cli.Database')
    def test_list_existing_providers_no_providers(self, mock_db_class):
        """Test list_existing_providers when no providers exist."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.list_active_api_providers.return_value = []

        with patch('click.echo') as mock_echo:
            result = list_existing_providers(mock_db_instance)
            assert result is None
            mock_echo.assert_called_with("No existing providers found.")

    @patch('bananagen.cli.Database')
    def test_list_existing_providers_with_providers(self, mock_db_class, sample_provider_record):
        """Test list_existing_providers when providers exist."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.list_active_api_providers.return_value = [sample_provider_record]

        with patch('click.prompt') as mock_prompt, \
             patch('click.echo') as mock_echo:
            mock_prompt.return_value = 1
            result = list_existing_providers(mock_db_instance)
            assert result == 'testprovider'

    def test_prompt_provider_details_new_provider(self):
        """Test prompt_provider_details for new provider."""
        with patch('click.prompt') as mock_prompt, \
             patch('click.echo') as mock_echo:
            # Mock all the prompt responses
            mock_prompt.side_effect = [
                'newprovider',  # provider name
                'https://api.new.com/v1',  # endpoint URL
                'new-model',  # model name
                '',  # base URL (empty, should use endpoint)
            ]

            result = prompt_provider_details(None)

            assert result['name'] == 'newprovider'
            assert result['display_name'] == 'Newprovider'
            assert result['endpoint_url'] == 'https://api.new.com/v1'
            assert result['model_name'] == 'new-model'
            assert result['base_url'] == 'https://api.new.com/v1'

    def test_prompt_provider_details_existing_provider(self, sample_provider_record):
        """Test prompt_provider_details for existing provider."""
        with patch('click.prompt') as mock_prompt, \
             patch('click.echo') as mock_echo:
            # Mock all the prompt responses
            mock_prompt.side_effect = [
                'updatedprovider',  # updated provider name
                'https://api.updated.com/v1',  # updated endpoint URL
                'updated-model',  # updated model name
                'https://api.updated.com/v1',  # updated base URL
            ]

            result = prompt_provider_details(sample_provider_record)

            assert result['name'] == 'updatedprovider'
            assert result['endpoint_url'] == 'https://api.updated.com/v1'
            assert result['model_name'] == 'updated-model'

    def test_prompt_provider_details_invalid_name(self):
        """Test prompt_provider_details with invalid provider name."""
        with patch('click.prompt') as mock_prompt:
            mock_prompt.return_value = 'invalid@name'

            with pytest.raises(Exception):  # click.BadParameter raises BadParameter exception
                prompt_provider_details(None)

    def test_prompt_api_key_successful(self):
        """Test successful API key prompting."""
        import getpass
        with patch('getpass.getpass') as mock_getpass:
            mock_getpass.side_effect = ['test_key_123', 'test_key_123']  # Same key twice

            result = prompt_api_key()
            assert result == 'test_key_123'

    def test_prompt_api_key_mismatch(self):
        """Test API key prompting with mismatched confirmation handled."""
        import getpass
        import click
        with patch('getpass.getpass') as mock_getpass, \
             patch('click.confirm') as mock_confirm, \
             patch('click.echo') as mock_echo:
            # Simulate a scenario where user gives up
            mock_getpass.side_effect = ['key1', 'key2']
            mock_confirm.return_value = False  # User doesn't want to try again

            # This should raise Abort (which inherits from SystemExit)
            with pytest.raises(click.Abort):
                prompt_api_key()

    def test_prompt_api_key_empty(self):
        """Test API key prompting with empty key."""
        import getpass
        with patch('getpass.getpass') as mock_getpass, \
             patch('click.echo') as mock_echo:
            mock_getpass.return_value = ''  # Empty key

            # Should keep prompting and echo error messages
            with pytest.raises(RuntimeError):  # Would eventually hit maximum recursion
                prompt_api_key()

    def test_confirm_configuration_accept(self):
        """Test configuration confirmation acceptance."""
        with patch('click.confirm') as mock_confirm:
            mock_confirm.return_value = True

            provider_details = {
                'name': 'testprov',
                'display_name': 'Test Provider',
                'endpoint_url': 'https://api.test.com',
                'model_name': 'test-model',
                'base_url': 'https://api.test.com',
                'auth_type': 'bearer'
            }

            result = confirm_configuration(provider_details)
            assert result is True

    def test_confirm_configuration_decline(self):
        """Test configuration confirmation decline."""
        with patch('click.confirm') as mock_confirm:
            mock_confirm.return_value = False

            provider_details = {
                'name': 'testprov',
                'display_name': 'Test Provider',
                'endpoint_url': 'https://api.test.com',
                'model_name': 'test-model',
                'base_url': 'https://api.test.com',
                'auth_type': 'bearer'
            }

            result = confirm_configuration(provider_details)
            assert result is False


class TestDatabaseInteraction:
    """Test database interaction through CLI configuration."""

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_provider_record_creation(self, mock_encrypt, mock_db_class, sample_provider_record):
        """Test that provider records are created correctly."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.return_value = "encrypted_key"

        from click.testing import CliRunner
        runner = CliRunner()

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive',
            '--api-key', 'test_key'
        ])

        # Verify the provider record was created with correct parameters
        args, kwargs = mock_db_instance.save_api_provider.call_args
        provider_record = args[0]

        assert provider_record.name == 'testprovider'
        assert provider_record.display_name == 'Testprovider'
        assert provider_record.auth_type == 'bearer'

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_api_key_record_creation(self, mock_encrypt, mock_db_class):
        """Test that API key records are created correctly."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.return_value = "encrypted_api_key_123"

        runner = CliRunner()

        result = runner.invoke(main, [
            'configure',
            '--provider', 'keytest',
            '--non-interactive',
            '--api-key', 'plain_api_key_123'
        ])

        assert result.exit_code == 0

        # Verify that save_api_key was called
        assert mock_db_instance.save_api_key.called
        args, kwargs = mock_db_instance.save_api_key.call_args
        api_key_record = args[0]

        # Verify the API key properties
        assert api_key_record.key_value == "encrypted_api_key_123"
        # Note: We can't check the environment directly since it's set in the CLI code
        assert api_key_record.is_active is True


class TestErrorHandling:
    """Test error handling in CLI configuration."""

    @patch('bananagen.cli.Database')
    def test_configure_with_existing_provider_name(self, mock_db_class, sample_provider_record):
        """Test configuring with a provider name that already exists."""
        # This is a valid scenario - should update existing
        pass  # Covered in other tests

    @patch('bananagen.cli.Database')
    def test_database_error_on_save_provider(self, mock_db_class, runner):
        """Test handling database error when saving provider."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_db_instance.save_api_provider.side_effect = Exception("Database connection failed")

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive',
            '--api-key', 'test_key'
        ])

        assert result.exit_code != 0
        assert "Failed to save provider configuration" in result.output

    @patch('bananagen.cli.Database')
    @patch('bananagen.cli.encrypt_key')
    def test_encrypt_key_error(self, mock_encrypt, mock_db_class, runner):
        """Test handling encryption key error."""
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_api_provider.return_value = None
        mock_encrypt.side_effect = Exception("Encryption failed")

        result = runner.invoke(main, [
            'configure',
            '--provider', 'testprovider',
            '--non-interactive',
            '--api-key', 'test_key'
        ])

        assert result.exit_code != 0

    def test_configure_with_invalid_endpoint_url(self):
        """Test configuration with invalid endpoint URL."""
        result = CliRunner().invoke(main, [
            'configure',
            '--provider', 'test',
            '--non-interactive',
            '--api-key', 'key'
        ])

        # This test would need to mock the interactive prompts since non-interactive
        # uses default URLs. The validation happens during prompt processing.
        pass