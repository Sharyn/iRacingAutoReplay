import pytest
import subprocess
from pathlib import Path
from typing import List, Any, Optional # Added Optional
import shlex # For comparing command parts if they were quoted

# Assuming pytest runs from the project root or paths are configured
from src.app_settings import AppSettings
from src.plugin_manager import PluginManager
from src.replay_data import OverlayData, CapturedVideoFile, RaceEvent
from src.ffmpeg_transcoder import FFmpegTranscoder
from src.video_editing import get_highlight_segments_to_keep

# Import the mock ffmpeg from the transcoder module to inspect its state if needed,
# or to check if the real ffmpeg-python is being used.
from src.ffmpeg_transcoder import ffmpeg as ffmpeg_module_in_transcoder

# --- Fixtures ---

@pytest.fixture
def mock_app_settings(tmp_path: Path) -> AppSettings:
    settings_file_path = tmp_path / "settings_for_transcoder_test.ini"
    settings = AppSettings(settings_filepath=settings_file_path)
    settings.working_folder = str(tmp_path / "transcoder_test_output")
    Path(settings.working_folder).mkdir(parents=True, exist_ok=True)
    settings.video_bitrate = 8000000 # 8 Mbps
    settings.highlight_video_target_duration_seconds = 10 # For highlight test
    settings.preferred_font_path = "TestFontForTranscoder" # For filter checking
    settings.save_settings()
    return settings

@pytest.fixture(scope="module") # Use module scope for dummy video to avoid recreating it for each test function
def dummy_video_file(tmp_path_factory) -> Optional[Path]:
    # Use tmp_path_factory for module-scoped temporary directory
    module_tmp_dir = tmp_path_factory.mktemp("transcoder_videos")
    video_file = module_tmp_dir / "dummy_input_video.mp4"
    duration = 20 # seconds, make it long enough for various highlight scenarios
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
        print(f"Creating dummy video: {video_file} ({duration}s)")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"smptebars=duration={duration}:size=320x240:rate=30",
            "-c:v", "libx264", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
            str(video_file)
        ], check=True, capture_output=True, timeout=20) # Increased timeout
        print(f"Dummy video created successfully at {video_file}")
        return video_file
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Could not create dummy video using ffmpeg CLI: {e}. Test may be limited.")
        # Fallback: create an empty file if ffmpeg CLI is not available
        # The mock ffmpeg.probe needs to be robust to this or provide a default duration.
        video_file.touch()
        print(f"Created empty dummy video file at {video_file} as fallback.")
        return video_file # Return path to empty file, tests need to handle this

@pytest.fixture
def mock_overlay_data(dummy_video_file: Optional[Path]) -> OverlayData:
    if not dummy_video_file: # If dummy video creation completely failed
        pytest.skip("Dummy video file could not be created, skipping transcoder setup tests.")

    # Create OverlayData that points to the dummy video file
    # Add some RaceEvents for highlight testing
    events = [
        RaceEvent(start_time=2.0, end_time=5.0, interest="Incident", with_overtake=True), # 3s duration
        RaceEvent(start_time=8.0, end_time=12.0, interest="Battle", with_overtake=False), # 4s duration
        RaceEvent(start_time=15.0, end_time=18.0, interest="Incident", with_overtake=True) # 3s duration
    ]
    return OverlayData(
        video_files=[CapturedVideoFile(filename=str(dummy_video_file))],
        race_events=events
    )

@pytest.fixture
def mock_plugin_manager_with_active_plugin(mock_app_settings: AppSettings, mock_overlay_data: OverlayData) -> PluginManager:
    # This fixture sets up PluginManager and ensures SimpleTimestampOverlay is loaded and active.
    # It assumes simple_timestamp_overlay.py exists in the standard plugin location.

    # Path to src/plugins directory
    test_file_path = Path(__file__).resolve()
    plugins_dir = test_file_path.parent.parent / "src" / "plugins"
    example_plugin_file = plugins_dir / "simple_timestamp_overlay.py"
    if not example_plugin_file.exists():
        pytest.skip(f"Example plugin not found at {example_plugin_file}. Cannot test plugin integration.")

    pm = PluginManager(settings=mock_app_settings)
    pm.load_plugins(str(plugins_dir))

    # Set SimpleTimestampOverlay as active
    # The mock_overlay_data here is just to satisfy initialize(), plugin might not use it.
    activated = pm.set_active_plugin("Simple Timestamp", mock_overlay_data)
    if not activated:
        pytest.fail("Could not activate 'Simple Timestamp' plugin for testing.")
    return pm


