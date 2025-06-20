import pytest
import time
from typing import Any

# Assuming pytest runs from project root or paths are configured
from src.irsdk_manager import PyIrSdkManager, PYIRSDK_AVAILABLE
# Access mock classes directly for configuration if needed, and if PYIRSDK_AVAILABLE is False
# This depends on how irsdk_manager.py structures its mock when PYIRSDK_AVAILABLE is False
if not PYIRSDK_AVAILABLE:
    pass
    # MockIRSDK = mock_pyirsdk_module.IRSDK # This is how it's structured

# --- Fixtures ---

@pytest.fixture
def manager() -> PyIrSdkManager:
    """Provides a PyIrSdkManager instance. It will use the internal mock if pyirsdk is not installed."""
    mgr = PyIrSdkManager()
    # Ensure that for tests, we are indeed using the mock if the real SDK might be present
    # For controlled unit testing of the manager's logic against its *own* mock interface:
    if PYIRSDK_AVAILABLE:
        # If we want to force testing against the mock even if pyirsdk is installed
        # we might need to temporarily patch PYIRSDK_AVAILABLE and re-init or have a dedicated mock_manager fixture.
        # For now, this fixture will use the real pyirsdk if available, or the built-in mock otherwise.
        # To specifically test the built-in mock:
        # We need to ensure PYIRSDK_AVAILABLE is False when PyIrSdkManager is initialized.
        # This is tricky without modifying the module itself or complex patching.
        # The tests below will largely assume the built-in mock is active if pyirsdk is not in test env.
        # If real pyirsdk is present, these tests might behave differently (e.g. try to connect to live sim).
        # For robust unit tests of PyIrSdkManager logic, we should ensure its ir_sdk is always the mock.
        # One way:
        if mgr.ir_sdk and mgr.ir_sdk.__class__.__name__ != "MockIRSDK":
            print("Warning: Real pyirsdk is installed. Tests ideally should run against a predictable mock.")
            # For now, we'll proceed. Some tests might behave unexpectedly if iRacing is running.
            # A better fixture would explicitly instantiate with MockIRSDK if that's the target.
            pass # Tests will run against real pyirsdk if it loaded.

    # Reset internal state for each test
    mgr._is_connected_flag = False
    mgr.last_tick_count = -1
    mgr._last_player_incident_count = 0
    if mgr.ir_sdk and hasattr(mgr.ir_sdk, '_mock_data'): # If it's the mock
        # Reset mock data to a known baseline for each test
        mock_sdk_instance = mgr.ir_sdk
        mock_sdk_instance._mock_data['IsInitialized'] = False
        mock_sdk_instance._mock_data['IsConnected'] = False
        mock_sdk_instance._mock_data['SessionTick'] = -1 # Important for get_latest_data_sample logic
        mock_sdk_instance._mock_data['PlayerCarMyIncidentCount'] = 0
        mock_sdk_instance._mock_data['SessionTime'] = 0.0
        # Ensure startup behavior is default (simulating success for most tests)
        mock_sdk_instance.startup = lambda test_file=None, dump_to=None: mock_sdk_instance._mock_startup_behavior()
        mock_sdk_instance._mock_startup_behavior = lambda: True # Default to successful startup

    return mgr

# Helper to modify mock startup behavior for specific tests
def set_mock_startup_response(manager_instance: PyIrSdkManager, should_succeed: bool):
    if manager_instance.ir_sdk and hasattr(manager_instance.ir_sdk, '_mock_data'):
        mock_sdk = manager_instance.ir_sdk

        def _custom_startup(test_file=None, dump_to=None):
            print(f"Custom MockIRSDK: startup() called. Simulating {'success' if should_succeed else 'failure'}.")
            mock_sdk._mock_data['IsInitialized'] = should_succeed
            mock_sdk._mock_data['IsConnected'] = should_succeed
            # _is_connected_flag in manager is set by manager.connect based on this return
            return should_succeed

        mock_sdk.startup = _custom_startup
        # Add the _mock_startup_behavior to the mock_sdk instance if not present
        if not hasattr(mock_sdk, '_mock_startup_behavior'):
            mock_sdk._mock_startup_behavior = lambda: True # Original default

# --- Test Functions ---

# Connection/Disconnection Tests
def test_initial_state(manager: PyIrSdkManager):
    """Test the initial state of the manager."""
    assert not manager.is_connected(), "Manager should not be connected initially."
    assert manager.last_tick_count == -1
    assert manager._last_player_incident_count == 0
    if not PYIRSDK_AVAILABLE: # Should be using mock
        assert manager.ir_sdk is not None
        assert manager.ir_sdk.__class__.__name__ == "MockIRSDK"

def test_connect_success(manager: PyIrSdkManager):
    """Test successful connection."""
    if manager.ir_sdk and hasattr(manager.ir_sdk, '_mock_data'): # If mock is active
    # Configure mock for successful startup using the helper
    set_mock_startup_response(manager, True)

    manager.connect()
    assert manager.is_connected(), "Manager should be connected after successful connect."


