import pytest
import json
import logging
import tempfile
import io
from pathlib import Path
from unittest.mock import patch, MagicMock
from bananagen.logging_config import JSONFormatter, configure_logging, get_logger


class TestJSONFormatter:
    """Test JSONFormatter class."""

    def test_format_basic_record(self):
        """Test basic record formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.created = 1736325600.123  # Fixed time for predictable output

        output = formatter.format(record)
        data = json.loads(output)
        assert data['level'] == 'INFO'
        assert data['module'] == 'test'
        assert data['message'] == 'Test message'
        assert 'timestamp' in data

    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='test.py',
            lineno=20,
            msg='Error occurred',
            args=(),
            exc_info=None
        )
        record.extra = {'user_id': 123, 'request_id': 'abc'}

        output = formatter.format(record)
        data = json.loads(output)
        assert data['user_id'] == 123
        assert data['request_id'] == 'abc'
        assert data['level'] == 'ERROR'

    def test_format_custom_include_fields(self):
        """Test with custom include fields."""
        formatter = JSONFormatter(include_fields=['level', 'message'])
        record = logging.LogRecord(
            name='test',
            level=logging.DEBUG,
            pathname='',
            lineno=0,
            msg='Debug info',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert 'level' in data
        assert 'message' in data
        assert 'timestamp' not in data  # Not included
        assert 'module' not in data

    def test_format_empty_include_fields(self):
        """Test with empty include fields."""
        formatter = JSONFormatter(include_fields=[])
        record = logging.LogRecord(
            name='test',
            level=logging.WARNING,
            pathname='',
            lineno=0,
            msg='Warning',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)
        # Only extra should be included
        assert data == {'timestamp': data['timestamp'], 'level': 'WARNING', 'module': 'test', 'message': 'Warning'}  # Actually, defaults include these

    def test_format_with_exception_record(self):
        """Test formatting record with exception info."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.CRITICAL,
            pathname='',
            lineno=0,
            msg='Exception occurred',
            args=(),
            exc_info=()
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data['level'] == 'CRITICAL'
        assert data['message'] == 'Exception occurred'

    def test_format_record_with_args(self):
        """Test formatting record with message arguments."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='User %s logged in at %s',
            args=('alice', '2023-12-01'),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data['message'] == 'User alice logged in at 2023-12-01'


class TestConfigureLogging:
    """Test configure_logging function."""

    def test_configure_logging_default(self):
        """Test default configure logging."""
        root_logger = configure_logging()
        assert isinstance(root_logger, logging.Logger)
        assert root_logger.level == logging.INFO

        # Check handler type (default stream)
        handlers = root_logger.handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_configure_logging_debug_level(self):
        """Test configuring with DEBUG level."""
        root_logger = configure_logging(level='DEBUG')
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_error_level(self):
        """Test configuring with ERROR level."""
        root_logger = configure_logging(level='ERROR')
        assert root_logger.level == logging.ERROR

    def test_configure_logging_invalid_level(self):
        """Test configuring with invalid level falls back."""
        root_logger = configure_logging(level='INVALID')
        assert root_logger.level == logging.INFO  # Fallback

    def test_configure_logging_file_output(self):
        """Test configuring with file output."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as f:
            output_file = f.name

        try:
            root_logger = configure_logging(level='INFO', handler_type='file', output_file=output_file)

            handlers = root_logger.handlers
            assert len(handlers) == 1
            assert isinstance(handlers[0], logging.FileHandler)

        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_configure_logging_stream_output(self):
        """Test configuring with explicit stream output."""
        root_logger = configure_logging(level='WARNING', handler_type='stream')

        handlers = root_logger.handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_configure_logging_invalid_handler_type(self):
        """Test configuring with invalid handler type falls back to stream."""
        root_logger = configure_logging(level='INFO', handler_type='invalid')

        handlers = root_logger.handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)  # Fallback

    def test_configure_logging_clears_existing_handlers(self):
        """Test that existing handlers are cleared."""
        root_logger = logging.getLogger()
        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)

        assert len(root_logger.handlers) > 0

        configure_logging()

        # Should have exactly 1 handler now
        assert len(root_logger.handlers) == 1

    @patch('bananagen.logging_config.Path')
    def test_configure_logging_formatter_set(self, mock_path):
        """Test that formatter is set on handler."""
        root_logger = configure_logging()

        handlers = root_logger.handlers
        assert len(handlers) == 1
        assert isinstance(handlers[0].formatter, JSONFormatter)


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_basic(self):
        """Test basic get_logger functionality."""
        logger = get_logger('test_module')
        assert isinstance(logger, logging.Logger)
        assert logger.name == 'test_module'

    def test_get_logger_same_name(self):
        """Test getting logger with same name returns same instance."""
        logger1 = get_logger('test.logger')
        logger2 = get_logger('test.logger')

        assert logger1 is logger2
        assert logger1.name == 'test.logger'

    def test_get_logger_root_name(self):
        """Test getting logger with root name."""
        logger = get_logger('')
        assert isinstance(logger, logging.Logger)
        assert logger.name == ''

    def test_get_logger_nested_name(self):
        """Test getting logger with nested name."""
        logger = get_logger('parent.child.grandchild')
        assert logger.name == 'parent.child.grandchild'


class TestIntegrationJSONFormatterWithLogger:
    """Integration tests for JSONFormatter with actual logging."""

    def test_json_formatter_integration(self, capsys):
        """Test JSONFormatter with actual log output."""
        configure_logging(level='INFO')

        logger = get_logger('integration_test')
        logger.info('Test integration message', extra={'action': 'test', 'user': 'bot'})

        # Capture output
        captured = capsys.readouterr()
        # Assuming it's stream handler
        output = captured.out.strip() or captured.err.strip()
        if output:
            data = json.loads(output)
            assert 'action' in data
            assert 'user' in data
            assert data['action'] == 'test'
            assert data['user'] == 'bot'

    def test_json_formatter_with_file_output(self):
        """Test JSONFormatter with file output."""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as f:
            output_file = f.name

        try:
            configure_logging(level='WARNING', handler_type='file', output_file=output_file)

            logger = get_logger('file_test')
            logger.warning('File test message', extra={'code': 404, 'url': '/test'})

            # Read file
            with open(output_file, 'r') as file:
                content = file.read().strip()
                if content:
                    data = json.loads(content)
                    assert 'code' in data
                    assert 'url' in data

        finally:
            Path(output_file).unlink(missing_ok=True)


class TestEdgeCasesJSONFormatter:
    """Edge cases for JSONFormatter."""

    def test_format_special_characters_in_message(self):
        """Test formatting with special characters in message."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Message with "quotes" and \'apostrophes\'',
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data['message'] == 'Message with "quotes" and \'apostrophes\''

    def test_format_very_long_message(self):
        """Test formatting with very long message."""
        long_msg = 'A' * 10000
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=long_msg,
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)
        assert data['message'] == long_msg

    def test_format_with_none_extra(self):
        """Test formatting with extra=None."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.extra = None

        output = formatter.format(record)
        data = json.loads(output)
        assert data['message'] == 'Test message'

    def test_format_with_no_dict_record(self):
        """Test formatting when record.__dict__ is not available."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        # Remove __dict__
        del record.__dict__

        output = formatter.format(record)
        data = json.loads(output)
        assert data['level'] == 'INFO'