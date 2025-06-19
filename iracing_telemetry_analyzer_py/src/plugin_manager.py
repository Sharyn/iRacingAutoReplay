"""
Manages overlay plugins for video processing.
"""

import importlib
import inspect
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app_settings import AppSettings
    from .replay_data import OverlayData


# --- FFmpeg Helper ---

def build_drawtext_filter(
    text: str,
    x: int,
    y: int,
    font_path: str = "sans", # Default to system sans-serif if path not specified
    font_size: int = 24,
    font_color: str = "white",
    box: bool = False,
    box_color: str = "black@0.5" # Black with 50% opacity
) -> str:
    """
    Builds an FFmpeg drawtext filter string.

    Args:
        text: The text to display. Needs to be escaped for FFmpeg.
        x: X-coordinate for the text.
        y: Y-coordinate for the text.
        font_path: Path to the font file or font name (OS dependent).
        font_size: Font size.
        font_color: Font color.
        box: Whether to draw a box behind the text.
        box_color: Color of the box if drawn.

    Returns:
        A string formatted for use with FFmpeg's drawtext filter.
    """
    # FFmpeg text escaping: ' \ : %
    # For simplicity, we'll only escape single quotes for now as they delimit the text itself.
    # A more robust solution would escape all special characters.
    escaped_text = text.replace("'", "\\'")

    filter_str = f"drawtext=text='{escaped_text}':x={x}:y={y}:fontsize={font_size}:fontcolor={font_color}"
    if font_path:
        # FFmpeg fontfile path needs specific escaping, especially on Windows
        # For now, assume path is okay or user handles it.
        # A common way for cross-platform is to use a known font name if available.
        # If font_path is not a full path, it's a font name.
        # If it's a path, it should be absolute or relative to where ffmpeg runs.
        # Let's assume font_path is either a system font name or a correctly formatted path.
        filter_str += f":fontfile='{font_path}'" # Quotes around font_path for paths with spaces

    if box:
        filter_str += f":box=1:boxcolor={box_color}:boxborderw=5" # boxborderw is padding
    return filter_str


# --- Plugin Interface ---

class OverlayPluginInterface(ABC):
    """
    Abstract base class for overlay plugins.
    Plugins provide FFmpeg filter options based on timestamps and video dimensions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the plugin."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the plugin does."""
        pass

    @abstractmethod
    def initialize(self, settings: 'AppSettings', overlay_data: 'OverlayData') -> None:
        """
        Called once when the plugin is selected as active.
        Allows the plugin to prepare based on settings and the full replay data.

        Args:
            settings: The application settings.
            overlay_data: The fully parsed OverlayData from the replay.
        """
        pass

    @abstractmethod
    def get_ffmpeg_filter_options(
        self, timestamp_seconds: float, video_width: int, video_height: int
    ) -> List[str]:
        """
        Generates FFmpeg filter strings for the given timestamp and video dimensions.

        Args:
            timestamp_seconds: The current timestamp in the video (in seconds).
            video_width: The width of the video frame.
            video_height: The height of the video frame.

        Returns:
            A list of FFmpeg filter strings (e.g., drawtext, overlay filters).
            Each string is a complete filter definition.
        """
        pass

    @abstractmethod
    def on_transcode_complete(self) -> None:
        """
        Called after the video transcoding process is finished.
        Plugins can use this for any cleanup or finalization tasks.
        """
        pass


# --- Plugin Manager ---

