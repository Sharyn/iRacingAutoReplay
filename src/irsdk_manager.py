"""
Manages interaction with iRacing Simulator using the irsdk library.
"""

import time
from typing import Optional, List, Dict, Any, Callable

from src.iracing_manager import IRacingManagerInterface # Ensure this path is correct for your structure

# Conditional import of irsdk
try:
    import irsdk
    IRSDK_AVAILABLE = True
except ImportError:
    IRSDK_AVAILABLE = False
    irsdk = None # Placeholder
    print("WARNING: irsdk library not found. IrsdkManager will operate in a mock mode.")

    # Create a mock irsdk and IRSDK class for basic functionality if library is missing
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
                'SessionInfo': {
                    'WeekendInfo': {
                        'TrackName': 'MockRaceway International',
                        'TrackDisplayName': 'MockRaceway',
                        'TrackID': 101,
                        'SessionID': 1234567890,
                        'WeekendOptions': {'NumStarters': 3}, # Ensure enough drivers for examples
                        'SessionLaps': 'Unlimited', # For lap counter in ReplayAnalyzer
                    },
                    'SessionInfo': { # Ensure a 'Race' session exists for ReplayAnalyzer
                        'Sessions': [
                            {'SessionNum': 0, 'SessionType': 'Practice', 'ResultsFastestLap': -1, 'ResultsOfficial': 0},
                            {'SessionNum': 1, 'SessionType': 'Qualify', 'ResultsFastestLap': -1, 'ResultsOfficial': 1},
                            {'SessionNum': 2, 'SessionType': 'Race', 'ResultsFastestLap': -1, 'ResultsOfficial': 0} # Target this
                        ]
                    },
                    'DriverInfo': {
                        'DriverCarIdx': 0,
                        'Drivers': [
                            {'CarIdx': 0, 'UserName': 'Mock Player', 'CarNumber': '42', 'IRating': 2500, 'LicString': 'A 4.99', 'TeamID': 0},
                            {'CarIdx': 1, 'UserName': 'Mock AI Opponent 1', 'CarNumber': '007', 'IRating': 1500, 'LicString': 'R 0.00', 'TeamID': 0},
                            {'CarIdx': 2, 'UserName': 'Mock AI Opponent 2', 'CarNumber': '13', 'IRating': 1800, 'LicString': 'C 3.50', 'TeamID': 0},
                        ]
                    },
                    'SplitTimeInfo': {},
                    'CarSetup': {
                        'Suspension': {'LFrideHeight': '5.5 cm', 'RFrideHeight': '5.6 cm'},
                        'Tires': {'LFcoldPressure': '150 kpa', 'RFcoldPressure': '150 kpa'}
                    }
                },
                'PlayerCarMyIncidentCount': 0, # This is a single value for the player
                'SessionState': 1,
                'SessionFlags': 0,
                'SessionNum': 0,
                # Initialize per-car telemetry arrays
                # For mock, let's use a smaller default number of cars, e.g., 10 for easier management.
                # Real SDK provides up to 64. ReplayAnalyzer will iterate based on actual array length.
                '_num_mock_cars': 10, # Internal helper for mock data sizing
                'CarIdxLap': [0] * 10,
                'CarIdxLapCompleted': [0] * 10,
                'CarIdxLapDistPct': [-1.0] * 10,
                'CarIdxTrackSurface': [IRSDK_TRK_LOC_ON_TRACK] * 10, # Start all on track
                'CarIdxClassPosition': [i+1 for i in range(10)], # Simple default positions
                'CarIdxF2Time': [0.0] * 10,
                'CarIdxBestLapTime': [-1.0] * 10, # Per-driver best lap time
                'CarIdxLastLapTime': [-1.0] * 10, # Per-driver last lap time
                'LapFastestLap': -1.0,          # Overall session fastest lap (single float value)
                'CarIdxSessionFlags': [0] * 10,
                'CarIdxOnPitRoad': [False] * 10,
                'CarIdxSteer': [0.0] * 10,
                'CarIdxRPM': [1000.0] * 10, # Default RPM
                'CarIdxGear': [1] * 10,      # Default gear
                'CarIdxIncidentCount': [0] * 10, # New per-car incident count
            }
            self._session_state_timeline = {}
            self._session_flags_timeline = {}
            # For car-specific telemetry timelines:
            # self._car_telemetry_timeline[session_time_threshold] = {car_idx: {telemetry_key: value}}
            self._car_telemetry_timeline: Dict[float, Dict[int, Dict[str, Any]]] = {}
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

        # Note: In the actual irsdk, 'IsInitialized' and 'IsConnected' are not properties
        # of the IRSDK object but keys accessed via ir_sdk['IsInitialized'], etc.
        # The main manager's is_connected() method uses this dict access correctly.
        # These mock properties are not strictly necessary if the mock's __getitem__ handles these keys.

        def freeze_var_buffer_latest(self):
            # print("MockIRSDK: freeze_var_buffer_latest() called.")
            if self._mock_connected:
                self._mock_data['SessionTick'] += 1
                self._mock_data['SessionTime'] += 1/60.0 # Simulate 60Hz data
                self._mock_data['ReplayFrameNum'] += 2 # Simulate 2 frames per tick at 30fps video for 60Hz data

                # Update SessionState and SessionFlags based on global timelines
                current_session_time = self._mock_data['SessionTime']
                for t, state in sorted(self._session_state_timeline.items()):
                    if current_session_time >= t:
                        self._mock_data['SessionState'] = state # Update global session state
                for t, flags in sorted(self._session_flags_timeline.items()):
                    if current_session_time >= t:
                        self._mock_data['SessionFlags'] = flags # Update global session flags

                # Update per-car telemetry based on _car_telemetry_timeline
                num_mock_cars = self._mock_data.get('_num_mock_cars', 10)
                for t, car_updates_at_time_t in sorted(self._car_telemetry_timeline.items()):
                    if current_session_time >= t:
                        for car_idx, telemetry_updates in car_updates_at_time_t.items():
                            if 0 <= car_idx < num_mock_cars: # Ensure car_idx is valid for mock arrays
                                for key_to_update, value in telemetry_updates.items():
                                    if key_to_update in self._mock_data and isinstance(self._mock_data[key_to_update], list):
                                        if car_idx < len(self._mock_data[key_to_update]):
                                            self._mock_data[key_to_update][car_idx] = value
                                        else:
                                            print(f"MockIRSDK Warning: CarIdx {car_idx} out of bounds for {key_to_update}")
                                    else:
                                        # This case is for non-array keys or if a key was missed in init.
                                        # Unlikely for per-car telemetry which should be arrays.
                                        print(f"MockIRSDK Warning: Key {key_to_update} not an array or not found in _mock_data for car {car_idx}")
                                        # self._mock_data[key_to_update] = value # Or handle more specifically
            return self._mock_data # In real irsdk, freeze doesn't return data itself

        def __getitem__(self, key: str) -> Any:
            # print(f"MockIRSDK: __getitem__('{key}') called.")
            # Handle dynamic timeline-based values first
            current_session_time = self._mock_data.get('SessionTime', 0) # Ensure SessionTime is available
            if key == 'SessionState':
                for t, state in sorted(getattr(self, '_session_state_timeline', {}).items()):
                    if current_session_time >= t:
                        self._mock_data['SessionState'] = state
                return self._mock_data.get(key)
            elif key == 'SessionFlags':
                for t, flags in sorted(getattr(self, '_session_flags_timeline', {}).items()):
                    if current_session_time >= t:
                        self._mock_data['SessionFlags'] = flags
                return self_mock_data.get(key)

            return self._mock_data.get(key)

        def get(self, key: str, default: Any = None) -> Any:
            """Mock for dictionary .get() method, incorporating timeline logic."""
            # This ensures that when IrsdkManager uses .get for these keys,
            # it still gets the timeline-updated values.
            current_session_time = self._mock_data.get('SessionTime', 0)
            if key == 'SessionState':
                for t, state in sorted(getattr(self, '_session_state_timeline', {}).items()):
                    if current_session_time >= t:
                        self._mock_data['SessionState'] = state
                return self._mock_data.get(key, default)
            elif key == 'SessionFlags':
                for t, flags in sorted(getattr(self, '_session_flags_timeline', {}).items()):
                    if current_session_time >= t:
                        self._mock_data['SessionFlags'] = flags
                return self._mock_data.get(key, default)
            elif key == 'PlayerCarMyIncidentCount': # Assuming this might also be timeline driven for tests
                # This was handled by patching in tests, but could be integrated here too if desired.
                # For now, let the patched version in tests handle PlayerCarMyIncidentCount.
                pass

            return self._mock_data.get(key, default)

        def broadcast_msg(self, msg_type, val1, val2=0, val3=0):
            print(f"MockIRSDK: broadcast_msg({msg_type}, {val1}, {val2}, {val3}) called.")

    if irsdk is None: # If the import failed, create the mock module structure
        class MockIrsdkModule:
            IRSDK = MockIRSDK
            # Add BroadcastMsg and ReplaySearchMode enums to the mock module
            # These should ideally match the structure of the real irsdk enums if possible
            # (e.g., if they are IntEnum or similar). For mock, simple classes are fine.
            class MockBroadcastMsg: # Renamed to avoid clash if real irsdk is partially imported
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

            # Assign these to the mock irsdk object so they can be accessed like irsdk.BroadcastMsg
            MockIrsdkModule.BroadcastMsg = MockBroadcastMsg
            MockIrsdkModule.ReplaySearchMode = MockReplaySearchMode

        irsdk = MockIrsdkModule() # Instantiate the mock module

