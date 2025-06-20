import configparser
import logging
import os

logger = logging.getLogger(__name__)

class AppSettings:
    """Manages application settings using configparser."""

    DEFAULT_SETTINGS_FILE = "settings.ini"
    DEFAULT_SETTINGS = {
        "General": {
            "iracing_sdk_path": "path/to/iracing/sdk", # Placeholder
            "default_working_directory": "~/iRacingTelemetry",
        },
        "UI": {
            "theme": "default",
            "main_window_width": "1280",
            "main_window_height": "720",
        },
        "ReplayAnalysis": {
            "auto_connect_sdk": "true",
            "event_detection_sensitivity": "medium", # Example: low, medium, high
        },
        "Dependencies": {
            "pyqt_version": "PyQt6", # Placeholder, actual version might vary
            "iracing_sdk_placeholder_version": "0.1.0" # Placeholder
        }
    }

    def __init__(self, settings_file_path=None):
        self.config = configparser.ConfigParser()
        self.settings_file_path = settings_file_path or self.DEFAULT_SETTINGS_FILE
        self._load_defaults()
        self._load_settings()

    def _load_defaults(self):
        """Loads default settings into the config parser instance."""
        for section, options in self.DEFAULT_SETTINGS.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, str(value))
        logger.info("Default settings loaded.")

    def _load_settings(self):
        """Loads settings from the INI file, creating it with defaults if it doesn't exist."""
        if not os.path.exists(self.settings_file_path):
            logger.warning(f"Settings file '{self.settings_file_path}' not found. Creating with default values.")
            self.save_settings()
        else:
            try:
                self.config.read(self.settings_file_path)
                logger.info(f"Settings loaded from '{self.settings_file_path}'.")
                # Ensure all default sections and keys exist after loading
                self._ensure_all_defaults_present()
            except configparser.Error as e:
                logger.error(f"Error reading settings file '{self.settings_file_path}': {e}. Using defaults.")
                self.config = configparser.ConfigParser() # Reset to empty
                self._load_defaults() # Reload defaults

    def _ensure_all_defaults_present(self):
        """Ensures that all default sections and keys are present in the loaded config."""
        changes_made = False
        for section, options in self.DEFAULT_SETTINGS.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                changes_made = True
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, str(value))
                    changes_made = True
        if changes_made:
            logger.info("Added missing default settings to the current configuration.")
            self.save_settings() # Save if we added missing defaults

    def get_setting(self, section, key, fallback=None):
        """Retrieves a setting value."""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            logger.warning(f"Setting '{key}' in section '{section}' not found: {e}. Using fallback: {fallback}")
            # Try to get from default if not found
            if section in self.DEFAULT_SETTINGS and key in self.DEFAULT_SETTINGS[section]:
                return self.DEFAULT_SETTINGS[section][key]
            return fallback

    def get_boolean_setting(self, section, key, fallback=False):
        """Retrieves a boolean setting value."""
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            logger.warning(f"Boolean setting '{key}' in section '{section}' not found: {e}. Using fallback: {fallback}")
            if section in self.DEFAULT_SETTINGS and key in self.DEFAULT_SETTINGS[section]:
                default_val_str = str(self.DEFAULT_SETTINGS[section][key]).lower()
                return default_val_str in ["true", "1", "yes", "on"]
            return fallback
        except ValueError as e:
            logger.error(f"ValueError for boolean setting '{key}' in section '{section}': {e}. Using fallback: {fallback}")
            return fallback


    def get_int_setting(self, section, key, fallback=0):
        """Retrieves an integer setting value."""
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            logger.warning(f"Integer setting '{key}' in section '{section}' not found: {e}. Using fallback: {fallback}")
            if section in self.DEFAULT_SETTINGS and key in self.DEFAULT_SETTINGS[section]:
                try:
                    return int(self.DEFAULT_SETTINGS[section][key])
                except ValueError:
                    return fallback
            return fallback
        except ValueError as e:
            logger.error(f"ValueError for integer setting '{key}' in section '{section}': {e}. Using fallback: {fallback}")
            return fallback

    def update_setting(self, section, key, value):
        """Updates a setting value."""
        if not self.config.has_section(section):
            self.config.add_section(section)
            logger.info(f"Added new section '{section}' during update.")
        self.config.set(section, key, str(value))
        logger.info(f"Setting '{key}' in section '{section}' updated to '{value}'.")

    def save_settings(self):
        """Saves the current settings to the INI file."""
        try:
            with open(self.settings_file_path, 'w') as configfile:
                self.config.write(configfile)
            logger.info(f"Settings saved to '{self.settings_file_path}'.")
        except IOError as e:
            logger.error(f"Error saving settings to '{self.settings_file_path}': {e}")

