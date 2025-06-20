import pytest
import math # Added for math.isclose
from pathlib import Path
from typing import List  # Dict needed for MockAppSettings if used as dict

# Assuming pytest runs from the project root or paths are configured
from src.app_settings import AppSettings
from src.irsdk_manager import PyIrSdkManager # Changed from Placeholder
from src.irsdk_manager import PYIRSDK_AVAILABLE # To understand mock behavior
if not PYIRSDK_AVAILABLE:
    # Ensure we can access the mock classes if the real pyirsdk isn't there
    pass

from src.replay_analyzer import ReplayAnalyzer, CURRENT_VERSION as ANALYZER_VERSION
from src.replay_data import OverlayData  # VideoEdit is imported from video_editing
from src.video_editing import get_highlight_segments_to_keep, VideoEdit


# --- Fixtures or Helper Classes ---

@pytest.fixture
def mock_app_settings(tmp_path: Path) -> AppSettings:
    """Provides AppSettings configured to use a temporary working folder."""

    # Create a new AppSettings instance for each test using this fixture
    # This ensures that if AppSettings modifies its state or default path resolution (not current behavior),
    # tests remain isolated.
    # We need to ensure that the DEFAULT_SETTINGS are not cached with a non-tmp_path if app_settings
    # module was imported previously. For testing, it's safer to override the filepath.

    # Create a dummy settings file in tmp_path or let AppSettings create it there.
    settings_file_path = tmp_path / "settings_for_integration_test.ini"

    settings = AppSettings(settings_filepath=settings_file_path)
    settings.working_folder = str(tmp_path / "iracing_analyzer_output") # Ensure working folder is in tmp_path
    Path(settings.working_folder).mkdir(parents=True, exist_ok=True)

    settings.highlight_video_target_duration_seconds = 30 # Target 30s for easier reasoning
    settings.video_bitrate = 5000000 # Example, not directly used by this test but good to have

    # Ensure other settings that might influence video_editing indirectly are default or known
    # For example, if video_editing had settings for merge tolerance, etc.

    settings.save_settings() # Save to ensure file exists if AppSettings expects it
    return settings


