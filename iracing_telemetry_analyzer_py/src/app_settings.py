import configparser
import os
from pathlib import Path

# Placeholder for config directory and settings file name
# In a real app, this might be determined using platform-specific logic
# e.g., appdirs package or Path.home() / '.config' / 'AppName'
CONFIG_DIR_NAME = "IracingReplayDirectorPy" # Subdirectory in user's Documents or home
SETTINGS_FILE_NAME = "settings.ini"

# Determine a default user-specific directory for working folder and settings
DEFAULT_USER_DOCUMENTS_PATH = Path.home() / "Documents"
DEFAULT_WORKING_FOLDER_BASE = DEFAULT_USER_DOCUMENTS_PATH / CONFIG_DIR_NAME
DEFAULT_CONFIG_FILE_PATH = DEFAULT_WORKING_FOLDER_BASE / SETTINGS_FILE_NAME


DEFAULT_SETTINGS = {
    # Section: General
    "General": {
        "working_folder": str(DEFAULT_WORKING_FOLDER_BASE), # User's documents/IracingReplayDirectorPy
        "last_video_file": "",
        "plugin_name": "JockeOverlays",
        "preferred_driver_names": "", # Comma-separated string
        "track_cameras_config_path": "track_cameras.xml", # Placeholder, could be relative to working_folder or absolute
        "use_new_settings_dialog": True, # Boolean
    },
    # Section: Recording
    "Recording": {
        "close_iracing_after_recording": False, # Boolean
        "fast_video_recording": False, # Boolean - Placeholder, meaning might need clarification
        "short_test_only": False, # Boolean
        "hotkey_stop_start": "Ctrl+Shift+S",
        "hotkey_pause_resume": "Ctrl+Shift+P",
    },
    # Section: Encoding
    "Encoding": {
        "capture_opening_scene": True, # Boolean
        "shutdown_pc_after_encoding": False, # Boolean
        "encode_video_after_capture": True, # Boolean
        "video_bitrate": 15000000, # Integer (15 Mbps)
        "highlight_video_only": False, # Boolean
        "highlight_video_target_duration_seconds": 120, # Integer
    }
}