if __name__ == "__main__":
    # Example usage:
    logging.basicConfig(level=logging.INFO) # For testing this script directly

    # Test with default path
    settings_manager = AppSettings()
    print(f"Default working directory: {settings_manager.get_setting('General', 'default_working_directory')}")
    settings_manager.update_setting("General", "default_working_directory", "/new/path/telemetry")
    print(f"Updated working directory: {settings_manager.get_setting('General', 'default_working_directory')}")

    # Test boolean
    print(f"Auto connect SDK: {settings_manager.get_boolean_setting('ReplayAnalysis', 'auto_connect_sdk')}")
    settings_manager.update_setting("ReplayAnalysis", "auto_connect_sdk", "False")
    print(f"Updated auto connect SDK: {settings_manager.get_boolean_setting('ReplayAnalysis', 'auto_connect_sdk')}")

    # Test integer
    print(f"Main window width: {settings_manager.get_int_setting('UI', 'main_window_width')}")
    settings_manager.update_setting("UI", "main_window_width", "1600")
    print(f"Updated main window width: {settings_manager.get_int_setting('UI', 'main_window_width')}")

    settings_manager.save_settings()
    print(f"Settings saved to {settings_manager.settings_file_path}")

    # Test loading from a custom path and handling non-existent file
    # custom_path = "custom_settings.ini"
    # if os.path.exists(custom_path):
    #     os.remove(custom_path)
    # custom_settings = AppSettings(custom_path)
    # print(f"Custom theme: {custom_settings.get_setting('UI', 'theme')}")
    # custom_settings.update_setting("UI", "theme", "dark")
    # custom_settings.save_settings()
    # print(f"Custom settings saved to {custom_settings.settings_file_path}")

    # Test loading an existing custom file
    # custom_settings_reloaded = AppSettings(custom_path)
    # print(f"Reloaded custom theme: {custom_settings_reloaded.get_setting('UI', 'theme')}")

    # Test fallback for non-existent key
    # print(f"Non-existent setting: {settings_manager.get_setting('NewSection', 'new_key', fallback='default_value')}")
    # print(f"Non-existent boolean: {settings_manager.get_boolean_setting('NewSection', 'new_bool', fallback=True)}")
    # print(f"Non-existent int: {settings_manager.get_int_setting('NewSection', 'new_int', fallback=123)}")

    # Test ensuring defaults
    # config_path_for_missing_test = "test_missing_defaults.ini"
    # temp_config = configparser.ConfigParser()
    # temp_config.add_section("General")
    # temp_config.set("General", "iracing_sdk_path", "some/other/path") # Only one option
    # with open(config_path_for_missing_test, 'w') as f:
    #    temp_config.write(f)
    # settings_with_missing = AppSettings(config_path_for_missing_test)
    # print(f"Default working dir (should be default): {settings_with_missing.get_setting('General', 'default_working_directory')}")
    # print(f"Theme (should be default): {settings_with_missing.get_setting('UI', 'theme')}")
    # if os.path.exists(config_path_for_missing_test):
    #    os.remove(config_path_for_missing_test)
    # if os.path.exists(custom_path):
    #    os.remove(custom_path)
    # if os.path.exists(settings_manager.DEFAULT_SETTINGS_FILE):
    #    os.remove(settings_manager.DEFAULT_SETTINGS_FILE) # Clean up default
    print("Example usage finished.")