def test_analyze_replays_and_generate_highlight_edits(mock_app_settings: AppSettings):
    """
    Tests the integration from ReplayAnalyzer producing OverlayData (using PyIrSdkManager with its mock)
    to video_editing processing it for highlight segments.
    """
    # 1. Setup
    # PyIrSdkManager will use its internal mock if real pyirsdk is not available/not connected.
    iracing_manager = PyIrSdkManager()

    # Configure the mock SDK within iracing_manager to simulate some incidents
    # This needs to happen before analyse_race is called.
    # ReplayAnalyzer's first call to get_incidents will see this.
    if hasattr(iracing_manager, 'ir_sdk') and hasattr(iracing_manager.ir_sdk, '_mock_data'):
        # Simulate 2 incidents detected by the time ReplayAnalyzer starts checking.
        # PyIrSdkManager's get_incidents uses 'PlayerCarMyIncidentCount'.
        # ReplayAnalyzer calls get_incidents periodically.
        # For this test, let's assume the first check in ReplayAnalyzer sees this.
        # ReplayAnalyzer's loop starts at SessionTime ~0. First incident check at ~2s.
        iracing_manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 2
        # Set a session time for when this incident is "detected" by get_incidents
        # This is tricky because get_incidents uses the *current* SessionTime from the SDK.
        # ReplayAnalyzer's loop updates SessionTime.
        # Let's ensure the mock SDK provides a SessionTime when get_incidents is called.
        iracing_manager.ir_sdk._mock_data['SessionTime'] = 2.5 # Arbitrary time for the incident event
    elif PYIRSDK_AVAILABLE and iracing_manager.ir_sdk is None:
        pytest.fail("PyIrSdkManager failed to initialize its IRSDK object even when PYIRSDK_AVAILABLE is True.")
    elif not PYIRSDK_AVAILABLE and (not hasattr(iracing_manager, 'ir_sdk') or not hasattr(iracing_manager.ir_sdk, '_mock_data')):
         pytest.fail("PyIrSdkManager's mock SDK is not correctly initialized.")


    replay_analyzer = ReplayAnalyzer(iracing_manager=iracing_manager, settings=mock_app_settings)

    # 2. Action: Run analyse_race to generate OverlayData XML
    # analyse_race returns the path to the created .replayscript.xml file
    # The abort_check lambda always returns False, so it won't abort.
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)

    assert xml_filepath_str is not None, "ReplayAnalyzer failed to produce an output file path."
    xml_filepath = Path(xml_filepath_str)
    assert xml_filepath.exists(), f"Generated OverlayData XML file not found at {xml_filepath}"

    # Load the OverlayData from the generated XML file
    loaded_overlay_data = OverlayData.load_from_xml(str(xml_filepath))
    assert loaded_overlay_data is not None
    assert loaded_overlay_data.captured_version == ANALYZER_VERSION
    assert len(loaded_overlay_data.race_events) > 0, "OverlayData should have race events from analyzer."

    # Call get_highlight_segments_to_keep
    highlight_segments: List[VideoEdit] = get_highlight_segments_to_keep(
        loaded_overlay_data, mock_app_settings
    )

    # 3. Assertions
    assert isinstance(highlight_segments, list), "Should return a list of VideoEdit objects."
    if highlight_segments: # Only check elements if list is not empty
        assert all(isinstance(segment, VideoEdit) for segment in highlight_segments)

    # --- Assertions based on ReplayAnalyzer's new data generation ---
    # ReplayAnalyzer now:
    # - Gets SessionInfo and converts to XML string.
    # - Periodically calls iracing_manager.get_incidents().
    #   - PyIrSdkManager.get_incidents() detects changes in PlayerCarMyIncidentCount.
    #   - If PlayerCarMyIncidentCount was preset to 2 in mock_sdk, and _last_player_incident_count is 0 in manager,
    #     one RaceEvent(interest='PlayerIncident', count_change=2) will be created.
    #     Its start_time will be the SessionTime when get_incidents was called (around 2.0s in ReplayAnalyzer's loop),
    #     and end_time = start_time + 1.0. This is a SECONDARY event (no overtake).
    # - The loop mainly generates LeaderBoard, CamDriver, MessageState, and potentially one FastLap.
    #   It no longer generates 'GenericInfo' or the initial two hardcoded 'Incident' events.

    # video_editing logic:
    # - Target duration: 30s.
    # - Category Ratios: PRIMARY: 0.4 (12s), SECONDARY: 0.3 (9s), TERTIARY: 0.2 (6s), BACKGROUND: 0.1 (3s).
    # - Max event durations: Secondary=15s. Merge tolerance: 0.5s.

    # Expected behavior for this test:
    # - One 'PlayerIncident' event (duration 1s) should be generated by ReplayAnalyzer.
    #   - Example: start_time=2.5s, end_time=3.5s (based on incident check interval and SessionTime).
    # - This 'PlayerIncident' (with_overtake=False) is a candidate for SECONDARY category.
    # - The 9s allocated to SECONDARY events should easily accommodate this 1s incident.
    # - Other event types ('Battle', 'Overtake', 'FirstLap', etc.) are not substantially generated by ReplayAnalyzer
    #   in a way that would be prioritized over this incident for a short highlight reel.

    if not highlight_segments:
        pytest.fail("No highlight segments were generated. Expected at least one 'PlayerIncident' segment.")

    print("\nGenerated VideoEdit Segments for Assertion:")
    total_kept_duration = 0
    player_incident_event_found_in_highlights = False

    # Find the expected PlayerIncident event in loaded_overlay_data.race_events
    # ReplayAnalyzer creates it around the first incident_check_interval (e.g. 2.0s)
    # with a duration of 1s.
    expected_incident_time_approx = 2.5 # ReplayAnalyzer get_incidents is called when current_session_time >= last_incident_check_session_time (2.0s)
                                        # and the event time is current_session_time.
                                        # The mock SDK was set to SessionTime = 2.5s for this incident.

    # Check if any generated RaceEvent is a PlayerIncident around the expected time
    generated_player_incident_event = None
    for event in loaded_overlay_data.race_events:
        if event.interest == 'PlayerIncident' and math.isclose(event.start_time, expected_incident_time_approx, abs_tol=0.5):
            generated_player_incident_event = event
            break

    assert generated_player_incident_event is not None, \
        f"ReplayAnalyzer did not generate the expected 'PlayerIncident' event around {expected_incident_time_approx}s."

    for i, segment in enumerate(highlight_segments):
        print(f"  Segment {i}: start={segment.start_time:.2f}, end={segment.end_time:.2f}, duration={segment.duration:.2f}")
        total_kept_duration += segment.duration
        assert segment.duration > 0, "VideoEdit segment duration should be positive."
        # Check if this segment covers the generated PlayerIncident
        if segment.start_time <= generated_player_incident_event.start_time and \
           segment.end_time >= generated_player_incident_event.end_time:
            player_incident_event_found_in_highlights = True

    assert player_incident_event_found_in_highlights, \
        f"The generated 'PlayerIncident' (around {generated_player_incident_event.start_time if generated_player_incident_event else 'N/A'}s) " \
        "was not covered by any highlight segment."

    # If only this one incident (1s duration) is selected, total duration should be ~1s.
    # It's possible other minor things (like first lap/last lap if any were generated and selected)
    # might be included if there's room in BACKGROUND. ReplayAnalyzer does not currently create these.
    if len(highlight_segments) == 1 and player_incident_event_found_in_highlights:
        assert math.isclose(total_kept_duration, generated_player_incident_event.end_time - generated_player_incident_event.start_time, abs_tol=0.1), \
            f"Total duration {total_kept_duration:.2f}s not matching expected single PlayerIncident duration."
    else:
        print(f"Warning: Highlight segments count is {len(highlight_segments)} or incident not isolated. Total duration: {total_kept_duration:.2f}s")

    # Total duration assertion
    assert total_kept_duration <= mock_app_settings.highlight_video_target_duration_seconds + 2.0, \
        f"Total duration {total_kept_duration:.2f}s exceeds target " \
        f"{mock_app_settings.highlight_video_target_duration_seconds}s significantly (plus tolerance)."

    # Cleanup of the generated XML file is handled by tmp_path if it's under mock_app_settings.working_folder
    # which it is.