class AppSettings:
    def __init__(self, settings_filepath=None):
        """
        Initializes application settings with defaults and then loads from an INI file.
        Settings are accessible as attributes of this instance.
        """
        if settings_filepath is None:
            settings_filepath = DEFAULT_CONFIG_FILE_PATH
        self.filepath = Path(settings_filepath)

        # Initialize all settings with defaults
        for section, options in DEFAULT_SETTINGS.items():
            for key, value in options.items():
                setattr(self, key, value)

        # Load settings from file, potentially overriding defaults
        self.load_settings()

    def _get_type(self, section, key):
        """Helper to determine the type of a setting based on defaults."""
        return type(DEFAULT_SETTINGS[section][key])

    def load_settings(self):
        """
        Loads settings from the INI file specified by self.filepath.
        Handles type conversions for boolean and integer values.
        """
        if not self.filepath.exists():
            # If settings file doesn't exist, it might be first run or uses defaults.
            # Consider saving defaults here if that's desired behavior: self.save_settings()
            # For now, we just proceed with defaults already set in __init__.
            # Ensure the directory exists for a future save_settings() call
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            return

        parser = configparser.ConfigParser()
        # Configparser by default treats keys case-insensitively, which is fine.
        parser.read(self.filepath)

        for section in parser.sections():
            if section not in DEFAULT_SETTINGS:
                # Potentially handle unknown sections if necessary (e.g., log a warning)
                continue
            for key, value_str in parser.items(section):
                if key not in DEFAULT_SETTINGS[section]:
                    # Potentially handle unknown keys if necessary
                    continue

                expected_type = self._get_type(section, key)
                try:
                    if expected_type == bool:
                        # configparser's getboolean is robust
                        actual_value = parser.getboolean(section, key)
                    elif expected_type == int:
                        actual_value = parser.getint(section, key)
                    elif expected_type == float: # Though no float defaults currently
                        actual_value = parser.getfloat(section, key)
                    else: # Assumed to be str
                        actual_value = value_str
                    setattr(self, key, actual_value)
                except ValueError as e:
                    print(f"Warning: Could not convert setting '{key}' in section '{section}' to {expected_type.__name__}. Using default. Error: {e}")
                    # Keep the default value already set in __init__
                except configparser.NoOptionError:
                     # This shouldn't happen if iterating parser.items(), but good for safety
                    print(f"Warning: Setting '{key}' in section '{section}' not found. Using default.")


    def save_settings(self):
        """
        Saves the current settings to the INI file specified by self.filepath.
        """
        parser = configparser.ConfigParser()

        for section_name, options in DEFAULT_SETTINGS.items():
            parser.add_section(section_name)
            for key in options.keys():
                value = getattr(self, key, None)
                if value is not None:
                    # Convert Python types to strings for INI file
                    if isinstance(value, bool):
                        parser.set(section_name, key, "yes" if value else "no")
                    else:
                        parser.set(section_name, key, str(value))

        try:
            # Ensure the configuration directory exists
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as configfile:
                parser.write(configfile)
        except IOError as e:
            # It would be good to raise this or handle it in a way the UI can catch
            print(f"Error: Could not save settings to {self.filepath}. Error: {e}")
            raise # Re-raise for UI to catch or handle

    def reset_to_defaults(self):
        """
        Resets the in-memory settings attributes to their program default values
        as defined in DEFAULT_SETTINGS.
        """
        print("Resetting AppSettings to program defaults.")
        for section, options in DEFAULT_SETTINGS.items():
            for key, value in options.items():
                # Ensure dynamic paths like working_folder are correctly re-evaluated if DEFAULT_SETTINGS
                # contains callables or special markers.
                # Currently, DEFAULT_SETTINGS stores direct values (str for paths, evaluated at import time).
                # If DEFAULT_SETTINGS itself had functions to get defaults, call them here.
                # For this project, DEFAULT_SETTINGS has static (at import time) values.
                setattr(self, key, value)

        # If DEFAULT_CONFIG_FILE_PATH or DEFAULT_WORKING_FOLDER_BASE were dynamic based on
        # e.g. Path.home() and that could change or needs re-evaluation, it's more complex.
        # But for this app, these are fine as they are set from DEFAULT_SETTINGS.
        # The main dynamic one is working_folder which is `str(DEFAULT_WORKING_FOLDER_BASE)`.
        # This is correctly reset by the loop above.


