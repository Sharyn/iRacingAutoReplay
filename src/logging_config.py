import logging
import logging.handlers
import sys

LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_FILE_BACKUP_COUNT = 5

def setup_logging(log_level=logging.INFO, log_to_console=True, log_file_path=None):
    """
    Set up basic logging for the application.

    Args:
        log_level: The minimum logging level to output (e.g., logging.DEBUG, logging.INFO).
        log_to_console: If True, logs will be output to the console.
        log_file_path: If provided, logs will be written to this file with rotation.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if log_file_path:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_path,
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fallback to console if file logging setup fails
            print(f"Error setting up file logging: {e}", file=sys.stderr)
            if not log_to_console: # Ensure there's at least console output
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)


if __name__ == "__main__":
    # Example usage:
    # By default, logs to console at INFO level
    setup_logging()
    logging.debug("This is a debug message.") # Won't be shown by default
    logging.info("This is an info message.")
    logging.warning("This is a warning message.")
    logging.error("This is an error message.")
    logging.critical("This is a critical message.")

    # Example with file logging (e.g., to 'app.log')
    # setup_logging(log_level=logging.DEBUG, log_file_path="app.log")
    # logging.debug("This debug message will go to console and app.log")
    # logging.info("This info message will also go to console and app.log")
