"""
Manages external video capture software using global hotkeys and monitors
for newly created video files.
"""

import enum
import threading
import time
import datetime # For recording start time
from pathlib import Path
from typing import List, Optional, Any, TYPE_CHECKING # Added Any for AppStateManager initially

# Conditional import for pyautogui for testing/CI environments
try:
    import pyautogui
except ImportError:
    # Mock pyautogui if not available, useful for environments where it can't be installed/run.
    class MockPyAutoGUI:
        def __getattr__(self, name):
            # This wrapper will be called for any attribute access on MockPyAutoGUI instance.
            def wrapper(*args, **kwargs):
                # Using f-string with '=' for self-documenting expressions (Python 3.8+)
                print(f"MOCK pyautogui: Call to {name}(args={args!r}, kwargs={kwargs!r})")
            return wrapper
    pyautogui = MockPyAutoGUI()
    print("WARNING: pyautogui not found or import failed. Using mock version. Hotkeys will not be sent.")


if TYPE_CHECKING:
    from iracing_telemetry_analyzer_py.src.app_settings import AppSettings
    from iracing_telemetry_analyzer_py.src.app_state_manager import AppStateManager # For type hinting


class RecorderState(enum.Enum):
    """
    Represents the state of the external screen recorder.
    """
    STOPPED = "Stopped"
    RUNNING = "Running"
    PAUSED = "Paused"

    def __str__(self):
        return self.value