# Helper to access the command list from the mock FFmpeg process
def get_last_ffmpeg_command(transcoder: FFmpegTranscoder) -> Optional[List[str]]:
    # This depends on how the mock ffmpeg is structured in ffmpeg_transcoder.py
    # Assuming the mock process object (returned by run_async) stores the command list
    # This is a bit of a hack into the mock's internals.
    # If the transcoder stored the last process, we could get it from there.
    # For now, let's assume the global mock object in ffmpeg_transcoder module might hold it,
    # or we capture stdout if it prints there.

    # The current mock in ffmpeg_transcoder.py's MockFFmpegNode.run() stores
    # the command on the MockProcess object it returns.
    # FFmpegTranscoder.transcode_video() calls run_async() and gets this process.
    # We need to get this process object.
    # Simplest for now: if ffmpeg_module_in_transcoder is the mock, assume it has a way to expose last cmd.
    # The current mock implementation makes the MockProcess (returned by run_async) store `self.cmd_list`.
    # However, `transcode_video` doesn't return this process.
    # MODIFYING the mock to store last_cmd_list on a class variable of MockFFmpegNode:
    if hasattr(ffmpeg_module_in_transcoder, "MockFFmpegNode") and \
       hasattr(ffmpeg_module_in_transcoder.MockFFmpegNode, 'last_cmd_list'):
        return ffmpeg_module_in_transcoder.MockFFmpegNode.last_cmd_list
    return None

# --- Test Functions ---

def test_transcode_full_video_setup(
    mock_app_settings: AppSettings,
    mock_plugin_manager: PluginManager,
    mock_overlay_data: OverlayData,
    dummy_video_file: Optional[Path], # Will be skipped if None by mock_overlay_data fixture
    tmp_path: Path,
    capsys # To capture print statements from mock ffmpeg if needed
):
    """Tests FFmpeg command setup for a full video transcode."""
    if not dummy_video_file: pytest.skip("Dummy video not available.")

    transcoder = FFmpegTranscoder(settings=mock_app_settings, plugin_manager=mock_plugin_manager)
    output_file = tmp_path / "full_output.mp4"

    # Capture the print output of the mock ffmpeg command
    # Alternatively, modify mock to store command and retrieve it.
    # The mock `run_async` does print the command.

    success = transcoder.transcode_video(
        overlay_data=mock_overlay_data,
        output_filepath=str(output_file),
        is_highlights=False
    )

    assert success, "Transcoding (mocked) should report success."

    # Check if the mock created the dummy output file
    if isinstance(ffmpeg_module_in_transcoder, Any) and \
       ffmpeg_module_in_transcoder.__class__.__name__ == 'MockFFmpegModule': # Check if it's our mock
        # The mock's run() method does Path(output_filepath).touch()
        assert output_file.exists(), "Mock FFmpeg should have created a dummy output file."

    captured_stdout = capsys.readouterr().out
    # Extract the MOCK FFMPEG CMD line
    cmd_line_printed = ""
    for line in captured_stdout.splitlines():
        if line.startswith("MOCK FFMPEG CMD:"):
            cmd_line_printed = line.replace("MOCK FFMPEG CMD:", "").strip()
            break

    assert cmd_line_printed, "Mock FFmpeg command was not printed to stdout."
    cmd_args = shlex.split(cmd_line_printed) # Split respecting quotes

    # Common assertions
    assert f"-i" in cmd_args
    assert str(dummy_video_file) in cmd_args
    assert str(output_file) in cmd_args
    assert "-vcodec" in cmd_args and "libx264" in cmd_args
    assert "-acodec" in cmd_args and "aac" in cmd_args
    # Check for the bitrate value. The flag (-b:v or -video_bitrate) depends on ffmpeg-python vs mock.
    assert str(mock_app_settings.video_bitrate) in cmd_args

    # Filter assertions (SimpleTimestampOverlay provides one drawtext filter)
    # The mock command reconstruction should include -filter_complex if filters are applied.
    assert "-filter_complex" in cmd_args, \
        "'-filter_complex' flag should be present if overlays are applied by the mock."
    assert mock_app_settings.preferred_font_path in cmd_line_printed, \
        "Font path from settings should be part of the command line (likely in filter_complex string)."

    # Full video specific: No -ss or -t for the main input (or covers full duration)
    # This depends on how the mock reconstructs. If -ss is 0 or not present, it's fine.
    # The mock adds -ss and -t if they are in input_kwargs. For full video, they shouldn't be.
    ss_indices = [i for i, x in enumerate(cmd_args) if x == "-ss"]
    input_file_index = cmd_args.index(str(dummy_video_file))

    has_ss_before_input = any(idx < input_file_index for idx in ss_indices)
    # A more robust check would be to ensure that if -ss is present for the main input, it's ~0.
    # The current transcoder doesn't add -ss for full video input.
    # The mock ffmpeg adds -ss if it finds it in the input node's kwargs.
    # Transcoder should not put it there for full video.
    assert not has_ss_before_input or cmd_args[ss_indices[0]+1] == "0" or cmd_args[ss_indices[0]+1] == "0.0", \
        "Full video transcode should not have significant -ss on input, or it should be near 0."