def test_connect_failure(manager: PyIrSdkManager):
    """Test connection failure."""
    # Configure mock for failed startup using the helper
    set_mock_startup_response(manager, False)

    manager.connect()
    assert not manager.is_connected(), "Manager should not be connected after failed connect."


def test_disconnect(manager: PyIrSdkManager, capsys):
    """Test disconnection."""
    # First, connect (mock configured by default in fixture to succeed startup)
    set_mock_startup_response(manager, True) # Ensure it's set to succeed for connect
    manager.connect()
    assert manager.is_connected(), "Pre-condition: Manager should be connected for disconnect test."

    manager.disconnect()
    assert not manager.is_connected(), "Manager should be disconnected."
    if not PYIRSDK_AVAILABLE or (manager.ir_sdk and manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
        captured = capsys.readouterr()
        assert "MockIRSDK: shutdown() called." in captured.out or "shutdown()" in captured.out # Check if shutdown was logged by mock

def test_is_connected_verification(manager: PyIrSdkManager):
    """Test how is_connected uses IsInitialized and IsConnected from SDK data."""
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("This test requires the MockIRSDK to be active and configurable.")

    # Simulate SDK connected state for the manager._is_connected_flag
    manager._is_connected_flag = True
    # Now test how is_connected() reads and updates based on mock_data
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'): # Guard for type checker
        pytest.skip("This test requires the MockIRSDK to be active and configurable.")
        return

    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    assert manager.is_connected(), "is_connected should be True if SDK vars are True and initial flag was True."
    assert manager._is_connected_flag, "Internal flag should remain True or be re-affirmed."

    manager.ir_sdk._mock_data['IsConnected'] = False
    assert not manager.is_connected(), "is_connected should be False if SDK IsConnected is False."
    assert not manager._is_connected_flag, "Internal flag should update to False."

    # Reset for next check
    manager._is_connected_flag = True # Simulate manager thought it was connected
    manager.ir_sdk._mock_data['IsConnected'] = True # SDK var is true
    manager.ir_sdk._mock_data['IsInitialized'] = False # But SDK not initialized
    assert not manager.is_connected(), "is_connected should be False if SDK IsInitialized is False."
    assert not manager._is_connected_flag, "Internal flag should update to False."

# Data Fetching Tests
def test_get_latest_data_sample_when_disconnected(manager: PyIrSdkManager):
    manager._is_connected_flag = False # Ensure disconnected state
    assert manager.get_latest_data_sample() is None

def test_get_latest_data_sample_success(manager: PyIrSdkManager):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")

    set_mock_startup_response(manager, True) # Ensure connected
    manager.connect()
    assert manager.is_connected(), "Manager must be connected for this test."

    # Configure mock data
    manager.ir_sdk._mock_data['SessionTime'] = 123.45
    manager.ir_sdk._mock_data['Speed'] = 67.0
    manager.ir_sdk._mock_data['RPM'] = 8000.0
    manager.ir_sdk._mock_data['SessionTick'] = 100 # Initial tick

    manager.last_tick_count = 99 # Ensure first sample is considered new

    sample = manager.get_latest_data_sample()
    assert sample is not None
    assert sample['SessionTime'] == 123.45
    assert sample['Speed'] == 67.0
    assert sample['RPM'] == 8000.0
    assert manager.last_tick_count == 100

    # Test no new data if tick count is same
    sample_again = manager.get_latest_data_sample()
    assert sample_again is None, "Should return None if SessionTick hasn't changed."

    # Test new data when tick count changes
    manager.ir_sdk._mock_data['SessionTick'] = 101
    manager.ir_sdk._mock_data['SessionTime'] = 123.55 # Time advanced
    new_sample = manager.get_latest_data_sample()
    assert new_sample is not None
    assert new_sample['SessionTime'] == 123.55
    assert manager.last_tick_count == 101


def test_get_latest_data_sample_key_error(manager: PyIrSdkManager, capsys):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Ensure connected
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    # Remove a key that TELEMETRY_KEYS expects
    original_speed = manager.ir_sdk._mock_data.pop('Speed', None)
    manager.ir_sdk._mock_data['SessionTick'] +=1 # Ensure new tick

    sample = manager.get_latest_data_sample() # Should handle KeyError gracefully
    assert sample is None, "Sample should be None or partial if a key error occurs during construction."
    captured = capsys.readouterr()
    assert "Error fetching telemetry data sample" in captured.out

    if original_speed is not None: # Restore for other tests
        manager.ir_sdk._mock_data['Speed'] = original_speed


def test_get_session_data_success(manager: PyIrSdkManager):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    # MockIRSDK already has a default SessionInfo
    expected_track_name = "MockRaceway From MockSDK"
    session_data = manager.get_session_data()
    assert session_data is not None
    assert isinstance(session_data, dict)
    assert session_data.get('WeekendInfo', {}).get('TrackName') == expected_track_name

def test_get_session_data_disconnected(manager: PyIrSdkManager):
    assert manager.get_session_data() is None

# Replay Control Tests (primarily testing call paths with mock)
@pytest.mark.parametrize("method_name,args", [
    ("replay_move_to_frame", (100,)),
    ("replay_set_speed", (2,)),
])
def test_replay_actions_call_broadcast_msg(manager: PyIrSdkManager, method_name: str, args: tuple, capsys):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Connect
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    method_to_call = getattr(manager, method_name)
    method_to_call(*args)

    captured = capsys.readouterr()
    assert "MockIRSDK: broadcast_msg" in captured.out

@pytest.mark.parametrize("method_name,expected_key,mock_value", [
    ("replay_get_current_frame", "ReplayFrameNum", 1234),
    ("replay_get_session_time", "SessionTime", 56.78),
    ("is_replay_playing", "IsReplayPlaying", True),
])
def test_replay_getters(manager: PyIrSdkManager, method_name: str, expected_key: str, mock_value: Any):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Connect
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    manager.ir_sdk._mock_data[expected_key] = mock_value

    method_to_call = getattr(manager, method_name)
    result = method_to_call()

    if method_name == "is_replay_playing":
        assert result == bool(mock_value)
    else:
        assert result == mock_value

# Incident Reporting Tests
def test_get_incidents_no_change(manager: PyIrSdkManager):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Connect
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 0
    manager._last_player_incident_count = 0 # Ensure it's set

    assert manager.get_incidents(0, 0) == []
    assert manager.get_incidents(0, 0) == [] # Still no change

def test_get_incidents_new_player_incident(manager: PyIrSdkManager, capsys):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Connect
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 0
    manager._last_player_incident_count = 0
    manager.ir_sdk._mock_data['SessionTime'] = 100.0

    # Simulate incident count increasing
    manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 2

    incidents = manager.get_incidents(0, 0)
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident['type'] == 'PlayerIncident'
    assert incident['session_time'] == 100.0
    assert incident['count_change'] == 2
    assert incident['new_total_incidents'] == 2
    assert manager._last_player_incident_count == 2

    # No new incidents if called again immediately
    assert manager.get_incidents(0, 0) == []


def test_get_incidents_count_decreases(manager: PyIrSdkManager):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, '_mock_data'):
        pytest.skip("Requires MockIRSDK.")
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: True # Connect
    manager.ir_sdk._mock_data['IsInitialized'] = True
    manager.ir_sdk._mock_data['IsConnected'] = True
    manager.connect()

    manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 3
    manager._last_player_incident_count = 3
    manager.ir_sdk._mock_data['SessionTime'] = 110.0

    # Simulate incident count decreasing (e.g., session reset or iRacing error)
    manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 1

    incidents = manager.get_incidents(0, 0)
    assert incidents == [], "Should not report new incidents if count decreases."
    assert manager._last_player_incident_count == 1, "Last count should be updated to the new lower value."

