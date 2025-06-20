import configparser
import os
from pathlib import Path

# Placeholder for config directory and settings file name
# In a real app, this might be determined using platform-specific logic
# e.g., using appdirs package or Path.home() / '.config' / 'AppName'
CONFIG_DIR_NAME = "IracingReplayDirectorPy"  # Subdirectory in user's Documents or chosen app data location
SETTINGS_FILE_NAME = "settings.ini"

# Determine a default user-specific directory for working folder and settings.
# Note: Path.home() / "Documents" is common but might not be ideal for all OSes or non-desktop apps.
# Consider platform-specific app data directories for broader compatibility if needed.
DEFAULT_USER_DOCUMENTS_PATH = Path.home() / "Documents"
DEFAULT_WORKING_FOLDER_BASE = DEFAULT_USER_DOCUMENTS_PATH / CONFIG_DIR_NAME
DEFAULT_CONFIG_FILE_PATH = DEFAULT_WORKING_FOLDER_BASE / SETTINGS_FILE_NAME


DEFAULT_SETTINGS = {
    # Section: General
    "General": {
        "working_folder": str(DEFAULT_WORKING_FOLDER_BASE),  # Default base for working directory
        "last_video_file": "",                               # Path to the last video file processed or recorded
        "plugin_name": "JockeOverlays",                      # Default overlay plugin
        "preferred_driver_names": "",                        # Comma-separated string of preferred driver names
        "track_cameras_config_path": "track_cameras.xml",    # Placeholder for track camera config file
                                                             # (could be relative to working_folder or absolute)
        "use_new_settings_dialog": True,                     # Boolean flag for UI features
    },
    # Section: Recording (primarily for external recorder interactions)
    "Recording": {
        "close_iracing_after_recording": False,  # Boolean: Attempt to close iRacing after recording
        "fast_video_recording": False,           # Boolean: Placeholder for a 'fast recording' mode preset
        "short_test_only": False,                # Boolean: Developer flag for shorter test runs
        "hotkey_stop_start": "Ctrl+Shift+S",     # Default hotkey to signal start/stop to recorder
        "hotkey_pause_resume": "Ctrl+Shift+P",   # Default hotkey to signal pause/resume to recorder
    },
    # Section: Encoding (video transcoding settings)
    "Encoding": {
        "capture_opening_scene": True,           # Boolean: Include opening scene in highlights
        "shutdown_pc_after_encoding": False,     # Boolean: Shutdown PC after transcoding completes
        "encode_video_after_capture": True,      # Boolean: Automatically start transcoding after capture/analysis
        "video_bitrate": 15000000,               # Integer: Target video bitrate in bps (e.g., 15 Mbps)
        "highlight_video_only": False,           # Boolean: Global default to only produce highlights
        "highlight_video_target_duration_seconds": 120,  # Integer: Target duration for highlight reels
    },
    # Section: Analysis
    "Analysis": {
        "analysis_replay_speed": 16,             # Integer: Replay speed during analysis phase (1x, 2x, 4x, 8x, 16x)
        "max_analysis_duration_seconds": 600,    # Integer: Max seconds of replay time to analyze from race start
        "analysis_pre_roll_seconds": 5,          # Integer: Seconds to pre-roll before detected race start for analysis
        "min_off_track_duration_for_event": 1.0, # Float: Minimum seconds a car must be off-track to log an event
        "battle_proximity_threshold_pct": 0.005, # Float: Lap distance % threshold to consider cars 'in battle' (0.5%)
        "min_battle_duration_seconds": 5.0,      # Float: Minimum seconds cars must be in proximity to log a 'Battle' event
        "overtake_proximity_threshold_pct": 0.002, # Float: Lap distance % for overtake detection (tighter)
        "track_typical_lap_time_seconds": 90.0,  # Float: Estimated typical lap time for a track, used for some heuristics
                                                 # (e.g. converting % lap distance to rough time proximity if needed)
        "fastest_lap_event_duration_seconds": 7.0, # Float: Duration for "Fastest Lap" type events on timeline
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
                        # configparser's getboolean is robust for various string representations of bools
                        actual_value = parser.getboolean(section, key)
                    elif expected_type == int:
                        actual_value = parser.getint(section, key)
                    elif expected_type == float:  # Though no float defaults are currently defined
                        actual_value = parser.getfloat(section, key)
                    else:  # Assumed to be str
                        actual_value = value_str
                    setattr(self, key, actual_value)
                except ValueError as e:
                    print(
                        f"Warning: Could not convert setting '{key}' in section '{section}' "
                        f"to type '{expected_type.__name__}'. Using default. Error: {e}"
                    )
                    # Keep the default value already set in __init__
                except configparser.NoOptionError:
                    # This shouldn't happen if iterating parser.items(), but included for safety
                    print(
                        f"Warning: Setting '{key}' in section '{section}' not found by configparser "
                        f"during item iteration. Using default."
                    )

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
    print(f"  Working folder: {settings.working_folder}")
    print(f"  Video bitrate: {settings.video_bitrate} bps")
    print(f"  Shutdown PC after encoding: {settings.shutdown_pc_after_encoding}")
    print(f"  Preferred drivers: '{settings.preferred_driver_names}' (empty means none)")

    # Modify a setting
    print("\nModifying some settings in memory...")
    original_bitrate = settings.video_bitrate
    settings.video_bitrate = 20000000  # 20 Mbps
    settings.preferred_driver_names = "Driver A, Driver B"
    print(f"  Changed video bitrate to: {settings.video_bitrate} bps")
    print(f"  Changed preferred drivers to: '{settings.preferred_driver_names}'")

    # Save settings back to a temporary file
    # This avoids altering the user's actual settings file during this example run.
    temp_settings_path = Path.cwd() / "temp_example_settings.ini"
    # Temporarily change the filepath for this instance to save to temp file
    original_filepath = settings.filepath
    settings.filepath = temp_settings_path
    print(f"\nSaving current settings to temporary file: {temp_settings_path}")
    try:
        settings.save_settings()  # Saves current state (including modifications) to temp_settings_path
        print("  Settings saved to temporary file.")
    except Exception as e:
        print(f"  Error saving to temporary file: {e}")

    # Restore original filepath if needed for further operations on 'settings' instance
    settings.filepath = original_filepath

    # Create a new instance, loading from the temp file to verify save/load
    if temp_settings_path.exists():
        print(f"\nLoading settings from {temp_settings_path} into a new instance...")
        settings_loaded = AppSettings(settings_filepath=temp_settings_path)
        print(f"  Loaded working folder: {settings_loaded.working_folder}")
        print(f"  Loaded video bitrate: {settings_loaded.video_bitrate} bps") # Should be 20000000
        print(f"  Loaded preferred drivers: '{settings_loaded.preferred_driver_names}'") # Should be "Driver A, Driver B"
        print(f"  Loaded shutdown PC: {settings_loaded.shutdown_pc_after_encoding}") # Should be default

        # Test case: what if a setting is removed from the file? It should revert to default.
        print(f"\nTesting resilience to missing option in INI file (using {temp_settings_path})...")
        # Save current state of settings_loaded (e.g., bitrate 20M) to temp_settings_path
        settings_loaded.save_settings()

        # Read content, remove a line, write back
        with open(temp_settings_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Remove video_bitrate for testing
        modified_lines = [line for line in lines if not line.strip().startswith("video_bitrate")]

        with open(temp_settings_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        print(f"  Manually removed 'video_bitrate' from {temp_settings_path}")

        settings_after_delete = AppSettings(settings_filepath=temp_settings_path)
        expected_default_bitrate = DEFAULT_SETTINGS['Encoding']['video_bitrate']
        print(
            f"  Loaded video bitrate after delete: {settings_after_delete.video_bitrate} "
            f"(should be default: {expected_default_bitrate})"
        )
        assert settings_after_delete.video_bitrate == expected_default_bitrate

        # Test reset_to_defaults
        print("\nTesting reset_to_defaults...")
        # Change a setting in settings_after_delete
        settings_after_delete.plugin_name = "TEMPORARY_PLUGIN_NAME_FOR_RESET_TEST"
        assert settings_after_delete.plugin_name != DEFAULT_SETTINGS['General']['plugin_name']

        settings_after_delete.reset_to_defaults() # Reset to program defaults
        assert settings_after_delete.plugin_name == DEFAULT_SETTINGS['General']['plugin_name']
        assert settings_after_delete.video_bitrate == DEFAULT_SETTINGS['Encoding']['video_bitrate']
        print("  reset_to_defaults appears to work: settings are back to program defaults.")

        # Clean up the temporary file
        try:
            os.remove(temp_settings_path)
            print(f"\nCleaned up temporary settings file: {temp_settings_path}")
        except OSError as e:
            print(f"\nError cleaning up temporary file {temp_settings_path}: {e}")

    print("\n--- Interaction with actual user settings file ---")
    print(f"The application uses settings from: {DEFAULT_CONFIG_FILE_PATH}")
    print("1. Run the application once to potentially create this file with defaults or loaded values.")
    print("2. Manually edit the file if you wish to change settings outside the app.")
    print("3. Run the application again to see if your manual edits are loaded correctly.")

    print("\nAppSettings module demonstration finished.")
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
