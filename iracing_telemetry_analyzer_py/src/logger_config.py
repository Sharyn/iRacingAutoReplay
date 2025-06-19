import logging
import logging.config
import os

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO', # Default level
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # Default is stderr
        },
        'file': {
            'level': 'DEBUG', # More verbose for file logging
            'formatter': 'standard',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'app.log', # Will be created in the current working directory
            'maxBytes': 1024*1024*5, # 5 MB
            'backupCount': 5,
            'encoding': 'utf-8',
        }
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['console', 'file'],
            'level': 'DEBUG', # Capture all debug messages and above at root level
            'propagate': False
        },
        'my_module': { # Example of a specific logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        },
        'PyQt6': { # Example for a library logger
            'handlers': ['console', 'file'],
            'level': 'WARNING', # Reduce noise from Qt
            'propagate': False
        }
    }
}

def setup_logging(default_level=logging.INFO, env_key='LOG_LEVEL'):
    """
    Setup logging configuration.
    You can override the default logging level by setting the LOG_LEVEL environment variable.
    Example: LOG_LEVEL=DEBUG
    """
    level = os.getenv(env_key, None)
    if level:
        LOGGING_CONFIG['handlers']['console']['level'] = level.upper()
        # Potentially update root logger level too if desired
        # LOGGING_CONFIG['loggers']['']['level'] = level.upper()

    logging.config.dictConfig(LOGGING_CONFIG)
    # logging.getLogger(__name__).info("Logging configured.") # Optional: log that logging is setup

if __name__ == '__main__':
    # Example usage:
    setup_logging()
    logger = logging.getLogger('my_module') # Get logger for 'my_module'
    logger.debug("This is a debug message from my_module.")
    logger.info("This is an info message from my_module.")
    logger.warning("This is a warning message from my_module.")
    logger.error("This is an error message from my_module.")
    logger.critical("This is a critical message from my_module.")

    root_logger = logging.getLogger() # Get root logger
    root_logger.debug("This is a debug message from root.") # Will be handled by root's handlers

    # Example of how another module might use the logger
    # In another_module.py:
    # import logging
    # logger = logging.getLogger(__name__) # Gets a logger named 'another_module'
    # logger.info("Hello from another_module")
    #
    # This logger will inherit from the root logger's configuration if not specifically defined
    # in LOGGING_CONFIG.
    # To give it specific handling, add an entry for 'another_module' in LOGGING_CONFIG['loggers'].
    # If 'propagate' is True for 'another_module', messages will also go to root handlers.
    # If 'propagate' is False, only 'another_module's handlers will be used.
    # Current root logger has propagate=False, so child loggers need their own handlers or they won't output.
    # Let's re-enable propagation for root for typical behavior unless specific loggers handle it.
    # For this example, my_module has propagate=False, so its messages won't go to root.

    # Correcting root logger propagation for general use:
    # If a logger is defined in `loggers` dict, its `propagate` setting is used.
    # If a logger is NOT defined, it inherits from parent, ultimately from root.
    # Root logger's `propagate` should generally be True if you want descendant loggers
    # (that don't have their own handlers and `propagate=False`) to send messages to root's handlers.
    # However, since we define specific handlers for '' (root), its own `propagate` attribute
    # isn't as critical as for other loggers. The key is that non-defined loggers will propagate to root.
    #
    # The current setup:
    # - Root logger ('') has handlers ['console', 'file'] and level DEBUG. Propagate is False.
    # - 'my_module' has handlers ['console', 'file'], level INFO, and Propagate False.
    #   Messages to 'my_module' will be handled by its handlers. Because propagate is False, they won't go to root's handlers.
    # - Loggers not explicitly defined (e.g., logging.getLogger('some.other.module')) will:
    #   1. Not have specific handlers.
    #   2. Propagate to their parent, eventually to the root logger ('').
    #   3. Be handled by the root logger's handlers if their level is >= root logger's level (DEBUG).

    # To demonstrate a logger that propagates to root:
    propagating_logger = logging.getLogger("app.propagating")
    # No specific config for 'app.propagating', so it uses root's config.
    # Its effective level will be DEBUG (from root), and messages go to root's handlers.
    propagating_logger.info("This message from app.propagating goes to root handlers.")
    propagating_logger.debug("This debug message from app.propagating also goes to root handlers.")

    # To test PyQt6 logger behavior (set to WARNING)
    pyqt_logger = logging.getLogger("PyQt6.QtWidgets")
    pyqt_logger.info("This PyQt6 info message will NOT be shown due to level WARNING.")
    pyqt_logger.warning("This PyQt6 warning message WILL be shown.")

    print("\nCheck app.log for file output.")
