import pytest
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox # For monkeypatching

# Assuming pytest runs from project root or paths are configured
# Adjust these imports based on your project structure and how pytest is run
from src.app_settings import AppSettings, DEFAULT_SETTINGS
from src.app_state_manager import AppStateManager
from src.ui.main_window import MainWindow
from src.plugin_manager import PluginManager
from src.replay_data import OverlayData

# Mock other managers that MainWindow expects but are not central to these specific tests
from src.iracing_manager import PlaceholderIRacingManager
from src.video_capture_manager import VideoCaptureManager
from src.replay_analyzer import ReplayAnalyzer
from src.ffmpeg_transcoder import FFmpegTranscoder


# --- Fixtures ---

@pytest.fixture
def mock_app_settings(tmp_path: Path) -> AppSettings:
    """Provides AppSettings using a temporary settings file."""
    settings_file = tmp_path / "test_settings.ini"
    settings = AppSettings(settings_filepath=settings_file)
    # Ensure a clean state by saving defaults if file didn't exist or was different
    settings.save_settings()
    return settings

@pytest.fixture
def mock_overlay_data() -> OverlayData:
    """Provides a minimal OverlayData instance for plugin initialization."""
    return OverlayData()

@pytest.fixture
def mock_plugin_manager(mock_app_settings: AppSettings, mock_overlay_data: OverlayData) -> PluginManager:
    """Provides a PluginManager with the SimpleTimestampOverlay loaded and active."""
    # This fixture loads plugins from the actual 'src/plugins' directory.

    test_file_path = Path(__file__).resolve()
    project_pkg_root = test_file_path.parent.parent.parent # iracing_telemetry_analyzer_py/
    plugins_dir = project_pkg_root / "src" / "plugins"

    example_plugin_file = plugins_dir / "simple_timestamp_overlay.py"
    if not example_plugin_file.exists():
        pytest.skip(f"Example plugin not found at {example_plugin_file}. Required for settings UI tests involving plugins.")

    pm = PluginManager(settings=mock_app_settings)
    pm.load_plugins(str(plugins_dir))

    # Set SimpleTimestampOverlay as active if loaded
    # This is important because MainWindow._load_settings_to_ui tries to set plugin from app_settings
    # and populates combo box. Let's ensure a known state.
    if pm.get_plugin_by_name("Simple Timestamp"):
        mock_app_settings.plugin_name = "Simple Timestamp" # Ensure this is the default for the test
        pm.set_active_plugin("Simple Timestamp", mock_overlay_data)
    else:
        pytest.fail("Simple Timestamp plugin could not be loaded or set as active for test setup.")
    return pm

@pytest.fixture
def main_window(qtbot, mock_app_settings: AppSettings, mock_plugin_manager: PluginManager):
    """Creates an instance of MainWindow with mocked dependencies."""
    # Create other necessary mock managers
    mock_app_state_manager = AppStateManager()
    mock_iracing_manager = PlaceholderIRacingManager()
    # VideoCaptureManager needs settings
    mock_video_capture_manager = VideoCaptureManager(settings=mock_app_settings)
    # ReplayAnalyzer needs iracing_manager and settings
    mock_replay_analyzer = ReplayAnalyzer(iracing_manager=mock_iracing_manager, settings=mock_app_settings)
    # FFmpegTranscoder needs settings and plugin_manager
    mock_ffmpeg_transcoder = FFmpegTranscoder(settings=mock_app_settings, plugin_manager=mock_plugin_manager)

    window = MainWindow(
        app_settings=mock_app_settings,
        app_state_manager=mock_app_state_manager,
        plugin_manager=mock_plugin_manager,
        replay_analyzer=mock_replay_analyzer,
        ffmpeg_transcoder=mock_ffmpeg_transcoder,
        video_capture_manager=mock_video_capture_manager
    )
    qtbot.addWidget(window)
    window.show() # Important for some UI elements to initialize properly
    return window

# --- Test Functions ---

def test_settings_tab_loads_initial_values(main_window: MainWindow, mock_app_settings: AppSettings):
    """Verify that UI elements in the Settings tab load initial values from AppSettings."""
    # String value
    assert main_window.ui_working_folder_edit.text() == mock_app_settings.working_folder

    # Boolean value (checkbox)
    assert main_window.ui_highlight_video_only_checkbox.isChecked() == mock_app_settings.highlight_video_only

    # Numerical value (spinbox, with conversion)
    expected_bitrate_mbps = mock_app_settings.video_bitrate // 1000000
    assert main_window.ui_video_bitrate_spinbox.value() == expected_bitrate_mbps

    # ComboBox (plugin selection)
    assert main_window.ui_plugin_combo.currentText() == mock_app_settings.plugin_name
    # Ensure the combo box actually contains the plugin name
    assert main_window.ui_plugin_combo.findText(mock_app_settings.plugin_name) != -1

