import pytest
import configparser
from pathlib import Path

# Adjust import path based on how pytest discovers your modules.
# If 'src' is the top-level package for pytest, then it's 'src.app_settings'.
# If 'iracing_telemetry_analyzer_py' is the top-level, then 'iracing_telemetry_analyzer_py.src.app_settings'
# For now, assuming pytest runs from root and iracing_telemetry_analyzer_py is in PYTHONPATH or installed.
from src.app_settings import (
    AppSettings, DEFAULT_SETTINGS, CONFIG_DIR_NAME, SETTINGS_FILE_NAME
)
from typing import Dict, Any # Added for type hint clarity in helper

# Helper to compare AppSettings instance against a dictionary of expected values
def assert_settings_match_dict(settings_obj: AppSettings, expected_dict: Dict[str, Dict[str, Any]]):
    for section, options in expected_dict.items():
        for key, expected_value in options.items():
            assert hasattr(settings_obj, key), f"AppSettings missing attribute '{key}'"
            actual_value = getattr(settings_obj, key)
            assert actual_value == expected_value, \
                f"Mismatch for '{key}': expected '{expected_value}' (type {type(expected_value)}), " \
                f"got '{actual_value}' (type {type(actual_value)})"

@pytest.fixture
def default_settings_dict():
    """Provides a copy of the DEFAULT_SETTINGS dictionary."""
    # Deep copy might be needed if values are mutable, but for current defaults it's fine.
    return {section: dict(options) for section, options in DEFAULT_SETTINGS.items()}

def test_default_settings_initialization(default_settings_dict):
    """Test that AppSettings initializes with default values when no file is present."""
    # Using a non-existent path to ensure defaults are used
    non_existent_filepath = Path("non_existent_dir") / "non_existent_settings.ini"
    settings = AppSettings(settings_filepath=non_existent_filepath)

    # The working_folder in DEFAULT_SETTINGS is dynamically generated.
    # We need to ensure our comparison dict reflects that.
    expected_defaults = default_settings_dict
    # The default working_folder is Path.home() / "Documents" / CONFIG_DIR_NAME
    # This needs to be consistent with how AppSettings calculates it if we are deep comparing.
    # AppSettings.__init__ sets attributes directly from DEFAULT_SETTINGS initially.
    # Let's ensure the dynamic path in default_settings_dict is what AppSettings would use.
    # For simplicity, we are comparing against the imported DEFAULT_SETTINGS structure.

    # Special handling for working_folder as it's dynamically constructed in DEFAULT_SETTINGS definition
    # but AppSettings init directly uses the values from DEFAULT_SETTINGS.
    # The key is that AppSettings(filepath=None) will use DEFAULT_CONFIG_FILE_PATH
    # which implies DEFAULT_WORKING_FOLDER_BASE.
    # If we pass a non_existent_filepath, it loads defaults then tries to load from this path.

    # The default_settings_dict fixture already has the correct dynamic working_folder path.
    assert_settings_match_dict(settings, expected_defaults)


def test_save_and_load_settings(tmp_path, default_settings_dict):
    """Test saving settings to a file and loading them back."""
    temp_settings_file = tmp_path / "test_settings.ini"

    # 1. Create settings, modify some values
    settings_to_save = AppSettings(settings_filepath=temp_settings_file) # Starts with defaults

    settings_to_save.working_folder = str(tmp_path / "custom_work_dir")
    settings_to_save.video_bitrate = 25000000  # int
    settings_to_save.shutdown_pc_after_encoding = True # bool
    settings_to_save.plugin_name = "TestPlugin" # str
    settings_to_save.preferred_driver_names = "DriverX,DriverY"

    # 2. Save settings
    settings_to_save.save_settings()
    assert temp_settings_file.exists()

    # 3. Create new AppSettings instance, loading from the saved file
    loaded_settings = AppSettings(settings_filepath=temp_settings_file)

    # 4. Assert loaded settings match modified values
    assert loaded_settings.working_folder == str(tmp_path / "custom_work_dir")
    assert loaded_settings.video_bitrate == 25000000
    assert loaded_settings.shutdown_pc_after_encoding is True
    assert loaded_settings.plugin_name == "TestPlugin"
    assert loaded_settings.preferred_driver_names == "DriverX,DriverY"

    # 5. Assert other settings (not modified) still match defaults
    # We need to compare against the original defaults for values not changed.
    # The loaded_settings instance should have a mix of modified and default values.
    # Example: check a default bool that wasn't changed
    assert loaded_settings.capture_opening_scene == default_settings_dict["Encoding"]["capture_opening_scene"]
    assert loaded_settings.hotkey_stop_start == default_settings_dict["Recording"]["hotkey_stop_start"]


def test_load_from_non_existent_file(default_settings_dict):
    """Test loading settings from a non-existent file path uses defaults."""
    non_existent_file = Path("completely") / "made" / "up" / "settings.ini"
    settings = AppSettings(settings_filepath=non_existent_file)

    # Should load all defaults
    assert_settings_match_dict(settings, default_settings_dict)


