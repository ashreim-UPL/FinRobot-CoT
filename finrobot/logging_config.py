# D:/dev/FinRobot/finrobot/logging_config.py

import logging
import os
import sys

# --- Import config singleton (assumes finrobot/config.py exists) ---
try:
    from .config import config
except ImportError:
    config = None

def setup_logging():
    """
    Sets up root logging based on configuration in config.yaml, or falls back to console DEBUG logging.
    Ensures log files and directories exist if specified.
    Call this ONCE at program start before using loggers elsewhere.
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    default_level = logging.ERROR  #    other options: DEBUG, INFO, WARNING, CRITICAL

    if not config:
        logging.basicConfig(level=default_level, format=log_format, force=True)
        logging.warning("Config module not available. Logging initialized with DEBUG level to console only.")
        return

    try:
        # Support for UTF-8 console output on Windows
        if sys.platform.startswith('win'):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

        # Load level from config, default to DEBUG
        log_level_str = config._get_config_value("logging.level", "WARNING").upper()
        log_level = getattr(logging, log_level_str, default_level)

        handlers = [logging.StreamHandler(sys.stdout)]
        print("Logging to stdout is active.")

        # File logging setup (optional, if in config.yaml)
        log_file_path = config.get_path("log_file")
        if log_file_path:
            base_dir = os.path.dirname(os.path.abspath(config.__file__))
            abs_log_path = os.path.normpath(os.path.join(base_dir, log_file_path))
            os.makedirs(os.path.dirname(abs_log_path), exist_ok=True)
            handlers.append(logging.FileHandler(abs_log_path, encoding="utf-8"))
            print(f"Additionally logging to file: {abs_log_path}")

        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=handlers,
            force=True
        )
        logging.getLogger("FinancialOrchestrator").info("Logging initialized successfully from logging_config.py.")
    except Exception as e:
        logging.basicConfig(level=default_level, format=log_format, force=True)
        logging.getLogger("FinancialOrchestrator").error("Failed to configure advanced logging: %s", e, exc_info=True)
        print("WARNING: Logging fell back to DEBUG level console logging due to an error.")

def setup_logger(name: str, log_file_name: str = "app.log", level: int = logging.INFO) -> logging.Logger:
    """Sets up and returns a logger instance with a specific name."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Propagation set to True to forward logs to root handlers
    logger.propagate = True
    return logger