class PluginManager:
    """
    Manages the discovery, loading, and interaction with overlay plugins.
    """

    def __init__(self, settings: 'AppSettings'):
        """
        Initializes the PluginManager.

        Args:
            settings: The application settings.
        """
        self.settings = settings
        self._plugins: Dict[str, OverlayPluginInterface] = {}
        self._active_plugin: Optional[OverlayPluginInterface] = None

    def load_plugins(self, plugin_directory: str) -> None:
        """
        Scans the plugin_directory for Python files, imports them,
        and discovers classes that implement OverlayPluginInterface.

        Args:
            plugin_directory: The path to the directory containing plugin modules.
        """
        self._plugins = {} # Resetting loaded plugins
        plugin_path = Path(plugin_directory)

        if not plugin_path.is_dir():
            print(f"Plugin directory {plugin_directory} not found or not a directory.")
            return

        for p_file in plugin_path.glob("*.py"):
            if p_file.name == "__init__.py":
                continue # Skip __init__.py files

            module_name = p_file.stem
            # Create a full module path for importlib like 'iracing_telemetry_analyzer_py.src.plugins.module_name'
            # This requires plugin_directory to be relative to something in sys.path or be added to sys.path.
            # A simpler way for standalone scripts/plugins is to use the file path directly.
            # For a package structure, we need to construct the proper module name.
            # Assuming plugin_directory is like 'iracing_telemetry_analyzer_py/src/plugins'
            # and the root 'iracing_telemetry_analyzer_py' is in sys.path or is the current structure.

            # Let's construct the module name based on the package structure
            # Example: if plugin_path is /abs/path/to/iracing_telemetry_analyzer_py/src/plugins
            # and current working dir is /abs/path/to/
            # then module should be iracing_telemetry_analyzer_py.src.plugins.module_name
            # This can get tricky. A common approach is to add plugin_path to sys.path temporarily
            # or rely on the existing package structure.
            # For now, assume the context allows direct import from the package.

            # For example, if plugin_directory is 'iracing_telemetry_analyzer_py/src/plugins'
            # and the root of the project is in sys.path:
            # module_import_path = f"iracing_telemetry_analyzer_py.src.plugins.{module_name}"
            # This requires this code to know its own package structure deeply.

            # A more robust way for dynamic loading from a specific path:
            try:
                spec = importlib.util.spec_from_file_location(module_name, str(p_file.resolve()))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                else:
                    print(f"Could not create spec for module {module_name} from {p_file}")
                    continue
            except Exception as e:
                print(f"Error importing plugin module {module_name} from {p_file}: {e}")
                continue

            for name, cls in inspect.getmembers(module, inspect.isclass):
                if (issubclass(cls, OverlayPluginInterface) and
                        cls is not OverlayPluginInterface and
                        not inspect.isabstract(cls)): # Ensure it's a concrete implementation
                    try:
                        plugin_instance = cls()
                        if plugin_instance.name in self._plugins:
                            print(
                                f"Warning: Duplicate plugin name '{plugin_instance.name}' "
                                f"(from module '{module_name}'). Skipping class '{cls.__name__}'."
                            )
                        else:
                            self._plugins[plugin_instance.name] = plugin_instance
                            print(f"Loaded plugin: '{plugin_instance.name}' from module '{module_name}'.")
                    except Exception as e:
                        print(f"Error instantiating plugin '{name}' from module '{module_name}': {e}")

        print(f"Plugin loading complete. Found {len(self._plugins)} plugins.")


    def get_available_plugins(self) -> List[OverlayPluginInterface]:
        """Returns a list of all loaded and valid plugin instances."""
        return list(self._plugins.values())

    def get_plugin_by_name(self, name: str) -> Optional[OverlayPluginInterface]:
        """
        Retrieves a loaded plugin instance by its name.

        Args:
            name: The name of the plugin to retrieve.

        Returns:
            The plugin instance, or None if not found.
        """
        return self._plugins.get(name)

    def set_active_plugin(self, plugin_name: str, overlay_data: 'OverlayData') -> bool:
        """
        Sets the currently active plugin and calls its initialize method.

        Args:
            plugin_name: The name of the plugin to activate.
            overlay_data: The OverlayData to pass to the plugin's initialize method.

        Returns:
            True if the plugin was successfully activated, False otherwise.
        """
        plugin = self.get_plugin_by_name(plugin_name)
        if plugin:
            try:
                plugin.initialize(settings=self.settings, overlay_data=overlay_data)
                self._active_plugin = plugin
                print(f"Active plugin set to: {plugin_name}")
                return True
            except Exception as e:
                print(f"Error initializing plugin {plugin_name}: {e}")
                self._active_plugin = None
                return False
        else:
            print(f"Error: Plugin '{plugin_name}' not found.")
            self._active_plugin = None
            return False

    def get_current_filters(
        self, timestamp_seconds: float, video_width: int, video_height: int
    ) -> List[str]:
        """
        Calls get_ffmpeg_filter_options on the currently active plugin.

        Args:
            timestamp_seconds: The current timestamp in the video.
            video_width: The width of the video.
            video_height: The height of the video.

        Returns:
            A list of FFmpeg filter strings, or an empty list if no active plugin
            or an error occurs.
        """
        if self._active_plugin:
            try:
                return self._active_plugin.get_ffmpeg_filter_options(
                    timestamp_seconds, video_width, video_height
                )
            except Exception as e:
                print(f"Error getting filters from plugin {self._active_plugin.name}: {e}")
                return []
        return []

    def signal_transcode_complete(self) -> None:
        """Signals the active plugin that transcoding is complete."""
        if self._active_plugin:
            try:
                self._active_plugin.on_transcode_complete()
            except Exception as e:
                print(f"Error calling on_transcode_complete for plugin {self._active_plugin.name}: {e}")


