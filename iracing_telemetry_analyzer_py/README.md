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
    (Replace `yourusername` with the actual repository URL if it's hosted. The second `cd` command should go into the repository root, not the inner `iracing_telemetry_analyzer_py` if your repo is named that way and contains the `src` and `pyproject.toml` at its top level.)
    **Note:** The project structure assumes a root directory (e.g., `project_root_name`) that contains the `iracing_telemetry_analyzer_py` package directory, `pyproject.toml`, etc. So after cloning, you would `cd project_root_name`.

2.  **Create and Activate a Virtual Environment:**
    From the repository root directory:
    ```bash
    # For Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```
    (Using `.venv` as the directory name is a common convention.)

3.  **Install Dependencies:**
    The project uses `pyproject.toml` for dependency management. Install the project in editable mode along with development dependencies. This command should be run from the repository root (where `pyproject.toml` is located).
    ```bash
    pip install -e .[dev]
    ```
    The `dev` extras group should be defined in `pyproject.toml` and include tools like `pytest`, `pytest-qt`, and `PyInstaller`.

## Running the Application

### From Command Line

1.  **Navigate to Repository Root:**
    Open your terminal or command prompt and change to the root directory of the cloned repository (this is the directory that contains the `iracing_telemetry_analyzer_py` folder and your `pyproject.toml`).
    ```bash
    cd path/to/your_repository_root
    ```

2.  **Activate Virtual Environment:**
    If you haven't already, activate the virtual environment you created during installation.
    ```bash
    # For Windows
    .\.venv\Scripts\activate

    # For macOS/Linux
    source .venv/bin/activate
    ```

3.  **Run the Application:**
    Use the `python -m` command to run the main GUI module as a script. This ensures Python correctly handles the package structure and imports.
    ```bash
    python -m iracing_telemetry_analyzer_py.src.main_gui
    ```

4.  **Explanation:**
    *   `python -m`: This flag tells Python to run a module from your `PYTHONPATH` as a script.
    *   `iracing_telemetry_analyzer_py.src.main_gui`: This is the full path to the `main_gui` module within your package structure. Using this dot-separated path allows Python to resolve imports correctly as if `iracing_telemetry_analyzer_py` is a top-level package.

### From PyCharm

Refer to the "Development Setup with PyCharm" section below for detailed instructions on configuring and running the application within the PyCharm IDE. The recommended method involves setting up a Run/Debug Configuration that uses the module name.

## Development Setup with PyCharm (Recommended for Developers)

These instructions provide a detailed guide for setting up the project in PyCharm.

1.  **Prerequisites:**
    *   Ensure Git and Python 3.9+ are installed on your system.
    *   Install PyCharm (Community or Professional Edition).

2.  **Clone the Repository:**
    Use your preferred method (e.g., Git command line, PyCharm's "Get from VCS" feature) to clone the project repository to your local machine.
    ```bash
    git clone https://github.com/yourusername/iracing_telemetry_analyzer_py_root.git
    ```
    (Assume `iracing_telemetry_analyzer_py_root` is the name of your repository root folder).

3.  **Open the Project in PyCharm:**
    *   Launch PyCharm.
    *   Select "Open".
    *   **Navigate to and open the root directory of the cloned repository** (e.g., `iracing_telemetry_analyzer_py_root`). This is the directory that contains the `iracing_telemetry_analyzer_py` package folder and `pyproject.toml`.

4.  **Python Interpreter & Virtual Environment:**
    *   PyCharm usually detects if a project needs a Python interpreter configured.
    *   Go to `File > Settings` (or `PyCharm > Settings...` on macOS).
    *   Navigate to `Project: your_repository_root_name > Python Interpreter`.
    *   If no interpreter is selected, or if you want to use the `.venv` you created:
        *   Click the gear icon (⚙️) or "Add Interpreter..." link, then select "Add Local Interpreter".
        *   Choose "Virtualenv Environment".
        *   Select "Existing" and point the "Interpreter" field to the Python executable within your `.venv` folder (e.g., `your_repository_root/.venv/bin/python` on Linux/macOS or `your_repository_root\.venv\Scripts\python.exe` on Windows).
        *   Alternatively, choose "New" to have PyCharm create/manage the virtual environment (e.g., in a `.venv` directory within the project). Ensure the "Base interpreter" is Python 3.9+.
    *   Click "OK". PyCharm will set this as the project interpreter.

5.  **Installing Dependencies (if not already done):**
    *   Open PyCharm's built-in **Terminal** (`View > Tool Windows > Terminal`).
    *   Ensure your virtual environment is activated.
    *   If you haven't installed dependencies yet, run:
        ```bash
        pip install -e .[dev]
        ```

6.  **Project Structure in PyCharm (Marking Sources Root):**
    *   In the "Project" tool window, expand your project root.
    *   Right-click on the `src` directory located inside the `iracing_telemetry_analyzer_py` package directory (i.e., `your_repository_root/iracing_telemetry_analyzer_py/src`).
    *   Select `Mark Directory as > Sources Root`.
    *   **Why?** This helps PyCharm with import resolution, code completion, and navigation, especially for absolute imports starting from `iracing_telemetry_analyzer_py.src.`.

7.  **Run/Debug Configuration for the GUI:**
    *   Go to `Run > Edit Configurations...`.
    *   Click the `+` (Add New Configuration) button and select "Python".
    *   **Name:** Enter a descriptive name, e.g., "Run App GUI".
    *   **Configuration Type:** Choose **"Module name"**.
        *   **Module name:** `iracing_telemetry_analyzer_py.src.main_gui`
    *   **Working directory:** Set this to your **repository root directory** (e.g., `$PROJECT_DIR$` if PyCharm opened the repo root, or the explicit path to `your_repository_root_name`). This ensures that relative paths used by the application (like for settings or plugins relative to the `src` structure if not handled absolutely) are resolved correctly.
    *   **Python interpreter:** Ensure this is set to the project's virtual environment interpreter.
    *   Click "OK" or "Apply".
    *   **Alternative using "Script path" (less ideal for packages):**
        *   If you prefer "Script path":
            *   **Script path:** `iracing_telemetry_analyzer_py/src/main_gui.py` (path relative to the repository root).
            *   **Working directory:** Set to the repository root (`$PROJECT_DIR$`).
        *   Using "Module name" is generally better for projects structured as packages to mimic `python -m` execution.

8.  **Running Tests:**
    *   PyCharm has excellent integration with `pytest`.
    *   After installing dependencies, PyCharm should automatically discover tests.
    *   Right-click on the `tests` directory and select "Run 'pytest in tests'".
    *   Test results will appear in PyCharm's Test Runner tool window.

## Configuration

The application uses a `settings.ini` file to store its configuration. When run for the first time, if this file doesn't exist, it will be created with default values in a directory typically located at:
*   Windows: `C:\\Users\\YourUser\\Documents\\IracingReplayDirectorPy\\settings.ini`
*   Linux/macOS: `~/Documents/IracingReplayDirectorPy/settings.ini`

Key settings include:
*   **`working_folder`**: Main directory for output files.
*   **`plugin_name`**: Default overlay plugin.
*   **`hotkey_stop_start` / `hotkey_pause_resume`**: Hotkeys for external recorder. Format: `ctrl+shift+s`.
*   **`video_bitrate`**: Target video bitrate in bps.
*   **`highlight_video_target_duration_seconds`**: Desired length for highlight videos.
*   Various boolean flags for application behavior.

Settings can be edited in `settings.ini` or via the "Settings" tab in the GUI.

## Basic Usage Workflow (Conceptual)

1.  **Setup (First Time):** Configure "Working Folder", "Recording Hotkeys", "Overlay Plugin", etc., in the "Settings" tab and save.
2.  **Video Capture:** Record your iRacing session using your external screen recording software.
3.  **Replay Analysis:** In the "Capture & Analysis" tab, (conceptually) load your iRacing replay. Click "Analyze Race Replay". An `.replayscript.xml` file will be generated.
4.  **Video Transcoding & Overlay:** Go to the "Transcoding" tab. The "Source Replay Script" should point to the generated XML. Specify "Output Video Path". Choose options like "Highlights Only". Click "Transcode Video".

## Project Structure

*   `your_repository_root/`
    *   `iracing_telemetry_analyzer_py/`: The main Python package.
        *   `src/`: Contains the application source code.
            *   `ui/`: PyQt6 UI components.
            *   `plugins/`: Example overlay plugins.
            *   `app_settings.py`, `main_gui.py`, etc.
        *   `tests/`: Unit and integration tests.
    *   `pyproject.toml`: Project metadata and dependencies.
    *   `README.md`: This file.
    *   `.venv/`: Virtual environment directory (if created here).
    *   `LICENSE`, `CONTRIBUTING.md`, etc.

## Troubleshooting

*   **FFmpeg Not Found (Developer Mode):** Ensure FFmpeg/ffprobe are installed and in PATH.
*   **PyAutoGUI Issues (Hotkey Sending):** May require OS-specific permissions or X11 on Linux.
*   **Plugin Loading Issues:** Ensure plugins are in `src/plugins` and implement `OverlayPluginInterface`.
*   **File Permissions:** Ensure write access to "Working Folder" and settings directory.
*   **Import Errors (Running from command line):** Always use `python -m iracing_telemetry_analyzer_py.src.main_gui` from the repository root after activating the virtual environment. This ensures Python treats your `src` directory as part of the `iracing_telemetry_analyzer_py` package correctly.

## Contributing

Contributions are welcome! Please refer to the `CONTRIBUTING.md` file for guidelines.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