# wait_for_iracing_to_start Tests
def test_wait_for_iracing_success(manager: PyIrSdkManager, monkeypatch):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, 'startup'):
        pytest.skip("Requires MockIRSDK with startup.")

    monkeypatch.setattr(time, 'sleep', lambda x: None) # Speed up test

    # Simulate startup succeeding after a few tries
    call_count = 0
    def mock_startup_delayed_success(test_file=None, dump_to=None):
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            if hasattr(manager.ir_sdk, '_mock_data'):
                manager.ir_sdk._mock_data['IsInitialized'] = True
                manager.ir_sdk._mock_data['IsConnected'] = True
            return True
        if hasattr(manager.ir_sdk, '_mock_data'):
            manager.ir_sdk._mock_data['IsInitialized'] = False
            manager.ir_sdk._mock_data['IsConnected'] = False
        return False

    manager.ir_sdk.startup = mock_startup_delayed_success
    # Also ensure is_connected inside the loop reflects the startup state for this test
    original_is_connected_method = manager.is_connected
    def mock_is_connected_for_wait():
        return manager.ir_sdk._mock_data['IsConnected'] if hasattr(manager.ir_sdk, '_mock_data') else False
    monkeypatch.setattr(manager, 'is_connected', mock_is_connected_for_wait)


    assert manager.wait_for_iracing_to_start(lambda: False) is True
    assert call_count >= 3

    monkeypatch.setattr(manager, 'is_connected', original_is_connected_method)


def test_wait_for_iracing_aborted(manager: PyIrSdkManager, monkeypatch):
    if not manager.ir_sdk or not hasattr(manager.ir_sdk, 'startup'):
        pytest.skip("Requires MockIRSDK with startup.")

    monkeypatch.setattr(time, 'sleep', lambda x: None)

    # Ensure startup always fails for this test so abort is the only exit
    manager.ir_sdk.startup = lambda test_file=None, dump_to=None: False
    if hasattr(manager.ir_sdk, '_mock_data'):
        manager.ir_sdk._mock_data['IsInitialized'] = False
        manager.ir_sdk._mock_data['IsConnected'] = False

    abort_call_count = 0
    def abort_after_two_calls():
        nonlocal abort_call_count
        abort_call_count += 1
        return abort_call_count >= 3 # Abort on 3rd check (after 2 sleeps)

    assert manager.wait_for_iracing_to_start(abort_after_two_calls) is False
    assert abort_call_count >= 3