def test_ui_changes_update_app_settings_memory(main_window: MainWindow, mock_app_settings: AppSettings, qtbot):
    """Test that changing UI widget values updates the in-memory AppSettings object."""

    # Test QLineEdit (working_folder)
    new_working_folder = str(Path(mock_app_settings.working_folder) / "new_subdir")
    main_window.ui_working_folder_edit.setText(new_working_folder)
    main_window.ui_working_folder_edit.editingFinished.emit() # Trigger the slot
    assert mock_app_settings.working_folder == new_working_folder

    # Test QCheckBox (highlight_video_only)
    original_highlight_only = mock_app_settings.highlight_video_only
    main_window.ui_highlight_video_only_checkbox.setChecked(not original_highlight_only)
    # toggled signal is emitted automatically by setChecked
    assert mock_app_settings.highlight_video_only == (not original_highlight_only)

    # Test QSpinBox (video_bitrate)
    new_bitrate_mbps = 25
    main_window.ui_video_bitrate_spinbox.setValue(new_bitrate_mbps)
    # valueChanged signal is emitted automatically by setValue
    assert mock_app_settings.video_bitrate == new_bitrate_mbps * 1000000 # Check conversion

    # Test QComboBox (plugin_name) - if there's another plugin to switch to
    if main_window.ui_plugin_combo.count() > 1:
        original_plugin_name = main_window.ui_plugin_combo.currentText()
        new_plugin_index = (main_window.ui_plugin_combo.currentIndex() + 1) % main_window.ui_plugin_combo.count()
        main_window.ui_plugin_combo.setCurrentIndex(new_plugin_index)
        # currentTextChanged signal is emitted automatically by setCurrentIndex if text actually changes
        new_plugin_name = main_window.ui_plugin_combo.itemText(new_plugin_index)
        assert mock_app_settings.plugin_name == new_plugin_name
    elif main_window.ui_plugin_combo.count() == 1:
        # Test setting to the same value, ensure it doesn't break
        current_plugin = main_window.ui_plugin_combo.currentText()
        main_window.ui_plugin_combo.setCurrentText(current_plugin) # Should re-emit if text is same but forced
        assert mock_app_settings.plugin_name == current_plugin
    else:
        print("WARN: Plugin combo box has less than 1 item, cannot fully test plugin change.")


def test_save_settings_button(main_window: MainWindow, mock_app_settings: AppSettings, monkeypatch):
    """Test that the 'Save Settings' button persists changes from AppSettings to file."""
    # Mock QMessageBox.information to prevent dialog popup
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: QMessageBox.StandardButton.Ok)

    # 1. Modify a setting via UI, which updates main_window.app_settings (in-memory)
    new_bitrate_mbps = 30
    main_window.ui_video_bitrate_spinbox.setValue(new_bitrate_mbps) # Updates app_settings.video_bitrate
    assert main_window.app_settings.video_bitrate == new_bitrate_mbps * 1000000

    # 2. Click "Save Settings" button
    main_window.ui_save_settings_button.click()

    # 3. Create a new AppSettings instance, loading from the same file
    # The file path is stored in main_window.app_settings.filepath
    reloaded_settings = AppSettings(settings_filepath=main_window.app_settings.filepath)

    # 4. Assert the new instance has the saved value
    assert reloaded_settings.video_bitrate == new_bitrate_mbps * 1000000

def test_reset_settings_button(main_window: MainWindow, mock_app_settings: AppSettings, monkeypatch):
    """Test that 'Reset to Defaults' button reverts AppSettings and UI to defaults."""
    # Mock QMessageBox.question to auto-confirm "Yes"
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    # Mock QMessageBox.information as well
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: QMessageBox.StandardButton.Ok)

    # 1. Change a setting via UI and verify it's changed in app_settings
    original_hotkey = mock_app_settings.hotkey_stop_start
    changed_hotkey = "Ctrl+Alt+End"
    assert changed_hotkey != original_hotkey # Ensure we are actually changing it

    main_window.ui_hotkey_start_stop_edit.setText(changed_hotkey)
    main_window.ui_hotkey_start_stop_edit.editingFinished.emit() # Trigger update
    assert main_window.app_settings.hotkey_stop_start == changed_hotkey

    # 2. Click "Reset to Defaults" button
    main_window.ui_reset_settings_button.click()

    # 3. Assert the setting in app_settings has reverted to its default value
    # We need the actual default value from DEFAULT_SETTINGS for hotkey_stop_start
    default_hotkey = DEFAULT_SETTINGS['Recording']['hotkey_stop_start']
    assert main_window.app_settings.hotkey_stop_start == default_hotkey

    # 4. Assert the UI widget itself has been updated to reflect this default value
    assert main_window.ui_hotkey_start_stop_edit.text() == default_hotkey

    # 5. Test another type, e.g., a checkbox
    default_highlight_only = DEFAULT_SETTINGS['Encoding']['highlight_video_only']
    main_window.ui_highlight_video_only_checkbox.setChecked(not default_highlight_only)
    assert main_window.app_settings.highlight_video_only == (not default_highlight_only)

    main_window.ui_reset_settings_button.click() # Click reset again
    assert main_window.app_settings.highlight_video_only == default_highlight_only
    assert main_window.ui_highlight_video_only_checkbox.isChecked() == default_highlight_only