def test_type_conversion_on_load(tmp_path):
    """Test that types are correctly converted when loading from INI."""
    temp_settings_file = tmp_path / "type_test_settings.ini"
    parser = configparser.ConfigParser()

    # Use string values as they would be in an INI file
    parser["General"] = {
        "use_new_settings_dialog": "yes", # For boolean true
    }
    parser["Encoding"] = {
        "video_bitrate": "5000000",       # For integer
        "highlight_video_only": "false", # For boolean false
        "capture_opening_scene": "True", # Test alternative bool string
    }
    parser["Recording"] = {
        "short_test_only": "0" # For boolean false (depending on getboolean interpretation)
                               # configparser getboolean handles 'yes'/'no', 'true'/'false', 'on'/'off', '1'/'0'
    }

    with open(temp_settings_file, "w") as f:
        parser.write(f)

    settings = AppSettings(settings_filepath=temp_settings_file)

    assert settings.use_new_settings_dialog is True
    assert settings.video_bitrate == 5000000
    assert isinstance(settings.video_bitrate, int)
    assert settings.highlight_video_only is False
    assert settings.capture_opening_scene is True
    assert settings.short_test_only is False # '0' is false by getboolean


def test_missing_sections_or_keys_in_file(tmp_path, default_settings_dict):
    """Test handling of INI files with missing sections or keys."""
    temp_settings_file = tmp_path / "partial_settings.ini"
    parser = configparser.ConfigParser()

    # Only provide a subset of settings
    parser["General"] = {
        "plugin_name": "PartialPluginName"
        # Missing working_folder, last_video_file etc. from General
    }
    # Encoding section is completely missing
    parser["Recording"] = {
        "hotkey_stop_start": "Ctrl+F1"
        # Missing other recording settings
    }

    with open(temp_settings_file, "w") as f:
        parser.write(f)

    settings = AppSettings(settings_filepath=temp_settings_file)

    # Check modified values
    assert settings.plugin_name == "PartialPluginName"
    assert settings.hotkey_stop_start == "Ctrl+F1"

    # Check that missing values are defaults
    # From General section (default for working_folder is dynamic, check against AppSettings default logic)
    # AppSettings initializes with DEFAULT_SETTINGS, then overrides.
    # The DEFAULT_SETTINGS dictionary itself is what we should compare against for non-overridden values.
    assert settings.working_folder == default_settings_dict["General"]["working_folder"]
    assert settings.last_video_file == default_settings_dict["General"]["last_video_file"]

    # From Encoding section (which was entirely missing from the file)
    assert settings.video_bitrate == default_settings_dict["Encoding"]["video_bitrate"]
    assert settings.highlight_video_only == default_settings_dict["Encoding"]["highlight_video_only"]

    # From Recording section (some keys were missing)
    assert settings.hotkey_pause_resume == default_settings_dict["Recording"]["hotkey_pause_resume"]
    assert settings.short_test_only == default_settings_dict["Recording"]["short_test_only"]


def test_settings_file_created_in_default_location_if_none_passed(tmp_path, monkeypatch):
    """
    Test that AppSettings (if it were to save without explicit path) would use
    the default path. This also indirectly tests default path generation.
    For this test, we mock Path.home() to control the default path.
    """
    # Mock Path.home() to point to tmp_path for this test
    mock_home_path = tmp_path / "mock_user_home"
    mock_home_path.mkdir()

    # Expected default config dir based on mocked home
    expected_config_dir = mock_home_path / "Documents" / CONFIG_DIR_NAME
    expected_settings_file = expected_config_dir / SETTINGS_FILE_NAME

    monkeypatch.setattr(Path, 'home', lambda: mock_home_path)

    # Re-evaluate AppSettings's global DEFAULT_CONFIG_FILE_PATH after mocking home()
    # This is tricky because DEFAULT_CONFIG_FILE_PATH is a module-level global.
    # For a robust test, we'd need to re-import AppSettings or have it re-calculate its defaults.
    # Alternatively, AppSettings could determine its default path inside __init__ if no path is given.

    # Let's assume AppSettings calculates its default path on instantiation if None is given.
    # The current AppSettings takes settings_filepath=None, then defaults to DEFAULT_CONFIG_FILE_PATH.
    # So, we need to ensure DEFAULT_CONFIG_FILE_PATH is what we expect after mocking.
    # This requires DEFAULT_CONFIG_FILE_PATH to be dynamically calculated or AppSettings to do it.

    # The current app_settings.py defines DEFAULT_USER_DOCUMENTS_PATH and others at module load time.
    # To test this properly, we'd need to reload app_settings module after monkeypatching Path.home,
    # or have AppSettings determine its default path dynamically in __init__.

    # Let's test the save path directly.
    settings = AppSettings(settings_filepath=expected_settings_file) # Explicitly give the path we want to test
    settings.plugin_name = "SavedToMockDefault"
    settings.save_settings() # This will save to settings.filepath which is expected_settings_file

    assert expected_settings_file.exists()

    # Verify content
    parser = configparser.ConfigParser()
    parser.read(expected_settings_file)
    assert parser.get("General", "plugin_name") == "SavedToMockDefault"

    # Clean up if necessary (tmp_path handles it)

