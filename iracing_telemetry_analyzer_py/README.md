# iRacing Telemetry Analyzer & Replay Director

## Introduction

The iRacing Telemetry Analyzer & Replay Director is a Python application designed to help iRacing users analyze their race replay data, automatically generate highlight reels, and overlay custom information onto videos. It provides tools for parsing replay data, controlling external video capture software, editing video segments, and transcoding final output with dynamic overlays.

This application is currently under development.

## Features

*   **Replay Analysis (Simulated):** Processes iRacing replay data to identify key events like incidents, overtakes, and battles. (Currently uses simulated data generation).
*   **Overlay Data Generation:** Creates a structured `.replayscript.xml` file containing synchronized event data, leaderboard snapshots, camera changes, and messages.
*   **Video Highlight Generation:** Automatically selects interesting segments from a race to create highlight reels based on event importance and user-defined duration.
*   **FFmpeg Transcoding:** Uses FFmpeg (via `ffmpeg-python`) to process source videos, apply overlays, and transcode them into final formats.
*   **Plugin System for Overlays:** Supports custom overlay plugins to draw dynamic information on videos during transcoding (e.g., timestamps, leaderboards). Includes a simple timestamp overlay plugin as an example.
*   **External Video Capture Control (Conceptual):** Designed to control external screen recording software (like OBS, Action!) via global hotkeys for starting, stopping, and pausing recordings. (Actual capture relies on user having compatible software).
*   **GUI Interface:** Provides a PyQt6-based graphical user interface for managing analysis, transcoding, and application settings.
*   **Cross-Platform (Goal):** Developed with cross-platform compatibility in mind (Windows, Linux, macOS), though some features like hotkey sending might require OS-specific adjustments.

## Prerequisites

### For End-Users (Packaged Version - Conceptual)

*   A compatible operating system (Windows, macOS, Linux).
*   FFmpeg and ffprobe: **Bundled with the packaged application.** No separate installation should be required.
*   (Optional) An external screen recording software compatible with global hotkeys if using the video capture assistance features.

### For Developers

*   **Git:** For cloning the repository.
*   **Python:** Version 3.9 or higher.
*   **pip:** Python package installer (usually comes with Python).
*   **FFmpeg:** The `ffmpeg` and `ffprobe` command-line tools must be installed and accessible in your system's PATH. This is used by `ffmpeg-python` and for creating test media.
*   **Virtual Environment Tool:** Recommended (e.g., `venv`, `virtualenv`).

## Installation

### For End-Users (Packaged Version - Conceptual)

1.  Download the latest release for your operating system from the (conceptual) releases page.
2.  Extract the archive to a folder.
3.  Run the executable (e.g., `iRacingReplayDirectorPY.exe` on Windows).