if __name__ == '__main__':
    print("--- PluginManager Demonstration ---")

    # Mock AppSettings and OverlayData for the demo
    class MockAppSettings:
        def __init__(self):
            self.some_setting = "test_value"
            # Define any settings your plugins might expect, e.g., preferred font
            self.preferred_font_path = "Arial" # Example

    class MockOverlayData:
        def __init__(self):
            self.some_data = "replay_info"
            # Add fields that a plugin might access, e.g., race_events
            self.race_events = []


    mock_settings = MockAppSettings()
    mock_overlay_data = MockOverlayData()

    # PluginManager expects AppSettings instance
    plugin_manager = PluginManager(settings=mock_settings)

    # Define the path to the plugins directory relative to this file's location
    # This assumes plugin_manager.py is in src/ and plugins are in src/plugins/
    # Path(__file__) gives path to current file (plugin_manager.py)
    # .parent gives src/
    # / "plugins" gives src/plugins/
    plugins_dir_path = Path(__file__).parent / "plugins"
    print(f"Attempting to load plugins from: {plugins_dir_path.resolve()}")

    # Before loading, we need to ensure the example plugin exists there.
    # The test environment will create it in a subsequent step.
    # For this demo to run standalone, we'd need to create a dummy plugin file here,
    # or ensure it's already present.

    # Create a dummy plugin file for the demo if it doesn't exist
    # (This part is tricky as this script itself is being created by the tool)
    # Let's assume the SimpleTimestampOverlay plugin will be created by the next tool call.
    # For now, loading might find nothing if that file isn't there yet.

    plugin_manager.load_plugins(str(plugins_dir_path))

    available_plugins = plugin_manager.get_available_plugins()
    if not available_plugins:
        print(
            "No plugins loaded. Ensure 'simple_timestamp_overlay.py' exists in the "
            f"'{plugins_dir_path.name}' directory."
        )
        print("If running this script directly, the example plugin might not be created yet by the parent process.")
    else:
        print("\nAvailable plugins:")
        for plugin in available_plugins:
            print(f"  - Name: '{plugin.name}', Description: '{plugin.description}'")

        # Try to set the example plugin as active
        plugin_to_activate = "Simple Timestamp"
        print(f"\nAttempting to set active plugin to: '{plugin_to_activate}'...")
        if plugin_manager.set_active_plugin(plugin_to_activate, mock_overlay_data):
            print(f"Plugin '{plugin_to_activate}' activated successfully.")

            print("\nGetting filter options for a few sample timestamps:")
            timestamps_to_test = [0.0, 10.5, 60.333]
            video_width, video_height = 1920, 1080 # Example dimensions
            for ts in timestamps_to_test:
                filters = plugin_manager.get_current_filters(ts, video_width, video_height)
                print(f"  Timestamp {ts:.2f}s (Video: {video_width}x{video_height}) - Filters: {filters}")

            print("\nSimulating transcode completion signal to active plugin...")
            plugin_manager.signal_transcode_complete()
        else:
            print(f"ERROR: Failed to activate plugin '{plugin_to_activate}'.")

    print("\nPluginManager demonstration finished.")

```
