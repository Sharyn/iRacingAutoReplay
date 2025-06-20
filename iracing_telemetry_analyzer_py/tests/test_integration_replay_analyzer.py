import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Any, Dict, Optional, Callable

# Assuming pytest runs from project root or paths are configured
from iracing_telemetry_analyzer_py.src.app_settings import AppSettings
from iracing_telemetry_analyzer_py.src.pyirsdk_manager import PyIrSdkManager, PYIRSDK_AVAILABLE
if not PYIRSDK_AVAILABLE:
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import pyirsdk as mock_pyirsdk_module

from iracing_telemetry_analyzer_py.src.replay_analyzer import ReplayAnalyzer
from iracing_telemetry_analyzer_py.src.replay_data import OverlayData, RaceEvent, Driver, LeaderBoardSnapshot
from iracing_telemetry_analyzer_py.src.utils import dict_to_xml_string # For verification if needed

from iracing_telemetry_analyzer_py.src.pyirsdk_manager import (
    IRSDK_TRK_LOC_ON_TRACK, # Import if needed for driver status in future tests
    # For this test suite, we need session state and flags
    # These are conceptual values used by MockIRSDK and ReplayAnalyzer
)

# Define constants for session states and flags used in tests
# These should align with how they are interpreted in ReplayAnalyzer and mocked in PyIrSdkManager
IRSDK_SESSION_STATE_GET_IN_CAR = 1
IRSDK_SESSION_STATE_PARADE_LAPS = 4 # Example, check ReplayAnalyzer if it uses specific values
IRSDK_SESSION_STATE_RACING = 5
IRSDK_SESSION_STATE_COOLDOWN = 6
IRSDK_CHECKERED_FLAG = 0x00000004


# --- Fixtures ---

@pytest.fixture
def mock_app_settings(tmp_path: Path) -> AppSettings:
    """Provides AppSettings configured for testing ReplayAnalyzer."""
    settings_file_path = tmp_path / "settings_for_analyzer_test.ini"
    settings = AppSettings(settings_filepath=settings_file_path)
    settings.working_folder = str(tmp_path / "replay_analyzer_output")
    Path(settings.working_folder).mkdir(parents=True, exist_ok=True)

    # Settings relevant to ReplayAnalyzer's behavior
    settings.analysis_replay_speed = 1 # Use 1x speed for more predictable SessionTime progression in tests
    settings.max_analysis_duration_seconds = 10 # Short duration for faster tests

    settings.save_settings()
    return settings