def test_transcode_highlights_video_setup(
    mock_app_settings: AppSettings,
    mock_plugin_manager: PluginManager,
    mock_overlay_data: OverlayData,
    dummy_video_file: Optional[Path],
    tmp_path: Path,
    capsys
):
    """Tests FFmpeg command setup for a highlights video transcode."""
    if not dummy_video_file: pytest.skip("Dummy video not available.")

    transcoder = FFmpegTranscoder(settings=mock_app_settings, plugin_manager=mock_plugin_manager)
    output_file = tmp_path / "highlight_output.mp4"

    success = transcoder.transcode_video(
        overlay_data=mock_overlay_data,
        output_filepath=str(output_file),
        is_highlights=True
    )
    assert success, "Transcoding (mocked) for highlights should report success."

    if isinstance(ffmpeg_module_in_transcoder, Any) and \
       ffmpeg_module_in_transcoder.__class__.__name__ == 'MockFFmpegModule':
        assert output_file.exists(), "Mock FFmpeg should have created a dummy highlight output file."

    captured_stdout = capsys.readouterr().out
    cmd_line_printed = ""
    for line in captured_stdout.splitlines():
        if line.startswith("MOCK FFMPEG CMD:"):
            cmd_line_printed = line.replace("MOCK FFMPEG CMD:", "").strip()
            break
    assert cmd_line_printed, "Mock FFmpeg command was not printed to stdout for highlights."
    cmd_args = shlex.split(cmd_line_printed)

    # Common assertions (as in full video test)
    assert f"-i" in cmd_args and str(dummy_video_file) in cmd_args
    assert str(output_file) in cmd_args
    assert mock_app_settings.preferred_font_path in cmd_line_printed

    # Highlights specific: -ss and -t for the input
    # Get the expected first segment from video_editing
    expected_segments = get_highlight_segments_to_keep(mock_overlay_data, mock_app_settings)
    assert len(expected_segments) > 0, "Highlights generation should produce segments for mock_overlay_data."
    first_segment = expected_segments[0]

    # Check for -ss (start time of the first segment)
    assert "-ss" in cmd_args
    ss_index = cmd_args.index("-ss") + 1
    assert ss_index < len(cmd_args)
    # Compare float values with tolerance
    assert abs(float(cmd_args[ss_index]) - first_segment.start_time) < 0.01

    # Check for -t (duration of the first segment)
    assert "-t" in cmd_args
    t_index = cmd_args.index("-t") + 1
    assert t_index < len(cmd_args)
    assert abs(float(cmd_args[t_index]) - first_segment.duration) < 0.01

