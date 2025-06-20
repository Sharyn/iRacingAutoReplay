import pytest
from pathlib import Path
from typing import List, Any, Dict

# Assuming pytest runs from the project root or paths are configured
from iracing_telemetry_analyzer_py.src.app_settings import AppSettings
from iracing_telemetry_analyzer_py.src.plugin_manager import PluginManager, OverlayPluginInterface, build_drawtext_filter
from iracing_telemetry_analyzer_py.src.replay_data import OverlayData # For mock


# --- Fixtures or Helper Classes ---

@pytest.fixture
def mock_app_settings(tmp_path: Path) -> AppSettings:
    """Provides AppSettings configured for testing."""
    # Using a real AppSettings instance, but its file path is within tmp_path
    settings_file_path = tmp_path / "settings_for_plugin_test.ini"
    settings = AppSettings(settings_filepath=settings_file_path)
    settings.working_folder = str(tmp_path / "plugin_test_output")
    Path(settings.working_folder).mkdir(parents=True, exist_ok=True)
    # Add any settings relevant to plugins, e.g., default font for build_drawtext_filter
    settings.preferred_font_path = "TestSans" # Example, actual font availability doesn't matter for string check
    settings.save_settings()
    return settings

@pytest.fixture
def mock_overlay_data() -> OverlayData:
    """Provides a minimal mock OverlayData instance."""
    # SimpleTimestampOverlay doesn't rely heavily on OverlayData content for filter generation
    # but initialize method expects it.
    return OverlayData()

@pytest.fixture
def plugins_directory() -> Path:
    """Returns the path to the plugins directory."""
    # This assumes the tests are run from a context where Path(__file__) is meaningful
    # and src/plugins is two levels up from tests/ and then down into src/plugins
    # tests/test_integration_plugin_system.py
    # parent -> tests/
    # parent.parent -> iracing_telemetry_analyzer_py/ (project root for this structure)
    # then src/plugins
    # This relative path needs to be robust based on test execution environment.
    # If tests are run from project root: 'iracing_telemetry_analyzer_py/src/plugins'
    # If tests dir is considered a package and src is sibling:
    # Path(__file__).parent = tests/
    # Path(__file__).parent.parent = iracing_telemetry_analyzer_py/
    # Path(__file__).parent.parent / "src" / "plugins"

    # Assuming the file structure is:
    # iracing_telemetry_analyzer_py/
    #   src/
    #     plugins/
    #       simple_timestamp_overlay.py
    #     plugin_manager.py
    #   tests/
    #     test_integration_plugin_system.py

    # Path to this test file
    test_file_path = Path(__file__).resolve()
    # Path to 'tests' directory
    tests_dir = test_file_path.parent
    # Path to 'iracing_telemetry_analyzer_py' directory (root of this namespaced package)
    project_pkg_root = tests_dir.parent
    # Path to 'src/plugins'
    plugins_dir = project_pkg_root / "src" / "plugins"

    # Ensure the example plugin (simple_timestamp_overlay.py) exists for the test to be meaningful.
    # This test doesn't create it; it assumes it's part of the source tree.
    example_plugin_file = plugins_dir / "simple_timestamp_overlay.py"
    if not example_plugin_file.exists():
        pytest.skip(f"Example plugin not found at {example_plugin_file}. Skipping plugin system integration test.")

    return plugins_dir


def test_load_plugins_and_generate_filters(
    mock_app_settings: AppSettings,
    mock_overlay_data: OverlayData,
    plugins_directory: Path
):
    """
    Tests loading plugins, setting an active plugin, and generating FFmpeg filters.
    """
    # 1. Setup
    plugin_manager = PluginManager(settings=mock_app_settings)

    # 2. Action: Load plugins
    plugin_manager.load_plugins(str(plugins_directory))

    # 3. Assertions for plugin loading
    available_plugins = plugin_manager.get_available_plugins()
    assert len(available_plugins) > 0, "PluginManager should have loaded at least one plugin."

    simple_timestamp_plugin_name = "Simple Timestamp"
    timestamp_plugin = plugin_manager.get_plugin_by_name(simple_timestamp_plugin_name)

    assert timestamp_plugin is not None, f"'{simple_timestamp_plugin_name}' should be loaded."
    assert isinstance(timestamp_plugin, OverlayPluginInterface)
    assert timestamp_plugin.name == simple_timestamp_plugin_name
    assert simple_timestamp_plugin_name in [p.name for p in available_plugins]

    # 4. Action: Set active plugin and get filters
    activated = plugin_manager.set_active_plugin(simple_timestamp_plugin_name, mock_overlay_data)
    assert activated, f"Failed to activate plugin '{simple_timestamp_plugin_name}'."

    test_timestamp = 10.525 # 10.53s
    video_width = 1920
    video_height = 1080

    filters: List[str] = plugin_manager.get_current_filters(
        timestamp_seconds=test_timestamp,
        video_width=video_width,
        video_height=video_height
    )

    # 5. Assertions for filter generation
    assert isinstance(filters, list), "get_current_filters should return a list."
    assert len(filters) == 1, "SimpleTimestampOverlay should return one filter string."

    filter_string = filters[0]
    assert "drawtext=" in filter_string, "Filter string should contain 'drawtext='."

    # Expected text: "Time: 00:10.53" (SimpleTimestampOverlay formats to 2 decimal places for seconds)
    # The plugin formats time as MM:SS.ss (05.2f for seconds part)
    expected_time_text = f"{int(test_timestamp // 60):02d}:{test_timestamp % 60:05.2f}" # 00:10.53
    expected_text_segment = f"text='Time: {expected_time_text}'"
    assert expected_text_segment in filter_string, \
        f"Filter string should contain correct timestamp text. Expected segment: '{expected_text_segment}', Got: '{filter_string}'"

    # Check for some basic styling from build_drawtext_filter via SimpleTimestampOverlay
    assert f"x=10" in filter_string
    assert f"y=10" in filter_string
    assert f"fontsize=36" in filter_string # As set in SimpleTimestampOverlay
    assert f"fontcolor=yellow" in filter_string # As set in SimpleTimestampOverlay
    assert f"box=1" in filter_string # Box is enabled in SimpleTimestampOverlay
    assert f"fontfile='{mock_app_settings.preferred_font_path}'" in filter_string # Check if font from settings is used

    # Test on_transcode_complete call (just ensure it doesn't error)
    try:
        plugin_manager.signal_transcode_complete()
    except Exception as e:
        pytest.fail(f"signal_transcode_complete() raised an exception: {e}")


def test_plugin_manager_no_active_plugin(mock_app_settings: AppSettings):
    """Test filter generation when no plugin is active."""
    plugin_manager = PluginManager(settings=mock_app_settings)
    # No plugins loaded or no active plugin set
    filters = plugin_manager.get_current_filters(10.0, 1920, 1080)
    assert filters == [], "Should return empty list if no active plugin."

def test_plugin_manager_activate_non_existent_plugin(
    mock_app_settings: AppSettings,
    mock_overlay_data: OverlayData,
    plugins_directory: Path
):
    """Test activating a plugin that doesn't exist."""
    plugin_manager = PluginManager(settings=mock_app_settings)
    plugin_manager.load_plugins(str(plugins_directory)) # Load existing ones

    activated = plugin_manager.set_active_plugin("NonExistentPlugin", mock_overlay_data)
    assert not activated, "Activating a non-existent plugin should fail (return False)."
    assert plugin_manager._active_plugin is None, "_active_plugin should be None after failed activation."

    filters = plugin_manager.get_current_filters(10.0, 1920, 1080)
    assert filters == [], "Should return empty list if plugin activation failed."

```