if __name__ == '__main__':
    # Example Usage:
    print(f"Default settings file path: {DEFAULT_CONFIG_FILE_PATH}")

    # Create AppSettings instance (loads from file if exists, else uses defaults)
    settings = AppSettings()

    # Access settings
    print(f"Working folder: {settings.working_folder}")
    print(f"Video bitrate: {settings.video_bitrate}")
    print(f"Shutdown PC after encoding: {settings.shutdown_pc_after_encoding}")
    print(f"Preferred drivers: '{settings.preferred_driver_names}' (empty means none)")

    # Modify a setting
    original_bitrate = settings.video_bitrate
    settings.video_bitrate = 20000000 # 20 Mbps
    settings.preferred_driver_names = "Driver A, Driver B"
    print(f"Changed video bitrate to: {settings.video_bitrate}")
    print(f"Changed preferred drivers to: {settings.preferred_driver_names}")


    # Save settings back to the file
    # For this example, let's use a temporary file to avoid altering user's actual settings
    temp_settings_path = Path.cwd() / "temp_settings.ini"
    print(f"Saving current settings to: {temp_settings_path}")
    settings.save_settings() # Saves current state (including modifications)

    # Create a new instance, loading from the temp file to verify save/load
    print(f"\nLoading settings from {temp_settings_path} into a new instance...")
    settings_loaded = AppSettings(settings_filepath=temp_settings_path)
    print(f"Loaded working folder: {settings_loaded.working_folder}") # Should be default from DEFAULT_SETTINGS
    print(f"Loaded video bitrate: {settings_loaded.video_bitrate}") # Should be 20000000
    print(f"Loaded preferred drivers: {settings_loaded.preferred_driver_names}") # Should be "Driver A, Driver B"
    print(f"Loaded shutdown PC: {settings_loaded.shutdown_pc_after_encoding}") # Should be default

    # Clean up the temporary file
    if temp_settings_path.exists():
        # os.remove(temp_settings_path)
        print(f"Temporary settings file {temp_settings_path} was created for testing.")
        # Revert changes for next run if needed, by saving defaults
        # settings.video_bitrate = original_bitrate
        # settings.preferred_driver_names = ""
        # settings.save_settings() # This would save back to DEFAULT_CONFIG_FILE_PATH if not careful

    print("\nTo test interaction with actual user settings file:")
    print(f"1. Run once to potentially create '{DEFAULT_CONFIG_FILE_PATH}' with defaults or loaded values.")
    print(f"2. Manually edit '{DEFAULT_CONFIG_FILE_PATH}'.")
    print(f"3. Run again to see if your manual edits are loaded correctly.")

    # Test case: what if a setting is removed from the file? It should revert to default.
    # To test: save, manually delete a line from temp_settings.ini, then load.
    if temp_settings_path.exists():
        print(f"\nTesting resilience to missing option in INI file (using {temp_settings_path})...")
        # Save current state (e.g., bitrate 20M)

        # We need to use the save method of the settings_loaded instance,
        # which is configured with temp_settings_path as its filepath.
        settings_loaded.save_settings() # settings_loaded.filepath is temp_settings_path

        # Read content, remove a line, write back
        with open(temp_settings_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified_lines = [line for line in lines if not line.strip().startswith("video_bitrate")]

        with open(temp_settings_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        print(f"  Manually removed 'video_bitrate' from {temp_settings_path}")

        settings_after_delete = AppSettings(settings_filepath=temp_settings_path)
        print(f"  Loaded video bitrate after delete: {settings_after_delete.video_bitrate} (should be default: {DEFAULT_SETTINGS['Encoding']['video_bitrate']})")
        assert settings_after_delete.video_bitrate == DEFAULT_SETTINGS['Encoding']['video_bitrate']

        # Test reset_to_defaults
        print("\nTesting reset_to_defaults...")
        settings_after_delete.plugin_name = "TEMPORARY_PLUGIN_NAME_FOR_RESET_TEST"
        assert settings_after_delete.plugin_name != DEFAULT_SETTINGS['General']['plugin_name']
        settings_after_delete.reset_to_defaults()
        assert settings_after_delete.plugin_name == DEFAULT_SETTINGS['General']['plugin_name']
        assert settings_after_delete.video_bitrate == DEFAULT_SETTINGS['Encoding']['video_bitrate'] # Should be back to default
        print("  reset_to_defaults appears to work.")

        # Clean up
        os.remove(temp_settings_path)
        print(f"  Cleaned up {temp_settings_path}")

    print("\nAppSettings module structure created.")

# To make working_folder and settings file path easily accessible if needed elsewhere:
def get_default_config_filepath():
    return DEFAULT_CONFIG_FILE_PATH

def get_default_working_folder():
    return DEFAULT_WORKING_FOLDER_BASE

# Ensure the default working folder exists when the module is loaded,
# as it's also the parent for the default settings.ini
# This is a side effect on import, consider if this is desired.
# Alternatively, create it only when AppSettings is instantiated or settings are saved.
# For now, creating it on load_settings/save_settings is preferred.
# DEFAULT_WORKING_FOLDER_BASE.mkdir(parents=True, exist_ok=True)
# print(f"Ensured default working folder exists: {DEFAULT_WORKING_FOLDER_BASE}")

```
