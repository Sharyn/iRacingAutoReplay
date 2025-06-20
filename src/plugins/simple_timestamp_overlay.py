"""
Example Overlay Plugin: Simple Timestamp Overlay.
Displays the current video timestamp on the screen.
"""

from typing import List, TYPE_CHECKING

# Assuming plugin_manager is in the parent directory relative to this plugin's location
# This import might need adjustment based on how plugins are finally loaded and sys.path is configured.
# For now, let's try a relative import path style that might work if 'src' is a package root.
# Or, rely on the PluginManager adding the plugin directory to sys.path or using importlib correctly.
# The provided PluginManager uses importlib.util.spec_from_file_location, so direct imports
# of other project modules might need careful handling (e.g. if they are not in sys.path).

# To access OverlayPluginInterface and build_drawtext_filter, we need to import them.
# If this plugin file is loaded by importlib by path, it doesn't automatically get the package context
# of the main application.
# A common way is to have the main app ensure its core modules are in sys.path,
# or the plugin interface definition is in a universally accessible place.

# Let's assume for now that plugin_manager (and thus its helpers) can be imported
# if the 'src' directory (parent of 'plugins') is in PYTHONPATH or recognized as a package.
try:
    from src.plugin_manager import OverlayPluginInterface, build_drawtext_filter
except ImportError:
    # Fallback for cases where relative import fails (e.g. script run directly, or complex loading)
    # This indicates a potential issue with how plugins will resolve dependencies on the core.
    # For now, this allows the file to be written, but runtime might fail if not loaded correctly.
    print("Warning (SimpleTimestampOverlay): Could not import OverlayPluginInterface or build_drawtext_filter via relative path.")
    # Define stubs if needed for the rest of the file to be syntactically valid,
    # though this means it won't work if the import truly fails at runtime.
    from abc import ABC, abstractmethod
    class OverlayPluginInterface(ABC):
        @property @abstractmethod
        def name(self) -> str: pass
        @property @abstractmethod
        def description(self) -> str: pass
        @abstractmethod
        def initialize(self, settings, overlay_data) -> None: pass
        @abstractmethod
        def get_ffmpeg_filter_options(self, ts, w, h) -> List[str]: pass
        @abstractmethod
        def on_transcode_complete(self) -> None: pass
    def build_drawtext_filter(*args, **kwargs) -> str: return "drawtext=text='Error: build_drawtext_filter not loaded'"


if TYPE_CHECKING:
    from src.app_settings import AppSettings
    from src.replay_data import OverlayData


class SimpleTimestampOverlay(OverlayPluginInterface):
    """
    An example plugin that displays the current video timestamp.
    """

    def __init__(self):
        self._settings: Optional['AppSettings'] = None
        self._overlay_data: Optional['OverlayData'] = None # Not strictly needed for this simple plugin

    @property
    def name(self) -> str:
        return "Simple Timestamp"

    @property
    def description(self) -> str:
        return "Displays the current video timestamp in the top-left corner."

    def initialize(self, settings: 'AppSettings', overlay_data: 'OverlayData') -> None:
        """
        Initializes the plugin with settings and overlay data.
        """
        self._settings = settings
        self._overlay_data = overlay_data # Store if needed for more complex plugins
        print(f"{self.name} plugin initialized.")
        # Example: Access a setting
        # preferred_font = getattr(self._settings, 'preferred_font_path', 'Arial')
        # print(f"{self.name}: Preferred font from settings: {preferred_font}")


    def get_ffmpeg_filter_options(
        self, timestamp_seconds: float, video_width: int, video_height: int
    ) -> List[str]:
        """
        Generates an FFmpeg drawtext filter to display the timestamp.
        """
        if self._settings is None:
            return [] # Not initialized

        # Format the timestamp (e.g., MM:SS.sss)
        minutes = int(timestamp_seconds // 60)
        seconds = timestamp_seconds % 60
        # Using a simple f-string for text. FFmpeg's own text expansion is more complex.
        # For FFmpeg text, special characters like ':', '%', '\' need escaping.
        # build_drawtext_filter should handle basic text escaping.
        time_str = f"{minutes:02d}:{seconds:05.2f}" # Example: 00:10.50

        # Position at top-left, with some padding
        x_pos = 10
        y_pos = 10

        font_path_setting = getattr(self._settings, 'preferred_font_path', 'sans') # Default to 'sans'

        # Use the helper to build the filter string
        drawtext_filter = build_drawtext_filter(
            text=f"Time: {time_str}",
            x=x_pos,
            y=y_pos,
            font_path=font_path_setting, # Use font from settings if available
            font_size=36,
            font_color="yellow",
            box=True,
            box_color="black@0.4"
        )
        return [drawtext_filter]

    def on_transcode_complete(self) -> None:
        """
        Called when transcoding is complete. No action needed for this plugin.
        """
        print(f"{self.name} plugin: Transcode complete notification received.")

# To make this plugin discoverable, it must be a class implementing OverlayPluginInterface.
# The PluginManager will instantiate it.

