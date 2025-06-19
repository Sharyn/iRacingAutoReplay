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
    from ..iracing_manager import IRacingManagerInterface # For type hint
    from ..pyirsdk_manager import PYIRSDK_AVAILABLE # To display SDK status


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
        video_capture_manager: 'VideoCaptureManager',
        iracing_manager: 'IRacingManagerInterface', # Added
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self.app_settings = app_settings
        self.app_state_manager = app_state_manager
        self.plugin_manager = plugin_manager
        self.replay_analyzer = replay_analyzer
        self.ffmpeg_transcoder = ffmpeg_transcoder
        self.video_capture_manager = video_capture_manager
        self.iracing_manager = iracing_manager # Store the instance

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

        self.connect_iracing_action = QAction("Connect to iRacing", self)
        self.connect_iracing_action.triggered.connect(self._connect_iracing)
        file_menu.addAction(self.connect_iracing_action)

        self.disconnect_iracing_action = QAction("Disconnect from iRacing", self)
        self.disconnect_iracing_action.triggered.connect(self._disconnect_iracing)
        self.disconnect_iracing_action.setEnabled(False) # Initially disabled
        file_menu.addAction(self.disconnect_iracing_action)

        file_menu.addSeparator()

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

        # Status Bar for telemetry
        self.ui_telemetry_status_label = QLabel("Telemetry: N/A")
        self.statusBar().addPermanentWidget(self.ui_telemetry_status_label)

        # Telemetry polling timer
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_live_telemetry)
        self.telemetry_timer.start(250) # Poll 4 times a second


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

    def _create_settings_tab(self) -> None: # Modified: This method now adds the tab directly.
        """Creates the Settings tab with various configuration options."""
        self.settings_tab_widget = QWidget() # Main widget for the settings tab
        settings_tab_layout = QVBoxLayout(self.settings_tab_widget)

        # General Settings (Paths, Plugin)
        settings_tab_layout.addWidget(self._create_general_settings_group())
        # Recording Hotkeys
        settings_tab_layout.addWidget(self._create_recording_hotkeys_group())
        # Video Options
        settings_tab_layout.addWidget(self._create_video_options_group())
        # Application Flags/Booleans
        settings_tab_layout.addWidget(self._create_application_flags_group())

        settings_tab_layout.addStretch() # Push content to top

        # Action Buttons for Settings Tab
        buttons_layout = QHBoxLayout()
        self.ui_save_settings_button = QPushButton("Save Settings")
        self.ui_save_settings_button.clicked.connect(self._save_settings_clicked)
        self.ui_save_settings_button.setToolTip("Save all settings from this tab to your settings.ini file.")
        buttons_layout.addWidget(self.ui_save_settings_button)

        self.ui_reset_settings_button = QPushButton("Reset to Defaults")
        self.ui_reset_settings_button.clicked.connect(self._reset_settings_clicked)
        self.ui_reset_settings_button.setToolTip("Reset settings in this UI to their default values. Does not save automatically.")
        buttons_layout.addWidget(self.ui_reset_settings_button)

        settings_tab_layout.addLayout(buttons_layout)

        self.tabs.addTab(self.settings_tab_widget, "Settings")

    def _create_general_settings_group(self) -> QGroupBox:
        group = QGroupBox("General & Paths")
        layout = QFormLayout()

        # Working Folder
        self.ui_working_folder_edit = QLineEdit()
        self.ui_working_folder_edit.setToolTip("Directory for output files (replayscripts, videos).")
        self.ui_working_folder_edit.editingFinished.connect(self._on_setting_working_folder_changed)
        browse_wf_button = QPushButton("Browse...")
        browse_wf_button.clicked.connect(self._browse_working_folder_clicked) # This updates UI, not app_settings directly
        wf_layout = QHBoxLayout()
        wf_layout.addWidget(self.ui_working_folder_edit)
        wf_layout.addWidget(browse_wf_button)
        layout.addRow(QLabel("Working Folder:"), wf_layout)

        # Plugin Selection
        self.ui_plugin_combo = QComboBox()
        self.ui_plugin_combo.setToolTip("Select the overlay plugin to use for transcoding.")
        self.ui_plugin_combo.currentTextChanged.connect(self._on_setting_plugin_changed)
        layout.addRow(QLabel("Overlay Plugin:"), self.ui_plugin_combo)

        # Preferred Driver Names
        self.ui_preferred_drivers_edit = QLineEdit()
        self.ui_preferred_drivers_edit.setToolTip("Comma-separated list of preferred driver names for camera focus (used by some plugins or analysis features).")
        self.ui_preferred_drivers_edit.editingFinished.connect(self._on_setting_preferred_drivers_changed)
        layout.addRow(QLabel("Preferred Drivers:"), self.ui_preferred_drivers_edit)

        group.setLayout(layout)
        return group

    def _create_recording_hotkeys_group(self) -> QGroupBox:
        group = QGroupBox("Recording Hotkeys (for external recorder)")
        layout = QFormLayout()

        self.ui_hotkey_start_stop_edit = QLineEdit()
        self.ui_hotkey_start_stop_edit.setToolTip(
            "Enter hotkey to start/stop external screen recording.\n"
            "Examples: 'ctrl+shift+s', 'f9', 'alt+r'.\n"
            "Modifiers: ctrl, alt, shift, win (or command/cmd for Mac).\n"
            "Use lowercase for single letters (e.g., 's' not 'S' if combined with a modifier).\n"
            "Special keys: 'space', 'enter', 'tab', 'esc', 'printscreen', 'pause', 'pageup', 'pagedown', etc."
        )
        self.ui_hotkey_start_stop_edit.editingFinished.connect(self._on_setting_hotkey_start_stop_changed)
        layout.addRow(QLabel("Start/Stop Recording:"), self.ui_hotkey_start_stop_edit)

        self.ui_hotkey_pause_resume_edit = QLineEdit()
        self.ui_hotkey_pause_resume_edit.setToolTip(
            "Enter hotkey to pause/resume external screen recording.\n"
            "Examples: 'ctrl+shift+p', 'pause', 'alt+p'.\n"
            "Modifiers: ctrl, alt, shift, win (or command/cmd for Mac).\n"
            "Use lowercase for single letters (e.g., 'p' not 'P' if combined with a modifier).\n"
            "Special keys: 'space', 'enter', 'tab', 'esc', 'printscreen', 'pause', etc."
        )
        self.ui_hotkey_pause_resume_edit.editingFinished.connect(self._on_setting_hotkey_pause_resume_changed)
        layout.addRow(QLabel("Pause/Resume Recording:"), self.ui_hotkey_pause_resume_edit)

        group.setLayout(layout)
        return group

    def _create_video_options_group(self) -> QGroupBox:
        group = QGroupBox("Video & Highlight Options")
        layout = QFormLayout()

        self.ui_video_bitrate_spinbox = QSpinBox()
        self.ui_video_bitrate_spinbox.setRange(1, 200) # In Mbps
        self.ui_video_bitrate_spinbox.setSuffix(" Mbps")
        self.ui_video_bitrate_spinbox.setToolTip("Target video bitrate for transcoded videos (e.g., 8-15 Mbps for 1080p).")
        self.ui_video_bitrate_spinbox.valueChanged.connect(self._on_setting_video_bitrate_changed)
        layout.addRow(QLabel("Video Bitrate:"), self.ui_video_bitrate_spinbox)

        self.ui_highlight_duration_spinbox = QSpinBox()
        self.ui_highlight_duration_spinbox.setRange(10, 600) # In seconds
        self.ui_highlight_duration_spinbox.setSuffix(" s")
        self.ui_highlight_duration_spinbox.setToolTip("Target total duration for generated highlight videos.")
        self.ui_highlight_duration_spinbox.valueChanged.connect(self._on_setting_highlight_duration_changed)
        layout.addRow(QLabel("Highlight Duration:"), self.ui_highlight_duration_spinbox)

        group.setLayout(layout)
        return group

    def _create_application_flags_group(self) -> QGroupBox:
        group = QGroupBox("Application Behavior Flags")
        layout = QVBoxLayout() # Using QVBoxLayout for a simple list of checkboxes

        self.ui_capture_opening_scene_checkbox = QCheckBox("Capture Opening Scene for Highlights")
        self.ui_capture_opening_scene_checkbox.setToolTip("If checked, includes an opening scene/intro in highlight videos (if available).")
        self.ui_capture_opening_scene_checkbox.toggled.connect(self._on_setting_capture_opening_scene_toggled)
        layout.addWidget(self.ui_capture_opening_scene_checkbox)

        self.ui_shutdown_pc_checkbox = QCheckBox("Shutdown PC After Encoding")
        self.ui_shutdown_pc_checkbox.setToolTip("If checked, the computer will attempt to shut down after video encoding completes.")
        self.ui_shutdown_pc_checkbox.toggled.connect(self._on_setting_shutdown_pc_toggled)
        layout.addWidget(self.ui_shutdown_pc_checkbox)

        self.ui_close_iracing_checkbox = QCheckBox("Close iRacing After Recording (External Recorder)")
        self.ui_close_iracing_checkbox.setToolTip("If checked, attempts to close iRacing after external recording stops (feature placeholder).")
        self.ui_close_iracing_checkbox.toggled.connect(self._on_setting_close_iracing_toggled)
        layout.addWidget(self.ui_close_iracing_checkbox)

        self.ui_encode_video_after_capture_checkbox = QCheckBox("Auto Transcode Video After Analysis/Capture")
        self.ui_encode_video_after_capture_checkbox.setToolTip("If checked, starts video transcoding automatically after analysis or capture finishes (feature placeholder).")
        self.ui_encode_video_after_capture_checkbox.toggled.connect(self._on_setting_encode_video_after_capture_toggled)
        layout.addWidget(self.ui_encode_video_after_capture_checkbox)

        self.ui_fast_video_recording_checkbox = QCheckBox("Fast Video Recording Mode (External Recorder)")
        self.ui_fast_video_recording_checkbox.setToolTip("Placeholder for a potentially faster, lower quality recording preset if supported by the external recorder.")
        self.ui_fast_video_recording_checkbox.toggled.connect(self._on_setting_fast_video_recording_toggled)
        layout.addWidget(self.ui_fast_video_recording_checkbox)

        self.ui_short_test_only_checkbox = QCheckBox("Short Test Only (Dev: limits processing)")
        self.ui_short_test_only_checkbox.setToolTip("Developer option: significantly reduces processing time for testing purposes (e.g., shorter simulated analysis).")
        self.ui_short_test_only_checkbox.toggled.connect(self._on_setting_short_test_only_toggled)
        layout.addWidget(self.ui_short_test_only_checkbox)

        self.ui_use_new_settings_dialog_checkbox = QCheckBox("Use New Settings Dialog (Dev: Placeholder)")
        self.ui_use_new_settings_dialog_checkbox.setToolTip("Developer placeholder for toggling UI features or experimental dialogs.")
        self.ui_use_new_settings_dialog_checkbox.toggled.connect(self._on_setting_use_new_settings_dialog_toggled)
        layout.addWidget(self.ui_use_new_settings_dialog_checkbox)

        self.ui_highlight_video_only_checkbox = QCheckBox("Transcode Highlights Only (Global Default)")
        self.ui_highlight_video_only_checkbox.setToolTip("If checked, the main transcode button will produce highlights by default (can be overridden by Transcoding tab option).")
        self.ui_highlight_video_only_checkbox.toggled.connect(self._on_setting_highlight_video_only_toggled)
        layout.addWidget(self.ui_highlight_video_only_checkbox)

        group.setLayout(layout)
        return group

    def _load_settings_to_ui(self):
        """Populates the Settings tab UI elements with values from AppSettings."""
        if not hasattr(self, 'ui_working_folder_edit'):
            print("WARN: Settings UI elements not ready for loading.")
            return # UI not fully built yet

        # General Settings
        self.ui_working_folder_edit.setText(self.app_settings.working_folder)
        self.ui_preferred_drivers_edit.setText(self.app_settings.preferred_driver_names)

        # Populate Plugin ComboBox
        self.ui_plugin_combo.clear()
        available_plugins = self.plugin_manager.get_available_plugins()
        if not available_plugins:
            self.ui_plugin_combo.addItem("No plugins found")
            self.ui_plugin_combo.setEnabled(False)
        else:
            for plugin in available_plugins:
                self.ui_plugin_combo.addItem(plugin.name) # Assumes plugin.name is unique and user-friendly

            current_plugin_name = self.app_settings.plugin_name
            current_index = self.ui_plugin_combo.findText(current_plugin_name)
            if current_index != -1:
                self.ui_plugin_combo.setCurrentIndex(current_index)
            elif available_plugins:
                self.ui_plugin_combo.setCurrentIndex(0)
            self.ui_plugin_combo.setEnabled(True)

        # Recording Hotkeys
        self.ui_hotkey_start_stop_edit.setText(self.app_settings.hotkey_stop_start)
        self.ui_hotkey_pause_resume_edit.setText(self.app_settings.hotkey_pause_resume)

        # Video Options
        self.ui_video_bitrate_spinbox.setValue(self.app_settings.video_bitrate // 1000000) # bps to Mbps
        self.ui_highlight_duration_spinbox.setValue(self.app_settings.highlight_video_target_duration_seconds)

        # Application Flags
        self.ui_capture_opening_scene_checkbox.setChecked(self.app_settings.capture_opening_scene)
        self.ui_shutdown_pc_checkbox.setChecked(self.app_settings.shutdown_pc_after_encoding)
        self.ui_close_iracing_checkbox.setChecked(self.app_settings.close_iracing_after_recording)
        self.ui_encode_video_after_capture_checkbox.setChecked(self.app_settings.encode_video_after_capture)
        self.ui_fast_video_recording_checkbox.setChecked(self.app_settings.fast_video_recording)
        self.ui_short_test_only_checkbox.setChecked(self.app_settings.short_test_only)
        self.ui_use_new_settings_dialog_checkbox.setChecked(self.app_settings.use_new_settings_dialog)
        self.ui_highlight_video_only_checkbox.setChecked(self.app_settings.highlight_video_only)

        self.status_text_edit.append("INFO: Settings loaded into Settings tab UI.")


    # --- Slots for Settings UI Element Changes ---

    def _on_setting_working_folder_changed(self):
        self.app_settings.working_folder = self.ui_working_folder_edit.text()
        self.status_text_edit.append(f"DEBUG: AppSettings.working_folder updated to: {self.app_settings.working_folder}")

    def _on_setting_plugin_changed(self, plugin_name: str):
        self.app_settings.plugin_name = plugin_name
        self.status_text_edit.append(f"DEBUG: AppSettings.plugin_name updated to: {self.app_settings.plugin_name}")
        # Potentially re-initialize or update active plugin if this change should be immediate
        # For now, just updates app_settings. Active plugin change usually happens via PluginManager.

    def _on_setting_preferred_drivers_changed(self):
        self.app_settings.preferred_driver_names = self.ui_preferred_drivers_edit.text()
        self.status_text_edit.append(f"DEBUG: AppSettings.preferred_driver_names updated to: {self.app_settings.preferred_driver_names}")

    def _on_setting_hotkey_start_stop_changed(self):
        self.app_settings.hotkey_stop_start = self.ui_hotkey_start_stop_edit.text()
        self.status_text_edit.append(f"DEBUG: AppSettings.hotkey_stop_start updated to: {self.app_settings.hotkey_stop_start}")

    def _on_setting_hotkey_pause_resume_changed(self):
        self.app_settings.hotkey_pause_resume = self.ui_hotkey_pause_resume_edit.text()
        self.status_text_edit.append(f"DEBUG: AppSettings.hotkey_pause_resume updated to: {self.app_settings.hotkey_pause_resume}")

    def _on_setting_video_bitrate_changed(self, value_mbps: int):
        self.app_settings.video_bitrate = value_mbps * 1000000 # Convert Mbps to bps
        self.status_text_edit.append(f"DEBUG: AppSettings.video_bitrate updated to: {self.app_settings.video_bitrate} bps")

    def _on_setting_highlight_duration_changed(self, value_seconds: int):
        self.app_settings.highlight_video_target_duration_seconds = value_seconds
        self.status_text_edit.append(f"DEBUG: AppSettings.highlight_video_target_duration_seconds updated to: {self.app_settings.highlight_video_target_duration_seconds}s")

    def _on_setting_capture_opening_scene_toggled(self, checked: bool):
        self.app_settings.capture_opening_scene = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.capture_opening_scene updated to: {checked}")

    def _on_setting_shutdown_pc_toggled(self, checked: bool):
        self.app_settings.shutdown_pc_after_encoding = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.shutdown_pc_after_encoding updated to: {checked}")

    def _on_setting_close_iracing_toggled(self, checked: bool):
        self.app_settings.close_iracing_after_recording = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.close_iracing_after_recording updated to: {checked}")

    def _on_setting_encode_video_after_capture_toggled(self, checked: bool):
        self.app_settings.encode_video_after_capture = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.encode_video_after_capture updated to: {checked}")

    def _on_setting_fast_video_recording_toggled(self, checked: bool):
        self.app_settings.fast_video_recording = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.fast_video_recording updated to: {checked}")

    def _on_setting_short_test_only_toggled(self, checked: bool):
        self.app_settings.short_test_only = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.short_test_only updated to: {checked}")

    def _on_setting_use_new_settings_dialog_toggled(self, checked: bool):
        self.app_settings.use_new_settings_dialog = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.use_new_settings_dialog updated to: {checked}")

    def _on_setting_highlight_video_only_toggled(self, checked: bool):
        self.app_settings.highlight_video_only = checked
        self.status_text_edit.append(f"DEBUG: AppSettings.highlight_video_only updated to: {checked}")


    # --- Button Click Slots ---
    def _save_settings_clicked(self):
        """Saves the current in-memory AppSettings to the settings.ini file."""
        try:
            self.app_settings.save_settings()
            self.statusBar().showMessage("Settings saved successfully.", 5000)
            self.status_text_edit.append("INFO: Settings saved to file.")
            QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")
        except Exception as e: # Catching general exception, could be more specific like IOError
            self.status_text_edit.append(f"ERROR: Failed to save settings - {e}")
            QMessageBox.warning(
                self,
                "Save Error",
                f"Could not save settings to {self.app_settings.filepath}.\n"
                f"Please check file permissions and path.\n\nError: {e}"
            )

    def _reset_settings_clicked(self):
        """Resets in-memory AppSettings to defaults and refreshes the UI."""
        reply = QMessageBox.question(
            self,
            'Confirm Reset',
            'Are you sure you want to reset all settings in the UI to their default values?\n'
            'This will revert any unsaved changes currently displayed.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.app_settings.reset_to_defaults()
                self._load_settings_to_ui() # Refresh Settings tab UI with new default values
                self.statusBar().showMessage("Settings reset to defaults. Click 'Save Settings' to persist them.", 8000)
                self.status_text_edit.append("INFO: Settings reset to defaults in UI. Save to persist.")
                QMessageBox.information(self, "Settings Reset", "Settings have been reset to their default values in the UI.\nClick 'Save Settings' to make these changes permanent.")
            except Exception as e:
                self.status_text_edit.append(f"ERROR: Failed to reset settings - {e}")
                QMessageBox.warning(self, "Reset Error", f"Could not reset settings.\n\nError: {e}")


    def _browse_working_folder_clicked(self):
        current_folder = self.ui_working_folder_edit.text() or self.app_settings.working_folder
        directory = QFileDialog.getExistingDirectory(
            self, "Select Working Folder", current_folder
        )
        if directory:
            self.ui_working_folder_edit.setText(directory)
            # This directly updates app_settings if connected, or user needs to "Save"
            # With editingFinished connected, it will update app_settings.working_folder automatically.
            self.status_text_edit.append(f"INFO: Working folder UI changed to: {directory}. Associated AppSetting updated.")


    def _show_about_dialog(self):
        QMessageBox.about(
            self,
            "About iRacing Telemetry Analyzer",
            "This application helps analyze iRacing replays and generate overlay videos.\n\n"
            "Version: 0.1.0 (Alpha)" # Placeholder version
        )

    # Removed old _browse_working_folder, as its functionality is now in _browse_working_folder_clicked for settings tab.

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

        # Update Connect/Disconnect menu items
        if hasattr(self, 'connect_iracing_action'): # Ensure menu is created
            is_im_connected = self.iracing_manager.is_connected()
            self.connect_iracing_action.setEnabled(not is_im_connected)
            self.disconnect_iracing_action.setEnabled(is_im_connected)


    def _connect_iracing(self):
        """Slot to connect to iRacing."""
        self.status_text_edit.append("Attempting to connect to iRacing...")
        self.app_state_manager.change_state(self.app_state_manager.current_state, "Connecting to iRacing...", force_notify=True)
        self.iracing_manager.connect()
        if self.iracing_manager.is_connected():
            self.app_state_manager.change_state(AppStates.IDLE, "Successfully connected to iRacing.")
            self.status_text_edit.append("INFO: Connected to iRacing.")
        else:
            status_msg = "Failed to connect to iRacing."
            if not PYIRSDK_AVAILABLE:
                status_msg += " (pyirsdk library not found/mocked)"
            else:
                status_msg += " (iRacing not running or SDK not active)"
            self.app_state_manager.change_state(AppStates.IDLE, status_msg) # Or ERROR state?
            self.status_text_edit.append(f"ERROR: {status_msg}")
            QMessageBox.warning(self, "Connection Failed", status_msg)
        self._update_ui_from_state(self.app_state_manager.current_state, self.app_state_manager.last_message)


    def _disconnect_iracing(self):
        """Slot to disconnect from iRacing."""
        self.status_text_edit.append("Disconnecting from iRacing...")
        self.iracing_manager.disconnect()
        self.app_state_manager.change_state(AppStates.IDLE, "Disconnected from iRacing.")
        self.status_text_edit.append("INFO: Disconnected from iRacing.")
        self._update_ui_from_state(self.app_state_manager.current_state, self.app_state_manager.last_message)


    def _update_live_telemetry(self):
        """Called by QTimer to update live telemetry display."""
        if not hasattr(self, 'ui_telemetry_status_label'): # UI not fully ready
            return

        if self.iracing_manager.is_connected():
            data_sample = self.iracing_manager.get_latest_data_sample()
            if data_sample:
                # Example: "Connected | Time: 123.45s | Speed: 150km/h | Gear: 4 | R: 10/100"
                session_time = data_sample.get('SessionTime', -1)
                speed_ms = data_sample.get('Speed', 0)
                speed_kmh = speed_ms * 3.6
                gear = data_sample.get('Gear', 'N')
                replay_frame = data_sample.get('ReplayFrameNum', 0)
                is_replay_playing = data_sample.get('IsReplayPlaying', False)

                telemetry_str = (
                    f"Connected | Time: {session_time:.2f}s | "
                    f"Speed: {speed_kmh:.0f}km/h | Gear: {gear} | "
                    f"Replay Frame: {replay_frame} ({'Play' if is_replay_playing else 'Pause'})"
                )
                self.ui_telemetry_status_label.setText(telemetry_str)
            else:
                self.ui_telemetry_status_label.setText("Connected | Waiting for new data...")
        else:
            self.ui_telemetry_status_label.setText(f"Disconnected. SDK Available: {PYIRSDK_AVAILABLE}")


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
