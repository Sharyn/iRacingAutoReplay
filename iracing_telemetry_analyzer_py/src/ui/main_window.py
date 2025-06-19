"""
Defines the main window for the iRacing Telemetry Analyzer application.
"""

from typing import Optional, Any, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer # Added QTimer for potential future use
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QCheckBox, QTabWidget, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QLabel, QSpinBox, QComboBox, QGroupBox, QFormLayout, QSizePolicy
)

if TYPE_CHECKING:
    from ..app_settings import AppSettings
    from ..app_state_manager import AppStateManager, AppStates
    # Forward declare other managers if specific methods are needed, else use Any
    from ..plugin_manager import PluginManager
    from ..replay_analyzer import ReplayAnalyzer
    from ..ffmpeg_transcoder import FFmpegTranscoder
    from ..video_capture_manager import VideoCaptureManager


class MainWindow(QMainWindow):
    """
    Main application window.
    """
    def __init__(
        self,
        app_settings: 'AppSettings',
        app_state_manager: 'AppStateManager',
        plugin_manager: 'PluginManager',
        replay_analyzer: 'ReplayAnalyzer',
        ffmpeg_transcoder: 'FFmpegTranscoder',
        video_capture_manager: 'VideoCaptureManager', # Added
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.app_settings = app_settings
        self.app_state_manager = app_state_manager
        self.plugin_manager = plugin_manager
        self.replay_analyzer = replay_analyzer
        self.ffmpeg_transcoder = ffmpeg_transcoder
        self.video_capture_manager = video_capture_manager

        self.setWindowTitle("iRacing Telemetry Analyzer & Replay Director")
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        self._create_menu_bar()
        self._init_ui()

        # Connect to AppStateManager for UI updates
        self.app_state_manager.register_observer(self._update_ui_from_state)
        # Initialize UI based on current state
        self._update_ui_from_state(self.app_state_manager.current_state, self.app_state_manager.last_message)


    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self._create_capture_analysis_tab()
        self._create_transcoding_tab()
        self._create_settings_tab() # Added a placeholder for settings

        # Status Area
        status_group = QGroupBox("Status & Logs")
        status_layout = QVBoxLayout()

        self.status_text_edit = QTextEdit()
        self.status_text_edit.setReadOnly(True)
        self.status_text_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        status_layout.addWidget(self.status_text_edit)

        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.progress_bar)

        status_group.setLayout(status_layout)
        self.main_layout.addWidget(status_group)


    def _create_capture_analysis_tab(self):
        self.capture_tab = QWidget()
        layout = QVBoxLayout(self.capture_tab)

        # Working Folder
        wf_layout = QHBoxLayout()
        wf_layout.addWidget(QLabel("Working Folder:"))
        self.working_folder_edit = QLineEdit(self.app_settings.working_folder)
        self.working_folder_edit.setReadOnly(True) # Typically set via settings dialog
        wf_layout.addWidget(self.working_folder_edit)
        # browse_wf_button = QPushButton("Browse")
        # browse_wf_button.clicked.connect(self._browse_working_folder) # To be implemented in settings
        # wf_layout.addWidget(browse_wf_button)
        layout.addLayout(wf_layout)

        # Analysis Options
        analysis_options_group = QGroupBox("Analysis & Recording Options")
        analysis_options_layout = QFormLayout()
        self.short_test_only_checkbox = QCheckBox("Short Test Only (Simulates shorter processing)")
        self.short_test_only_checkbox.setChecked(self.app_settings.short_test_only)
        self.short_test_only_checkbox.toggled.connect(
            lambda checked: setattr(self.app_settings, 'short_test_only', checked)
        )
        analysis_options_layout.addRow(self.short_test_only_checkbox)

        self.close_iracing_checkbox = QCheckBox("Close iRacing After Recording (Placeholder)")
        self.close_iracing_checkbox.setChecked(self.app_settings.close_iracing_after_recording)
        self.close_iracing_checkbox.toggled.connect(
            lambda checked: setattr(self.app_settings, 'close_iracing_after_recording', checked)
        )
        analysis_options_layout.addRow(self.close_iracing_checkbox)
        analysis_options_group.setLayout(analysis_options_layout)
        layout.addWidget(analysis_options_group)

        # Actions
        self.analyze_race_button = QPushButton("Analyze Race Replay")
        self.analyze_race_button.clicked.connect(self._analyze_race_clicked)
        layout.addWidget(self.analyze_race_button)

        layout.addStretch() # Pushes elements to the top
        self.tabs.addTab(self.capture_tab, "Capture & Analysis")

    def _create_transcoding_tab(self):
        self.transcoding_tab = QWidget()
        layout = QVBoxLayout(self.transcoding_tab)

        # Source Replay Script
        srs_layout = QHBoxLayout()
        srs_layout.addWidget(QLabel("Source Replay Script:"))
        self.source_script_edit = QLineEdit()
        self.source_script_edit.setReadOnly(True) # Should be updated after analysis
        srs_layout.addWidget(self.source_script_edit)
        browse_srs_button = QPushButton("Browse")
        browse_srs_button.clicked.connect(self._browse_source_script)
        srs_layout.addWidget(browse_srs_button)
        layout.addLayout(srs_layout)

        # Output Video Path (auto-suggested or browsable)
        ovp_layout = QHBoxLayout()
        ovp_layout.addWidget(QLabel("Output Video Path:"))
        self.output_video_edit = QLineEdit() # Can be auto-filled
        ovp_layout.addWidget(self.output_video_edit)
        browse_ovp_button = QPushButton("Save As...")
        browse_ovp_button.clicked.connect(self._browse_output_video)
        ovp_layout.addWidget(browse_ovp_button)
        layout.addLayout(ovp_layout)

        # Transcoding Options
        transcoding_options_group = QGroupBox("Transcoding Options")
        transcoding_options_layout = QFormLayout()

        self.highlight_only_checkbox = QCheckBox("Highlights Only")
        self.highlight_only_checkbox.setChecked(self.app_settings.highlight_video_only)
        self.highlight_only_checkbox.toggled.connect(
            lambda checked: setattr(self.app_settings, 'highlight_video_only', checked)
        )
        transcoding_options_layout.addRow(self.highlight_only_checkbox)

        self.shutdown_pc_checkbox = QCheckBox("Shutdown PC After Encoding (Placeholder)")
        self.shutdown_pc_checkbox.setChecked(self.app_settings.shutdown_pc_after_encoding)
        self.shutdown_pc_checkbox.toggled.connect(
            lambda checked: setattr(self.app_settings, 'shutdown_pc_after_encoding', checked)
        )
        transcoding_options_layout.addRow(self.shutdown_pc_checkbox)

        # Video Bitrate
        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(QLabel("Video Bitrate (Mbps):"))
        self.video_bitrate_spinbox = QSpinBox()
        self.video_bitrate_spinbox.setRange(1, 200) # 1 Mbps to 200 Mbps
        self.video_bitrate_spinbox.setValue(self.app_settings.video_bitrate // 1000000) # Convert from bps to Mbps
        self.video_bitrate_spinbox.valueChanged.connect(
            lambda value: setattr(self.app_settings, 'video_bitrate', value * 1000000)
        )
        bitrate_layout.addWidget(self.video_bitrate_spinbox)
        bitrate_layout.addStretch()
        transcoding_options_layout.addRow(bitrate_layout)

        transcoding_options_group.setLayout(transcoding_options_layout)
        layout.addWidget(transcoding_options_group)

        # Actions
        self.transcode_video_button = QPushButton("Transcode Video")
        self.transcode_video_button.clicked.connect(self._transcode_video_clicked)
        layout.addWidget(self.transcode_video_button)

        layout.addStretch()
        self.tabs.addTab(self.transcoding_tab, "Transcoding")

    def _create_settings_tab(self):
        """ Creates the Settings tab (placeholder for now). """
        self.settings_tab = QWidget()
        layout = QVBoxLayout(self.settings_tab)
        layout.addWidget(QLabel("Application settings will be configurable here."))
        layout.addWidget(QLabel("(e.g., working folder, hotkeys, default paths, plugin settings)"))

        # Example: Display current plugin
        active_plugin_name = self.plugin_manager._active_plugin.name if self.plugin_manager._active_plugin else "None" # Accessing private for demo
        layout.addWidget(QLabel(f"Currently Active Overlay Plugin (Example): {active_plugin_name}"))

        layout.addStretch()
        self.tabs.addTab(self.settings_tab, "Settings")


    # --- Slots and Actions ---
    def _show_about_dialog(self):
        QMessageBox.about(
            self,
            "About iRacing Telemetry Analyzer",
            "This application helps analyze iRacing replays and generate overlay videos.\n\n"
            "Version: 0.1.0 (Alpha)" # Placeholder version
        )

    def _browse_working_folder(self): # Placeholder, real one in settings dialog
        # directory = QFileDialog.getExistingDirectory(self, "Select Working Folder")
        # if directory:
        #     self.working_folder_edit.setText(directory)
        #     self.app_settings.working_folder = directory
        self.status_text_edit.append("INFO: Working folder selection would be handled in a dedicated settings dialog.")


    def _browse_source_script(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Replay Script XML", self.app_settings.working_folder, "XML Files (*.replayscript.xml *.xml)"
        )
        if filepath:
            self.source_script_edit.setText(filepath)
            self.status_text_edit.append(f"Selected replay script: {filepath}")
            # Suggest output path based on this
            p = Path(filepath)
            self.output_video_edit.setText(str(p.with_suffix(".mp4")))


    def _browse_output_video(self):
        # Suggest initial path based on source script or working folder
        suggested_dir = Path(self.source_script_edit.text()).parent if self.source_script_edit.text() else self.app_settings.working_folder
        suggested_filename = Path(self.source_script_edit.text()).stem + "_highlight.mp4" if self.source_script_edit.text() else "output_video.mp4"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Video As", str(Path(suggested_dir) / suggested_filename), "MP4 Video Files (*.mp4)"
        )
        if filepath:
            self.output_video_edit.setText(filepath)
            self.status_text_edit.append(f"Output video will be saved to: {filepath}")


    def _analyze_race_clicked(self):
        self.status_text_edit.append("INFO: 'Analyze Race' button clicked. (Placeholder action)")
        # Example of changing state:
        # self.app_state_manager.change_state(AppStates.ANALYZING_REPLAY, "Starting analysis...")
        # In a real app, this would trigger self.replay_analyzer.analyse_race in a worker thread.
        # For now, simulate completion and update UI elements
        # self.source_script_edit.setText(str(Path(self.app_settings.working_folder) / "simulated_analysis.replayscript.xml"))
        # self.output_video_edit.setText(str(Path(self.app_settings.working_folder) / "simulated_analysis.mp4"))
        # self.app_state_manager.change_state(AppStates.IDLE, "Analysis complete (simulated).")
        self.status_text_edit.append("TODO: Implement actual race analysis call in a worker thread.")


    def _transcode_video_clicked(self):
        self.status_text_edit.append("INFO: 'Transcode Video' button clicked. (Placeholder action)")
        if not self.source_script_edit.text():
            QMessageBox.warning(self, "Missing Input", "Please select a Source Replay Script first.")
            return
        if not self.output_video_edit.text():
            QMessageBox.warning(self, "Missing Output", "Please specify an Output Video Path.")
            return

        # Example of changing state:
        # self.app_state_manager.change_state(AppStates.TRANSCODING_VIDEO, "Starting transcoding...")
        # In a real app, this would trigger self.ffmpeg_transcoder.transcode_video in a worker thread.
        # For now, simulate:
        # self.progress_bar.setValue(0) # Reset progress
        # for i in range(101): QTimer.singleShot(i*20, lambda v=i: self.progress_bar.setValue(v)) # Simulate progress
        # QTimer.singleShot(2100, lambda: self.app_state_manager.change_state(AppStates.IDLE, "Transcoding complete (simulated)."))
        self.status_text_edit.append("TODO: Implement actual transcoding call in a worker thread with progress.")


    def _update_ui_from_state(self, new_state: 'AppStates', message: Optional[str]):
        """
        Updates UI elements based on the application state.
        This method is connected to the AppStateManager.
        """
        self.status_text_edit.append(f"STATE CHANGE: {new_state} - {message or ''}")

        is_idle = (new_state == AppStates.IDLE)
        is_analyzing = (new_state == AppStates.ANALYZING_REPLAY)
        is_capturing = (new_state == AppStates.CAPTURING_VIDEO) # Example for future
        is_transcoding = (new_state == AppStates.TRANSCODING_VIDEO)

        # Enable/disable buttons
        self.analyze_race_button.setEnabled(is_idle)
        self.transcode_video_button.setEnabled(is_idle and bool(self.source_script_edit.text())) # Enable only if script is loaded

        # Update progress bar (simplified)
        if is_transcoding:
            self.progress_bar.setValue(0) # Or some intermediate value if progress is reported
            self.progress_bar.setEnabled(True)
            self.progress_bar.setFormat("Processing... %p%")
        elif is_idle or new_state == AppStates.ERROR:
            self.progress_bar.setValue(100 if is_idle and self.progress_bar.value() > 0 else 0) # Show full if coming from active state
            self.progress_bar.setEnabled(False)
            self.progress_bar.setFormat("Progress" if is_idle else "Error!")

        if message:
            self.statusBar().showMessage(f"{new_state}: {message}", 5000) # Show in status bar for 5s
        else:
            self.statusBar().showMessage(f"State: {new_state}", 5000)


    def closeEvent(self, event):
        """Handle window close event for any cleanup."""
        # Example: Save settings before closing
        # self.app_settings.save_settings() # Assuming AppSettings has a save method
        print("Main window closing. Application shutting down.")
        # TODO: Ensure any running worker threads are properly stopped.
        # For example, if analysis or transcoding is running, signal it to stop.
        # if self.app_state_manager.current_state not in [AppStates.IDLE, AppStates.ERROR]:
        #    reply = QMessageBox.question(self, 'Confirm Exit',
        #                                 "A process is currently running. Are you sure you want to exit?",
        #                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        #                                 QMessageBox.StandardButton.No)
        #    if reply == QMessageBox.StandardButton.No:
        #        event.ignore()
        #        return
            # else:
                # Signal worker threads to stop
                # self.some_cancel_event.set()

        super().closeEvent(event)

```
