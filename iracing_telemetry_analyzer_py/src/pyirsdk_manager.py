"""
Manages interaction with iRacing Simulator using the pyirsdk library.
"""

import time
from typing import Optional, List, Dict, Any, Callable, TYPE_CHECKING

from ..iracing_manager import IRacingManagerInterface # Ensure this path is correct for your structure

# Conditional import of pyirsdk
try:
    import pyirsdk
    PYIRSDK_AVAILABLE = True
except ImportError:
    PYIRSDK_AVAILABLE = False
    pyirsdk = None # Placeholder
    print("WARNING: pyirsdk library not found. PyIrSdkManager will operate in a mock mode.")

    # Create a mock pyirsdk and IRSDK class for basic functionality if library is missing
    class MockIRSDK:
        def __init__(self, *args, **kwargs):
            self._mock_connected = False
            self._mock_data = {
                'SessionTime': 0.0,
                'SessionTick': -1,
                'ReplayFrameNum': 0,
                'IsReplayPlaying': False,
                'PlayerCarIdx': 0,
                'Speed': 0.0,
                'RPM': 0.0,
                'Gear': 0,
                'IsInitialized': False,
                'IsConnected': False,
                'SessionInfo': { # More structured mock SessionInfo
                    'WeekendInfo': {
                        'TrackName': 'MockRaceway International',
                        'TrackDisplayName': 'MockRaceway',
                        'TrackID': 101,
                        'SessionID': 1234567890,
                        'WeekendOptions': {'NumStarters': 2},
                    },
                    'SessionInfo': {
                        'Sessions': [
                            {'SessionNum': 0, 'SessionType': 'Practice', 'ResultsFastestLap': -1, 'ResultsOfficial': 0},
                            {'SessionNum': 1, 'SessionType': 'Qualify', 'ResultsFastestLap': -1, 'ResultsOfficial': 1},
                            {'SessionNum': 2, 'SessionType': 'Race', 'ResultsFastestLap': -1, 'ResultsOfficial': 0}
                        ]
                    },
                    'DriverInfo': {
                        'DriverCarIdx': 0, # Player's car index
                        'Drivers': [
                            {'CarIdx': 0, 'UserName': 'Mock Player', 'CarNumber': '42', 'IRating': 2500, 'LicString': 'A 4.99'},
                            {'CarIdx': 1, 'UserName': 'Mock AI Opponent 1', 'CarNumber': '007', 'IRating': 1500, 'LicString': 'R 0.00'},
                            {'CarIdx': 2, 'UserName': 'Mock AI Opponent 2', 'CarNumber': '13', 'IRating': 1800, 'LicString': 'C 3.50'},
                        ]
                    },
                    'SplitTimeInfo': {}, # Often present
                    'CarSetup': { # Basic car setup info
                        'Suspension': {'LFrideHeight': '5.5 cm', 'RFrideHeight': '5.6 cm'},
                        'Tires': {'LFcoldPressure': '150 kpa', 'RFcoldPressure': '150 kpa'}
                    }
                },
                'PlayerCarMyIncidentCount': 0,
            }
            print("MockIRSDK instantiated.")

        def startup(self, test_file=None, dump_to=None) -> bool:
            # Simulate successful connection for testing purposes if iRacing isn't running.
            print("MockIRSDK: startup() called. Simulating successful connection for demo/testing.")
            self._mock_connected = True
            self._mock_data['IsInitialized'] = True
            self._mock_data['IsConnected'] = True
            return self._mock_connected

        def shutdown(self):
            print("MockIRSDK: shutdown() called.")
            self._mock_connected = False # Should be set by manager based on this call
            # These values would reflect sim state, which becomes "not connected" after shutdown
            self._mock_data['IsInitialized'] = False
            self._mock_data['IsConnected'] = False

        # Note: In the actual pyirsdk, 'IsInitialized' and 'IsConnected' are not properties
        # of the IRSDK object but keys accessed via ir_sdk['IsInitialized'], etc.
        # The main manager's is_connected() method uses this dict access correctly.
        # These mock properties are not strictly necessary if the mock's __getitem__ handles these keys.

        def freeze_var_buffer_latest(self):
            # print("MockIRSDK: freeze_var_buffer_latest() called.")
            # Simulate time passing and data changing slightly if connected
            if self._mock_connected: # This won't be true in current mock startup
                self._mock_data['SessionTick'] += 1
                self._mock_data['SessionTime'] += 1/60.0
                self._mock_data['ReplayFrameNum'] +=1
            return self._mock_data # In real pyirsdk, freeze doesn't return data itself

        def __getitem__(self, key: str) -> Any:
            # print(f"MockIRSDK: __getitem__('{key}') called.")
            return self._mock_data.get(key) # Return default/None if key missing

        def broadcast_msg(self, msg_type, val1, val2=0, val3=0):
            print(f"MockIRSDK: broadcast_msg({msg_type}, {val1}, {val2}, {val3}) called.")

    if pyirsdk is None: # If the import failed, create the mock module structure
        class MockPyirsdkModule:
            IRSDK = MockIRSDK
            # Add BroadcastMsg and ReplaySearchMode enums to the mock module
            # These should ideally match the structure of the real pyirsdk enums if possible
            # (e.g., if they are IntEnum or similar). For mock, simple classes are fine.
            class MockBroadcastMsg: # Renamed to avoid clash if real pyirsdk is partially imported
                REPLAY_SET_PLAY_SPEED = 1 # Using distinct placeholder values
                REPLAY_SEARCH = 2
                REPLAY_SET_PLAY_POSITION = 3
                REPLAY_SET_STATE = 4
                # ... other messages as needed by manager ...
                def __init__(self, value): self.value = value # For enum-like behavior if needed
                def __repr__(self): return f"<MockBroadcastMsg: {self.value}>"


            class MockReplaySearchMode: # Renamed
                TO_FRAME = 0
                TO_START = 1
                TO_END = 2
                # ... other modes ...
                def __init__(self, value): self.value = value
                def __repr__(self): return f"<MockReplaySearchMode: {self.value}>"

            # Assign these to the mock pyirsdk object so they can be accessed like pyirsdk.BroadcastMsg
            MockPyirsdkModule.BroadcastMsg = MockBroadcastMsg
            MockPyirsdkModule.ReplaySearchMode = MockReplaySearchMode

        pyirsdk = MockPyirsdkModule() # Instantiate the mock module