### For Developers

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/iracing_telemetry_analyzer_py.git
    cd iracing_telemetry_analyzer_py
    ```
    (Replace `yourusername` with the actual repository URL if it's hosted.)

2.  **Create and Activate a Virtual Environment:**
    It's highly recommended to use a virtual environment.
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    The project uses `pyproject.toml` for dependency management. Install the project in editable mode along with development dependencies (which include `pytest`, `pytest-qt`, `PyInstaller`). This command should be run from the root of the `iracing_telemetry_analyzer_py` directory (where `pyproject.toml` is located).
    ```bash
    pip install -e .[dev]
    ```
    The `dev` extras group should be defined in `pyproject.toml` and include tools like `pytest`, `pytest-qt`, and `PyInstaller`.

## Development Setup with PyCharm (Recommended for Developers)

These instructions provide a detailed guide for setting up the project in PyCharm.

1.  **Prerequisites:**
    *   Ensure Git and Python 3.9+ are installed on your system.
    *   Install PyCharm (Community or Professional Edition).

2.  **Clone the Repository:**
    Use your preferred method (e.g., Git command line, PyCharm's "Get from VCS" feature) to clone the project repository to your local machine.
    ```bash
    git clone https://github.com/yourusername/iracing_telemetry_analyzer_py.git
    ```

3.  **Open the Project in PyCharm:**
    *   Launch PyCharm.
    *   Select "Open" and navigate to the directory where you cloned the repository.
    *   It's generally recommended to open the `iracing_telemetry_analyzer_py` directory itself as the PyCharm project root.

4.  **Python Interpreter & Virtual Environment:**
    *   PyCharm usually detects if a project needs a Python interpreter configured. It might prompt you to configure one or automatically pick one up.
    *   **Create/Set Virtual Environment:**
        *   Go to `File > Settings` (or `PyCharm > Preferences` on macOS).
        *   Navigate to `Project: iracing_telemetry_analyzer_py > Python Interpreter`.
        *   If no interpreter is selected or if you want to create a new venv:
            *   Click the gear icon (⚙️) or "Add Interpreter..." link.
            *   Select "Add Local Interpreter".
            *   Choose "Virtualenv Environment" from the left pane.
            *   Select "New" and ensure the "Base interpreter" points to your Python 3.9+ installation. The "Location" will typically default to a `venv` folder within your project root.
            *   Click "OK".
        *   PyCharm will create the virtual environment and set it as the project interpreter.

5.  **Installing Dependencies:**
    *   Once the virtual environment is set up and selected, open PyCharm's built-in **Terminal** (`View > Tool Windows > Terminal`).
    *   Ensure your virtual environment is activated in the terminal (e.g., `(venv)` should appear in the prompt).
    *   Navigate to the project root directory (`iracing_telemetry_analyzer_py`) if not already there. This is the directory containing `pyproject.toml`.
    *   Install the project in editable mode with development dependencies:
        ```bash
        pip install -e .[dev]
        ```
        (This assumes `pytest`, `pytest-qt`, `PyInstaller`, and other development tools are listed under a `[project.optional-dependencies.dev]` group in your `pyproject.toml`.)

6.  **Project Structure in PyCharm (Marking Sources Root):**
    *   In the "Project" tool window (usually on the left), right-click on the `src` directory (i.e., `iracing_telemetry_analyzer_py/src`).
    *   Select `Mark Directory as > Sources Root`.
    *   **Why?** This tells PyCharm that imports should be resolved relative to the `src` directory, matching how Python will see it if `src` is effectively the package root or added to `PYTHONPATH`. This helps with code completion and navigation for imports like `from app_settings import AppSettings` when working with files within `src`.

7.  **Running/Debugging the GUI:**
    *   Go to `Run > Edit Configurations...`.
    *   Click the `+` (Add New Configuration) button and select "Python".
    *   **Name:** Enter a descriptive name, e.g., "Run App GUI".
    *   **Script path:** Click the folder icon and navigate to `src/main_gui.py` within your project structure (e.g., `.../iracing_telemetry_analyzer_py/src/main_gui.py`).
    *   **Working directory:** Set this to your project root directory (e.g., the path to `iracing_telemetry_analyzer_py`). This ensures that relative paths used in the application (like for loading settings or plugins) are resolved correctly from the project root.
    *   **Python interpreter:** Ensure this is set to the project's virtual environment interpreter you configured earlier.
    *   Click "OK" or "Apply".
    *   You can now run or debug the application using this configuration from the PyCharm toolbar.

8.  **Running Tests:**
    *   PyCharm has excellent integration with `pytest`.
    *   After installing dependencies (including `pytest` and `pytest-qt`), PyCharm should automatically discover tests in your `tests` directory.
    *   You can typically run tests by:
        *   Right-clicking on the `tests` directory (or a specific test file/function) and selecting "Run 'pytest in tests'" (or similar).
        *   Opening a test file and clicking the green play icons in the gutter next to test functions or classes.
    *   Test results will be displayed in PyCharm's Test Runner tool window.

## Configuration

The application uses a `settings.ini` file to store its configuration. When run for the first time, if this file doesn't exist, it will be created with default values in a directory typically located at:
*   Windows: `C:\\Users\\YourUser\\Documents\\IracingReplayDirectorPy\\settings.ini`
*   Linux/macOS: `~/Documents/IracingReplayDirectorPy/settings.ini` (This path might vary based on `Path.home()` behavior; a platform-specific app data directory is a future improvement).

Key settings include:

*   **`working_folder`**: The main directory where output files (replay scripts, transcoded videos) will be saved.
*   **`plugin_name`**: The name of the default overlay plugin to use for video transcoding.
*   **`hotkey_stop_start`**: Hotkey string to signal external screen recording software to start/stop recording (e.g., `Ctrl+Shift+S`).
*   **`hotkey_pause_resume`**: Hotkey string to signal external screen recording software to pause/resume.
    *   **Hotkey Format**: Hotkeys are parsed by `pyautogui`. Modifiers are `ctrl`, `alt`, `shift`, `win` (or `command`/`cmd` on macOS). Keys are generally lowercase (e.g., 's', 'p', 'f9'). Special keys include 'space', 'enter', 'tab', 'esc', 'pause', etc. Combine with `+`, e.g., `ctrl+shift+f10`.
*   **`video_bitrate`**: Target bitrate for transcoded videos in bps (bits per second). For example, `15000000` for 15 Mbps.
*   **`highlight_video_target_duration_seconds`**: Desired total length for generated highlight videos.
*   Various boolean flags to control application behavior (e.g., `shutdown_pc_after_encoding`, `highlight_video_only`).

These settings can be edited directly in the `settings.ini` file or through the "Settings" tab in the application GUI.

## Running the Application

### Packaged Version (Conceptual)
Double-click the executable.

### Developer Version
1.  Ensure your virtual environment is activated.
2.  Navigate to the root directory of the project (`iracing_telemetry_analyzer_py`).
3.  Run the main GUI script from the `src` directory:
    ```bash
    python -m src.main_gui
    ```
    Or, if you have configured PyCharm as described above, use the "Run App GUI" configuration.

## Basic Usage Workflow (Conceptual)

1.  **Setup (First Time):**
    *   Launch the application.
    *   Go to the "Settings" tab.
    *   Configure your "Working Folder" where all outputs will be saved.
    *   Set up your "Recording Hotkeys" to match the global hotkeys of your screen capture software (e.g., OBS, Action!, NVIDIA ShadowPlay/GeForce Experience).
    *   Choose a default "Overlay Plugin".
    *   Adjust other settings like "Video Bitrate" as needed.
    *   Click "Save Settings".

2.  **Video Capture (Using External Software):**
    *   (Outside this app) Start iRacing and your screen recording software.
    *   Use the hotkeys you configured (or the recording software's direct interface) to record your race session. Save the video file.
    *   *Future integration aims for this app to send the hotkeys via the `VideoCaptureManager`.*

3.  **Replay Analysis:**
    *   In the "Capture & Analysis" tab.
    *   (Conceptually) Load your iRacing replay file (e.g., `.rpy`).
    *   Click "Analyze Race Replay".
    *   The application will (simulate) processing the replay, identifying key events.
    *   An `.replayscript.xml` file containing structured data about the race (events, leaderboards, etc.) will be saved in your working folder. The path to this script will appear in the "Source Replay Script" field on the "Transcoding" tab.

4.  **Video Transcoding & Overlay:**
    *   Go to the "Transcoding" tab.
    *   The "Source Replay Script" field should point to the `.replayscript.xml` file generated in the previous step (or you can browse for one).
    *   Specify an "Output Video Path" for the final video.
    *   Choose options like "Highlights Only" if desired.
    *   Select an overlay plugin from the Settings tab if you want to change from the default.
    *   Click "Transcode Video".
    *   The application will use FFmpeg to process the source video (identified from `OverlayData` or a placeholder if full capture integration isn't complete) based on the replay script.
    *   If "Highlights Only" is selected, `video_editing.py` logic will be used to select segments.
    *   The chosen plugin will provide filter strings to FFmpeg to draw overlays.
    *   Progress will be shown in the progress bar and status area.

## Project Structure

*   `iracing_telemetry_analyzer_py/`
    *   `src/`: Contains the main application source code.
        *   `ui/`: PyQt6 user interface components (e.g., `main_window.py`).
        *   `plugins/`: Example overlay plugins (e.g., `simple_timestamp_overlay.py`).
        *   `app_settings.py`: Manages application settings and `settings.ini`.
        *   `app_state_manager.py`: Manages global application state.
        *   `ffmpeg_transcoder.py`: Handles video transcoding with FFmpeg.
        *   `iracing_manager.py`: Interface for iRacing SDK interactions (currently a placeholder).
        *   `main_gui.py`: Main entry point for the GUI application.
        *   `plugin_manager.py`: Discovers, loads, and manages overlay plugins.
        *   `replay_analyzer.py`: Simulates analysis of replay data.
        *   `replay_data.py`: Defines dataclasses for replay and overlay data structures.
        *   `video_capture_manager.py`: Manages interaction with external screen recorders (hotkeys, file discovery).
        *   `video_editing.py`: Logic for selecting highlight video segments.
    *   `tests/`: Contains unit and integration tests using `pytest`.
        *   `ui/`: UI-specific tests.
    *   `docs/`: (Conceptual) For project documentation.
    *   `bin/ffmpeg/`: (Conceptual) Suggested location for FFmpeg binaries for bundling.
    *   `assets/`: (Conceptual) For application assets like icons.
    *   `pyproject.toml`: Project metadata, dependencies, and build configuration.
    *   `README.md`: This file.
    *   `CONTRIBUTING.md`: Guidelines for contributors.
    *   `LICENSE`: Project license file.
    *   `iracing_telemetry_analyzer_py.spec`: PyInstaller specification file (conceptual).

## Troubleshooting

*   **FFmpeg Not Found (Developer Mode):** Ensure FFmpeg and ffprobe are installed and their directory is added to your system's PATH environment variable. Verify by typing `ffmpeg -version` in a terminal.
*   **PyAutoGUI Issues (Hotkey Sending):**
    *   On **Linux with Wayland**, PyAutoGUI might not work correctly due to security restrictions. X11 might be required.
    *   On **macOS**, you may need to grant accessibility permissions to your terminal or IDE.
    *   Ensure your external screen recorder is configured to accept the global hotkeys being sent.
*   **Plugin Loading Issues:** Ensure plugins are placed in the `src/plugins` directory and correctly implement the `OverlayPluginInterface`. Check console output for error messages during plugin loading.
*   **File Permissions:** The application needs write access to the configured "Working Folder" and the directory where `settings.ini` is stored.

## Contributing

Contributions are welcome! Please refer to the `CONTRIBUTING.md` file for guidelines on project setup, code style, testing, and submitting changes.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
```
