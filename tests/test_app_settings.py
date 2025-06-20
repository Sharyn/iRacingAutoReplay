import unittest
import os
import configparser
import logging

# Add project root to path if src is not found.
# This is often needed if running tests directly from the 'tests' directory
# without pytest or proper PYTHONPATH setup.
import sys
# Assuming 'src' is at the same level as 'tests' directory
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# A better way for discoverability is to ensure the project is installed in editable mode
# or that the test runner (like pytest) handles path discovery.

# For this subtask, we assume that the `src` directory is directly importable.
# If ModuleNotFoundError occurs, path adjustments or test runner configurations are needed.
try:
    from src.app_settings import AppSettings
except ModuleNotFoundError:
    # Fallback for environments where src might not be in path by default
    # This is a common issue when running `python tests/test_app_settings.py` directly
    # without further setup. `pytest` usually handles this better.
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.app_settings import AppSettings


# Configure logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestAppSettings(unittest.TestCase):
    """Unit tests for the AppSettings class."""

    TEST_SETTINGS_FILE = "test_settings.ini"
    DEFAULT_SETTINGS_BACKUP_FILE = "settings.ini.bkp" # If default is 'settings.ini'

    @classmethod
    def setUpClass(cls):
        """Set up for all tests in this class."""
        # Configure a separate logger for test outputs if desired, or use root.
        # For simplicity, we'll assume root logger is fine or configured elsewhere.
        logger.info("Setting up TestAppSettings class.")

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in this class."""
        logger.info("Tearing down TestAppSettings class.")

    def setUp(self):
        """Set up for each test method."""
        logger.debug(f"Setting up test: {self._testMethodName}")
        # Ensure a clean slate for each test by removing any pre-existing test settings file
        if os.path.exists(self.TEST_SETTINGS_FILE):
            os.remove(self.TEST_SETTINGS_FILE)
        # If AppSettings uses a default "settings.ini", we might want to back it up
        # if AppSettings.DEFAULT_SETTINGS_FILE == "settings.ini" and os.path.exists("settings.ini"):
        #     os.rename("settings.ini", self.DEFAULT_SETTINGS_BACKUP_FILE)

        # Create a new AppSettings instance for each test, using the test file name
        self.settings = AppSettings(settings_file_path=self.TEST_SETTINGS_FILE)


    def tearDown(self):
        """Tear down after each test method."""
        logger.debug(f"Tearing down test: {self._testMethodName}")
        # Clean up the test settings file created during the test
        if os.path.exists(self.TEST_SETTINGS_FILE):
            os.remove(self.TEST_SETTINGS_FILE)
        # Restore default settings.ini if it was backed up
        # if os.path.exists(self.DEFAULT_SETTINGS_BACKUP_FILE):
        #     if os.path.exists("settings.ini"): # Should have been removed by AppSettings test
        #         os.remove("settings.ini")
        #     os.rename(self.DEFAULT_SETTINGS_BACKUP_FILE, "settings.ini")


    def test_01_default_settings_creation(self):
        """Test if settings file is created with default values."""
        logger.info("Running test_01_default_settings_creation")
        self.assertTrue(os.path.exists(self.TEST_SETTINGS_FILE))

        # Verify some default values
        config = configparser.ConfigParser()
        config.read(self.TEST_SETTINGS_FILE)

        self.assertEqual(config.get("General", "iracing_sdk_path"),
                         AppSettings.DEFAULT_SETTINGS["General"]["iracing_sdk_path"])
        self.assertEqual(config.get("UI", "theme"),
                         AppSettings.DEFAULT_SETTINGS["UI"]["theme"])
        self.assertEqual(config.getboolean("ReplayAnalysis", "auto_connect_sdk"),
                         True) # Based on default "true"
        self.assertEqual(config.getint("UI", "main_window_width"),
                         1280) # Based on default "1280"

    def test_02_get_setting(self):
        """Test retrieving settings."""
        logger.info("Running test_02_get_setting")
        # Check a default value
        self.assertEqual(self.settings.get_setting("UI", "theme"), "default")

        # Check a non-existent key with fallback
        self.assertEqual(self.settings.get_setting("NonExistentSection", "non_existent_key", fallback="test_fallback"),
                         "test_fallback")
        # Check a non-existent key in existing section with fallback
        self.assertEqual(self.settings.get_setting("General", "non_existent_key", fallback="another_fallback"),
                         "another_fallback")

    def test_03_update_and_save_setting(self):
        """Test updating and saving a setting."""
        logger.info("Running test_03_update_and_save_setting")
        new_theme = "dark_mode"
        self.settings.update_setting("UI", "theme", new_theme)
        self.settings.save_settings()

        # Create a new AppSettings instance to load from the saved file
        new_settings_instance = AppSettings(settings_file_path=self.TEST_SETTINGS_FILE)
        self.assertEqual(new_settings_instance.get_setting("UI", "theme"), new_theme)

        # Test updating a numeric value (it's stored as string but retrievable as type)
        self.settings.update_setting("UI", "main_window_width", "1920")
        self.settings.save_settings()
        new_settings_instance_2 = AppSettings(settings_file_path=self.TEST_SETTINGS_FILE)
        self.assertEqual(new_settings_instance_2.get_int_setting("UI", "main_window_width"), 1920)


    def test_04_get_boolean_setting(self):
        """Test retrieving boolean settings with type conversion."""
        logger.info("Running test_04_get_boolean_setting")
        # Default is "true"
        self.assertTrue(self.settings.get_boolean_setting("ReplayAnalysis", "auto_connect_sdk"))

        self.settings.update_setting("ReplayAnalysis", "auto_connect_sdk", "False")
        self.assertFalse(self.settings.get_boolean_setting("ReplayAnalysis", "auto_connect_sdk"))

        self.settings.update_setting("ReplayAnalysis", "auto_connect_sdk", "0")
        self.assertFalse(self.settings.get_boolean_setting("ReplayAnalysis", "auto_connect_sdk"))

        self.settings.update_setting("ReplayAnalysis", "auto_connect_sdk", "yes")
        self.assertTrue(self.settings.get_boolean_setting("ReplayAnalysis", "auto_connect_sdk"))

        # Test fallback for boolean
        self.assertTrue(self.settings.get_boolean_setting("NonExistent", "some_bool", fallback=True))
        self.assertFalse(self.settings.get_boolean_setting("NonExistent", "other_bool", fallback=False))

        # Test malformed boolean (should use fallback or raise depending on strictness, current AppSettings falls back)
        self.settings.update_setting("ReplayAnalysis", "malformed_bool", "maybe")
        self.settings.save_settings() # Save to ensure it's read back if AppSettings re-reads
        # Current AppSettings get_boolean_setting has error handling that returns fallback on ValueError
        self.assertFalse(self.settings.get_boolean_setting("ReplayAnalysis", "malformed_bool", fallback=False))
        self.assertTrue(self.settings.get_boolean_setting("ReplayAnalysis", "another_malformed", fallback=True))


    def test_05_get_int_setting(self):
        """Test retrieving integer settings with type conversion."""
        logger.info("Running test_05_get_int_setting")
        # Default is "1280"
        self.assertEqual(self.settings.get_int_setting("UI", "main_window_width"), 1280)

        self.settings.update_setting("UI", "main_window_width", "1024")
        self.assertEqual(self.settings.get_int_setting("UI", "main_window_width"), 1024)

        # Test fallback for integer
        self.assertEqual(self.settings.get_int_setting("NonExistent", "some_int", fallback=999), 999)

        # Test malformed integer (should use fallback or raise, current AppSettings falls back)
        self.settings.update_setting("UI", "malformed_int", "not_an_int")
        self.settings.save_settings()
        self.assertEqual(self.settings.get_int_setting("UI", "malformed_int", fallback=777), 777)


    def test_06_load_settings_file_not_found(self):
        """Test behavior when settings file doesn't exist (should create defaults)."""
        logger.info("Running test_06_load_settings_file_not_found")
        temp_settings_file = "non_existent_temp_settings.ini"
        if os.path.exists(temp_settings_file):
            os.remove(temp_settings_file)

        local_settings = AppSettings(settings_file_path=temp_settings_file)
        self.assertTrue(os.path.exists(temp_settings_file)) # File should be created
        self.assertEqual(local_settings.get_setting("UI", "theme"),
                         AppSettings.DEFAULT_SETTINGS["UI"]["theme"]) # Check a default

        if os.path.exists(temp_settings_file): # Clean up
            os.remove(temp_settings_file)

    def test_07_ensure_all_defaults_present_on_load(self):
        """Test that missing sections/keys are added from defaults when an old file is loaded."""
        logger.info("Running test_07_ensure_all_defaults_present_on_load")
        partial_settings_file = "partial_settings.ini"

        # Create a config file with only one section and one option
        config = configparser.ConfigParser()
        config.add_section("General")
        config.set("General", "iracing_sdk_path", "custom/path/for/test")
        # Deliberately omit "default_working_directory" from General
        # Deliberately omit the "UI" section entirely

        with open(partial_settings_file, 'w') as f:
            config.write(f)

        # Now load this partial file with AppSettings
        loaded_settings = AppSettings(settings_file_path=partial_settings_file)

        # Check that the custom value is retained
        self.assertEqual(loaded_settings.get_setting("General", "iracing_sdk_path"), "custom/path/for/test")

        # Check that the missing default key in "General" was added
        self.assertEqual(loaded_settings.get_setting("General", "default_working_directory"),
                         AppSettings.DEFAULT_SETTINGS["General"]["default_working_directory"])

        # Check that the missing "UI" section and its keys were added
        self.assertEqual(loaded_settings.get_setting("UI", "theme"),
                         AppSettings.DEFAULT_SETTINGS["UI"]["theme"])
        self.assertEqual(loaded_settings.get_int_setting("UI", "main_window_height"),
                         int(AppSettings.DEFAULT_SETTINGS["UI"]["main_window_height"]))

        # Verify the file itself was updated
        re_read_config = configparser.ConfigParser()
        re_read_config.read(partial_settings_file)
        self.assertTrue(re_read_config.has_option("General", "default_working_directory"))
        self.assertTrue(re_read_config.has_section("UI"))
        self.assertTrue(re_read_config.has_option("UI", "theme"))

        if os.path.exists(partial_settings_file):
            os.remove(partial_settings_file)


if __name__ == "__main__":
    # This allows running the tests directly using `python tests/test_app_settings.py`
    # It's often better to use a test runner like `pytest` or `python -m unittest discover`

    # If run directly, ensure logging is set up to see output from tests
    if not logging.getLoggerClass().root.hasHandlers(): # Check if root logger is configured
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # unittest.main() will discover and run tests in this file
    unittest.main()