@pytest.fixture
def pyirsdk_manager_fixture(mock_app_settings: AppSettings) -> PyIrSdkManager:
    """
    Provides a PyIrSdkManager instance. Its internal MockIRSDK can be configured
    by tests before running ReplayAnalyzer.
    """
    manager = PyIrSdkManager() # This will use MockIRSDK if pyirsdk is not installed/available

    """
    Provides a PyIrSdkManager instance. Its internal MockIRSDK can be configured
    by tests before running ReplayAnalyzer.
    """
    # Force use of MockIRSDK for these tests by temporarily patching PYIRSDK_AVAILABLE
    # if the real one was somehow imported.
    # This requires careful handling if other tests expect real pyirsdk.
    # For now, assume test environment doesn't have real pyirsdk or we accept testing against it if it's off.

    manager = PyIrSdkManager()

    if not (hasattr(manager, 'ir_sdk') and manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
        if PYIRSDK_AVAILABLE and manager.ir_sdk is not None:
             pytest.skip(
                "Test requires internal MockIRSDK of PyIrSdkManager, but real SDK seems active. "
                "Consider running tests in an environment without pyirsdk installed for these specific tests, "
                "or enhance fixture to forcibly use MockIRSDK."
            )
        else: # Should not happen if PYIRSDK_AVAILABLE is False, as __init__ should create MockIRSDK
            pytest.fail(
                "PyIrSdkManager's internal mock SDK (MockIRSDK) is not available or not named 'MockIRSDK'."
            )

    # Default mock SDK setup
    mock_sdk = manager.ir_sdk
    mock_sdk._mock_data['IsInitialized'] = True # Simulate SDK is initialized
    mock_sdk._mock_data['IsConnected'] = True   # Simulate SDK is connected to (non-running) sim
    mock_sdk._mock_data['SessionTime'] = 0.0
    mock_sdk._mock_data['PlayerCarMyIncidentCount'] = 0
    mock_sdk._mock_data['SessionInfo'] = { # Default basic SessionInfo structure
        'WeekendInfo': {'TrackDisplayName': 'Test Track from Fixture', 'SessionLaps': 'Unlimited'},
        'SessionInfo': {'Sessions': [{'SessionNum': 0, 'SessionType': 'Race', 'ResultsOfficial':0}]},
        'DriverInfo': {'Drivers': []}
    }
    mock_sdk._incident_timeline = {} # session_time_threshold: new_incident_count

    # Store original methods before patching if complex patching is needed.
    # For simple timeline-based value changes (SessionState, SessionFlags, CarIdxLastLapTime),
    # the MockIRSDK's freeze_var_buffer_latest and __getitem__ already handle these via
    # _session_state_timeline, _session_flags_timeline, and _car_telemetry_timeline.
    # The _incident_timeline was a specific patch for PlayerCarMyIncidentCount.
    # No further generic patching is added here unless proven necessary for new tests.

    # Ensure manager's internal connection flag reflects mock's state after setup
    manager._is_connected_flag = True
    if hasattr(mock_sdk, '_mock_data'): # Ensure mock_sdk is the MockIRSDK instance
      manager._last_player_incident_count = mock_sdk._mock_data.get('PlayerCarMyIncidentCount', 0)

    yield manager


@pytest.fixture
def replay_analyzer(
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
) -> ReplayAnalyzer:
    """Provides a ReplayAnalyzer instance initialized with mock dependencies."""
    return ReplayAnalyzer(iracing_manager=pyirsdk_manager_fixture, settings=mock_app_settings)


# --- Test Functions ---

def test_replay_analyzer_populates_session_data_xml(
    replay_analyzer: ReplayAnalyzer, # Use the combined fixture
    pyirsdk_manager_fixture: PyIrSdkManager # Still needed to configure mock SDK
):
    """
    Tests that ReplayAnalyzer correctly gets SessionInfo from PyIrSdkManager,
    converts it to XML, and stores it in OverlayData.session_data_xml.
    """
    # 1. Setup
    # Configure specific SessionInfo for this test
    mock_session_info = {
        "WeekendInfo": {"TrackName": "TestVille Speedway", "TrackWeatherType": "Sunny"},
        "DriverInfo": {"Drivers": [{"UserName": "Test Driver XML", "CarNumber": "101"}]}
    }
    pyirsdk_manager_fixture.ir_sdk._mock_data['SessionInfo'] = mock_session_info

    # analyzer = ReplayAnalyzer(iracing_manager=pyirsdk_manager_fixture, settings=mock_app_settings) # Now from fixture

    # 2. Action
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None

    loaded_overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    # 3. Assertions
    assert loaded_overlay_data.session_data_xml is not None
    assert len(loaded_overlay_data.session_data_xml) > 0

    # Parse the XML string and check content
    try:
        root = ET.fromstring(loaded_overlay_data.session_data_xml)
        assert root.tag == "SessionInfo", "Root tag of session_data_xml should be 'SessionInfo'."

        track_name_element = root.find("WeekendInfo/TrackName")
        assert track_name_element is not None, "TrackName element not found in parsed SessionInfo XML."
        assert track_name_element.text == "TestVille Speedway"

        driver_name_element = root.find("DriverInfo/Drivers/UserName") # utils.dict_to_xml creates <Drivers><UserName>...</UserName></Drivers> for list of dicts
        assert driver_name_element is not None, "Driver UserName element not found."
        assert driver_name_element.text == "Test Driver XML"

    except ET.ParseError as e:
        pytest.fail(f"Failed to parse session_data_xml: {e}\nXML Content:\n{loaded_overlay_data.session_data_xml}")


def test_replay_analyzer_processes_player_incidents(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings # For configuring durations if needed by test setup
):
    """
    Tests that ReplayAnalyzer creates 'PlayerIncident' RaceEvents based on
    changes in PlayerCarMyIncidentCount from PyIrSdkManager.
    """
    # 1. Setup
    # Configure incident timeline for the mock SDK: {session_time_threshold: new_incident_count}
    # ReplayAnalyzer checks for incidents every 2s of SessionTime. Max duration is 10s.
    # SessionTime in mock advances by ~1/60s per get_latest_data_sample call within ReplayAnalyzer's loop.
    # ReplayAnalyzer analysis_replay_speed is 1x for this test.

    # Incident 1: count becomes 2 at SessionTime >= 3.0s
    # Incident 2: count becomes 3 at SessionTime >= 7.0s
    # This test relies on the _incident_timeline, which was a direct patch in the original
    # pyirsdk_manager_fixture. If that fixture is simplified, this test might need adjustment
    # or specific configuration of the mock SDK here.
    # For now, assume _incident_timeline is still effectively patched or managed by MockIRSDK.
    # If MockIRSDK's __getitem__ or freeze_var_buffer_latest handles PlayerCarMyIncidentCount
    # via a new timeline (e.g., self.player_incident_timeline), configure that here.
    # The provided fixture still has the direct patch for PlayerCarMyIncidentCount.

    pyirsdk_manager_fixture.ir_sdk._incident_timeline = { # type: ignore[attr-defined]
        3.0: 2,
        7.0: 3
    }
    pyirsdk_manager_fixture.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 0 # type: ignore[attr-defined]
    pyirsdk_manager_fixture._last_player_incident_count = 0


    # analyzer = ReplayAnalyzer(iracing_manager=pyirsdk_manager_fixture, settings=mock_app_settings) # From fixture

    # 2. Action
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    loaded_overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    # 3. Assertions
    player_incident_events = [event for event in loaded_overlay_data.race_events if event.interest == 'PlayerIncident']

    assert len(player_incident_events) == 2, \
        f"Expected 2 PlayerIncident events, got {len(player_incident_events)}. Events: {player_incident_events}"

    # Incident 1 (2 new incidents)
    # ReplayAnalyzer's incident check is every 2s. SessionTime in mock is dynamic.
    # The first check likely happens around SessionTime 2.0-4.0.
    # The incident event's start_time is the SessionTime when get_incidents was called.
    inc1 = player_incident_events[0]
    assert inc1.interest == 'PlayerIncident'
    # Check if time is roughly around/after 3.0s (when count changed) + processing delay
    assert 3.0 <= inc1.start_time < 3.0 + pyirsdk_manager_fixture.ir_sdk._mock_data.get('SessionTime', 0) / (mock_app_settings.max_analysis_duration_seconds * 60) + 2.0 # Allow for check interval
    # This assertion for time is tricky because it depends on ReplayAnalyzer's loop speed
    # and when get_incidents is called relative to SessionTime updates.
    # A simpler check:
    assert hasattr(inc1, 'count_change'), "Incident event should have 'count_change' if generated by PyIrSdkManager"
    # This detail is not part of RaceEvent. The test should check RaceEvent fields.
    # The PyIrSdkManager creates a dict, ReplayAnalyzer converts it to RaceEvent.
    # The current ReplayAnalyzer doesn't store count_change in RaceEvent.

    # Incident 2 (1 new incident)
    inc2 = player_incident_events[1]
    assert inc2.interest == 'PlayerIncident'
    assert 7.0 <= inc2.start_time < 7.0 + pyirsdk_manager_fixture.ir_sdk._mock_data.get('SessionTime', 0) / (mock_app_settings.max_analysis_duration_seconds * 60) + 2.0

    # Verify that _last_player_incident_count in PyIrSdkManager was updated
    assert pyirsdk_manager_fixture._last_player_incident_count == 3


def test_replay_analyzer_populates_leaderboard_drivers(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager
):
    """
    Tests that ReplayAnalyzer populates LeaderBoardSnapshot.drivers using
    SessionInfo from PyIrSdkManager.
    """
    # 1. Setup
    mock_drivers_info = [
        {'CarIdx': 0, 'UserName': 'Player Test', 'CarNumber': '10'},
        {'CarIdx': 1, 'UserName': 'AI Buddy', 'CarNumber': '20'},
        {'CarIdx': 5, 'UserName': 'Another AI', 'CarNumber': '30'}
    ]
    pyirsdk_manager_fixture.ir_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = mock_drivers_info # type: ignore[attr-defined]
    pyirsdk_manager_fixture.ir_sdk._mock_data['PlayerCarIdx'] = 0 # type: ignore[attr-defined]


    # analyzer = ReplayAnalyzer(iracing_manager=pyirsdk_manager_fixture, settings=mock_app_settings) # From fixture

    # 2. Action
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    loaded_overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    # 3. Assertions
    assert loaded_overlay_data.leader_boards is not None
    assert len(loaded_overlay_data.leader_boards) > 0, "Leaderboards should have been populated."

    first_leaderboard: LeaderBoardSnapshot = loaded_overlay_data.leader_boards[0]
    assert len(first_leaderboard.drivers) == len(mock_drivers_info), \
        "Number of drivers in leaderboard should match mock SessionInfo."

    for i, driver_in_lb in enumerate(first_leaderboard.drivers):
        # Find corresponding mock_driver by car_idx as sorting might change order
        mock_driver_for_comp = next((md for md in mock_drivers_info if md['CarIdx'] == driver_in_lb.car_idx), None)
        assert mock_driver_for_comp is not None, f"Driver with CarIdx {driver_in_lb.car_idx} not found in mock_drivers_info"
        assert driver_in_lb.user_name == mock_driver_for_comp['UserName']
        assert driver_in_lb.car_number == mock_driver_for_comp['CarNumber']
        assert driver_in_lb.car_idx == mock_driver_for_comp['CarIdx']

# --- New Tests for Race Start/End Detection ---

def test_analyzer_race_start_end_checkered_flag(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests normal race start and end triggered by a checkered flag."""
    mock_app_settings.analysis_pre_roll_seconds = 2
    mock_app_settings.max_analysis_duration_seconds = 30
    # Analyzer's internal green flag scan timeout is long (180s real time, 300s session time)
    # max_analysis_duration_seconds will stop the overall analysis if green flag isn't found sooner.
    # This test expects green flag to be found.

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    mock_sdk._session_state_timeline = { # type: ignore[attr-defined]
        0.0: IRSDK_SESSION_STATE_GET_IN_CAR,
        5.0: IRSDK_SESSION_STATE_PARADE_LAPS, # Or another pre-race state
        10.0: IRSDK_SESSION_STATE_RACING,     # Green flag
        35.0: IRSDK_SESSION_STATE_COOLDOWN    # Post-race state
    }
    mock_sdk._session_flags_timeline = { # type: ignore[attr-defined]
        32.0: IRSDK_CHECKERED_FLAG
    }
    # Ensure a basic SessionInfo for driver processing
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = [{'CarIdx': 0, 'UserName': 'P0', 'CarIsPaceCar': 0}] # type: ignore[attr-defined]


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    race_start_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceStart']
    assert len(race_start_events) == 1
    assert race_start_events[0].start_time == pytest.approx(10.0, abs=0.1)

    race_end_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceEnd']
    assert len(race_end_events) == 1
    # End should be at checkered flag time, not CoolDown state time if flag is earlier
    assert race_end_events[0].start_time == pytest.approx(32.0, abs=0.1)

    assert len(overlay_data.leader_boards) > 0, "Leaderboards should have data."
    # First leaderboard entry should be around (RaceStartTime - PreRoll)
    expected_first_lb_time = 10.0 - mock_app_settings.analysis_pre_roll_seconds
    assert overlay_data.leader_boards[0].start_time == pytest.approx(expected_first_lb_time, abs=0.5) # Allow some flex due to tick rate

    # Last leaderboard entry should be around actual race end time
    # (or slightly after, as loop might do one more iteration)
    assert overlay_data.leader_boards[-1].start_time == pytest.approx(32.0, abs=1.0)


def test_analyzer_race_end_by_cooldown(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests race end triggered by CoolDown state when no checkered flag is thrown early."""
    mock_app_settings.analysis_pre_roll_seconds = 1
    mock_app_settings.max_analysis_duration_seconds = 30

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    mock_sdk._session_state_timeline = { # type: ignore[attr-defined]
        0.0: IRSDK_SESSION_STATE_GET_IN_CAR,
        8.0: IRSDK_SESSION_STATE_RACING,  # Green flag at 8.0s
        25.0: IRSDK_SESSION_STATE_COOLDOWN # Race ends due to state change
    }
    mock_sdk._session_flags_timeline = {} # No checkered flag # type: ignore[attr-defined]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = [{'CarIdx': 0, 'UserName': 'P0', 'CarIsPaceCar': 0}] # type: ignore[attr-defined]

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    race_start_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceStart']
    assert len(race_start_events) == 1
    assert race_start_events[0].start_time == pytest.approx(8.0, abs=0.1)

    race_end_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceEnd']
    assert len(race_end_events) == 1
    assert race_end_events[0].start_time == pytest.approx(25.0, abs=0.1) # End due to CoolDown

    assert len(overlay_data.leader_boards) > 0
    expected_first_lb_time = 8.0 - mock_app_settings.analysis_pre_roll_seconds
    assert overlay_data.leader_boards[0].start_time == pytest.approx(expected_first_lb_time, abs=0.5)
    assert overlay_data.leader_boards[-1].start_time == pytest.approx(25.0, abs=1.0)


def test_analyzer_race_start_not_found(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """
    Tests behavior when race start (SessionState=Racing) is not found.
    ReplayAnalyzer currently defaults to Frame 0 and continues.
    """
    mock_app_settings.analysis_pre_roll_seconds = 1
    # Set max_analysis_duration_seconds short enough that if green flag scan is very long,
    # this duration itself might limit the analysis before scan timeout.
    # ReplayAnalyzer's GREEN_FLAG_SCAN_TIMEOUT_SECONDS (internal real-time limit) is 180s.
    # The session time scan limit is 300s.
    # The overall analysis is also limited by settings.max_analysis_duration_seconds from green flag.
    # If green flag is not found, it defaults to SessionTime=0 for "green flag".
    mock_app_settings.max_analysis_duration_seconds = 5

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    mock_sdk._session_state_timeline = { # type: ignore[attr-defined]
        0.0: IRSDK_SESSION_STATE_GET_IN_CAR,
        # Never reaches IRSDK_SESSION_STATE_RACING
        20.0: IRSDK_SESSION_STATE_PARADE_LAPS # Stays in parade laps beyond analysis duration
    }
    mock_sdk._session_flags_timeline = {} # type: ignore[attr-defined]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = [{'CarIdx': 0, 'UserName': 'P0', 'CarIsPaceCar': 0}] # type: ignore[attr-defined]


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None # Analyzer currently proceeds from frame 0
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    race_start_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceStart']
    # If green flag scan fails, ReplayAnalyzer defaults to SessionTime 0.0 for race start.
    # It does not add a 'RaceStart' event in this fallback path.
    assert len(race_start_events) == 0, "No 'RaceStart' event should be generated if green flag scan fails."

    # Analysis should run from SessionTime 0 for max_analysis_duration_seconds
    # Pre-roll is from this assumed 0.0 start, so first leaderboard could be negative if pre-roll > 0,
    # but ReplayAnalyzer caps seek frame at 0.
    if overlay_data.leader_boards:
        assert overlay_data.leader_boards[0].start_time == pytest.approx(0.0, abs=0.5) # Starts from time 0
        # Last leaderboard should be around max_analysis_duration_seconds from this assumed 0.0 start
        assert overlay_data.leader_boards[-1].start_time == pytest.approx(mock_app_settings.max_analysis_duration_seconds, abs=1.0)
    else:
        # This case could happen if max_analysis_duration_seconds is extremely small, e.g. 0
        assert mock_app_settings.max_analysis_duration_seconds <= 0


def test_analyzer_max_duration_cuts_analysis(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests that max_analysis_duration_seconds correctly limits analysis time."""
    mock_app_settings.analysis_pre_roll_seconds = 1
    mock_app_settings.max_analysis_duration_seconds = 15 # Analyze for 15s after green flag

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    mock_sdk._session_state_timeline = { # type: ignore[attr-defined]
        0.0: IRSDK_SESSION_STATE_GET_IN_CAR,
        10.0: IRSDK_SESSION_STATE_RACING, # Green flag at 10.0s
        # No CoolDown or Checkered flag within the analysis window (10s to 10+15=25s)
        50.0: IRSDK_SESSION_STATE_COOLDOWN # Well after max_analysis_duration
    }
    mock_sdk._session_flags_timeline = {} # type: ignore[attr-defined]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = [{'CarIdx': 0, 'UserName': 'P0', 'CarIsPaceCar': 0}] # type: ignore[attr-defined]


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    race_start_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceStart']
    assert len(race_start_events) == 1
    assert race_start_events[0].start_time == pytest.approx(10.0, abs=0.1)

    race_end_events = [ev for ev in overlay_data.race_events if ev.interest == 'RaceEnd']
    assert len(race_end_events) == 0, "No 'RaceEnd' event should be generated by state/flag within analysis window."

    assert len(overlay_data.leader_boards) > 0
    expected_first_lb_time = 10.0 - mock_app_settings.analysis_pre_roll_seconds
    assert overlay_data.leader_boards[0].start_time == pytest.approx(expected_first_lb_time, abs=0.5)

    # Analysis should stop at approx (RaceStartTime + max_analysis_duration_seconds)
    expected_last_lb_time = 10.0 + mock_app_settings.max_analysis_duration_seconds
    assert overlay_data.leader_boards[-1].start_time == pytest.approx(expected_last_lb_time, abs=1.0)


# --- New Tests for Leaderboard Construction ---

def test_analyzer_full_leaderboard_population_and_sorting(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests basic leaderboard population, driver data, and sorting."""
    mock_app_settings.max_analysis_duration_seconds = 20 # Ensure SessionTime 15.0s is captured
    mock_app_settings.analysis_pre_roll_seconds = 0 # Simplify time for this test

    mock_sdk = pyirsdk_manager_fixture.ir_sdk

    # Configure SessionInfo for drivers
    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'CarA', 'CarNumber': '01', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'CarB', 'CarNumber': '02', 'CarIsPaceCar': 0},
        {'CarIdx': 2, 'UserName': 'CarC', 'CarNumber': '03', 'CarIsPaceCar': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]

    # Configure telemetry timeline for a specific session time
    target_session_time = 15.0
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # Ensure analysis runs # type: ignore[attr-defined]
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        target_session_time: {
            0: {'CarIdxLap': 2, 'CarIdxLapCompleted': 1, 'CarIdxLapDistPct': 0.8, 'CarIdxClassPosition': 1, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxSessionFlags': 0, 'CarIdxOnPitRoad': False, 'CarIdxBestLapTime': 90.1, 'CarIdxLastLapTime': 90.1, 'CarIdxIncidentCount': 0}, # CarA
            1: {'CarIdxLap': 2, 'CarIdxLapCompleted': 1, 'CarIdxLapDistPct': 0.7, 'CarIdxClassPosition': 2, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxSessionFlags': 0, 'CarIdxOnPitRoad': False, 'CarIdxBestLapTime': 90.5, 'CarIdxLastLapTime': 90.5, 'CarIdxIncidentCount': 0}, # CarB
            2: {'CarIdxLap': 1, 'CarIdxLapCompleted': 0, 'CarIdxLapDistPct': 0.9, 'CarIdxClassPosition': 3, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxSessionFlags': 0, 'CarIdxOnPitRoad': False, 'CarIdxBestLapTime': 91.0, 'CarIdxLastLapTime': 91.0, 'CarIdxIncidentCount': 0}  # CarC
        }
    }
    # Initialize car_analysis_states for all drivers (ReplayAnalyzer does this based on SessionInfo)
    # Also initialize last_known_car_lap_times
    for driver_info in drivers_session_info:
        car_idx = driver_info['CarIdx']
        replay_analyzer.car_analysis_states[car_idx] = {
            'last_incident_count': 0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK,
            'off_track_start_time': None, 'user_name': driver_info['UserName'],
            'is_in_pits': False, 'pit_stop_start_time': None, 'current_pit_stop_count': 0
        }
        replay_analyzer.last_known_car_lap_times[car_idx] = -1.0


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    assert len(overlay_data.leader_boards) > 0

    # Find the leaderboard snapshot at or just after target_session_time
    target_lb: Optional[LeaderBoardSnapshot] = None
    for lb in overlay_data.leader_boards:
        if lb.start_time >= target_session_time:
            target_lb = lb
            break

    assert target_lb is not None, f"No leaderboard found at or after SessionTime {target_session_time}"
    assert len(target_lb.drivers) == 3

    # Verify Sorting & Positions (CarA, CarB, CarC based on Lap, then LapDistPct)
    # Expected: CarA (Lap 2, 0.8), CarB (Lap 2, 0.7), CarC (Lap 1, 0.9)
    # Note: ReplayAnalyzer sorts by -(Lap), -(LapDistPct), ClassPos. So higher lap/dist is better.

    driver_a_data = next((d for d in target_lb.drivers if d.car_idx == 0), None)
    driver_b_data = next((d for d in target_lb.drivers if d.car_idx == 1), None)
    driver_c_data = next((d for d in target_lb.drivers if d.car_idx == 2), None)

    assert driver_a_data is not None and driver_a_data.position == 1
    assert driver_b_data is not None and driver_b_data.position == 2
    assert driver_c_data is not None and driver_c_data.position == 3

    # Verify Driver Data for CarA (idx 0)
    assert driver_a_data.user_name == 'CarA'
    assert driver_a_data.car_number == '01'
    assert driver_a_data.current_lap == 2 # Lap 2 (1 completed + 1)
    assert driver_a_data.lap_dist_pct == pytest.approx(0.8)
    assert driver_a_data.class_position == 1 # This is from CarIdxClassPosition, not the calculated .position
    assert driver_a_data.status == 'OnTrack'
    # Personal best and last lap times are now handled by fastest lap logic, check those are passed through
    # Based on current setup, these would be from the timeline if a new lap was detected by that logic.
    # For this specific test, we are checking values directly from telemetry for the snapshot.
    # ReplayAnalyzer's fastest lap logic updates `driver_personal_best_laps` and `last_known_car_lap_times`.
    # The driver object in leaderboard gets `best_lap_time` from `driver_personal_best_laps`
    # and `last_lap_time` from `last_known_car_lap_times`.
    # If no "new lap" was triggered by timeline for CarA at 15.0s, its last_lap_time in LB might be None or previous.
    # Let's assume for this test that the values in timeline are "fresh" and should be reflected if logic allows.
    # The simplified "new lap" detection in ReplayAnalyzer uses:
    # `abs(current_car_last_lap_time - self.last_known_car_lap_times.get(car_idx_val, -1.0)) > 0.001`
    # So, if CarIdxLastLapTime in timeline is different from -1.0 (initial), it will be processed.
    assert driver_a_data.best_lap_time == pytest.approx(90.1) # Set via timeline and processed by fastest lap logic
    assert driver_a_data.last_lap_time == pytest.approx(90.1)


def test_analyzer_leaderboard_filters_pace_car(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests that pace cars are filtered out of the leaderboard."""
    mock_app_settings.max_analysis_duration_seconds = 5
    mock_sdk = pyirsdk_manager_fixture.ir_sdk

    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'Driver 1', 'CarNumber': '11', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'Pace Car', 'CarNumber': 'PC1', 'CarIsPaceCar': 1}, # This is a pace car
        {'CarIdx': 2, 'UserName': 'Driver 2', 'CarNumber': '22', 'CarIsPaceCar': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    # Provide minimal telemetry for all cars, including pace car
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        1.0: {
            0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.1, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
            1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.2, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}, # Pace Car Telemetry
            2: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.3, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
        }
    }
    for driver_info in drivers_session_info: # Initialize states
        replay_analyzer.car_analysis_states[driver_info['CarIdx']] = {'user_name': driver_info['UserName'], 'current_pit_stop_count': 0, 'is_in_pits': False, 'pit_stop_start_time': None}


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    assert len(overlay_data.leader_boards) > 0
    target_lb = overlay_data.leader_boards[0] # Check the first available leaderboard

    assert len(target_lb.drivers) == 2, "Pace car should be filtered out."
    car_indices_in_leaderboard = {d.car_idx for d in target_lb.drivers}
    assert 0 in car_indices_in_leaderboard
    assert 2 in car_indices_in_leaderboard
    assert 1 not in car_indices_in_leaderboard # Pace car (idx 1) should not be present


def test_analyzer_leaderboard_handles_missing_telemetry(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests robustness when some telemetry data for a driver is missing or invalid."""
    mock_app_settings.max_analysis_duration_seconds = 5
    mock_sdk = pyirsdk_manager_fixture.ir_sdk

    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'Driver A', 'CarNumber': 'DA', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'Driver B', 'CarNumber': 'DB', 'CarIsPaceCar': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Telemetry: Driver A is fine, Driver B has invalid LapDistPct
    target_time = 2.0
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        target_time: {
            0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.5, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxClassPosition': 1},
            1: {'CarIdxLap': 1, 'CarIdxLapDistPct': -1.0, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxClassPosition': 2} # Invalid LapDistPct
        }
    }
    for driver_info in drivers_session_info: # Initialize states
        replay_analyzer.car_analysis_states[driver_info['CarIdx']] = {'user_name': driver_info['UserName'], 'current_pit_stop_count': 0, 'is_in_pits': False, 'pit_stop_start_time': None}


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None # Analysis should not crash
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    assert len(overlay_data.leader_boards) > 0
    target_lb: Optional[LeaderBoardSnapshot] = None
    for lb in overlay_data.leader_boards:
        if lb.start_time >= target_time:
            target_lb = lb
            break

    assert target_lb is not None
    assert len(target_lb.drivers) == 2

    driver_b_data = next((d for d in target_lb.drivers if d.car_idx == 1), None)
    assert driver_b_data is not None
    assert driver_b_data.lap_dist_pct == -1.0 # Should reflect the invalid data
    # Driver B should likely be sorted last due to invalid lap_dist_pct if on same lap
    assert driver_b_data.position == 2


def test_analyzer_leaderboard_updates_driver_status(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests that driver.status is correctly updated in leaderboards."""
    mock_app_settings.max_analysis_duration_seconds = 10
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_OFF_TRACK, IRSDK_TRK_LOC_IN_PIT_STALL

    drivers_session_info = [{'CarIdx': 0, 'UserName': 'TestDriver', 'CarNumber': '00', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Timeline for Driver 0 status changes
    time_on_track = 2.0
    time_enter_pits = 4.0 # Enters pit stall directly
    time_off_track = 6.0

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        time_on_track:   {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
        time_enter_pits: {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL, 'CarIdxOnPitRoad': True}}, # Implies OnPitRoad is true too
        time_off_track:  {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK, 'CarIdxOnPitRoad': False}},
    }
    replay_analyzer.car_analysis_states[0] = {'user_name': 'TestDriver', 'current_pit_stop_count': 0, 'is_in_pits': False, 'pit_stop_start_time': None}


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    assert len(overlay_data.leader_boards) > 0

    status_checks = {
        time_on_track: 'OnTrack',
        time_enter_pits: 'InPits',
        time_off_track: 'OffTrack',
    }

    for session_t, expected_status in status_checks.items():
        target_lb: Optional[LeaderBoardSnapshot] = None
        for lb in overlay_data.leader_boards:
            if lb.start_time >= session_t: # Find first LB at or after the event time
                target_lb = lb
                break

        assert target_lb is not None, f"No leaderboard found for SessionTime >= {session_t}"
        driver_data = next((d for d in target_lb.drivers if d.car_idx == 0), None)
        assert driver_data is not None, f"Driver 0 not found in leaderboard at SessionTime {target_lb.start_time}"
        assert driver_data.status == expected_status, \
            f"Driver status at SessionTime {target_lb.start_time} was '{driver_data.status}', expected '{expected_status}'"


# --- New Tests for Per-Car Incident Detection ---

def test_analyzer_detects_incident_points_for_multiple_cars(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests detection of incident points for multiple cars based on CarIdxIncidentCount."""
    mock_app_settings.max_analysis_duration_seconds = 20 # Ensure all incident times are covered
    mock_app_settings.analysis_pre_roll_seconds = 0

    mock_sdk = pyirsdk_manager_fixture.ir_sdk

    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'Car0', 'CarNumber': 'C0', 'CarIsPaceCar': 0, 'InitIncidents': 0},
        {'CarIdx': 1, 'UserName': 'Car1', 'CarNumber': 'C1', 'CarIsPaceCar': 0, 'InitIncidents': 0},
        {'CarIdx': 2, 'UserName': 'Car2', 'CarNumber': 'C2', 'CarIsPaceCar': 0, 'InitIncidents': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Initialize car_analysis_states and last_known_car_lap_times for ReplayAnalyzer
    # This is crucial because ReplayAnalyzer initializes these based on SessionInfo at its start.
    # For incident points, 'last_incident_count' is key.
    for driver_info in drivers_session_info:
        car_idx = driver_info['CarIdx']
        replay_analyzer.car_analysis_states[car_idx] = {
            'last_incident_count': 0, # Start with 0 known incidents for the test
            'last_track_surface': IRSDK_TRK_LOC_ON_TRACK,
            'off_track_start_time': None, 'user_name': driver_info['UserName'],
            'is_in_pits': False, 'pit_stop_start_time': None, 'current_pit_stop_count': 0
        }
        # Other initializations if necessary for other parts of analyzer...
        replay_analyzer.last_known_car_lap_times[car_idx] = -1.0


    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: {0: {'CarIdxIncidentCount': 2}}, # Car0: 0 -> 2 incidents
        12.0: {1: {'CarIdxIncidentCount': 1}}, # Car1: 0 -> 1 incident
        15.0: {1: {'CarIdxIncidentCount': 3}}, # Car1: 1 -> 3 incidents (2 new)
        # Car2 IncidentCount remains default (0 from mock_data init, or needs explicit 0 if that changes)
    }
    # Ensure Car2's incident count is part of the telemetry data stream, even if 0,
    # or ensure the mock SDK provides default 0 for unspecified cars in a timeline tick.
    # Current MockIRSDK behavior: if a car_idx is not in timeline for a tick, its values don't change from previous state.
    # And PyIrSdkManager's get_latest_data_sample initializes CarIdxIncidentCount with an array of zeros.
    # So, Car2 should remain at 0 if not in timeline.

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    incident_point_events = [ev for ev in overlay_data.race_events if ev.interest == 'Incident_Points']

    # Expected: 1 event for Car0 (0->2), 2 events for Car1 (0->1, then 1->3)
    assert len(incident_point_events) == 3, f"Expected 3 Incident_Points events, got {len(incident_point_events)}"

    car0_events = [ev for ev in incident_point_events if ev.car_idx == 0]
    assert len(car0_events) == 1
    assert car0_events[0].start_time == pytest.approx(10.0, abs=0.5)
    assert "0->2" in car0_events[0].details # Details format: "Incident points: CarX changed 0->2"

    car1_events = [ev for ev in incident_point_events if ev.car_idx == 1]
    assert len(car1_events) == 2
    assert car1_events[0].start_time == pytest.approx(12.0, abs=0.5)
    assert "0->1" in car1_events[0].details
    assert car1_events[1].start_time == pytest.approx(15.0, abs=0.5)
    assert "1->3" in car1_events[1].details

    car2_events = [ev for ev in incident_point_events if ev.car_idx == 2]
    assert len(car2_events) == 0, "Car2 should have no incident point events."


def test_analyzer_detects_off_track_incidents(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests off-track incident detection, respecting min_off_track_duration_for_event."""
    mock_app_settings.min_off_track_duration_for_event = 2.0
    mock_app_settings.max_analysis_duration_seconds = 25 # Cover all event times

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    # Import IRSDK_TRK_LOC_OFF_TRACK if not globally available in test file
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_OFF_TRACK

    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'Car0_OffTrackYes', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'Car1_OffTrackNoShort', 'CarIsPaceCar': 0},
        {'CarIdx': 2, 'UserName': 'Car2_StaysOnTrack', 'CarIsPaceCar': 0},
        {'CarIdx': 3, 'UserName': 'Car3_OffTrackEndsSim', 'CarIsPaceCar': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Initialize car_analysis_states
    for driver_info in drivers_session_info:
        car_idx = driver_info['CarIdx']
        replay_analyzer.car_analysis_states[car_idx] = {
            'last_incident_count': 0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK,
            'off_track_start_time': None, 'user_name': driver_info['UserName'],
            'is_in_pits': False, 'pit_stop_start_time': None, 'current_pit_stop_count': 0
        }

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        # Car0: Off-track for 3s (5s to 8s) -> Event
        5.0:  {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK}},
        8.0:  {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}},
        # Car1: Off-track for 1s (10s to 11s) -> No Event (duration < min_off_track_duration_for_event)
        10.0: {1: {'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK}},
        11.0: {1: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}},
        # Car2: Stays OnTrack (no entries needed if default is OnTrack, or explicit OnTrack)
        # Car3: Off-track at 15s, analysis ends at 20s while still off-track -> No Event
        15.0: {3: {'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    off_track_events = [ev for ev in overlay_data.race_events if ev.interest == 'Incident_OffTrack']

    assert len(off_track_events) == 1, f"Expected 1 Incident_OffTrack event, got {len(off_track_events)}"

    event_car0 = off_track_events[0]
    assert event_car0.car_idx == 0
    assert event_car0.start_time == pytest.approx(5.0, abs=0.1)
    assert event_car0.end_time == pytest.approx(8.0, abs=0.1)
    assert "Duration: 3.0" in event_car0.details # Details format: "Off-track: CarX for Xs"


def test_analyzer_off_track_active_at_analysis_end(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests that an off-track state active at the end of analysis does not generate an event."""
    mock_app_settings.min_off_track_duration_for_event = 1.0 # Short duration
    mock_app_settings.max_analysis_duration_seconds = 10 # Analysis ends at SessionTime 10s

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_OFF_TRACK

    drivers_session_info = [{'CarIdx': 0, 'UserName': 'Car0_StillOffTrack', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    replay_analyzer.car_analysis_states[0] = { # Initialize state for Car0
        'last_incident_count': 0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK,
        'off_track_start_time': None, 'user_name': 'Car0_StillOffTrack',
        'is_in_pits': False, 'pit_stop_start_time': None, 'current_pit_stop_count': 0
    }

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        5.0: {0: {'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK}}, # Goes off-track at 5s
        # Stays off-track until analysis ends at 10s
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    off_track_events = [ev for ev in overlay_data.race_events if ev.interest == 'Incident_OffTrack']

    assert len(off_track_events) == 0, \
        f"Expected 0 Incident_OffTrack events if car still off-track at analysis end, got {len(off_track_events)}"


# --- New Tests for Battle and Overtake Detection ---

def test_analyzer_detects_battle(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests detection of a sustained battle."""
    mock_app_settings.min_battle_duration_seconds = 3.0
    mock_app_settings.battle_proximity_threshold_pct = 0.005 # 0.5%
    mock_app_settings.max_analysis_duration_seconds = 25

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0},
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Initialize car_analysis_states for ReplayAnalyzer
    for driver in drivers_session_info:
        replay_analyzer.car_analysis_states[driver['CarIdx']] = {
            'user_name': driver['UserName'], 'current_pit_stop_count': 0, 'is_in_pits': False,
            'pit_stop_start_time': None, 'last_incident_count': 0,
            'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None
        }
        replay_analyzer.previous_tick_driver_data[driver['CarIdx']] = {}


    # Cars are close from 10s to 20s (10s duration)
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        9.9:  { # Ensure they are on the same lap just before battle starts
            0: {'CarIdxLap': 1, 'CarIdxLapCompleted': 0, 'CarIdxLapDistPct': 0.490, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
            1: {'CarIdxLap': 1, 'CarIdxLapCompleted': 0, 'CarIdxLapDistPct': 0.495, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
        },
        10.0: { # Battle starts
            0: {'CarIdxLapDistPct': 0.500},
            1: {'CarIdxLapDistPct': 0.5005}, # Difference is 0.0005 (0.05%)
        },
        15.0: { # Still in battle
            0: {'CarIdxLapDistPct': 0.600},
            1: {'CarIdxLapDistPct': 0.6003},
        },
        20.0: { # Still in battle - battle ends here as per this tick
            0: {'CarIdxLapDistPct': 0.700},
            1: {'CarIdxLapDistPct': 0.7004},
        },
        20.1: { # Cars separate slightly after 20.0s, battle should have ended at 20.0
            0: {'CarIdxLapDistPct': 0.710},
            1: {'CarIdxLapDistPct': 0.712}, # Difference 0.002 (0.2%) still within proximity for this tick
                                        # but the active_battle should be popped if proximity increases beyond threshold
        }
    }
    # To ensure battle finalizes at 20.0, the next tick (20.1) should show them separated OR loop ends.
    # The logic finalizes active battles after loop.
    # Let's ensure they are far apart at a later tick to clearly end it if loop continues.
    mock_sdk._car_telemetry_timeline[22.0] = {0: {'CarIdxLapDistPct': 0.800}, 1: {'CarIdxLapDistPct': 0.810}}


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    battle_events = [ev for ev in overlay_data.race_events if ev.interest == 'Battle']
    assert len(battle_events) == 1
    battle = battle_events[0]
    assert battle.start_time == pytest.approx(10.0, abs=0.1)
    assert battle.end_time == pytest.approx(20.0, abs=0.1) # Ends when they were last close or separated
    assert sorted((battle.car_idx, battle.other_car_idx)) == [0, 1]


def test_analyzer_battle_not_long_enough(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.min_battle_duration_seconds = 5.0
    mock_app_settings.battle_proximity_threshold_pct = 0.005
    mock_app_settings.max_analysis_duration_seconds = 15

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [
        {'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for driver in drivers_session_info: # Init states
        replay_analyzer.car_analysis_states[driver['CarIdx']] = {'user_name': driver['UserName'], 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
        replay_analyzer.previous_tick_driver_data[driver['CarIdx']] = {}


    # Close from 10s to 12s (2s duration), min_battle_duration is 5s
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: {0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.500, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}, 1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.5005, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}},
        12.0: {0: {'CarIdxLapDistPct': 0.520}, 1: {'CarIdxLapDistPct': 0.5205}}, # Still close
        12.1: {0: {'CarIdxLapDistPct': 0.550}, 1: {'CarIdxLapDistPct': 0.560}}, # Separated
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    battle_events = [ev for ev in overlay_data.race_events if ev.interest == 'Battle']
    assert len(battle_events) == 0


def test_analyzer_battle_ends_by_separation(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.min_battle_duration_seconds = 2.0
    mock_app_settings.battle_proximity_threshold_pct = 0.005
    mock_app_settings.max_analysis_duration_seconds = 15

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for driver in drivers_session_info: # Init states
        replay_analyzer.car_analysis_states[driver['CarIdx']] = {'user_name': driver['UserName'], 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
        replay_analyzer.previous_tick_driver_data[driver['CarIdx']] = {}

    # Battle from 5s to 8s, then separate at 8.1s
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        5.0: {0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.300, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}, 1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.3004, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}},
        8.0: {0: {'CarIdxLapDistPct': 0.330}, 1: {'CarIdxLapDistPct': 0.3303}}, # Still close
        8.1: {0: {'CarIdxLapDistPct': 0.340}, 1: {'CarIdxLapDistPct': 0.350}}, # Separated (0.01 diff > 0.005)
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    battle_events = [ev for ev in overlay_data.race_events if ev.interest == 'Battle']
    assert len(battle_events) == 1
    assert battle_events[0].start_time == pytest.approx(5.0, abs=0.1)
    assert battle_events[0].end_time == pytest.approx(8.0, abs=0.1) # Ends when they were last close


def test_analyzer_battle_ends_by_off_track(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.min_battle_duration_seconds = 2.0
    mock_app_settings.battle_proximity_threshold_pct = 0.005
    mock_app_settings.max_analysis_duration_seconds = 15
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_OFF_TRACK

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for driver in drivers_session_info: # Init states
        replay_analyzer.car_analysis_states[driver['CarIdx']] = {'user_name': driver['UserName'], 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
        replay_analyzer.previous_tick_driver_data[driver['CarIdx']] = {}

    # Battle from 5s to 8s, then CarB goes off-track at 8.0s
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        5.0:  {0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.300, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}, 1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.3004, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}},
        7.9:  {0: {'CarIdxLapDistPct': 0.320}, 1: {'CarIdxLapDistPct': 0.3203, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}}, # Still close and on track
        8.0:  {0: {'CarIdxLapDistPct': 0.330}, 1: {'CarIdxLapDistPct': 0.3303, 'CarIdxTrackSurface': IRSDK_TRK_LOC_OFF_TRACK}}, # CarB goes off-track
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    battle_events = [ev for ev in overlay_data.race_events if ev.interest == 'Battle']
    assert len(battle_events) == 1
    assert battle_events[0].start_time == pytest.approx(5.0, abs=0.1)
    # Battle ends at 7.9 (last moment both were on track and close).
    # When CarB goes off-track at 8.0, it's no longer eligible for battle continuation for that tick.
    assert battle_events[0].end_time == pytest.approx(7.9, abs=0.1)


def test_analyzer_detects_overtake(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.overtake_proximity_threshold_pct = 0.002 # 0.2%
    mock_app_settings.max_analysis_duration_seconds = 15

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for car_idx_val in [0,1]: # Init states
        replay_analyzer.car_analysis_states[car_idx_val] = {'user_name': f'Car{chr(65+car_idx_val)}', 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
        replay_analyzer.previous_tick_driver_data[car_idx_val] = {'lap_dist_pct': 0.0, 'current_lap': 1, 'session_time': 9.9}


    # At 10.0s: CarA (0.500) behind CarB (0.5005) - diff 0.0005 (0.05%) < 0.2%
    # At 11.0s: CarA (0.501) ahead of CarB (0.5005) - CarA overtook CarB
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: {
            0: {'CarIdxLap': 1, 'CarIdxLapCompleted': 0, 'CarIdxLapDistPct': 0.5000, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
            1: {'CarIdxLap': 1, 'CarIdxLapCompleted': 0, 'CarIdxLapDistPct': 0.5005, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}
        },
        11.0: { # Overtake happens here
            0: {'CarIdxLapDistPct': 0.5010}, # CarA now ahead
            1: {'CarIdxLapDistPct': 0.5005}  # CarB position unchanged relative to S/F, but now behind CarA
        },
    }
    # Prime previous_tick_driver_data for the 10.0s tick
    replay_analyzer.previous_tick_driver_data[0] = {'lap_dist_pct': 0.490, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarA'}
    replay_analyzer.previous_tick_driver_data[1] = {'lap_dist_pct': 0.495, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarB'}


    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    overtake_events = [ev for ev in overlay_data.race_events if ev.interest == 'Overtake']

    assert len(overtake_events) == 1
    overtake = overtake_events[0]
    assert overtake.car_idx == 0 # CarA is the overtaker
    assert overtake.other_car_idx == 1 # CarB was overtaken
    assert overtake.start_time == pytest.approx(11.0 - 0.25, abs=0.1) # Overtake event time is current_session_time
    assert overtake.end_time == pytest.approx(11.0 + 0.25, abs=0.1)


def test_analyzer_no_overtake_if_too_far(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.overtake_proximity_threshold_pct = 0.002 # 0.2%
    mock_app_settings.max_analysis_duration_seconds = 15
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    # ... (setup drivers, session state, car_analysis_states, previous_tick_driver_data as in test_analyzer_detects_overtake)
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for car_idx_val in [0,1]: # Init states
        replay_analyzer.car_analysis_states[car_idx_val] = {'user_name': f'Car{chr(65+car_idx_val)}', 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
    replay_analyzer.previous_tick_driver_data[0] = {'lap_dist_pct': 0.400, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarA'}
    replay_analyzer.previous_tick_driver_data[1] = {'lap_dist_pct': 0.410, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarB'}


    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: { # Cars swap positions but are too far (0.01 diff > 0.002)
            0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.510, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
            1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.500, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}
        }
    }
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    overtake_events = [ev for ev in overlay_data.race_events if ev.interest == 'Overtake']
    assert len(overtake_events) == 0


def test_analyzer_no_overtake_if_no_position_change(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.overtake_proximity_threshold_pct = 0.002
    mock_app_settings.max_analysis_duration_seconds = 15
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for car_idx_val in [0,1]: # Init states
        replay_analyzer.car_analysis_states[car_idx_val] = {'user_name': f'Car{chr(65+car_idx_val)}', 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
    replay_analyzer.previous_tick_driver_data[0] = {'lap_dist_pct': 0.5000, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarA'}
    replay_analyzer.previous_tick_driver_data[1] = {'lap_dist_pct': 0.5005, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarB'}


    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: { # Cars are close but maintain order
            0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.5010, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK},
            1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.5015, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}
        }
    }
    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    overtake_events = [ev for ev in overlay_data.race_events if ev.interest == 'Overtake']
    assert len(overtake_events) == 0


def test_analyzer_overtake_debounce(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.overtake_proximity_threshold_pct = 0.002
    mock_app_settings.max_analysis_duration_seconds = 15
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    drivers_session_info = [{'CarIdx': 0, 'UserName': 'CarA', 'CarIsPaceCar': 0}, {'CarIdx': 1, 'UserName': 'CarB', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for car_idx_val in [0,1]: # Init states
        replay_analyzer.car_analysis_states[car_idx_val] = {'user_name': f'Car{chr(65+car_idx_val)}', 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0}
    # Initialize previous_tick_driver_data to set up the first overtake check
    replay_analyzer.previous_tick_driver_data[0] = {'lap_dist_pct': 0.4900, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarA'}
    replay_analyzer.previous_tick_driver_data[1] = {'lap_dist_pct': 0.4905, 'current_lap': 1, 'session_time': 9.9, 'user_name':'CarB'}


    # Overtake at 10.0s (A overtakes B)
    # B retakes at 10.2s (within 1s debounce)
    # A retakes again at 10.4s (still within 1s of first overtake)
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: {0: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.500, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}, 1: {'CarIdxLap': 1, 'CarIdxLapDistPct': 0.499, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK}}, # A overtakes B
        10.2: {0: {'CarIdxLapDistPct': 0.500}, 1: {'CarIdxLapDistPct': 0.501}}, # B overtakes A
        10.4: {0: {'CarIdxLapDistPct': 0.502}, 1: {'CarIdxLapDistPct': 0.501}}, # A overtakes B
        11.5: {0: {'CarIdxLapDistPct': 0.502}, 1: {'CarIdxLapDistPct': 0.503}}, # B overtakes A again (this one should count as it's >1s after the first one at 10.0)
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    overtake_events = sorted([ev for ev in overlay_data.race_events if ev.interest == 'Overtake'], key=lambda x: x.start_time)

    assert len(overtake_events) == 2, f"Expected 2 overtake events due to debounce, got {len(overtake_events)}"

    assert overtake_events[0].car_idx == 0 # A overtook B
    assert overtake_events[0].other_car_idx == 1
    assert overtake_events[0].start_time == pytest.approx(10.0 - 0.25, abs=0.1)

    assert overtake_events[1].car_idx == 1 # B overtook A
    assert overtake_events[1].other_car_idx == 0
    assert overtake_events[1].start_time == pytest.approx(11.5 - 0.25, abs=0.1)


# --- New Tests for Pit Stop Detection ---

def test_analyzer_detects_full_pit_stop_sequence(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests detection of a complete pit stop sequence."""
    mock_app_settings.max_analysis_duration_seconds = 25
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_ON_PIT_ROAD, IRSDK_TRK_LOC_IN_PIT_STALL

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    driver_car_idx = 0
    drivers_session_info = [{'CarIdx': driver_car_idx, 'UserName': 'CarA_Pitter', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Initialize car_analysis_states for the pitter
    replay_analyzer.car_analysis_states[driver_car_idx] = {
        'user_name': 'CarA_Pitter', 'current_pit_stop_count': 0, 'is_in_pits': False,
        'pit_stop_start_time': None, 'last_incident_count': 0,
        'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None
    }
    replay_analyzer.previous_tick_driver_data[driver_car_idx] = {}


    # Pit Stop Sequence for CarA (idx 0)
    # OnTrack -> OnPitRoad (Entry at 5.0s) -> InPitStall (at 6.0s) -> OnPitRoad (Exit stall at 10.0s) -> OnTrack (Exit pit lane at 11.0s)
    entry_pit_road_time = 5.0
    enter_stall_time = 6.0
    exit_stall_time = 10.0
    exit_pit_lane_time = 11.0

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        entry_pit_road_time - 0.1: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
        entry_pit_road_time:       {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}},
        enter_stall_time:          {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL, 'CarIdxOnPitRoad': True}},
        exit_stall_time:           {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}},
        exit_pit_lane_time:        {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    pit_stop_events = [ev for ev in overlay_data.race_events if ev.interest == 'PitStop']
    assert len(pit_stop_events) == 1
    pit_event = pit_stop_events[0]

    assert pit_event.car_idx == driver_car_idx
    assert pit_event.start_time == pytest.approx(entry_pit_road_time, abs=0.1)
    assert pit_event.end_time == pytest.approx(exit_pit_lane_time, abs=0.1)
    assert "Pit stop #1" in pit_event.details

    # Verify leaderboard status and pit count
    lb_before_stop: Optional[LeaderBoardSnapshot] = next((lb for lb in overlay_data.leader_boards if lb.start_time < entry_pit_road_time), None)
    lb_in_stall: Optional[LeaderBoardSnapshot] = next((lb for lb in overlay_data.leader_boards if lb.start_time >= enter_stall_time and lb.start_time < exit_stall_time), None)
    lb_after_stop: Optional[LeaderBoardSnapshot] = next((lb for lb in overlay_data.leader_boards if lb.start_time >= exit_pit_lane_time), None)

    if lb_before_stop: # Might not exist if analysis starts too close to pit stop
        driver_state_before = next((d for d in lb_before_stop.drivers if d.car_idx == driver_car_idx), None)
        if driver_state_before:
            assert driver_state_before.pit_stop_count == 0
            assert driver_state_before.status == 'OnTrack'

    assert lb_in_stall is not None
    driver_state_in_stall = next((d for d in lb_in_stall.drivers if d.car_idx == driver_car_idx), None)
    assert driver_state_in_stall is not None
    assert driver_state_in_stall.pit_stop_count == 1
    assert driver_state_in_stall.status == 'InPits'

    assert lb_after_stop is not None
    driver_state_after = next((d for d in lb_after_stop.drivers if d.car_idx == driver_car_idx), None)
    assert driver_state_after is not None
    assert driver_state_after.pit_stop_count == 1
    assert driver_state_after.status == 'OnTrack'


def test_analyzer_handles_multiple_pit_stops_for_single_car(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 40
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_ON_PIT_ROAD, IRSDK_TRK_LOC_IN_PIT_STALL
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    driver_car_idx = 0
    # ... (similar setup as above for driver info and initial states) ...
    drivers_session_info = [{'CarIdx': driver_car_idx, 'UserName': 'CarA_MultiPitter', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    replay_analyzer.car_analysis_states[driver_car_idx] = {'user_name': 'CarA_MultiPitter','current_pit_stop_count': 0,'is_in_pits': False,'pit_stop_start_time': None,'last_incident_count':0, 'last_track_surface':IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
    replay_analyzer.previous_tick_driver_data[driver_car_idx] = {}


    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        # Stop 1
        5.0:  {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}},
        6.0:  {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL}},
        10.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD}},
        11.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
        # On track segment
        15.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
        # Stop 2
        20.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}},
        21.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL}},
        25.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD}},
        26.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    pit_stop_events = [ev for ev in overlay_data.race_events if ev.interest == 'PitStop']

    assert len(pit_stop_events) == 2
    assert "Pit stop #1" in pit_stop_events[0].details
    assert pit_stop_events[0].start_time == pytest.approx(5.0, abs=0.1)
    assert pit_stop_events[0].end_time == pytest.approx(11.0, abs=0.1)
    assert "Pit stop #2" in pit_stop_events[1].details
    assert pit_stop_events[1].start_time == pytest.approx(20.0, abs=0.1)
    assert pit_stop_events[1].end_time == pytest.approx(26.0, abs=0.1)

    lb_after_stop2: Optional[LeaderBoardSnapshot] = next((lb for lb in overlay_data.leader_boards if lb.start_time >= 26.0), None)
    assert lb_after_stop2 is not None
    driver_state_after2 = next((d for d in lb_after_stop2.drivers if d.car_idx == driver_car_idx), None)
    assert driver_state_after2 is not None
    assert driver_state_after2.pit_stop_count == 2


def test_analyzer_detects_drive_through_as_pit_event(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 20
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_ON_PIT_ROAD
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    driver_car_idx = 0
    # ... (similar setup for driver info, initial states) ...
    drivers_session_info = [{'CarIdx': driver_car_idx, 'UserName': 'CarA_DriveThru', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    replay_analyzer.car_analysis_states[driver_car_idx] = {'user_name': 'CarA_DriveThru','current_pit_stop_count': 0,'is_in_pits': False,'pit_stop_start_time': None,'last_incident_count':0, 'last_track_surface':IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
    replay_analyzer.previous_tick_driver_data[driver_car_idx] = {}

    # Drive-through: OnTrack -> OnPitRoad (5.0s) -> OnPitRoad (stays, e.g. at 8.0s) -> OnTrack (10.0s)
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        5.0:  {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}},
        8.0:  {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD, 'CarIdxOnPitRoad': True}}, # Still on pit road, not in stall
        10.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK, 'CarIdxOnPitRoad': False}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    pit_stop_events = [ev for ev in overlay_data.race_events if ev.interest == 'PitStop']

    assert len(pit_stop_events) == 1
    pit_event = pit_stop_events[0]
    assert pit_event.start_time == pytest.approx(5.0, abs=0.1)
    assert pit_event.end_time == pytest.approx(10.0, abs=0.1)
    assert "Pit stop #1" in pit_event.details

    lb_on_pit_road: Optional[LeaderBoardSnapshot] = next((lb for lb in overlay_data.leader_boards if lb.start_time >= 8.0 and lb.start_time < 10.0), None)
    assert lb_on_pit_road is not None
    driver_state_on_pit_road = next((d for d in lb_on_pit_road.drivers if d.car_idx == driver_car_idx), None)
    assert driver_state_on_pit_road is not None
    assert driver_state_on_pit_road.status == 'InPits' # Current logic: OnPitRoad is InPits
    assert driver_state_on_pit_road.pit_stop_count == 1


def test_analyzer_handles_analysis_end_while_car_in_pits(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 10 # Analysis ends at 10s
    from iracing_telemetry_analyzer_py.src.pyirsdk_manager import IRSDK_TRK_LOC_IN_PIT_STALL
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    driver_car_idx = 0
    # ... (similar setup for driver info, initial states) ...
    drivers_session_info = [{'CarIdx': driver_car_idx, 'UserName': 'CarA_InPitsEnd', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    replay_analyzer.car_analysis_states[driver_car_idx] = {'user_name': 'CarA_InPitsEnd','current_pit_stop_count': 0,'is_in_pits': False,'pit_stop_start_time': None,'last_incident_count':0, 'last_track_surface':IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
    replay_analyzer.previous_tick_driver_data[driver_car_idx] = {}


    # Car enters pit stall at 5.0s, analysis ends at 10.0s while car is still there
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        5.0: {driver_car_idx: {'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL, 'CarIdxOnPitRoad': True}},
        # No further updates, car remains in stall
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)
    pit_stop_events = [ev for ev in overlay_data.race_events if ev.interest == 'PitStop']

    assert len(pit_stop_events) == 0 # No event because car did not exit pit area

    # Check final leaderboard state
    assert len(overlay_data.leader_boards) > 0
    last_lb = overlay_data.leader_boards[-1]
    driver_state_final = next((d for d in last_lb.drivers if d.car_idx == driver_car_idx), None)
    assert driver_state_final is not None
    assert driver_state_final.pit_stop_count == 1 # Pit entry was detected
    assert driver_state_final.status == 'InPits' # Still in pits at end of analysis


# --- New Tests for Fastest Lap Detection ---

def test_analyzer_fastest_lap_initial_and_pb(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests initial session fastest lap and personal best from a single lap."""
    mock_app_settings.max_analysis_duration_seconds = 15
    mock_app_settings.fastest_lap_event_duration_seconds = 5.0 # From app_settings

    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    car_a_idx = 0
    drivers_session_info = [{'CarIdx': car_a_idx, 'UserName': 'CarA', 'CarNumber': '1', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]

    # Initialize ReplayAnalyzer's states for CarA
    replay_analyzer.driver_personal_best_laps = {}
    replay_analyzer.overall_fastest_lap_time = None
    replay_analyzer.car_analysis_states[car_a_idx] = {
        'user_name': 'CarA', 'last_known_car_lap_times': -1.0, # Needs to be different from upcoming lap time
        'current_pit_stop_count': 0, 'is_in_pits': False, 'pit_stop_start_time': None,
        'last_incident_count': 0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None
    }
    replay_analyzer.last_known_car_lap_times[car_a_idx] = -1.0 # Ensure first lap is processed


    lap_time_t1 = 90.0
    session_time_t1 = 10.0
    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        session_time_t1: {
            car_a_idx: {'CarIdxLastLapTime': lap_time_t1, 'CarIdxLapCompleted': 1} # Completes lap 1
        }
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    session_fl_events = [ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_Session']
    pb_fl_events = [ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_DriverPB']

    assert len(session_fl_events) == 1
    assert session_fl_events[0].car_idx == car_a_idx
    assert f"{lap_time_t1:.3f}s" in session_fl_events[0].details
    assert session_fl_events[0].start_time == pytest.approx(session_time_t1)

    assert len(pb_fl_events) == 1
    assert pb_fl_events[0].car_idx == car_a_idx
    assert f"{lap_time_t1:.3f}s" in pb_fl_events[0].details
    assert pb_fl_events[0].start_time == pytest.approx(session_time_t1)

    assert len(overlay_data.fastest_laps) == 1
    assert overlay_data.fastest_laps[0].lap_time == pytest.approx(lap_time_t1)
    assert overlay_data.fastest_laps[0].driver.car_idx == car_a_idx

    lb_after_t1 = next((lb for lb in overlay_data.leader_boards if lb.start_time >= session_time_t1), None)
    assert lb_after_t1 is not None
    driver_a_lb_data = next((d for d in lb_after_t1.drivers if d.car_idx == car_a_idx), None)
    assert driver_a_lb_data is not None
    assert driver_a_lb_data.best_lap_time == pytest.approx(lap_time_t1)
    assert driver_a_lb_data.last_lap_time == pytest.approx(lap_time_t1)


def test_analyzer_fastest_lap_new_session_best(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 25
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    # ... (setup drivers [CarA, CarB], session state, init analyzer states) ...
    drivers_info = [
        {'CarIdx': 0, 'UserName': 'CarA', 'CarNumber':'1', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'CarB', 'CarNumber':'2', 'CarIsPaceCar': 0}
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for info in drivers_info:
        replay_analyzer.car_analysis_states[info['CarIdx']] = {'user_name': info['UserName'], 'last_known_car_lap_times': -1.0, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
        replay_analyzer.last_known_car_lap_times[info['CarIdx']] = -1.0
    replay_analyzer.driver_personal_best_laps = {}
    replay_analyzer.overall_fastest_lap_time = None


    time_t1 = 10.0; car_a_lap1_time = 90.0
    time_t2 = 20.0; car_b_lap1_time = 88.0 # New session best

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        time_t1: {0: {'CarIdxLastLapTime': car_a_lap1_time, 'CarIdxLapCompleted': 1}},
        time_t2: {1: {'CarIdxLastLapTime': car_b_lap1_time, 'CarIdxLapCompleted': 1}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    session_fl_events = sorted([ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_Session'], key=lambda ev: ev.start_time)
    pb_fl_events = sorted([ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_DriverPB'], key=lambda ev: ev.start_time)

    assert len(session_fl_events) == 2
    assert session_fl_events[0].car_idx == 0 and f"{car_a_lap1_time:.3f}s" in session_fl_events[0].details
    assert session_fl_events[1].car_idx == 1 and f"{car_b_lap1_time:.3f}s" in session_fl_events[1].details

    assert len(pb_fl_events) == 2
    assert pb_fl_events[0].car_idx == 0 and f"{car_a_lap1_time:.3f}s" in pb_fl_events[0].details
    assert pb_fl_events[1].car_idx == 1 and f"{car_b_lap1_time:.3f}s" in pb_fl_events[1].details

    assert len(overlay_data.fastest_laps) == 2
    assert overlay_data.fastest_laps[-1].lap_time == pytest.approx(car_b_lap1_time)
    assert overlay_data.fastest_laps[-1].driver.car_idx == 1


def test_analyzer_fastest_lap_driver_improves_pb_not_session(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 35
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    # ... (setup drivers [CarA, CarB], session state, init analyzer states) ...
    drivers_info = [
        {'CarIdx': 0, 'UserName': 'CarA', 'CarNumber':'1', 'CarIsPaceCar': 0},
        {'CarIdx': 1, 'UserName': 'CarB', 'CarNumber':'2', 'CarIsPaceCar': 0}
    ]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    for info in drivers_info:
        replay_analyzer.car_analysis_states[info['CarIdx']] = {'user_name': info['UserName'], 'last_known_car_lap_times': -1.0, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
        replay_analyzer.last_known_car_lap_times[info['CarIdx']] = -1.0
    replay_analyzer.driver_personal_best_laps = {}
    replay_analyzer.overall_fastest_lap_time = None

    time_t1 = 10.0; car_a_lap1_time = 90.0
    time_t2 = 20.0; car_b_lap1_time = 88.0 # Session Best
    time_t3 = 30.0; car_a_lap2_time = 89.0 # CarA PB, but not session best

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        time_t1: {0: {'CarIdxLastLapTime': car_a_lap1_time, 'CarIdxLapCompleted': 1}},
        time_t2: {1: {'CarIdxLastLapTime': car_b_lap1_time, 'CarIdxLapCompleted': 1}},
        time_t3: {0: {'CarIdxLastLapTime': car_a_lap2_time, 'CarIdxLapCompleted': 2}},
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    session_fl_events = sorted([ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_Session'], key=lambda ev: ev.start_time)
    pb_fl_events = sorted([ev for ev in overlay_data.race_events if ev.interest == 'FastestLap_DriverPB'], key=lambda ev: ev.start_time)

    assert len(session_fl_events) == 2 # CarA at T1, CarB at T2
    assert session_fl_events[0].car_idx == 0 and f"{car_a_lap1_time:.3f}s" in session_fl_events[0].details
    assert session_fl_events[1].car_idx == 1 and f"{car_b_lap1_time:.3f}s" in session_fl_events[1].details

    assert len(pb_fl_events) == 3 # CarA T1, CarB T2, CarA T3
    assert pb_fl_events[0].car_idx == 0 and f"{car_a_lap1_time:.3f}s" in pb_fl_events[0].details
    assert pb_fl_events[1].car_idx == 1 and f"{car_b_lap1_time:.3f}s" in pb_fl_events[1].details
    assert pb_fl_events[2].car_idx == 0 and f"{car_a_lap2_time:.3f}s" in pb_fl_events[2].details

    assert len(overlay_data.fastest_laps) == 2 # History of session bests
    assert overlay_data.fastest_laps[-1].lap_time == pytest.approx(car_b_lap1_time)
    assert overlay_data.fastest_laps[-1].driver.car_idx == 1

    lb_after_t3 = next((lb for lb in overlay_data.leader_boards if lb.start_time >= time_t3), None)
    assert lb_after_t3 is not None
    driver_a_lb_data = next((d for d in lb_after_t3.drivers if d.car_idx == 0), None)
    assert driver_a_lb_data is not None
    assert driver_a_lb_data.best_lap_time == pytest.approx(car_a_lap2_time)
    assert driver_a_lb_data.last_lap_time == pytest.approx(car_a_lap2_time)


def test_analyzer_fastest_lap_ignores_invalid_times(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    mock_app_settings.max_analysis_duration_seconds = 15
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    # ... (setup CarA, session state, init analyzer states) ...
    car_a_idx = 0
    drivers_session_info = [{'CarIdx': car_a_idx, 'UserName': 'CarA', 'CarNumber':'1', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    replay_analyzer.car_analysis_states[car_a_idx] = {'user_name': 'CarA', 'last_known_car_lap_times': -1.0, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
    replay_analyzer.last_known_car_lap_times[car_a_idx] = -1.0
    replay_analyzer.driver_personal_best_laps = {}
    replay_analyzer.overall_fastest_lap_time = None


    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        10.0: {car_a_idx: {'CarIdxLastLapTime': 0.0, 'CarIdxLapCompleted': 1}}, # Invalid time
        12.0: {car_a_idx: {'CarIdxLastLapTime': -1.0, 'CarIdxLapCompleted': 2}}, # Invalid time
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    assert len([ev for ev in overlay_data.race_events if 'FastestLap' in ev.interest]) == 0
    assert len(overlay_data.fastest_laps) == 0

    lb_after_events = next((lb for lb in overlay_data.leader_boards if lb.start_time >= 12.0), None)
    if lb_after_events : # Leaderboards might be sparse depending on exact timing and loop iterations
        driver_a_lb_data = next((d for d in lb_after_events.drivers if d.car_idx == car_a_idx), None)
        assert driver_a_lb_data is not None
        assert driver_a_lb_data.best_lap_time is None
        assert driver_a_lb_data.last_lap_time is None


def test_analyzer_fastest_lap_new_lap_detection(
    replay_analyzer: ReplayAnalyzer,
    pyirsdk_manager_fixture: PyIrSdkManager,
    mock_app_settings: AppSettings
):
    """Tests that a lap time is only processed once when CarIdxLastLapTime doesn't clear immediately."""
    mock_app_settings.max_analysis_duration_seconds = 20
    mock_sdk = pyirsdk_manager_fixture.ir_sdk
    car_a_idx = 0
    # ... (setup CarA, session state, init analyzer states) ...
    drivers_session_info = [{'CarIdx': car_a_idx, 'UserName': 'CarA', 'CarNumber':'1', 'CarIsPaceCar': 0}]
    mock_sdk._mock_data['SessionInfo']['DriverInfo']['Drivers'] = drivers_session_info # type: ignore[attr-defined]
    mock_sdk._session_state_timeline = {0.0: IRSDK_SESSION_STATE_RACING} # type: ignore[attr-defined]
    replay_analyzer.car_analysis_states[car_a_idx] = {'user_name': 'CarA', 'last_known_car_lap_times': -1.0, 'current_pit_stop_count':0, 'is_in_pits':False, 'pit_stop_start_time':None, 'last_incident_count':0, 'last_track_surface': IRSDK_TRK_LOC_ON_TRACK, 'off_track_start_time': None}
    replay_analyzer.last_known_car_lap_times[car_a_idx] = -1.0 # Important: initial state for last_known
    replay_analyzer.driver_personal_best_laps = {}
    replay_analyzer.overall_fastest_lap_time = None


    time_t1_lap_post = 10.0 # CarA posts 90.0s
    time_t2_same_lap_data = 10.1 # SDK still shows 90.0s for CarIdxLastLapTime, same lap
    time_t3_new_lap_post = 15.0 # CarA posts 89.0s on next lap

    mock_sdk._car_telemetry_timeline = { # type: ignore[attr-defined]
        time_t1_lap_post:      {car_a_idx: {'CarIdxLastLapTime': 90.0, 'CarIdxLapCompleted': 1, 'CarIdxLap': 2}},
        time_t2_same_lap_data: {car_a_idx: {'CarIdxLastLapTime': 90.0, 'CarIdxLapCompleted': 1, 'CarIdxLap': 2}}, # Still same lap time
        time_t3_new_lap_post - 0.1: {car_a_idx: {'CarIdxLapCompleted': 1, 'CarIdxLap': 2}}, # still on lap 2 before crossing line
        time_t3_new_lap_post:  {car_a_idx: {'CarIdxLastLapTime': 89.0, 'CarIdxLapCompleted': 2, 'CarIdxLap': 3}}, # New lap, new time
    }

    xml_filepath_str = replay_analyzer.analyse_race(abort_check=lambda: False)
    assert xml_filepath_str is not None
    overlay_data = OverlayData.load_from_xml(xml_filepath_str)

    # Filter for both types of fastest lap events
    all_fl_events = sorted([ev for ev in overlay_data.race_events if 'FastestLap' in ev.interest], key=lambda x: x.start_time)

    # Expect 2 sets of events: one for 90.0s at T1, one for 89.0s at T3
    # Each set has a PB and a Session event (initially session, then potentially just PB if not overall best)
    assert len(all_fl_events) == 4 # PB+Session for 90s, PB+Session for 89s (as 89 is new overall)

    # Events for 90.0s lap at T1
    assert all_fl_events[0].start_time == pytest.approx(time_t1_lap_post, abs=0.1)
    assert f"{90.0:.3f}s" in all_fl_events[0].details
    assert all_fl_events[1].start_time == pytest.approx(time_t1_lap_post, abs=0.1)
    assert f"{90.0:.3f}s" in all_fl_events[1].details

    # Events for 89.0s lap at T3
    assert all_fl_events[2].start_time == pytest.approx(time_t3_new_lap_post, abs=0.1)
    assert f"{89.0:.3f}s" in all_fl_events[2].details
    assert all_fl_events[3].start_time == pytest.approx(time_t3_new_lap_post, abs=0.1)
    assert f"{89.0:.3f}s" in all_fl_events[3].details

    # Check overlay_data.fastest_laps (history of session bests)
    assert len(overlay_data.fastest_laps) == 2
    assert overlay_data.fastest_laps[0].lap_time == pytest.approx(90.0)
    assert overlay_data.fastest_laps[1].lap_time == pytest.approx(89.0)

    # Final state check
    lb_after_t3 = next((lb for lb in overlay_data.leader_boards if lb.start_time >= time_t3_new_lap_post), None)
    assert lb_after_t3 is not None
    driver_a_lb_data = next((d for d in lb_after_t3.drivers if d.car_idx == car_a_idx), None)
    assert driver_a_lb_data is not None
    assert driver_a_lb_data.best_lap_time == pytest.approx(89.0)
    assert driver_a_lb_data.last_lap_time == pytest.approx(89.0)
```
