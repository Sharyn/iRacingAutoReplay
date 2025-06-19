import pytest
import math # Added for math.isclose
from pathlib import Path
from typing import List, Any # Dict needed for MockAppSettings if used as dict

# Assuming pytest runs from the project root or paths are configured
from iracing_telemetry_analyzer_py.src.app_settings import AppSettings
from iracing_telemetry_analyzer_py.src.iracing_manager import PlaceholderIRacingManager
from iracing_telemetry_analyzer_py.src.replay_analyzer import ReplayAnalyzer, CURRENT_VERSION as ANALYZER_VERSION
from iracing_telemetry_analyzer_py.src.replay_data import OverlayData, RaceEvent, VideoEdit # VideoEdit might be from video_editing
from iracing_telemetry_analyzer_py.src.video_editing import get_highlight_segments_to_keep, InterestCategory # InterestCategory for understanding logic


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
    Tests the integration from ReplayAnalyzer producing OverlayData
    to video_editing processing it for highlight segments.
    """
    # 1. Setup
    iracing_manager = PlaceholderIRacingManager()
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

    # --- Assertions based on ReplayAnalyzer's simulated data ---
    # ReplayAnalyzer simulation logic (as of last update):
    # - Adds 2 initial 'Incident' events, both with with_overtake=True:
    #   - Event 1: 5.0s - 10.0s (duration 5s), with_overtake=True (PRIMARY)
    #   - Event 2: 25.0s - 30.0s (duration 5s), with_overtake=True (PRIMARY)
    # - Loop (100 virtual seconds, 2 samples/sec = 200 iterations):
    #   - current_sample_time goes from 0.0 to 99.5
    #   - Adds LeaderBoardSnapshot, CamDriver at each step.
    #   - Adds MessageState every 10 virtual seconds.
    #   - Adds FastLap at 15 virtual seconds (current_sample_time = 15.0). This is a single point event, not a duration.
    #     video_editing currently doesn't explicitly use FastLap for segments.
    #   - Adds 'GenericInfo' RaceEvent (duration 0.5s) at each step. These should be mostly ignored.

    # video_editing logic:
    # - Target duration: 30s (from mock_app_settings)
    # - Category Ratios: PRIMARY: 0.4 (12s), SECONDARY: 0.3 (9s), TERTIARY: 0.2 (6s), BACKGROUND: 0.1 (3s)
    # - Max event durations for selection: Primary=20s, Secondary=15s, Tertiary=10s, Background=30s.
    # - Merge tolerance: 0.5s

    # Expected behavior:
    # - The two 'Incident' events (3s and 5s) are strong candidates for PRIMARY. Total 8s.
    #   - Incident 1: start=5, end=8
    #   - Incident 2: start=25, end=30
    # - 'GenericInfo' events from the loop should not be selected by primary/secondary/tertiary.
    # - 'Battle', 'Overtake', 'FirstLap', 'LastLap', 'Restart' events are not explicitly created in ReplayAnalyzer's loop,
    #   only the initial incidents and then generic ones.
    #   The `video_editing` module's categories for SECONDARY, TERTIARY, BACKGROUND will find no events
    #   from the `ReplayAnalyzer`'s main loop data, only from the initial hardcoded incidents.

    # Therefore, we expect the two primary incidents to be selected.
    # Their total duration is 3s + 5s = 8s, which is less than the 12s allocated for PRIMARY.

    # Let's check the properties of the returned segments.
    # Since the two incidents are far apart (8.0s and 25.0s), they should not be merged.

    if not highlight_segments:
        # This might happen if no events passed the filters or selection criteria.
        # Given ReplayAnalyzer's incidents, we expect segments.
        pytest.fail("No highlight segments were generated, which is unexpected.")

    print("\nGenerated VideoEdit Segments for Assertion:")
    total_kept_duration = 0
    for i, segment in enumerate(highlight_segments):
        print(f"  Segment {i}: start={segment.start_time:.2f}, end={segment.end_time:.2f}, duration={segment.duration:.2f}")
        total_kept_duration += segment.duration
        assert segment.duration > 0, "VideoEdit segment duration should be positive."

    # Assertions on the content of segments based on expected incidents
    # We expect the two 'Incident' events to be the primary content.
    # Incident 1: 5.0s - 10.0s (duration 5s)
    # Incident 2: 25.0s - 30.0s (duration 5s)
    # Both are with_overtake=True, so they are PRIMARY candidates.
    # Other categories (SECONDARY, TERTIARY, BACKGROUND) will find no other significant distinct events
    # from ReplayAnalyzer's current output that don't overlap these or are 'GenericInfo'.

    # The video_editing module sorts all selected events and then merges.
    # If only these two incidents are selected, they will remain separate segments.
    assert len(highlight_segments) >= 1, "Expected at least one segment from the primary incidents."

    # A more robust check: ensure the *times* of the known important events are covered.
    incident1_covered = any(s.start_time <= 5.0 and s.end_time >= 10.0 for s in highlight_segments)
    incident2_covered = any(s.start_time <= 25.0 and s.end_time >= 30.0 for s in highlight_segments)

    # If the selection logic picks *only* these two and they don't get merged with anything else:
    # Their total duration is 5s + 5s = 10s. Primary allocation is 0.4 * 30s = 12s. So both should fit.
    if len(highlight_segments) == 2:
        assert incident1_covered, "The first incident (5-10s) was not covered by a highlight segment."
        assert incident2_covered, "The second incident (25-30s) was not covered by a highlight segment."
        expected_total_duration = (10.0 - 5.0) + (30.0 - 25.0) # 5s + 5s = 10s
        assert math.isclose(total_kept_duration, expected_total_duration, abs_tol=0.1), \
            f"Total duration {total_kept_duration:.2f}s not matching expected {expected_total_duration:.2f}s for two incidents."
    else:
        # This case might occur if other minor events get selected or merging behavior changes.
        print(
            f"Warning: Number of segments is {len(highlight_segments)}, expected 2 if only the two "
            f"main incidents were chosen and remained separate. Actual total duration: {total_kept_duration:.2f}s."
        )
        # At least check they are covered if the segment count is different.
        assert incident1_covered or incident2_covered, "At least one of the main incidents should be covered."


    # Total duration assertion
    # target_total_duration = 30s. Max event duration for primary is 20s.
    # The two incidents sum to 10s. This is well within the 12s allocated for PRIMARY.
    # So, total_kept_duration should be close to 10s if no other categories contribute significantly.
    assert total_kept_duration <= mock_app_settings.highlight_video_target_duration_seconds + 2.0, \
        f"Total duration {total_kept_duration:.2f}s exceeds target " \
        f"{mock_app_settings.highlight_video_target_duration_seconds}s significantly."
    # A more specific check for this case, given the input:
    if len(highlight_segments) == 2 : # If it matches the simple two-incident case
         assert math.isclose(total_kept_duration, 10.0, abs_tol=0.1), \
            "With current ReplayAnalyzer data, expected total duration of highlights to be around 10s."


    # Cleanup of the generated XML file is handled by tmp_path if it's under mock_app_settings.working_folder
    # which it is.
```
