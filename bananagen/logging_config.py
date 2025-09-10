import logging
import json
from typing import Optional, Any, Dict

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Formats log records as JSON with consistent fields and support for extra context.
    """
    
    def __init__(self, include_fields: Optional[list] = None):
        super().__init__()
        self.datefmt = '%Y-%m-%dT%H:%M:%S%z'
        if include_fields is None:
            include_fields = ['timestamp', 'level', 'module', 'message']
        self.include_fields = include_fields
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON string.
        
        Includes standard fields and any extra context from record.__dict__.
        """
        # Base log entry
        log_entry: Dict[str, Any] = {}
        
        if 'timestamp' in self.include_fields:
            log_entry['timestamp'] = self.formatTime(record, self.datefmt)
        
        if 'level' in self.include_fields:
            log_entry['level'] = record.levelname
        
        if 'module' in self.include_fields:
            log_entry['module'] = record.name
        
        if 'message' in self.include_fields:
            log_entry['message'] = record.getMessage()
        
        # Add any extra fields from record.__dict__
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelno', 'levelname', 'pathname',
                              'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                              'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process', 'message']:
                    if key in self.include_fields or 'extra' in self.include_fields:
                        log_entry[key] = value
        
        # Allow 'extra' dict to be passed and merged
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            log_entry.update(record.extra)
        
        return json.dumps(log_entry, ensure_ascii=False)

def configure_logging(level: str = 'INFO', handler_type: str = 'stream', output_file: Optional[str] = None) -> logging.Logger:
    """
    Configure application-wide logging with JSON formatting.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        handler_type: Type of handler ('stream' for console output, 'file' for file output)
        output_file: Path to log file if using file handler
    
    Returns:
        Configured root logger
    """
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Remove any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    if handler_type == 'file' and output_file:
        handler = logging.FileHandler(output_file)
    else:
        handler = logging.StreamHandler()
    
    # Set formatter
    formatter = JSONFormatter()
    handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for a specific module.
    
    Args:
        name: The name of the logger (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)