class VideoCaptureManager:
    """
    Controls an external screen recorder via hotkeys and discovers captured video files.
    """
    SCAN_INTERVAL_SECONDS = 5  # How often to scan for new video files.

    def __init__(self, settings: 'AppSettings', app_state_manager: Optional['AppStateManager'] = None):
        """
        Initializes the VideoCaptureManager.

        Args:
            settings: An AppSettings instance containing configuration like
                      working_folder and hotkey strings.
            app_state_manager: Optional AppStateManager for future state updates from this manager.
        """
        self.settings = settings
        self.app_state_manager = app_state_manager # Store for potential future use (e.g., reporting errors)

        self._recorder_status: RecorderState = RecorderState.STOPPED
        self.captured_video_files: List[Path] = []

        self._recording_start_time: Optional[datetime.datetime] = None
        self._scan_timer: Optional[threading.Timer] = None
        self._timer_stop_event = threading.Event() # Used to signal the timer thread to stop

        # Ensure working folder exists
        try:
            Path(self.settings.working_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating working folder '{self.settings.working_folder}': {e}")
            # Depending on severity, could raise error or set a "disabled" state.

    def _send_hotkey(self, hotkey_string: str) -> None:
        """
        Parses a hotkey string (e.g., 'Ctrl+Shift+S') and sends it using pyautogui.

        Args:
            hotkey_string: The hotkey combination to send.
        """
        if not hotkey_string:
            print("Warning: Hotkey string is empty. No hotkey sent.")
            return

        # Convert to lowercase and split by '+'
        keys = [key.strip().lower() for key in hotkey_string.split('+')]

        # pyautogui.hotkey() takes individual keys as *args
        # It supports common modifier keys like 'ctrl', 'shift', 'alt', 'win'
        # and special keys like 'f1'-'f12', 'enter', 'esc', etc.
        print(f"Sending hotkey: {hotkey_string} (parsed as: {keys})")
        try:
            # Filter out empty strings that might result from splitting " + "
            valid_keys = [k for k in keys if k]
            if valid_keys:
                pyautogui.hotkey(*valid_keys)
            else:
                print(f"Warning: Hotkey string '{hotkey_string}' resulted in no valid keys.")
        except Exception as e:
            # pyautogui can raise various errors, e.g., if a key name is invalid
            # or if it can't control the host OS (e.g. headless server, Wayland without specific setup)
            print(f"Error sending hotkey '{hotkey_string}': {e}")


    def _scan_for_new_videos(self) -> None:
        """
        Scans the working folder for new .mp4 or .avi files created after
        recording started. This method is called periodically by a timer.
        """
        if self._timer_stop_event.is_set(): # Check if stopping is requested
            return

        if self._recording_start_time is None:
            # Should not happen if timer is running, but good for safety
            return

        working_dir = Path(self.settings.working_folder)
        if not working_dir.is_dir():
            return # Working directory doesn't exist or is not a directory.

        # print(f"Debug: Scanning for videos in {working_dir} since {self._recording_start_time}...")
        try:
            for ext in ("*.mp4", "*.avi"): # Common video extensions
                for filepath in working_dir.glob(ext):
                    if filepath.is_file():
                        try:
                            file_mod_time_ts = filepath.stat().st_mtime
                            file_mod_datetime = datetime.datetime.fromtimestamp(file_mod_time_ts)

                            # Compare file modification time with recording start time
                            if file_mod_datetime >= self._recording_start_time:
                                if filepath not in self.captured_video_files:
                                    print(f"Discovered new video file: {filepath}")
                                    self.captured_video_files.append(filepath)
                        except OSError as e: # Catch stat errors e.g. file deleted during scan
                            print(f"Error stating file {filepath}: {e}")
        except Exception as e: # Catch any other errors during scan, e.g., permission issues
            print(f"Error scanning for videos: {e}")


        # Reschedule the timer if not stopping
        if not self._timer_stop_event.is_set():
            self._scan_timer = threading.Timer(self.SCAN_INTERVAL_SECONDS, self._scan_for_new_videos)
            self._scan_timer.daemon = True # Allow main program to exit even if timer is running
            self._scan_timer.start()
        else:
            print("Scan timer stopping as requested.")


    def activate(self, start_recording: bool = True) -> None:
        """
        Activates video capture monitoring. Optionally starts recording immediately.

        Args:
            start_recording: If True and not already recording, sends the
                             start/stop hotkey to begin recording.
        """
        print(f"VideoCaptureManager activating. Start recording: {start_recording}")
        self.captured_video_files = [] # Reset file list
        self._recording_start_time = datetime.datetime.now()
        self._timer_stop_event.clear() # Clear stop event for the new timer session

        if start_recording and self._recorder_status == RecorderState.STOPPED:
            self._send_hotkey(self.settings.hotkey_stop_start)
            self._recorder_status = RecorderState.RUNNING

        # Start periodic scanning only if it's not already running from a previous activate
        if self._scan_timer is None or not self._scan_timer.is_alive():
            self._scan_for_new_videos() # Initial scan, which will also schedule the next one
        print(f"Recorder status: {self._recorder_status}")


    def deactivate(self, is_highlight_mode: bool = False) -> List[Path]:
        """
        Deactivates video capture monitoring, stops recording, performs a final scan,
        and returns the list of captured video files.

        Args:
            is_highlight_mode: If True and recorder is RUNNING, sends pause/resume hotkey.
                               Otherwise (or if PAUSED/STOPPED), sends start/stop hotkey
                               to ensure recording stops.

        Returns:
            A list of Path objects for discovered video files.
        """
        print(f"VideoCaptureManager deactivating. Highlight mode: {is_highlight_mode}")

        # Signal the timer to stop further scheduling
        self._timer_stop_event.set()
        if self._scan_timer and self._scan_timer.is_alive():
            self._scan_timer.cancel() # Attempt to cancel the current running timer
            print("Scan timer cancelled.")
        self._scan_timer = None

        if self._recorder_status == RecorderState.RUNNING:
            if is_highlight_mode:
                print("Highlight mode: Sending pause/resume hotkey.")
                self._send_hotkey(self.settings.hotkey_pause_resume)
                # We assume it's paused now for highlights, but actual state might differ.
                # For simplicity, we'll just send the key and not change _recorder_status here
                # as we are deactivating. The goal is to finalize the video.
            else:
                print("Normal mode: Sending start/stop hotkey to stop recording.")
                self._send_hotkey(self.settings.hotkey_stop_start)
        elif self._recorder_status == RecorderState.PAUSED:
            # If paused, we might need to send stop to finalize, or pause again if that's how stop works
            # Assuming start/stop hotkey also serves to stop when paused.
            print("Was paused: Sending start/stop hotkey to ensure recording stops.")
            self._send_hotkey(self.settings.hotkey_stop_start)

        self._recorder_status = RecorderState.STOPPED
        print(f"Recorder status set to: {self._recorder_status}")

        # Wait a bit for the recorder to finalize the file
        print("Waiting for video file finalization (2 seconds)...")
        time.sleep(2)

        # Perform one last scan
        print("Performing final scan for video files...")
        self._timer_stop_event.clear() # Temporarily allow one more scan
        self._scan_for_new_videos()    # This won't reschedule if _timer_stop_event is set right after
        self._timer_stop_event.set()   # Ensure it remains set

        print(f"Deactivation complete. Found {len(self.captured_video_files)} files.")
        return list(self.captured_video_files) # Return a copy


    def pause(self) -> None:
        """Sends the pause/resume hotkey if the recorder is currently running."""
        if self._recorder_status == RecorderState.RUNNING:
            print("Pausing recording...")
            self._send_hotkey(self.settings.hotkey_pause_resume)
            self._recorder_status = RecorderState.PAUSED
            print(f"Recorder status: {self._recorder_status}")
        else:
            print(f"Cannot pause. Recorder not running (current state: {self._recorder_status}).")


    def resume(self) -> None:
        """Sends the pause/resume hotkey if the recorder is currently paused."""
        if self._recorder_status == RecorderState.PAUSED:
            print("Resuming recording...")
            self._send_hotkey(self.settings.hotkey_pause_resume)
            self._recorder_status = RecorderState.RUNNING
            print(f"Recorder status: {self._recorder_status}")
        else:
            print(f"Cannot resume. Recorder not paused (current state: {self._recorder_status}).")


    def stop(self) -> List[Path]:
        """
        Stops recording if active (running or paused) and deactivates monitoring.
        This is similar to deactivate but more explicit about stopping.
        Returns the list of captured files.
        """
        print("Stopping video capture explicitly...")
        if self._recorder_status == RecorderState.RUNNING or self._recorder_status == RecorderState.PAUSED:
            # No special highlight mode consideration here, just stop.
            return self.deactivate(is_highlight_mode=False)
        else:
            # If already stopped, still call deactivate to ensure cleanup and file scan
            print("Recorder was already stopped. Running deactivation logic.")
            return self.deactivate(is_highlight_mode=False)


    def get_recorder_status(self) -> RecorderState:
        """Returns the current perceived status of the recorder."""
        return self._recorder_status


if __name__ == '__main__':
    print("--- VideoCaptureManager Demonstration ---")

    # Mock AppSettings for the demonstration
    class MockAppSettings:
        def __init__(self, working_dir):
            self.working_folder = str(working_dir) # Ensure it's a string
            self.hotkey_stop_start = "Ctrl+Alt+S"
            self.hotkey_pause_resume = "Ctrl+Alt+P"

    # Create a temporary directory for testing file discovery
    temp_dir = Path("./temp_video_capture_test_dir")
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"Temporary working directory for test: {temp_dir.resolve()}")

    mock_settings = MockAppSettings(temp_dir)

    # --- Mock pyautogui for this test block to avoid actual key presses ---
    # Store the original pyautogui.hotkey method (it could be the real one or the class-level mock)
    original_pyautogui_hotkey_method = pyautogui.hotkey

    # Define a test-specific mock function for pyautogui.hotkey
    def local_mock_hotkey_func(*args, **kwargs):
        key_str = "+".join(args)
        print(f"LOCAL MOCK PYAUTOGUI: pyautogui.hotkey('{key_str}') called with {kwargs=}.")

    # Apply the test-specific mock
    pyautogui.hotkey = local_mock_hotkey_func
    # --- End Mock pyautogui ---

    vcm = VideoCaptureManager(settings=mock_settings)

    print("\n1. Activating and starting recording...")
    vcm.activate(start_recording=True)
    assert vcm.get_recorder_status() == RecorderState.RUNNING
    assert vcm._scan_timer is not None and vcm._scan_timer.is_alive(), \
        "Scan timer should be active after activation."
    print(f"  Captured files after activate: {vcm.captured_video_files}")

    print("\n2. Simulating file creation...")
    time.sleep(0.1) # Ensure time moves forward slightly for timestamp comparisons
    if vcm._recording_start_time:
        (temp_dir / "video1.mp4").write_text("dummy video 1 content")
        (temp_dir / "some_other_file.txt").write_text("not a video")
        print(
            f"  Created dummy files. Current time: {datetime.datetime.now()}, "
            f"Recording started at: {vcm._recording_start_time}"
        )
    else:
        # This case should ideally not be hit if activate() works correctly.
        print("  ERROR: _recording_start_time not set; cannot simulate file creation accurately.")

    # Manually trigger scan for deterministic testing
    if vcm._scan_timer:
        vcm._scan_timer.cancel() # Stop the currently scheduled timer
    print("  Manually triggering video scan...")
    vcm._scan_for_new_videos() # Call scan logic directly
    assert Path(temp_dir / "video1.mp4") in vcm.captured_video_files, \
        "video1.mp4 should be discovered."
    # Note: _scan_for_new_videos will reschedule itself if _timer_stop_event is not set.
    # For this demo, subsequent operations will manage the timer or perform final scans.

    print("\n3. Pausing recording...")
    vcm.pause()
    assert vcm.get_recorder_status() == RecorderState.PAUSED

    print("\n4. Simulating another file while paused...")
    (temp_dir / "video2.avi").write_text("dummy video 2 content")
    if vcm._scan_timer and vcm._scan_timer.is_alive(): vcm._scan_timer.cancel() # Stop timer if it was rescheduled
    print("  Manually triggering video scan...")
    vcm._scan_for_new_videos()
    assert Path(temp_dir / "video2.avi") in vcm.captured_video_files, \
        "video2.avi should be discovered."

    print("\n5. Resuming recording...")
    vcm.resume()
    assert vcm.get_recorder_status() == RecorderState.RUNNING

    print("\n6. Deactivating (highlight mode)...")
    captured_files = vcm.deactivate(is_highlight_mode=True)
    assert vcm.get_recorder_status() == RecorderState.STOPPED
    assert vcm._scan_timer is None or not vcm._scan_timer.is_alive(), \
        "Scan timer should be stopped after deactivation."
    print(f"  Deactivated. Captured files list: {[f.name for f in captured_files]}")
    assert len(captured_files) == 2, "Should have discovered video1.mp4 and video2.avi."
    assert Path(temp_dir / "video1.mp4") in captured_files
    assert Path(temp_dir / "video2.avi") in captured_files

    print("\n7. Activating again (no immediate start), then stopping...")
    vcm.activate(start_recording=False) # Just set up monitoring
    assert vcm.get_recorder_status() == RecorderState.STOPPED # Status remains STOPPED

    (temp_dir / "video3.mp4").write_text("dummy video 3 content")
    # Manually scan to ensure video3.mp4 is found with the new _recording_start_time
    if vcm._scan_timer and vcm._scan_timer.is_alive(): vcm._scan_timer.cancel()
    print("  Manually triggering video scan before stop...")
    vcm._scan_for_new_videos()

    captured_files_on_stop = vcm.stop()
    assert vcm.get_recorder_status() == RecorderState.STOPPED
    print(f"  Stopped. Captured files list: {[f.name for f in captured_files_on_stop]}")
    assert Path(temp_dir / "video3.mp4") in captured_files_on_stop, \
        "video3.mp4 should be the only file discovered in this session."
    assert len(captured_files_on_stop) == 1, \
        "Only files since the last activate() call should be returned."

    # --- Restore original pyautogui.hotkey ---
    pyautogui.hotkey = original_pyautogui_hotkey_method
    print("\nRestored original pyautogui.hotkey method.")
    # --- End Restore ---

    # Clean up temporary directory
    print("\nCleaning up temporary directory and files...")
    try:
        for item in temp_dir.iterdir():
            item.unlink() # Delete files first
        temp_dir.rmdir()  # Then delete directory
        print(f"  Successfully cleaned up: {temp_dir.resolve()}")
    except Exception as e:
        print(f"  Error during cleanup of {temp_dir.resolve()}: {e}")

    print("\nVideoCaptureManager demonstration finished.")

```
