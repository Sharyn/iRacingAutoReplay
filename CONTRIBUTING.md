# Contributing to iRacing Telemetry Analyzer & Replay Director

First off, thank you for considering contributing! Your help is greatly appreciated. This document provides guidelines for contributing to this project.

## Table of Contents
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Forking and Cloning](#forking-and-cloning)
  - [Virtual Environment](#virtual-environment)
  - [Installing Dependencies](#installing-dependencies)
- [Project Structure Overview](#project-structure-overview)
- [Key Modules Overview](#key-modules-overview)
- [Plugin API](#plugin-api)
  - [Creating a New Plugin](#creating-a-new-plugin)
- [Running Tests](#running-tests)
  - [Unit and Integration Tests](#unit-and-integration-tests)
  - [Test Coverage](#test-coverage)
- [Code Style and Conventions](#code-style-and-conventions)
  - [PEP 8](#pep-8)
  - [Type Hinting](#type-hinting)
  - [Docstrings](#docstrings)
  - [Commit Messages](#commit-messages)
- [Submitting Changes](#submitting-changes)
  - [Branching](#branching)
  - [Committing](#committing)
  - [Pushing](#pushing)
  - [Opening a Pull Request](#opening-a-pull-request)
- [Reporting Bugs or Requesting Features](#reporting-bugs-or-requesting-features)
- [Questions?](#questions)

## Getting Started

### Prerequisites
Ensure you have the following installed:
- Git
- Python (version 3.9 or higher recommended, as specified in `pyproject.toml`)
- `pip` (Python package installer)
- FFmpeg (must be in your system's PATH for development and running some tests)

### Forking and Cloning
1.  **Fork** the repository on GitHub.
2.  **Clone** your fork locally:
    ```bash
    git clone https://github.com/YourUsername/iracing_telemetry_analyzer_py.git
    cd iracing_telemetry_analyzer_py
    ```

### Virtual Environment
It's strongly recommended to work within a Python virtual environment:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Installing Dependencies
Install the project in editable mode along with development dependencies:
```bash
pip install -e .[dev]
```
This command assumes the `dev` extras group in `pyproject.toml` includes `pytest`, `pytest-qt`, `PyInstaller`, and any other necessary development tools.

## Project Structure Overview

A brief overview of the main directories:
-   `iracing_telemetry_analyzer_py/`
    -   `src/`: Contains the main application source code.
        -   `ui/`: PyQt6 user interface components (e.g., `main_window.py`).
        -   `plugins/`: Example overlay plugins. This is where new plugins should be added.
        -   `app_settings.py`: Manages application settings and `settings.ini`.
        -   `app_state_manager.py`: Manages global application state.
        -   `ffmpeg_transcoder.py`: Handles video transcoding with FFmpeg.
        -   `iracing_manager.py`: Defines the interface for iRacing SDK interactions.
        -   `main_gui.py`: Main entry point for the GUI application.
        -   `plugin_manager.py`: Discovers, loads, and manages overlay plugins.
        -   `replay_analyzer.py`: Core logic for analyzing replay data (currently simulated).
        -   `replay_data.py`: Defines dataclasses for replay and overlay data structures.
        -   `video_capture_manager.py`: Manages interaction with external screen recorders.
        -   `video_editing.py`: Logic for selecting highlight video segments.
    -   `tests/`: Contains unit and integration tests.
        -   `ui/`: UI-specific tests.
    -   `docs/`: (Conceptual) For project documentation.
    -   `bin/ffmpeg/`: (Conceptual) Suggested location for FFmpeg binaries if they were to be bundled directly in the repo for some reason (not typical for source distribution).
    -   `assets/`: (Conceptual) For application assets like icons.
    -   `pyproject.toml`: Project metadata, dependencies, and build configuration.
    -   `README.md`: Main project README.
    -   `CONTRIBUTING.md`: This file.
    -   `LICENSE`: Project license file.
    -   `iracing_telemetry_analyzer_py.spec`: PyInstaller specification file.

## Key Modules Overview

-   **`main_gui.py`**: Entry point for the application. Initializes all components and starts the GUI.
-   **`ui/main_window.py`**: Defines the main application window, its layout, tabs, and basic UI interactions. Connects UI elements to backend logic.
-   **`app_settings.py` (`AppSettings` class)**: Manages loading, accessing, and saving application settings from/to `settings.ini`.
-   **`app_state_manager.py` (`AppStateManager` class)**: Handles global application state transitions and notifies observers (like the UI) of these changes.
-   **`replay_data.py`**: Contains dataclasses (`OverlayData`, `RaceEvent`, `Driver`, etc.) that define the structure for storing and manipulating replay information. Includes XML and JSON serialization/deserialization.
-   **`replay_analyzer.py` (`ReplayAnalyzer` class)**: Responsible for processing replay information (currently simulated) to produce structured `OverlayData`.
-   **`video_editing.py` (`get_highlight_segments_to_keep` function)**: Implements logic to select interesting segments from `OverlayData` for creating highlight videos.
-   **`plugin_manager.py` (`PluginManager` and `OverlayPluginInterface`)**: Manages the plugin lifecycle (loading, discovery, activation) and defines the interface for overlay plugins.
-   **`ffmpeg_transcoder.py` (`FFmpegTranscoder` class)**: Uses `ffmpeg-python` (or a mock) to handle video transcoding, applying filters provided by plugins, and managing FFmpeg processes.
-   **`video_capture_manager.py` (`VideoCaptureManager` class)**: Intended to control external screen recording software via hotkeys and discover newly recorded video files.
-   **`iracing_manager.py` (`IRacingManagerInterface` and `PlaceholderIRacingManager`)**: Defines the interface for interacting with the iRacing simulation (currently uses a placeholder implementation).

## Plugin API

The application supports plugins for generating video overlays.

### Creating a New Plugin
1.  Create a new Python file in the `iracing_telemetry_analyzer_py/src/plugins/` directory (e.g., `my_awesome_overlay.py`).
2.  In your file, define a class that inherits from `OverlayPluginInterface` (from `plugin_manager.py`).
3.  Implement all the abstract methods and properties defined in `OverlayPluginInterface`:
    *   `name` (property): Return a unique string name for your plugin.
    *   `description` (property): Return a brief description.
    *   `initialize(self, settings: AppSettings, overlay_data: OverlayData) -> None`: Use this to store `settings` and `overlay_data` if your plugin needs them to generate filters.
    *   `get_ffmpeg_filter_options(self, timestamp_seconds: float, video_width: int, video_height: int) -> List[str]`: This is the core method. Return a list of FFmpeg filter strings (e.g., using `build_drawtext_filter` from `plugin_manager.py` or constructing them manually). The filters should be appropriate for the given `timestamp_seconds`.
    *   `on_transcode_complete(self) -> None`: For any cleanup your plugin needs to do.
4.  Your plugin will be automatically discovered by the `PluginManager` when the application starts if it's placed in the `plugins` directory and correctly implements the interface.

Refer to `simple_timestamp_overlay.py` in the `plugins` directory for a basic example.

## Running Tests

The project uses `pytest` for testing.

### Unit and Integration Tests
1.  Ensure you have installed development dependencies (`pip install -e .[dev]`). This should include `pytest` and `pytest-qt`.
2.  Navigate to the project root directory (`iracing_telemetry_analyzer_py`).
3.  Run tests using the `pytest` command:
    ```bash
    pytest
    ```
    Or, to run tests for a specific file:
    ```bash
    pytest tests/ui/test_main_window_settings.py
    ```
    PyCharm also provides excellent integration for running pytest tests directly from the IDE.

### Test Coverage (Conceptual)
To generate a test coverage report (if `pytest-cov` is configured):
```bash
pytest --cov=src
```
This would show which parts of the `src` code are covered by tests.

## Code Style and Conventions

### PEP 8
Please adhere to [PEP 8 -- Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/). Using a linter/formatter like Black or Flake8 is encouraged.

### Type Hinting
All new functions and methods should include type hints as per [PEP 484 -- Type Hints](https://www.python.org/dev/peps/pep-0484/).

### Docstrings
-   Modules, classes, functions, and methods should have clear, concise docstrings.
-   Use Google Python Style Guide format for docstrings (or NumPy/Sphinx style if preferred, but be consistent). Example:
    ```python
    def my_function(arg1: str, arg2: int) -> bool:
        """Does something interesting.

        Args:
            arg1: The first argument, a string.
            arg2: The second argument, an integer.

        Returns:
            True if successful, False otherwise.
        """
        # ... code ...
    ```

### Commit Messages
-   Try to follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.
-   Brief summary in the first line (max 50-72 chars).
-   More detailed explanation in the body if needed, after a blank line.
-   Example: `feat: Add advanced turbo encabulator widget to settings`

## Submitting Changes

### Branching
Create a new branch for your feature or bugfix:
```bash
git checkout -b feat/my-new-feature  # For a new feature
git checkout -b fix/issue-123       # For a bugfix related to issue #123
```

### Committing
Make your changes, write good commit messages (see above), and commit frequently.

### Pushing
Push your branch to your fork on GitHub:
```bash
git push origin feat/my-new-feature
```

### Opening a Pull Request
-   Go to the original project repository on GitHub.
-   You should see a prompt to create a Pull Request from your recently pushed branch.
-   Provide a clear title and description for your PR, explaining the changes and referencing any relevant issues.
-   Ensure all tests are passing.

## Reporting Bugs or Requesting Features
-   Use the GitHub Issues section of the project repository.
-   Before submitting, check if a similar issue or feature request already exists.
-   For bug reports, please include:
    -   Steps to reproduce the bug.
    -   Expected behavior.
    -   Actual behavior.
    -   Your operating system, Python version, and application version (if applicable).
    -   Any relevant error messages or logs.
-   For feature requests, clearly describe the proposed feature and its potential benefits.

## Questions?
If you have questions about contributing or the project, feel free to open an issue on GitHub with the "question" label.

Thank you for contributing!
```
