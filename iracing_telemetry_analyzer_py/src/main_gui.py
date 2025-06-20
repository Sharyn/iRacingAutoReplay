"""
Main GUI application script for the iRacing Telemetry Analyzer.
Initializes backend components, sets up the main window, and starts the Qt event loop.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

# Assuming the script is run from the root of the project or 'src' is in PYTHONPATH
# Adjust imports based on actual execution context if necessary.
try:
    from iracing_telemetry_analyzer_py.src.app_settings import AppSettings
    from iracing_telemetry_analyzer_py.src.app_state_manager import AppStateManager, AppStates
    from iracing_telemetry_analyzer_py.src.ui.main_window import MainWindow
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import PyIrSdkManager, PYIRSDK_AVAILABLE # Changed to PyIrSdkManager
    from iracing_telemetry_analyzer_py.src.video_capture_manager import VideoCaptureManager
    from iracing_telemetry_analyzer_py.src.replay_analyzer import ReplayAnalyzer
    from iracing_telemetry_analyzer_py.src.ffmpeg_transcoder import FFmpegTranscoder
    from iracing_telemetry_analyzer_py.src.plugin_manager import PluginManager
    from iracing_telemetry_analyzer_py.src.replay_data import OverlayData # For mock overlay data in main if needed
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure the script is run from a context where 'src' modules are discoverable.")
    print("For example, run 'python -m iracing_telemetry_analyzer_py.src.main_gui' from the project root,")
    print("or ensure 'iracing_telemetry_analyzer_py' is in PYTHONPATH.")
    sys.exit(1)


def main():
    """
    Main function to initialize and run the application.
    """
    app = QApplication(sys.argv)

    # 1. Initialize Core Settings and State Management
    # AppSettings will try to load from its default path or use defaults.
    app_settings = AppSettings()
    app_state_manager = AppStateManager()

    # Log initial state (e.g., application started)
    app_state_manager.change_state(
        AppStates.IDLE,
        "Application initialized. All systems nominal.",
        force_notify=True # Ensure UI updates with initial message
    )

    # 2. Initialize Plugin Manager and Load Plugins
    plugin_manager = PluginManager(settings=app_settings)
    # Determine plugin directory: relative to this script's location in src/
    # Assuming main_gui.py is in src/, and plugins are in src/plugins/
    # Path(__file__) is src/main_gui.py
    # Path(__file__).parent is src/
    # Path(__file__).parent / "plugins" is src/plugins/
    script_dir = Path(__file__).parent.resolve()
    plugins_dir = script_dir / "plugins"
    print(f"Loading plugins from: {plugins_dir}")
    plugin_manager.load_plugins(str(plugins_dir))

    # Set a default active plugin if any are loaded
    available_plugins = plugin_manager.get_available_plugins()
    if available_plugins:
        # For now, just pick the first one as default or a specific named one
        # In a real app, this might come from settings.
        default_plugin_name = available_plugins[0].name
        # Create a dummy OverlayData for plugin initialization if needed here,
        # or expect MainWindow to handle setting active plugin later when actual data is ready.
        # For now, let's not initialize it here, let UI/workflow do it.
        # plugin_manager.set_active_plugin(default_plugin_name, OverlayData())
        print(f"Default plugin to be potentially activated: {default_plugin_name}")
        # The MainWindow will need the plugin_manager to populate any plugin selection UI.
    else:
        print("No plugins found or loaded.")
        app_state_manager.change_state(AppStates.IDLE, "Warning: No plugins loaded.", force_notify=True)


    # 3. Initialize Backend Managers (Service Locators or similar)
    # Use PyIrSdkManager
    iracing_manager = PyIrSdkManager()

    video_capture_manager = VideoCaptureManager(settings=app_settings) # Pass settings

    replay_analyzer = ReplayAnalyzer(
        iracing_manager=iracing_manager,
        settings=app_settings
    )

    ffmpeg_transcoder = FFmpegTranscoder(
        settings=app_settings,
        plugin_manager=plugin_manager # Pass plugin_manager
    )

    # 4. Initialize and Show Main Window
    main_window = MainWindow(
        app_settings=app_settings,
        app_state_manager=app_state_manager,
        plugin_manager=plugin_manager,
        replay_analyzer=replay_analyzer,
        ffmpeg_transcoder=ffmpeg_transcoder,
        video_capture_manager=video_capture_manager,
        iracing_manager=iracing_manager # Pass the actual iracing_manager
    )

    # Attempt initial connection to iRacing
    print("Attempting initial connection to iRacing SDK...")
    iracing_manager.connect()
    # Initial status update based on connection attempt
    if iracing_manager.is_connected():
        app_state_manager.change_state(AppStates.IDLE, "Successfully connected to iRacing.", force_notify=True)
    else:
        status_msg = "Failed to connect to iRacing."
        if not PYIRSDK_AVAILABLE:
            status_msg += " (pyirsdk library not found/mocked)"
        else:
            status_msg += " (iRacing not running or SDK not active)"
        app_state_manager.change_state(AppStates.IDLE, status_msg, force_notify=True)


    main_window.show()

    # 5. Start Qt Event Loop
    exit_code = app.exec()

    # Ensure disconnection when application is closing
    print("Application closing, disconnecting from iRacing SDK...")
    iracing_manager.disconnect()

    sys.exit(exit_code)


if __name__ == '__main__':
    # This structure allows running the GUI by executing this script directly.
    # Ensure that the iracing_telemetry_analyzer_py (parent of src) is in PYTHONPATH
    # or run using `python -m iracing_telemetry_analyzer_py.src.main_gui` from project root.

    # Example of how to adjust sys.path if needed when running script directly:
    # current_script_path = Path(__file__).resolve()
    # project_root = current_script_path.parent.parent.parent # Assuming src/main_gui.py, so up three levels
    # src_path = current_script_path.parent.parent # Assuming src/
    # if str(project_root) not in sys.path:
    #    sys.path.insert(0, str(project_root))
    # if str(src_path) not in sys.path:
    #    sys.path.insert(0, str(src_path))

    main()

```