class PyIrSdkManager(IRacingManagerInterface):
    """
    Implementation of IRacingManagerInterface using the pyirsdk library.
    """
    # Based on pyirsdk, variable names are often PascalCase.
    TELEMETRY_KEYS = [
        'SessionTime', 'SessionTick', 'ReplayFrameNum', 'IsReplayPlaying',
        'PlayerCarIdx', 'Speed', 'RPM', 'Gear'
    ]
    STATUS_KEYS = ['IsInitialized', 'IsConnected'] # iRacing internal state vars

    def __init__(self):
        """Initializes the PyIrSdkManager."""
        self.ir_sdk: Optional[pyirsdk.IRSDK] = None
        self.last_tick_count: int = -1
        self._is_connected_flag: bool = False # Internal flag managed by connect/disconnect
        self._last_player_incident_count: int = 0 # For get_incidents

        if PYIRSDK_AVAILABLE:
            try:
                print("Attempting to instantiate pyirsdk.IRSDK() for real.")
                self.ir_sdk = pyirsdk.IRSDK()
                print("pyirsdk.IRSDK() instantiated successfully.")
            except Exception as e:
                print(f"Error instantiating real pyirsdk.IRSDK: {e}")
                # self.ir_sdk will remain None, PYIRSDK_AVAILABLE might still be true
                # but subsequent calls will fail if self.ir_sdk is None.
        else:
            # If pyirsdk wasn't available, self.ir_sdk is already None.
            # We can optionally instantiate the mock here if we want the manager
            # to always have an ir_sdk object, even if it's a mock one.
            # This depends on how strictly we want to separate the mock from real usage.
            # For now, if PYIRSDK_AVAILABLE is False, self.ir_sdk will be None initially.
            # The following line ensures self.ir_sdk gets the MockIRSDK instance if pyirsdk failed to import.
            if not PYIRSDK_AVAILABLE and self.ir_sdk is None : # Explicitly check if it's mock scenario
                print("PYIRSDK module not loaded, ensuring MockIRSDK is used by PyIrSdkManager.")
                self.ir_sdk = pyirsdk.IRSDK() # This will call MockIRSDK constructor due to above patch

        if self.ir_sdk is None and PYIRSDK_AVAILABLE: # Real SDK was expected but failed to init
             print("CRITICAL: PYIRSDK module was available but IRSDK() instantiation failed. Manager is non-functional.")
        elif self.ir_sdk is None and not PYIRSDK_AVAILABLE: # Mock SDK somehow also failed to init (shouldn't happen with current mock)
             print("CRITICAL: MockIRSDK also failed to instantiate. Manager is non-functional.")


    def connect(self) -> None:
        """
        Establishes a connection to the iRacing simulation using pyirsdk.startup().
        """
        if self.ir_sdk:
            try:
                print("PyIrSdkManager: Calling ir_sdk.startup()...")
                # startup() returns True if sim is found and connection is made, False otherwise.
                # It also updates internal state like ir_sdk['IsConnected']
                self._is_connected_flag = self.ir_sdk.startup()
                if self._is_connected_flag:
                    self.last_tick_count = -1 # Reset tick count on new connection
                    print("Successfully connected to iRacing via pyirsdk.startup().")
                else:
                    print("Failed to connect via pyirsdk.startup(). iRacing may not be running.")
            except Exception as e:
                print(f"Error during ir_sdk.startup(): {e}")
                self._is_connected_flag = False
        else:
            print("PyIrSdkManager: Cannot connect, pyirsdk.IRSDK object not available.")
            self._is_connected_flag = False

    def disconnect(self) -> None:
        """Disconnects from iRacing and shuts down the pyirsdk link."""
        if self.ir_sdk and hasattr(self.ir_sdk, 'shutdown'):
            try:
                print("PyIrSdkManager: Calling ir_sdk.shutdown()...")
                self.ir_sdk.shutdown()
                print("Disconnected from iRacing via pyirsdk.shutdown().")
            except Exception as e:
                print(f"Error during ir_sdk.shutdown(): {e}")
        else:
            print("PyIrSdkManager: No active ir_sdk object to shut down.")
        self._is_connected_flag = False # Always set to false on disconnect attempt

    def is_connected(self) -> bool:
        """
        Checks if currently connected to iRacing.
        Uses pyirsdk's 'IsConnected' and 'IsInitialized' variables.
        """
        if self.ir_sdk and self._is_connected_flag: # Check our flag first
            try:
                # pyirsdk variables are typically PascalCase
                # These are updated by pyirsdk internally when data is received
                # after startup() is successful and freeze_var_buffer_latest() is called.
                # For a basic check after startup(), relying on startup()'s return is primary.
                # For ongoing checks, these vars are more accurate.
                # The mock needs to provide these via __getitem__
                is_init = self.ir_sdk['IsInitialized']
                is_conn = self.ir_sdk['IsConnected']
                self._is_connected_flag = bool(is_init and is_conn) # Update our flag
                return self._is_connected_flag
            except (TypeError, KeyError) as e: # TypeError if ir_sdk is None, KeyError if var missing
                # This might happen if ir_sdk is the mock and doesn't perfectly emulate dict access
                # or if the real pyirsdk isn't fully initialized before this check.
                print(f"PyIrSdkManager.is_connected: Error accessing status variables: {e}")
                self._is_connected_flag = False
                return False
        return False


    def get_latest_data_sample(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves a snapshot of latest telemetry data using pyirsdk.
        """
        if not self.is_connected() or not self.ir_sdk:
            # print("Debug: get_latest_data_sample called but not connected.")
            return None

        try:
            # freeze_var_buffer_latest() ensures all subsequent variable accesses
            # in this tick are from the same data frame.
            self.ir_sdk.freeze_var_buffer_latest()

            # Check if data is new using SessionTick (PascalCase for iRacing vars)
            current_tick = self.ir_sdk['SessionTick']
            if current_tick == self.last_tick_count and self.last_tick_count != -1: # Avoid initial state being "not new"
                # print("Debug: No new data tick.")
                return None # No new data
            self.last_tick_count = current_tick

            data_sample = {key: self.ir_sdk[key] for key in self.TELEMETRY_KEYS}
            return data_sample
        except (TypeError, KeyError) as e: # TypeError if ir_sdk is None, KeyError if var missing
            print(f"Error fetching telemetry data sample: {e}")
            # This could happen if a key in TELEMETRY_KEYS is not available
            # or if ir_sdk is not behaving as expected (e.g. mock issues).
            return None
        except Exception as e: # Catch any other pyirsdk related errors
            print(f"Unexpected error getting data sample: {e}")
            return None

    # --- Stubbed Methods ---
    def get_session_data(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves static session information (e.g., track, weather, drivers).
        `pyirsdk` typically provides this as a parsed dictionary via `ir_sdk['SessionInfo']`.
        """
        if not self.is_connected() or not self.ir_sdk:
            print("PyIrSdkManager.get_session_data: Cannot fetch, not connected or SDK not available.")
            return None

        try:
            # SessionInfo is generally static after being loaded by the sim/SDK.
            # A freeze might ensure it's from a consistent state if other data is read simultaneously,
            # but for SessionInfo alone, it's often not strictly required after initial load.
            # self.ir_sdk.freeze_var_buffer_latest() # Optional, depending on desired atomicity with other vars

            session_info = self.ir_sdk['SessionInfo'] # This is already a dict in pyirsdk
            if not isinstance(session_info, dict): # Basic validation
                print(
                    f"PyIrSdkManager.get_session_data: 'SessionInfo' was expected to be a dict, "
                    f"but got type: {type(session_info)}. Returning as is."
                )
            return session_info
        except KeyError:
            print("PyIrSdkManager.get_session_data: 'SessionInfo' key not found in SDK data.")
            return None
        except TypeError as e: # Handle cases where self.ir_sdk might be None unexpectedly
            print(f"PyIrSdkManager.get_session_data: SDK object error - {e}")
            return None
        except Exception as e: # Catch-all for other unexpected pyirsdk errors
            print(f"PyIrSdkManager.get_session_data: Unexpected error - {e}")
            return None

    def replay_move_to_frame(self, frame_number: int) -> None:
        """Moves the iRacing replay to a specific frame number."""
        if not self.is_connected() or not self.ir_sdk:
            print("PyIrSdkManager.replay_move_to_frame: Cannot execute, not connected or SDK not available.")
            return
        if not PYIRSDK_AVAILABLE: # Guard for using real pyirsdk enums
            print("PyIrSdkManager.replay_move_to_frame: Real pyirsdk features (enums) not available for this command.")
            return

        try:
            print(f"PyIrSdkManager: Broadcasting REPLAY_SEARCH to frame {frame_number}...")
            self.ir_sdk.broadcast_msg(
                pyirsdk.BroadcastMsg.REPLAY_SEARCH,       # type: ignore[attr-defined] # Mock/Real
                pyirsdk.ReplaySearchMode.TO_FRAME,  # type: ignore[attr-defined] # Mock/Real
                frame_number
            )
        except AttributeError as ae: # Handles if BroadcastMsg or ReplaySearchMode is missing on pyirsdk mock
            print(f"PyIrSdkManager.replay_move_to_frame: Attribute error (likely mock setup issue or API change): {ae}")
        except Exception as e:
            print(f"PyIrSdkManager.replay_move_to_frame: Error sending command: {e}")


    def replay_set_speed(self, speed_multiplier: int) -> None:
        """Sets the playback speed of the iRacing replay."""
        if not self.is_connected() or not self.ir_sdk:
            print("PyIrSdkManager.replay_set_speed: Cannot execute, not connected or SDK not available.")
            return
        if not PYIRSDK_AVAILABLE: # Guard for using real pyirsdk enums
            print("PyIrSdkManager.replay_set_speed: Real pyirsdk features (enums) not available for this command.")
            return

        try:
            # pyirsdk replay speed: 0=pause, 1=normal.
            # The second parameter (val1) is speed, third (val2) is ReplaySlowMotionMode (0 for normal/fast).
            print(f"PyIrSdkManager: Broadcasting REPLAY_SET_PLAY_SPEED to {speed_multiplier}x...")
            self.ir_sdk.broadcast_msg(
                pyirsdk.BroadcastMsg.REPLAY_SET_PLAY_SPEED, # type: ignore[attr-defined]
                speed_multiplier,
                0 # 0 for ReplaySlowMotionMode.NORMAL
            )
        except AttributeError as ae:
            print(f"PyIrSdkManager.replay_set_speed: Attribute error (likely mock setup issue or API change): {ae}")
        except Exception as e:
            print(f"PyIrSdkManager.replay_set_speed: Error sending command: {e}")

    def replay_get_current_frame(self) -> Optional[int]:
        """Gets the current frame number of the iRacing replay."""
        if not self.is_connected() or not self.ir_sdk: return None
        try:
            # freeze_var_buffer_latest() implicitly called by get_latest_data_sample if used before this
            # If calling standalone, ensure data is fresh or use freeze.
            # For simplicity, assume data is reasonably fresh or will be fetched if needed.
            # self.ir_sdk.freeze_var_buffer_latest() # Uncomment if direct, isolated calls are expected
            return self.ir_sdk['ReplayFrameNum']
        except (TypeError, KeyError) as e:
            print(f"Error getting current replay frame: {e}")
            return None

    def replay_get_session_time(self) -> Optional[float]:
        if not self.is_connected() or not self.ir_sdk: return None
        try:
            # self.ir_sdk.freeze_var_buffer_latest() # Uncomment if direct, isolated calls are expected
            return self.ir_sdk['SessionTime']
        except (TypeError, KeyError) as e:
            print(f"Error getting current session time: {e}")
            return None

    def is_replay_playing(self) -> bool:
        if not self.is_connected() or not self.ir_sdk: return False
        try:
            # self.ir_sdk.freeze_var_buffer_latest() # Uncomment if direct, isolated calls are expected
            return bool(self.ir_sdk['IsReplayPlaying'])
        except (TypeError, KeyError) as e:
            print(f"Error checking replay playing state: {e}")
            return False

    def get_incidents(self, wait_time_seconds: float, max_incidents: int) -> List[Dict[str, Any]]:
        """
        Retrieves a list of incidents.

        NOTE: This is a highly simplified initial implementation. It only checks for changes
        in 'PlayerCarMyIncidentCount' and reports that as a single "PlayerIncident".
        It does not use wait_time_seconds or max_incidents in this basic form.
        A full implementation would require more sophisticated event detection logic,
        likely residing in ReplayAnalyzer or a dedicated incident detection module,
        by observing various telemetry variables over time (e.g., CarLeftRight, SessionFlags).
        """
        if not self.is_connected() or not self.ir_sdk:
            print("PyIrSdkManager.get_incidents: Cannot fetch, not connected or SDK not available.")
            return []

        incidents: List[Dict[str, Any]] = []
        try:
            # Ensure data is from the same tick, especially if reading multiple related vars
            self.ir_sdk.freeze_var_buffer_latest()

            # Using .get(key, default_value) for safety if keys are missing or if ir_sdk is None
            # (though initial check should catch ir_sdk being None)
            player_incident_count = self.ir_sdk.get('PlayerCarMyIncidentCount', self._last_player_incident_count)
            current_session_time = self.ir_sdk.get('SessionTime', 0.0)

            if player_incident_count > self._last_player_incident_count:
                count_change = player_incident_count - self._last_player_incident_count
                incident_event = {
                    'type': 'PlayerIncident', # Generic type for this basic detection
                    'session_time': current_session_time,
                    'count_change': count_change,
                    'new_total_incidents': player_incident_count
                }
                incidents.append(incident_event)
                print(
                    f"PyIrSdkManager.get_incidents: Detected player incident(s). "
                    f"Count change: {count_change} at {current_session_time:.2f}s. "
                    f"New total: {player_incident_count}."
                )

            self._last_player_incident_count = player_incident_count # Update last known count
            return incidents

        except KeyError as e:
            print(f"PyIrSdkManager.get_incidents: Key not found in SDK data ('{e}'). Could not check for incidents.")
            return []
        except TypeError as e:
            print(f"PyIrSdkManager.get_incidents: SDK object error - {e}")
            return []
        except Exception as e:
            print(f"PyIrSdkManager.get_incidents: Unexpected error - {e}")
            return []

    def focus_iracing_window(self) -> None:
        # pyirsdk does not provide a method to focus the iRacing window.
        # This would require OS-specific calls (e.g., pywin32 on Windows).
        print("focus_iracing_window() - NOT IMPLEMENTED by pyirsdk. OS-specific calls needed.")
        # raise NotImplementedError("focus_iracing_window() requires OS-specific implementation.")
        pass # Allow to proceed without error for now

    def wait_for_iracing_to_start(self, abort_check: Callable[[], bool]) -> bool:
        # This method would repeatedly try to connect() or check status until successful or aborted.
        print("Attempting to wait for iRacing to start...")
        timeout_seconds = 600 # Max wait time (e.g., 10 minutes)
        check_interval = 2    # Seconds between checks

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if abort_check():
                print("wait_for_iracing_to_start aborted by caller.")
                return False

            self.connect() # Attempt to connect
            if self.is_connected():
                print("iRacing successfully connected during wait_for_iracing_to_start.")
                return True

            print(f"iRacing not yet available. Waiting {check_interval}s...")
            time.sleep(check_interval)

        print("Timed out waiting for iRacing to start.")
        return False


if __name__ == '__main__':
    print(f"--- PyIrSdkManager Demonstration (PYIRSDK_AVAILABLE: {PYIRSDK_AVAILABLE}) ---")

    manager = PyIrSdkManager()

    print("\nAttempting to connect...")
    manager.connect() # This will call startup()

    print(f"Is connected: {manager.is_connected()}")

    if manager.is_connected():
        print("\nFetching data samples for 5 ticks (if new data):")
        for i in range(10): # Try up to 10 times to get 5 new data ticks
            sample = manager.get_latest_data_sample()
            if sample:
                print(f"  Sample {i+1}: {sample}")
                if len([s for s in manager.TELEMETRY_KEYS if s in sample]) >= 5: # Heuristic for "enough data"
                    break
            else:
                print(f"  Sample {i+1}: No new data or not connected.")
            time.sleep(1/60.0) # Simulate waiting for next sim tick

        print("\n--- Testing Session Data ---")
        session_data = manager.get_session_data()
        if session_data:
            print(f"  SessionData type: {type(session_data)}")
            track_name = session_data.get('WeekendInfo', {}).get('TrackName', 'N/A')
            print(f"  Track Name from SessionInfo: {track_name}")
            if PYIRSDK_AVAILABLE and manager.is_connected() and not isinstance(manager.ir_sdk, MockIRSDK): # Real SDK might provide more
                 print(f"  SessionInfo (first 5 keys): {{ {', '.join(list(session_data.keys())[:5])}... }}")
        else:
            print("  Could not retrieve session data (or not connected).")

        print("\n--- Testing Replay Controls ---")
        print("  Simulating replay control calls (these are broadcast messages):")
        manager.replay_set_speed(2)
        current_frame = manager.replay_get_current_frame()
        print(f"  Current replay frame (mock/actual): {current_frame}")
        if current_frame is not None:
            manager.replay_move_to_frame(current_frame + 100)
            print(f"  Attempted to move to frame {current_frame + 100}")
        print(f"  Is replay playing (mock/actual): {manager.is_replay_playing()}")
        manager.replay_set_speed(1) # Set back to normal

        print("\n--- Testing Incident Detection ---")
        # Test initial incident count (should be 0 from mock, or actual if connected)
        manager._last_player_incident_count = manager.ir_sdk.get('PlayerCarMyIncidentCount', 0) if manager.ir_sdk else 0

        incidents = manager.get_incidents(0,0) # Params not used by basic impl.
        print(f"  Initial incidents check: {incidents} (Last known count: {manager._last_player_incident_count})")

        # Simulate player incident for mock SDK or if real SDK is being used for testing without sim
        if manager.ir_sdk and \
           (not PYIRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
            print("  Simulating player incident for mock SDK...")
            manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 2 # type: ignore[attr-defined]
            manager.ir_sdk._mock_data['SessionTime'] += 10 # type: ignore[attr-defined] # Advance time for incident

        incidents = manager.get_incidents(0,0)
        print(f"  Incidents after potential change: {incidents}")
        if incidents: # This block will only be meaningful if an incident was simulated/occurred
            assert incidents[0]['type'] == 'PlayerIncident'
            if not PYIRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK":
                 assert incidents[0]['new_total_incidents'] == 2

        # Test resetting incident count if it changes back (e.g. new session, or fixed by iRacing)
        # This part tests if _last_player_incident_count is updated correctly by get_incidents
        if manager.ir_sdk and \
           (not PYIRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
            print("  Simulating incident count decrease for mock SDK...")
            manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 1 # type: ignore[attr-defined]

        incidents_after_decrease = manager.get_incidents(0,0)
        print(f"  Incidents after count decreased (should be empty): {incidents_after_decrease}")
        assert not incidents_after_decrease, "Should not report new incidents if count decreases."
        # Verify _last_player_incident_count was updated to the new lower value
        assert manager._last_player_incident_count == (manager.ir_sdk.get('PlayerCarMyIncidentCount', 0) if manager.ir_sdk else 0)


    else:
        print("Could not connect to iRacing. This is expected if iRacing is not running.")
        print("The __main__ block will primarily test the MockSDK behavior in this case.")

    print("\nAttempting to disconnect...")
    manager.disconnect()
    print(f"Is connected after disconnect: {manager.is_connected()}")

    print("\nPyIrSdkManager demonstration finished.")

```