# Define iRacing SDK constants for track locations (standard values)
# These might be exposed by the real irsdk, but defining them here ensures availability for mock & logic.
IRSDK_TRK_LOC_NOT_IN_WORLD = -1
IRSDK_TRK_LOC_OFF_TRACK = 0
IRSDK_TRK_LOC_ON_TRACK = 1
IRSDK_TRK_LOC_IN_PIT_STALL = 2
# Note: iRacing official irsdk_TrkLoc enum for "approaching pits" is not explicitly defined.
# Often, logic combines CarIdxOnPitRoad and CarIdxTrackSurface to determine this.
# For simplicity, ReplayAnalyzer might use a broader interpretation or focus on key states.
# IRSDK_TRK_LOC_APROACHING_PITS = 3 # This was a conceptual value
IRSDK_TRK_LOC_ON_PIT_ROAD = 4 # This corresponds to irsdk_TrkLoc_InPitRoad in C# SDK often.
                              # The actual irsdk might use different enum values or direct strings/ints.
                              # ReplayAnalyzer will use these defined constants.

# For SessionFlags (already used in ReplayAnalyzer conceptually):
# IRSDK_CHECKERED_FLAG_VALUE = 0x00000004


class IrsdkManager(IRacingManagerInterface):
    """
    Implementation of IRacingManagerInterface using the irsdk library.
    """
    # Based on irsdk, variable names are often PascalCase.
    GENERAL_TELEMETRY_KEYS = [
        'SessionTime', 'SessionTick', 'ReplayFrameNum', 'IsReplayPlaying',
        'PlayerCarIdx', 'Speed', 'RPM', 'Gear', 'SessionState', 'SessionFlags', 'SessionNum',
        'PlayerCarPosition', 'PlayerCarClassPosition', 'PlayerCarLap',
        'LapLastLapTime', # This is often player-specific in iRacing's direct telemetry
                          # but ReplayAnalyzer will primarily use CarIdxLastLapTime for all cars.
        'LapFastestLap',  # Overall session fastest lap time
        'PlayerCarMyIncidentCount'
    ]
    # Keys for per-car telemetry arrays (names match iRacing SDK variables)
    PER_CAR_TELEMETRY_KEYS = [
        'CarIdxLap', 'CarIdxLapCompleted', 'CarIdxLapDistPct', 'CarIdxTrackSurface',
        'CarIdxClassPosition', 'CarIdxF2Time', 'CarIdxBestLapTime', 'CarIdxLastLapTime',
        'CarIdxSessionFlags', 'CarIdxOnPitRoad', 'CarIdxSteer', 'CarIdxRPM', 'CarIdxGear',
        'CarIdxIncidentCount' # Added per-car incident count
    ]
    # STATUS_KEYS = ['IsInitialized', 'IsConnected'] # These are fetched via GENERAL_TELEMETRY_KEYS

    def __init__(self):
        """Initializes the IrsdkManager."""
        self.ir_sdk: Optional[irsdk.IRSDK] = None
        self.last_tick_count: int = -1
        self._is_connected_flag: bool = False # Internal flag managed by connect/disconnect
        self._last_player_incident_count: int = 0 # For get_incidents

        if IRSDK_AVAILABLE:
            try:
                print("Attempting to instantiate irsdk.IRSDK() for real.")
                self.ir_sdk = irsdk.IRSDK()
                print("irsdk.IRSDK() instantiated successfully.")
            except Exception as e:
                print(f"Error instantiating real irsdk.IRSDK: {e}")
                # self.ir_sdk will remain None, IRSDK_AVAILABLE might still be true
                # but subsequent calls will fail if self.ir_sdk is None.
        else:
            # If irsdk wasn't available, self.ir_sdk is already None.
            # We can optionally instantiate the mock here if we want the manager
            # to always have an ir_sdk object, even if it's a mock one.
            # This depends on how strictly we want to separate the mock from real usage.
            # For now, if IRSDK_AVAILABLE is False, self.ir_sdk will be None initially.
            # The following line ensures self.ir_sdk gets the MockIRSDK instance if irsdk failed to import.
            if not IRSDK_AVAILABLE and self.ir_sdk is None : # Explicitly check if it's mock scenario
                print("IRSDK module not loaded, ensuring MockIRSDK is used by IrsdkManager.")
                self.ir_sdk = irsdk.IRSDK() # This will call MockIRSDK constructor due to above patch

        if self.ir_sdk is None and IRSDK_AVAILABLE: # Real SDK was expected but failed to init
             print("CRITICAL: IRSDK module was available but IRSDK() instantiation failed. Manager is non-functional.")
        elif self.ir_sdk is None and not IRSDK_AVAILABLE: # Mock SDK somehow also failed to init (shouldn't happen with current mock)
             print("CRITICAL: MockIRSDK also failed to instantiate. Manager is non-functional.")


    def connect(self) -> None:
        """
        Establishes a connection to the iRacing simulation using irsdk.startup().
        """
        if self.ir_sdk:
            try:
                print("IrsdkManager: Calling ir_sdk.startup()...")
                # startup() returns True if sim is found and connection is made, False otherwise.
                # It also updates internal state like ir_sdk['IsConnected']
                self._is_connected_flag = self.ir_sdk.startup()
                if self._is_connected_flag:
                    self.last_tick_count = -1 # Reset tick count on new connection
                    print("Successfully connected to iRacing via irsdk.startup().")
                else:
                    print("Failed to connect via irsdk.startup(). iRacing may not be running.")
            except Exception as e:
                print(f"Error during ir_sdk.startup(): {e}")
                self._is_connected_flag = False
        else:
            print("IrsdkManager: Cannot connect, irsdk.IRSDK object not available.")
            self._is_connected_flag = False

    def disconnect(self) -> None:
        """Disconnects from iRacing and shuts down the irsdk link."""
        if self.ir_sdk and hasattr(self.ir_sdk, 'shutdown'):
            try:
                print("IrsdkManager: Calling ir_sdk.shutdown()...")
                self.ir_sdk.shutdown()
                print("Disconnected from iRacing via irsdk.shutdown().")
            except Exception as e:
                print(f"Error during ir_sdk.shutdown(): {e}")
        else:
            print("IrsdkManager: No active ir_sdk object to shut down.")
        self._is_connected_flag = False # Always set to false on disconnect attempt

    def is_connected(self) -> bool:
        """
        Checks if currently connected to iRacing.
        Uses irsdk's 'IsConnected' and 'IsInitialized' variables.
        """
        if self.ir_sdk and self._is_connected_flag: # Check our flag first
            try:
                # irsdk variables are typically PascalCase
                # These are updated by irsdk internally when data is received
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
                # or if the real irsdk isn't fully initialized before this check.
                print(f"IrsdkManager.is_connected: Error accessing status variables: {e}")
                self._is_connected_flag = False
                return False
        return False


    def get_latest_data_sample(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves a snapshot of latest telemetry data using irsdk.
        """
        if not self.is_connected() or not self.ir_sdk:
            # print("Debug: get_latest_data_sample called but not connected.")
            return None

        try:
            # freeze_var_buffer_latest() ensures all subsequent variable accesses
            # in this tick are from the same data frame.
            self.ir_sdk.freeze_var_buffer_latest()

            # Check if data is new using SessionTick (PascalCase for iRacing vars)
            current_tick = self.ir_sdk['SessionTick'] # General key
            if current_tick == self.last_tick_count and self.last_tick_count != -1:
                # print("IrsdkManager.get_latest_data_sample: No new data tick.")
                return None # No new data
            self.last_tick_count = current_tick

            data_sample = {}
            # Fetch general telemetry keys
            for key in self.GENERAL_TELEMETRY_KEYS:
                try:
                    data_sample[key] = self.ir_sdk[key]
                except KeyError:
                    # print(f"IrsdkManager.get_latest_data_sample: General key '{key}' not found.")
                    data_sample[key] = None # Or some other default

            # Fetch per-car telemetry arrays
            for key in self.PER_CAR_TELEMETRY_KEYS:
                try:
                    data_sample[key] = self.ir_sdk[key]
                except KeyError:
                    # print(f"IrsdkManager.get_latest_data_sample: Per-car key '{key}' not found.")
                    data_sample[key] = [] # Default to empty list for missing arrays

            return data_sample
        except (TypeError, KeyError) as e:
            print(f"IrsdkManager.get_latest_data_sample: Error fetching telemetry data - {e}")
            return None
        except Exception as e:
            print(f"IrsdkManager.get_latest_data_sample: Unexpected error - {e}")
            return None

    def get_session_data(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves static session information (e.g., track, weather, drivers).
        `irsdk` typically provides this as a parsed dictionary via `ir_sdk['SessionInfo']`.
        """
        if not self.is_connected() or not self.ir_sdk:
            print("IrsdkManager.get_session_data: Cannot fetch, not connected or SDK not available.")
            return None

        try:
            # SessionInfo is generally static after being loaded by the sim/SDK.
            # A freeze might ensure it's from a consistent state if other data is read simultaneously,
            # but for SessionInfo alone, it's often not strictly required after initial load.
            # self.ir_sdk.freeze_var_buffer_latest() # Optional, depending on desired atomicity with other vars

            session_info = self.ir_sdk['SessionInfo'] # This is already a dict in irsdk
            if not isinstance(session_info, dict): # Basic validation
                print(
                    f"IrsdkManager.get_session_data: 'SessionInfo' was expected to be a dict, "
                    f"but got type: {type(session_info)}. Returning as is."
                )
            return session_info
        except KeyError:
            print("IrsdkManager.get_session_data: 'SessionInfo' key not found in SDK data.")
            return None
        except TypeError as e: # Handle cases where self.ir_sdk might be None unexpectedly
            print(f"IrsdkManager.get_session_data: SDK object error - {e}")
            return None
        except Exception as e: # Catch-all for other unexpected irsdk errors
            print(f"IrsdkManager.get_session_data: Unexpected error - {e}")
            return None

    def replay_move_to_frame(self, frame_number: int) -> None:
        """Moves the iRacing replay to a specific frame number."""
        if not self.is_connected() or not self.ir_sdk:
            print("IrsdkManager.replay_move_to_frame: Cannot execute, not connected or SDK not available.")
            return
        if not IRSDK_AVAILABLE: # Guard for using real irsdk enums
            print("IrsdkManager.replay_move_to_frame: Real irsdk features (enums) not available for this command.")
            return

        try:
            print(f"IrsdkManager: Broadcasting REPLAY_SEARCH to frame {frame_number}...")
            self.ir_sdk.broadcast_msg(
                irsdk.BroadcastMsg.REPLAY_SEARCH,       # type: ignore[attr-defined] # Mock/Real
                irsdk.ReplaySearchMode.TO_FRAME,  # type: ignore[attr-defined] # Mock/Real
                frame_number
            )
        except AttributeError as ae: # Handles if BroadcastMsg or ReplaySearchMode is missing on irsdk mock
            print(f"IrsdkManager.replay_move_to_frame: Attribute error (likely mock setup issue or API change): {ae}")
        except Exception as e:
            print(f"IrsdkManager.replay_move_to_frame: Error sending command: {e}")


    def replay_set_speed(self, speed_multiplier: int) -> None:
        """Sets the playback speed of the iRacing replay."""
        if not self.is_connected() or not self.ir_sdk:
            print("IrsdkManager.replay_set_speed: Cannot execute, not connected or SDK not available.")
            return
        if not IRSDK_AVAILABLE: # Guard for using real irsdk enums
            print("IrsdkManager.replay_set_speed: Real irsdk features (enums) not available for this command.")
            return

        try:
            # irsdk replay speed: 0=pause, 1=normal.
            # The second parameter (val1) is speed, third (val2) is ReplaySlowMotionMode (0 for normal/fast).
            print(f"IrsdkManager: Broadcasting REPLAY_SET_PLAY_SPEED to {speed_multiplier}x...")
            self.ir_sdk.broadcast_msg(
                irsdk.BroadcastMsg.REPLAY_SET_PLAY_SPEED, # type: ignore[attr-defined]
                speed_multiplier,
                0 # 0 for ReplaySlowMotionMode.NORMAL
            )
        except AttributeError as ae:
            print(f"IrsdkManager.replay_set_speed: Attribute error (likely mock setup issue or API change): {ae}")
        except Exception as e:
            print(f"IrsdkManager.replay_set_speed: Error sending command: {e}")

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
            print("IrsdkManager.get_incidents: Cannot fetch, not connected or SDK not available.")
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
                    f"IrsdkManager.get_incidents: Detected player incident(s). "
                    f"Count change: {count_change} at {current_session_time:.2f}s. "
                    f"New total: {player_incident_count}."
                )

            self._last_player_incident_count = player_incident_count # Update last known count
            return incidents

        except KeyError as e:
            print(f"IrsdkManager.get_incidents: Key not found in SDK data ('{e}'). Could not check for incidents.")
            return []
        except TypeError as e:
            print(f"IrsdkManager.get_incidents: SDK object error - {e}")
            return []
        except Exception as e:
            print(f"IrsdkManager.get_incidents: Unexpected error - {e}")
            return []

    def focus_iracing_window(self) -> None:
        # irsdk does not provide a method to focus the iRacing window.
        # This would require OS-specific calls (e.g., pywin32 on Windows).
        print("focus_iracing_window() - NOT IMPLEMENTED by irsdk. OS-specific calls needed.")
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
    print(f"--- IrsdkManager Demonstration (IRSDK_AVAILABLE: {IRSDK_AVAILABLE}) ---")

    manager = IrsdkManager()

    print("\nAttempting to connect...")
    manager.connect() # This will call startup()

    print(f"Is connected: {manager.is_connected()}")

    if manager.is_connected():
        print("\nFetching data samples for a few ticks (if new data):")
        found_new_data_count = 0
        for i in range(30): # Try up to 30 times (0.5s of sim time if 60Hz)
            sample = manager.get_latest_data_sample()
            if sample:
                found_new_data_count +=1
                print(f"  Sample (Tick {sample.get('SessionTick', 'N/A')}): SessionTime={sample.get('SessionTime', 'N/A'):.2f}, "
                      f"Speed={sample.get('Speed', 'N/A'):.2f}, Gear={sample.get('Gear', 'N')}")
                if 'CarIdxLap' in sample:
                    print(f"    CarIdxLap (first few): {sample['CarIdxLap'][:4]}")
                if found_new_data_count >= 2: # Get at least 2 new data points
                    break
            else:
                # print(f"  Attempt {i+1}: No new data or not connected.")
                pass
            if not manager.is_connected(): break # Stop if connection lost
            time.sleep(1/60.0) # Simulate waiting for next sim tick
        if found_new_data_count == 0:
            print("  No new data samples were fetched in the loop.")

        print("\n--- Testing Session Data ---")
        session_data = manager.get_session_data()
        if session_data:
            print(f"  SessionData type: {type(session_data)}")
            track_name = session_data.get('WeekendInfo', {}).get('TrackName', 'N/A')
            print(f"  Track Name from SessionInfo: {track_name}")
            if IRSDK_AVAILABLE and manager.is_connected() and not isinstance(manager.ir_sdk, MockIRSDK): # Real SDK might provide more
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
           (not IRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
            print("  Simulating player incident for mock SDK...")
            manager.ir_sdk._mock_data['PlayerCarMyIncidentCount'] = 2 # type: ignore[attr-defined]
            manager.ir_sdk._mock_data['SessionTime'] += 10 # type: ignore[attr-defined] # Advance time for incident

        incidents = manager.get_incidents(0,0)
        print(f"  Incidents after potential change: {incidents}")
        if incidents: # This block will only be meaningful if an incident was simulated/occurred
            assert incidents[0]['type'] == 'PlayerIncident'
            if not IRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK":
                 assert incidents[0]['new_total_incidents'] == 2

        # Test resetting incident count if it changes back (e.g. new session, or fixed by iRacing)
        # This part tests if _last_player_incident_count is updated correctly by get_incidents
        if manager.ir_sdk and \
           (not IRSDK_AVAILABLE or manager.ir_sdk.__class__.__name__ == "MockIRSDK"):
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

    print("\nIrsdkManager demonstration finished.")


