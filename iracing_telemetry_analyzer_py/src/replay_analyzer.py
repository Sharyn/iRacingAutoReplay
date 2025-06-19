"""
Analyzes iRacing replay data (simulated for now) to generate an OverlayData script.
"""

from datetime import datetime as Datetime # Alias to avoid confusion with module
import time
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .iracing_manager import IRacingManagerInterface
    from .app_settings import AppSettings
from .utils import dict_to_xml_string # Import the new utility

from .replay_data import (
    OverlayData,
    Driver,
    RaceEvent,
    LeaderBoardSnapshot,
    CamDriver,
    MessageState,
    FastLap
)

# Import track location constants
from .pyirsdk_manager import (
    IRSDK_TRK_LOC_NOT_IN_WORLD,
    IRSDK_TRK_LOC_OFF_TRACK,
    IRSDK_TRK_LOC_ON_TRACK,
    IRSDK_TRK_LOC_IN_PIT_STALL,
    IRSDK_TRK_LOC_ON_PIT_ROAD
)

CURRENT_VERSION = "0.1.0-python"

class ReplayAnalyzer:
    """
    Analyzes iRacing replay data by controlling the replay (via IRacingManagerInterface)
    and processing (simulated) telemetry to generate an OverlayData script.
    """

    def __init__(self, iracing_manager: 'IRacingManagerInterface', settings: 'AppSettings'):
        """
        Initializes the ReplayAnalyzer.

        Args:
            iracing_manager: An instance of a class implementing IRacingManagerInterface
                             for interacting with iRacing.
            settings: An AppSettings instance containing application configuration.
        """
        self.iracing_manager = iracing_manager
        self.settings = settings
        # Stores state per car_idx for various analyses
        self.car_analysis_states: Dict[int, Dict[str, Any]] = {}
        # For battle detection: key = tuple(sorted(car_idx1, car_idx2)), value = {'start_time': float, 'last_close_time': float, 'd1_name': str, 'd2_name': str}
        self.active_battles: Dict[Tuple[int, int], Dict[str, Any]] = {}
        # For overtake detection: key = car_idx, value = {'lap_dist_pct': float, 'current_lap': int, 'session_time': float, 'user_name': str}
        self.previous_tick_driver_data: Dict[int, Dict[str, Any]] = {}

        # For fastest lap detection
        self.overall_fastest_lap_time: Optional[float] = None
        self.overall_fastest_lap_driver_details: Optional[Dict[str, Any]] = None
        self.driver_personal_best_laps: Dict[int, float] = {} # Key: car_idx, Value: best_lap_time
        # To track last lap time per car to detect new laps simply
        self.last_known_car_lap_times: Dict[int, float] = {}


    def analyse_race(self, abort_check: Callable[[], bool]) -> Optional[str]:
        """
        Performs the main race analysis process.

        This method simulates seeking through a replay, gathering data,
        and generating an OverlayData structure, which is then saved to XML and JSON.

        Args:
            abort_check: A callable that returns True if the analysis should be aborted.

        Returns:
            Optional[str]: The filepath to the saved .replayscript.xml file,
                           or None if analysis was aborted or failed.
        """
        print("Starting race analysis...")
        overlay_data = OverlayData()
        overlay_data.overlay_datetime = Datetime.utcnow()
        overlay_data.captured_version = CURRENT_VERSION

        # Ensure working folder exists (AppSettings should ideally handle this, but good practice)
        working_dir = Path(self.settings.working_folder)
        try:
            working_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error ensuring working folder {working_dir} exists: {e}")
            return None # Cannot proceed without a working folder

        print("Focusing iRacing window...")
        self.iracing_manager.focus_iracing_window()

        print("Waiting for iRacing to start/connect...")
        if not self.iracing_manager.is_connected():
            self.iracing_manager.connect()

        started = self.iracing_manager.wait_for_iracing_to_start(abort_check)
        if not started:
            print("ERROR: iRacing did not start or connection failed. Aborting analysis.")
            if hasattr(self.iracing_manager, 'replay_set_speed'):
                self.iracing_manager.replay_set_speed(1)
            return None

        session_info_dict = self.iracing_manager.get_session_data()
        if session_info_dict:
            try:
                overlay_data.session_data_xml = dict_to_xml_string(session_info_dict, 'SessionInfo')
                # Log some basic info from session data
                track_name = session_info_dict.get('WeekendInfo', {}).get('TrackDisplayName', 'N/A')
                print(f"Track found in SessionInfo: {track_name}")
                race_session = next((s for s in session_info_dict.get('SessionInfo', {}).get('Sessions', []) if s.get('SessionType') == 'Race'), None)
                if race_session:
                    print(f"Race session found (SessionNum: {race_session.get('SessionNum')}). Official: {race_session.get('ResultsOfficial', False)}")
            except Exception as e:
                print(f"Error processing session_info_dict for XML conversion: {e}")
                overlay_data.session_data_xml = f"<ErrorProcessingSessionData>{e}</ErrorProcessingSessionData>"
        else:
            print("Warning: Could not retrieve session data from iRacing manager.")
            overlay_data.session_data_xml = "<SessionInfoNotFound />"

        # Initialize overall fastest lap from SessionInfo if available (though live telemetry is primary)
        if session_info_dict:
            track_fastest_lap_info = session_info_dict.get('WeekendInfo', {}).get('TrackFastestLap', {})
            if isinstance(track_fastest_lap_info, list) and len(track_fastest_lap_info) > 0: # Sometimes it's a list
                track_fastest_lap_info = track_fastest_lap_info[0] # Take the first one

            initial_session_fastest_time = track_fastest_lap_info.get('LapTime', None)
            if initial_session_fastest_time and initial_session_fastest_time > 0:
                self.overall_fastest_lap_time = float(initial_session_fastest_time)
                # Note: We don't know the driver from this initial data point easily.
                print(f"Initialized overall_fastest_lap_time from SessionInfo: {self.overall_fastest_lap_time:.3f}s")

        # Initialize car_analysis_states based on drivers in SessionInfo
        self.driver_details_map: Dict[int, Dict[str, Any]] = {}
        if session_info_dict and 'DriverInfo' in session_info_dict and 'Drivers' in session_info_dict['DriverInfo']:
            for driver_info in session_info_dict['DriverInfo']['Drivers']:
                car_idx = driver_info.get('CarIdx')
                if car_idx is not None and driver_info.get('CarIsPaceCar', 0) == 0:
                    self.driver_details_map[car_idx] = driver_info
                    self.car_analysis_states[car_idx] = {
                        'last_incident_count': driver_info.get('InitIncidents', 0),
                        'last_track_surface': IRSDK_TRK_LOC_ON_TRACK,
                        'off_track_start_time': None,
                        'user_name': driver_info.get('UserName', f'Car {car_idx}'),
                        'is_in_pits': False,
                        'pit_stop_start_time': None,
                        'current_pit_stop_count': 0,
                    }
                    self.last_known_car_lap_times[car_idx] = -1.0 # Initialize last known lap time
        print(f"Initialized car analysis states for {len(self.car_analysis_states)} drivers.")


        # --- Scan for Green Flag (Race Start) ---
        print("Scanning for actual race start (green flag)...")
        self.iracing_manager.replay_set_speed(1) # Play at normal speed for scan
        time.sleep(0.1) # Let speed command take effect

        actual_race_start_session_time = 0.0
        actual_race_start_frame_number = 0
        race_start_found = False
        scan_start_monotonic_time = time.monotonic()
        # Max 2-3 minutes of real time to find green flag, or if session time exceeds typical pre-race
        max_scan_real_time_seconds = 180
        max_scan_session_time_seconds = 300 # e.g. 5 mins of session time

        IRSDK_SESSION_STATE_RACING = 5 # from pyirsdk enums (conceptually)

        while (time.monotonic() - scan_start_monotonic_time) < max_scan_real_time_seconds:
            if abort_check():
                print("Race start scan aborted by caller.")
                self.iracing_manager.replay_set_speed(0)
                return None

            data_sample = self.iracing_manager.get_latest_data_sample()
            if data_sample:
                current_session_time_scan = data_sample.get('SessionTime', 0.0)
                current_session_state = data_sample.get('SessionState')

                if current_session_state == IRSDK_SESSION_STATE_RACING:
                    actual_race_start_session_time = current_session_time_scan
                    actual_race_start_frame_number = data_sample.get('ReplayFrameNum', 0)
                    overlay_data.race_events.append(
                        RaceEvent(interest='RaceStart',
                                  start_time=actual_race_start_session_time,
                                  end_time=actual_race_start_session_time + 0.5)
                    )
                    print(f"Race Start (Green Flag) detected at SessionTime: {actual_race_start_session_time:.2f}s, Frame: {actual_race_start_frame_number}")
                    race_start_found = True
                    break

                if current_session_time_scan > max_scan_session_time_seconds:
                    print(f"Race start scan exceeded max session time ({max_scan_session_time_seconds}s).")
                    break
            time.sleep(0.1) # Polling interval for scan

        if not race_start_found:
            print("ERROR: Actual race start (SessionState=Racing) not found within scan limits. Using frame 0 as fallback.")
            # Fallback to frame 0 if no green flag detected, or return None
            # For now, we'll proceed from frame 0 for analysis if green not found.
            # actual_race_start_session_time = 0.0 (already default)
            # actual_race_start_frame_number = 0 (already default)
            # Consider returning None or raising an error for a real application
            # return None

        # --- Reposition Replay for Analysis (with pre-roll) ---
        pre_roll_seconds = getattr(self.settings, 'analysis_pre_roll_seconds', 5)
        # Frame rate assumption for pre-roll calculation (iRacing typically 60fps for replay physics/data)
        # TODO: Get actual ReplayFPS from SessionInfo if available for more accuracy
        assumed_replay_fps = 60
        target_start_frame = max(0, actual_race_start_frame_number - (assumed_replay_fps * pre_roll_seconds))

        print(f"Repositioning replay to analysis start point (Frame: {target_start_frame}, with {pre_roll_seconds}s pre-roll)...")
        self.iracing_manager.replay_move_to_frame(int(target_start_frame))
        time.sleep(1.0) # Allow time for seek command to process and data to stabilize

        # Update last_session_time to where we actually seeked to, to start data gathering correctly
        # This requires getting a sample after seeking.
        initial_sample_after_seek = self.iracing_manager.get_latest_data_sample()
        last_session_time = initial_sample_after_seek.get('SessionTime', -1.0) if initial_sample_after_seek else -1.0
        if last_session_time < 0 and actual_race_start_session_time > 0 : # If seek somehow failed to give valid time
            # Fallback to a time slightly before detected race start if preroll seek failed
            last_session_time = max(0, actual_race_start_session_time - pre_roll_seconds -1)

        # --- Main Data Analysis Loop ---
        analysis_speed = getattr(self.settings, 'analysis_replay_speed', 16)
        # Max duration to analyze *from the detected race start*
        max_analysis_from_race_start = getattr(self.settings, 'max_analysis_duration_seconds', 600)
        # Absolute session time at which to stop analysis
        absolute_stop_session_time = actual_race_start_session_time + max_analysis_from_race_start

        print(f"Starting main data analysis loop. Replay speed: {analysis_speed}x. Analyzing until SessionTime ~{absolute_stop_session_time:.2f}s.")
        self.iracing_manager.replay_set_speed(analysis_speed) # Set desired analysis speed

        no_new_data_timeout_seconds = 15
        last_data_received_monotonic_time = time.monotonic()
        incident_check_interval_seconds = 2.0
        last_incident_check_session_time = last_session_time # Start checking from current point

        loop_iterations = 0
        max_loop_iterations = (max_analysis_from_race_start + pre_roll_seconds) * assumed_replay_fps * 2 # Generous safety

        IRSDK_CHECKERED_FLAG_VALUE = 0x00000004 # from iRSDKExternals.h, irsdk_checkered
        IRSDK_SESSION_STATE_COOL_DOWN = 6      # irsdk_SessionState_CoolDown
        IRSDK_SESSION_STATE_FINISHED = 4       # irsdk_SessionState_Finished (usually precedes CoolDown)


        while loop_iterations < max_loop_iterations:
            loop_iterations += 1
            if abort_check():
                print("Analysis aborted by abort_check.")
                break

            data_sample = self.iracing_manager.get_latest_data_sample()

            if not data_sample:
                if (time.monotonic() - last_data_received_monotonic_time) > no_new_data_timeout_seconds:
                    print("No new data received for an extended period. Assuming end of replay or issue.")
                    break
                if not self.iracing_manager.is_replay_playing() and last_session_time > 0:
                    print("Replay is no longer playing and data has been received previously. Ending analysis.")
                    break
                time.sleep(0.05)
                continue

            current_session_time = data_sample.get('SessionTime', last_session_time)

            if current_session_time <= last_session_time and last_session_time != -1.0:
                if (time.monotonic() - last_data_received_monotonic_time) > no_new_data_timeout_seconds:
                    print(f"SessionTime has not advanced for {no_new_data_timeout_seconds}s. Ending analysis.")
                    break
                time.sleep(0.05)
                continue

            last_session_time = current_session_time
            last_data_received_monotonic_time = time.monotonic()

            # Check for race end conditions relative to actual_race_start_session_time
            if current_session_time > absolute_stop_session_time:
                print(f"Reached max analysis duration relative to race start ({max_analysis_from_race_start}s).")
                break

            current_session_state = data_sample.get('SessionState')
            current_session_flags = data_sample.get('SessionFlags', 0)

            if current_session_time >= actual_race_start_session_time: # Only process after detected race start
                if (current_session_flags & IRSDK_CHECKERED_FLAG_VALUE) or \
                   current_session_state == IRSDK_SESSION_STATE_COOL_DOWN or \
                   current_session_state == IRSDK_SESSION_STATE_FINISHED:
                    actual_race_end_session_time = current_session_time
                    overlay_data.race_events.append(
                        RaceEvent(interest='RaceEnd',
                                  start_time=actual_race_end_session_time,
                                  end_time=actual_race_end_session_time + 0.5)
                    )
                    print(f"Race End condition detected at SessionTime: {actual_race_end_session_time:.2f}s. State: {current_session_state}, Flags: {current_session_flags:#0x}")
                    break # End main analysis loop

            # --- Populate OverlayData based on SDK sample & SessionInfo ---
            if current_session_time < (actual_race_start_session_time - pre_roll_seconds - 0.5) and pre_roll_seconds > 0 :
                 time.sleep(0.01)
                 continue

            player_car_idx_from_sample = data_sample.get('PlayerCarIdx') # This is the current driver the Sim is focused on, or player.

            # --- Enhanced LeaderBoardSnapshot Population ---
            current_drivers_list: List[Driver] = []
            # Use driver_details_map (from SessionInfo) as the base list of all competing drivers
            # Max cars to process - could be from SessionInfo (NumStarters) or a constant like 64
            # For mock, this might be len(data_sample.get('CarIdxLap', []))
            num_cars_in_session = len(self.driver_details_map)
            max_cars_to_process = len(data_sample.get('CarIdxLap', [])) if data_sample.get('CarIdxLap') else num_cars_in_session

            # Get per-car telemetry arrays, with fallbacks for safety
            car_idx_lap = data_sample.get('CarIdxLap', [0]*max_cars_to_process)
            car_idx_lap_completed = data_sample.get('CarIdxLapCompleted', [0]*max_cars_to_process)
            car_idx_lap_dist_pct = data_sample.get('CarIdxLapDistPct', [-1.0]*max_cars_to_process)
            car_idx_track_surface_raw = data_sample.get('CarIdxTrackSurface', [0]*max_cars_to_process) # Renamed to avoid clash
            car_idx_class_pos = data_sample.get('CarIdxClassPosition', [0]*max_cars_to_process)
            car_idx_f2_time = data_sample.get('CarIdxF2Time', [0.0]*max_cars_to_process)
            # CarIdxBestLapTime from telemetry is session best for that driver, not necessarily overall
            # We will manage our own driver_personal_best_laps and overall_fastest_lap_time
            car_idx_last_lap_time_telemetry = data_sample.get('CarIdxLastLapTime', [-1.0]*max_cars_to_process)
            car_idx_session_flags = data_sample.get('CarIdxSessionFlags', [0]*max_cars_to_process)
            car_idx_on_pit_road_flags = data_sample.get('CarIdxOnPitRoad', [False]*max_cars_to_process)

            for car_idx_val in range(max_cars_to_process):
                current_car_driver_details = self.driver_details_map.get(car_idx_val) # Renamed from static_driver_info
                if not current_car_driver_details:
                    continue

                car_state = self.car_analysis_states.get(car_idx_val)
                if not car_state:
                    print(f"Warning: Missing car_analysis_state for car_idx {car_idx_val}")
                    continue

                # --- Fastest Lap Detection ---
                # Ensure car_idx_val is within bounds for car_idx_last_lap_time_telemetry
                if car_idx_val < len(car_idx_last_lap_time_telemetry):
                    current_car_last_lap_time = car_idx_last_lap_time_telemetry[car_idx_val]

                    # Simplified "new lap" detection: positive time and different from last known time for this car
                    is_new_valid_lap = False
                    if current_car_last_lap_time > 0.0 and \
                       abs(current_car_last_lap_time - self.last_known_car_lap_times.get(car_idx_val, -1.0)) > 0.001: # Avoid float precision issues
                        is_new_valid_lap = True
                        self.last_known_car_lap_times[car_idx_val] = current_car_last_lap_time

                    if is_new_valid_lap:
                        driver_name_for_event = current_car_driver_details.get('UserName', f'Car {car_idx_val}')
                        fastest_lap_duration_setting = getattr(self.settings, 'fastest_lap_event_duration_seconds', 7.0)

                        # Driver's Personal Best
                        current_pb = self.driver_personal_best_laps.get(car_idx_val)
                        if current_pb is None or current_car_last_lap_time < current_pb:
                            self.driver_personal_best_laps[car_idx_val] = current_car_last_lap_time
                            pb_event = RaceEvent(
                                interest='FastestLap_DriverPB',
                                start_time=current_session_time,
                                end_time=current_session_time + fastest_lap_duration_setting, # Duration from settings
                                car_idx=car_idx_val,
                                details=f"PB: {current_car_last_lap_time:.3f}s by {driver_name_for_event}"
                            )
                            overlay_data.race_events.append(pb_event)
                            # print(f"  Driver PB: {driver_name_for_event} set {current_car_last_lap_time:.3f}s at {current_session_time:.2f}s")

                        # Overall Session Fastest Lap
                        if self.overall_fastest_lap_time is None or current_car_last_lap_time < self.overall_fastest_lap_time:
                            self.overall_fastest_lap_time = current_car_last_lap_time
                            self.overall_fastest_lap_driver_details = current_car_driver_details # Store static details

                            session_fl_event = RaceEvent(
                                interest='FastestLap_Session',
                                start_time=current_session_time,
                                # Use a potentially longer duration for session fastest lap events from settings
                                end_time=current_session_time + getattr(self.settings, 'fastest_lap_event_duration_seconds', 10.0),
                                car_idx=car_idx_val,
                                details=f"New Session Fastest Lap: {current_car_last_lap_time:.3f}s by {driver_name_for_event}"
                            )
                            overlay_data.race_events.append(session_fl_event)

                            # Update overlay_data.fastest_laps (history of session fastest laps)
                            fl_driver_obj = Driver( # Create a simple Driver instance for FastLap
                                car_idx=car_idx_val,
                                user_name=driver_name_for_event,
                                car_number=current_car_driver_details.get('CarNumber', str(car_idx_val))
                            )
                            overlay_data.fastest_laps.append(
                                FastLap(start_time=current_session_time, driver=fl_driver_obj, lap_time=current_car_last_lap_time)
                            )
                            # print(f"  Overall Fastest Lap: {driver_name_for_event} set {current_car_last_lap_time:.3f}s at {current_session_time:.2f}s")

                # --- Pit Stop Detection Logic ---
                current_car_track_surface = IRSDK_TRK_LOC_NOT_IN_WORLD
                if car_idx_val < len(car_idx_track_surface_raw):
                    current_car_track_surface = car_idx_track_surface_raw[car_idx_val]

                is_car_on_pit_road_flag = False
                if car_idx_val < len(car_idx_on_pit_road_flags):
                    is_car_on_pit_road_flag = car_idx_on_pit_road_flags[car_idx_val]

                is_physically_in_pit_area = is_car_on_pit_road_flag or \
                                           current_car_track_surface == IRSDK_TRK_LOC_IN_PIT_STALL or \
                                           current_car_track_surface == IRSDK_TRK_LOC_ON_PIT_ROAD

                if is_physically_in_pit_area and not car_state['is_in_pits']:
                    car_state['is_in_pits'] = True
                    car_state['pit_stop_start_time'] = current_session_time
                    car_state['current_pit_stop_count'] += 1
                    # print(f"Pit Entry: Car {car_idx_val} ({car_state['user_name']}) at {current_session_time:.2f}s, Count: {car_state['current_pit_stop_count']}")

                elif (not is_physically_in_pit_area and current_car_track_surface == IRSDK_TRK_LOC_ON_TRACK) and car_state['is_in_pits']:
                    if car_state['pit_stop_start_time'] is not None:
                        pit_duration = current_session_time - car_state['pit_stop_start_time']
                        pit_event = RaceEvent(
                            interest='PitStop',
                            start_time=car_state['pit_stop_start_time'],
                            end_time=current_session_time,
                            car_idx=car_idx_val,
                            details=f"Pit stop #{car_state['current_pit_stop_count']} for {car_state['user_name']} (Duration: {pit_duration:.2f}s)"
                        )
                        overlay_data.race_events.append(pit_event)
                        # print(f"Pit Exit & Event: Car {car_idx_val} ({car_state['user_name']}) at {current_session_time:.2f}s. Duration: {pit_duration:.2f}s")

                    car_state['is_in_pits'] = False
                    car_state['pit_stop_start_time'] = None

                # --- Determine Driver Status for Leaderboard ---
                driver_status = "Unknown"
                if is_car_on_pit_road_flag or current_car_track_surface == IRSDK_TRK_LOC_IN_PIT_STALL:
                    driver_status = 'InPits'
                elif current_car_track_surface == IRSDK_TRK_LOC_ON_TRACK:
                    driver_status = 'OnTrack'
                elif current_car_track_surface == IRSDK_TRK_LOC_OFF_TRACK:
                    driver_status = 'OffTrack'
                elif current_car_track_surface == IRSDK_TRK_LOC_NOT_IN_WORLD:
                    driver_status = 'NotInWorld'
                # Consider other flags from CarIdxSessionFlags if needed for 'Finished', 'Out', etc.

                current_drivers_list.append(Driver(
                    car_idx=car_idx_val,
                    user_name=current_car_driver_details.get('UserName', f'Driver {car_idx_val}'),
                    car_number=current_car_driver_details.get('CarNumber', str(car_idx_val)),
                    status=driver_status,
                    current_lap=car_idx_lap_completed[car_idx_val] + 1 if car_idx_val < len(car_idx_lap_completed) else None,
                    lap_dist_pct=car_idx_lap_dist_pct[car_idx_val] if car_idx_val < len(car_idx_lap_dist_pct) else -1.0,
                    class_position=car_idx_class_pos[car_idx_val] if car_idx_val < len(car_idx_class_pos) else 0,
                    best_lap_time=self.driver_personal_best_laps.get(car_idx_val), # Use our tracked PB
                    last_lap_time=self.last_known_car_lap_times.get(car_idx_val) if self.last_known_car_lap_times.get(car_idx_val, -1.0) > 0 else None,
                    pit_stop_count=car_state['current_pit_stop_count']
                ))

            # Sort drivers: Lap (desc), LapDistPct (desc), ClassPos (asc), CarIdx (asc)
                if not static_driver_info:
                    continue

                car_state = self.car_analysis_states.get(car_idx_val)
                if not car_state: # Should exist if static_driver_info exists
                    print(f"Warning: Missing car_analysis_state for car_idx {car_idx_val}")
                    continue

                # --- Pit Stop Detection Logic ---
                current_car_track_surface = IRSDK_TRK_LOC_NOT_IN_WORLD
                if car_idx_val < len(car_idx_track_surface):
                    current_car_track_surface = car_idx_track_surface[car_idx_val]

                is_car_on_pit_road_flag = False
                if car_idx_val < len(car_idx_on_pit_road_flags):
                    is_car_on_pit_road_flag = car_idx_on_pit_road_flags[car_idx_val]

                is_physically_in_pit_area = is_car_on_pit_road_flag or \
                                           current_car_track_surface == IRSDK_TRK_LOC_IN_PIT_STALL or \
                                           current_car_track_surface == IRSDK_TRK_LOC_ON_PIT_ROAD

                if is_physically_in_pit_area and not car_state['is_in_pits']:
                    car_state['is_in_pits'] = True
                    car_state['pit_stop_start_time'] = current_session_time
                    car_state['current_pit_stop_count'] += 1
                    # print(f"Pit Entry: Car {car_idx_val} ({car_state['user_name']}) at {current_session_time:.2f}s, Count: {car_state['current_pit_stop_count']}")

                elif (not is_physically_in_pit_area and current_car_track_surface == IRSDK_TRK_LOC_ON_TRACK) and car_state['is_in_pits']:
                    if car_state['pit_stop_start_time'] is not None:
                        pit_duration = current_session_time - car_state['pit_stop_start_time']
                        pit_event = RaceEvent(
                            interest='PitStop',
                            start_time=car_state['pit_stop_start_time'],
                            end_time=current_session_time,
                            car_idx=car_idx_val,
                            details=f"Pit stop #{car_state['current_pit_stop_count']} for {car_state['user_name']} (Duration: {pit_duration:.2f}s)"
                        )
                        overlay_data.race_events.append(pit_event)
                        # print(f"Pit Exit & Event: Car {car_idx_val} ({car_state['user_name']}) at {current_session_time:.2f}s. Duration: {pit_duration:.2f}s")

                    car_state['is_in_pits'] = False
                    car_state['pit_stop_start_time'] = None

                # --- Determine Driver Status for Leaderboard ---
                driver_status = "Unknown"
                if is_car_on_pit_road_flag or current_car_track_surface == IRSDK_TRK_LOC_IN_PIT_STALL:
                    driver_status = 'InPits'
                elif current_car_track_surface == IRSDK_TRK_LOC_ON_TRACK:
                    driver_status = 'OnTrack'
                elif current_car_track_surface == IRSDK_TRK_LOC_OFF_TRACK:
                    driver_status = 'OffTrack'
                elif current_car_track_surface == IRSDK_TRK_LOC_NOT_IN_WORLD:
                    driver_status = 'NotInWorld'
                # Consider other flags from CarIdxSessionFlags if needed for 'Finished', 'Out', etc.

                current_drivers_list.append(Driver(
                    car_idx=car_idx_val,
                    user_name=static_driver_info.get('UserName', f'Driver {car_idx_val}'),
                    car_number=static_driver_info.get('CarNumber', str(car_idx_val)),
                    status=driver_status,
                    current_lap=car_idx_lap_completed[car_idx_val] + 1 if car_idx_val < len(car_idx_lap_completed) else None,
                    lap_dist_pct=car_idx_lap_dist_pct[car_idx_val] if car_idx_val < len(car_idx_lap_dist_pct) else -1.0,
                    class_position=car_idx_class_pos[car_idx_val] if car_idx_val < len(car_idx_class_pos) else 0,
                    best_lap_time=car_idx_best_lap_time[car_idx_val] if (car_idx_val < len(car_idx_best_lap_time) and car_idx_best_lap_time[car_idx_val] > 0) else None,
                    last_lap_time=car_idx_last_lap_time[car_idx_val] if (car_idx_val < len(car_idx_last_lap_time) and car_idx_last_lap_time[car_idx_val] > 0) else None,
                    pit_stop_count=car_state['current_pit_stop_count'] # Assign pit stop count
                    # position will be set after sorting.
                ))

            # Sort drivers: Lap (desc), LapDistPct (desc), ClassPos (asc), CarIdx (asc)
            current_drivers_list.sort(
                key=lambda d: (
                    -(d.current_lap or -1), # Sort descending for lap number
                    -(d.lap_dist_pct or -1.0), # Sort descending for lap distance
                    d.class_position or 999, # Sort ascending for class position
                    d.car_idx or 999
                )
            )

            # Assign positions after sorting
            for pos_idx, driver_obj in enumerate(current_drivers_list):
                driver_obj.position = pos_idx + 1

            # Get player's current position for LeaderBoardSnapshot.race_position
            player_lb_pos_str = "P?"
            if player_car_idx_from_sample is not None:
                player_in_lb = next((d for d in current_drivers_list if d.car_idx == player_car_idx_from_sample), None)
                if player_in_lb and player_in_lb.position is not None:
                    player_lb_pos_str = f"P{player_in_lb.position}"


            overlay_data.leader_boards.append(
                LeaderBoardSnapshot(
                    start_time=current_session_time,
                    drivers=current_drivers_list,
                    race_position=player_lb_pos_str,
                    lap_counter=f"L {data_sample.get('PlayerCarLap', '?')}/{session_info_dict.get('WeekendInfo',{}).get('SessionLaps', 'N/A') if session_info_dict else '?'}"
                )
            )

            # --- Battle and Overtake Detection ---
            # Filter current_drivers_list to get only those currently on track with valid lap data
            on_track_drivers_for_battle_overtake = [
                d for d in current_drivers_list
                if d.status == 'OnTrack' and d.lap_dist_pct is not None and d.current_lap is not None
            ]
            # Sort by lap and distance for easier comparison (leader first)
            on_track_drivers_for_battle_overtake.sort(key=lambda d: (-(d.current_lap or -1), -(d.lap_dist_pct or -1.0)))

            # Iterate through unique pairs of on-track drivers
            for i in range(len(on_track_drivers_for_battle_overtake)):
                for j in range(i + 1, len(on_track_drivers_for_battle_overtake)):
                    d1 = on_track_drivers_for_battle_overtake[i]
                    d2 = on_track_drivers_for_battle_overtake[j]

                    if d1.car_idx is None or d2.car_idx is None: continue # Should not happen with valid drivers

                    battle_key = tuple(sorted((d1.car_idx, d2.car_idx)))

                    if d1.current_lap == d2.current_lap: # Battle/Overtake only if on same lap
                        dist_diff_pct = abs(d1.lap_dist_pct - d2.lap_dist_pct)

                        # Battle Detection
                        if dist_diff_pct <= getattr(self.settings, 'battle_proximity_threshold_pct', 0.005):
                            if battle_key not in self.active_battles:
                                self.active_battles[battle_key] = {
                                    'start_time': current_session_time,
                                    'last_close_time': current_session_time,
                                    'd1_name': d1.user_name or f"Car {d1.car_idx}",
                                    'd2_name': d2.user_name or f"Car {d2.car_idx}"
                                }
                            else:
                                self.active_battles[battle_key]['last_close_time'] = current_session_time
                        elif battle_key in self.active_battles: # Cars no longer close enough
                            battle_info = self.active_battles.pop(battle_key)
                            battle_duration = battle_info['last_close_time'] - battle_info['start_time']
                            if battle_duration >= getattr(self.settings, 'min_battle_duration_seconds', 5.0):
                                overlay_data.race_events.append(RaceEvent(
                                    interest='Battle', start_time=battle_info['start_time'],
                                    end_time=battle_info['last_close_time'], car_idx=battle_key[0],
                                    other_car_idx=battle_key[1],
                                    details=f"Battle: {battle_info['d1_name']} & {battle_info['d2_name']} for {battle_duration:.1f}s"))

                        # Overtake Detection
                        if dist_diff_pct <= getattr(self.settings, 'overtake_proximity_threshold_pct', 0.002):
                            prev_d1_data = self.previous_tick_driver_data.get(d1.car_idx)
                            prev_d2_data = self.previous_tick_driver_data.get(d2.car_idx)

                            if prev_d1_data and prev_d2_data and \
                               prev_d1_data['current_lap'] == d1.current_lap and \
                               prev_d2_data['current_lap'] == d2.current_lap and \
                               prev_d1_data['lap_dist_pct'] is not None and \
                               prev_d2_data['lap_dist_pct'] is not None:

                                d1_was_behind_d2_prev = prev_d1_data['lap_dist_pct'] < prev_d2_data['lap_dist_pct']
                                d1_is_ahead_of_d2_now = d1.lap_dist_pct >= d2.lap_dist_pct

                                d2_was_behind_d1_prev = prev_d2_data['lap_dist_pct'] < prev_d1_data['lap_dist_pct']
                                d2_is_ahead_of_d1_now = d2.lap_dist_pct >= d1.lap_dist_pct

                                d1_overtook_d2 = d1_was_behind_d2_prev and d1_is_ahead_of_d2_now
                                d2_overtook_d1 = d2_was_behind_d1_prev and d2_is_ahead_of_d1_now

                                overtake_event_time = current_session_time

                                if d1_overtook_d2 or d2_overtook_d1:
                                    overtaker, passed = (d1, d2) if d1_overtook_d2 else (d2, d1)
                                    last_overtake_key = f"overtake_{battle_key}" # Use battle_key for uniqueness

                                    # Check car_analysis_states for last overtake time involving this pair
                                    # Need a common place or a way to store pair-specific event times if debouncing per pair
                                    # For simplicity, this example uses overtaker's state.
                                    overtaker_state = self.car_analysis_states.get(overtaker.car_idx)
                                    last_pair_overtake_time = -1000.0 # Default to allow first event
                                    if overtaker_state:
                                        last_pair_overtake_time = overtaker_state.get(last_overtake_key, -1000.0)

                                    if current_session_time - last_pair_overtake_time > 1.0: # Debounce for 1 second for this pair
                                        ot_event = RaceEvent(
                                            interest='Overtake', start_time=overtake_event_time - 0.25,
                                            end_time=overtake_event_time + 0.25, car_idx=overtaker.car_idx,
                                            other_car_idx=passed.car_idx, with_overtake=True,
                                            details=f"{overtaker.user_name or f'Car {overtaker.car_idx}'} overtook {passed.user_name or f'Car {passed.car_idx}'}")
                                        overlay_data.race_events.append(ot_event)
                                        if overtaker_state:
                                            overtaker_state[last_overtake_key] = current_session_time

            # Update previous_tick_driver_data for the next iteration
            self.previous_tick_driver_data = {
                d.car_idx: {
                    'lap_dist_pct': d.lap_dist_pct,
                    'current_lap': d.current_lap,
                    'session_time': current_session_time,
                    'user_name': d.user_name # For event details
                }
                for d in on_track_drivers_for_battle_overtake if d.car_idx is not None
            }

            # --- CamDriver Update ---
            current_player_driver_for_cam = None
            if player_car_idx_from_sample is not None:
                current_player_driver_for_cam = next((d for d in current_drivers_list if d.car_idx == player_car_idx_from_sample), None)

            if current_player_driver_for_cam:
                overlay_data.cam_drivers.append(
                    CamDriver(start_time=current_session_time,
                              cam_group_number=data_sample.get('CamCameraNumber', 1),
                              current_driver=current_player_driver_for_cam)
                )

            # --- MessageState (example: every 30s of session time) ---
            if int(current_session_time) % 30 == 0 and \
               (len(overlay_data.message_states) == 0 or \
                abs(overlay_data.message_states[-1].time - current_session_time) > 1.0):
                overlay_data.message_states.append(
                    MessageState(time=current_session_time, messages=[f"Live Update: {current_session_time:.1f}s"])
                )

            # The old logic for overlay_data.fastest_laps using player-specific LapLastLapTime is now superseded
            # by the per-car logic above that updates self.overall_fastest_lap_time and appends to
            # overlay_data.fastest_laps when a new session fastest lap is set by any driver.
            # No further changes needed here for FastLap list population.

            # Incident detection (points & off-track) is already done per-car inside the loop above.
            # The old self.iracing_manager.get_incidents() which was player-specific is no longer primary.

            # --- Battle and Overtake Detection ---
            # Use on_track_drivers_for_battle_overtake which was populated during driver list construction
            on_track_drivers_for_battle_overtake.sort(key=lambda d: (-(d.current_lap or -1), -(d.lap_dist_pct or -1.0)))

            # Iterate through unique pairs of on-track drivers
            for i in range(len(on_track_drivers_for_battle_overtake)):
                for j in range(i + 1, len(on_track_drivers_for_battle_overtake)):
                    d1 = on_track_drivers_for_battle_overtake[i]
                    d2 = on_track_drivers_for_battle_overtake[j]

                    # Ensure valid car_idx and data for comparison
                    if d1.car_idx is None or d2.car_idx is None or \
                       d1.current_lap is None or d2.current_lap is None or \
                       d1.lap_dist_pct is None or d2.lap_dist_pct is None:
                        continue

                    battle_key = tuple(sorted((d1.car_idx, d2.car_idx)))

                    # Battle Detection Logic
                    if d1.current_lap == d2.current_lap:
                        dist_diff_pct = abs(d1.lap_dist_pct - d2.lap_dist_pct)
                        if dist_diff_pct <= getattr(self.settings, 'battle_proximity_threshold_pct', 0.005):
                            if battle_key not in self.active_battles:
                                self.active_battles[battle_key] = {
                                    'start_time': current_session_time,
                                    'last_close_time': current_session_time,
                                    'd1_name': d1.user_name, # Store names for event details
                                    'd2_name': d2.user_name
                                }
                            else:
                                self.active_battles[battle_key]['last_close_time'] = current_session_time
                        elif battle_key in self.active_battles: # Cars no longer close enough
                            battle_info = self.active_battles.pop(battle_key)
                            battle_duration = battle_info['last_close_time'] - battle_info['start_time']
                            if battle_duration >= getattr(self.settings, 'min_battle_duration_seconds', 5.0):
                                overlay_data.race_events.append(RaceEvent(
                                    interest='Battle', start_time=battle_info['start_time'],
                                    end_time=battle_info['last_close_time'], car_idx=battle_key[0],
                                    other_car_idx=battle_key[1],
                                    details=f"Battle: {battle_info['d1_name']} & {battle_info['d2_name']} for {battle_duration:.1f}s"))

                    # Overtake Detection Logic (simplified)
                    # Check only if they are on the same lap and very close
                    if d1.current_lap == d2.current_lap and \
                       abs(d1.lap_dist_pct - d2.lap_dist_pct) <= getattr(self.settings, 'overtake_proximity_threshold_pct', 0.002):

                        prev_d1_data = self.previous_tick_driver_data.get(d1.car_idx)
                        prev_d2_data = self.previous_tick_driver_data.get(d2.car_idx)

                        if prev_d1_data and prev_d2_data and \
                           prev_d1_data['current_lap'] == d1.current_lap and \
                           prev_d2_data['current_lap'] == d2.current_lap and \
                           prev_d1_data['lap_dist_pct'] is not None and \
                           prev_d2_data['lap_dist_pct'] is not None:

                            # d1 was behind d2, now d1 is ahead of d2 (or at same dist_pct but further in list implies ahead)
                            d1_overtook_d2 = (prev_d1_data['lap_dist_pct'] < prev_d2_data['lap_dist_pct'] and \
                                              d1.lap_dist_pct >= d2.lap_dist_pct)
                            # d2 was behind d1, now d2 is ahead of d1
                            d2_overtook_d1 = (prev_d2_data['lap_dist_pct'] < prev_d1_data['lap_dist_pct'] and \
                                              d2.lap_dist_pct >= d1.lap_dist_pct)

                            overtake_event_time = current_session_time # Or average of this and previous tick's session time

                            if d1_overtook_d2:
                                overlay_data.race_events.append(RaceEvent(
                                    interest='Overtake', start_time=overtake_event_time - 0.25, # Approximate recent past
                                    end_time=overtake_event_time + 0.25, car_idx=d1.car_idx,
                                    other_car_idx=d2.car_idx, with_overtake=True,
                                    details=f"{d1.user_name} overtook {d2.user_name}"))
                            elif d2_overtook_d1:
                                overlay_data.race_events.append(RaceEvent(
                                    interest='Overtake', start_time=overtake_event_time - 0.25,
                                    end_time=overtake_event_time + 0.25, car_idx=d2.car_idx,
                                    other_car_idx=d1.car_idx, with_overtake=True,
                                    details=f"{d2.user_name} overtook {d1.user_name}"))

            # Update previous_tick_driver_data for the next iteration using on_track_drivers
            self.previous_tick_driver_data = {
                d.car_idx: {'lap_dist_pct': d.lap_dist_pct, 'current_lap': d.current_lap, 'session_time': current_session_time, 'user_name': d.user_name}
                for d in on_track_drivers_for_battle_overtake if d.car_idx is not None
            }

            if loop_iterations % 120 == 0:
                print(f"  Analysis loop progress: SessionTime={current_session_time:.2f}s")

        # After loop, finalize any active battles
        for battle_key, battle_info in list(self.active_battles.items()): # Use list for safe iteration if popping
            duration = battle_info['last_close_time'] - battle_info['start_time']
            if duration >= getattr(self.settings, 'min_battle_duration_seconds', 5.0):
                overlay_data.race_events.append(RaceEvent(
                    interest='Battle', start_time=battle_info['start_time'], end_time=battle_info['last_close_time'],
                    car_idx=battle_key[0], other_car_idx=battle_key[1],
                    details=f"Battle: {battle_info['d1_name']} & {battle_info['d2_name']} for {duration:.1f}s (ended post-loop)"))
            self.active_battles.pop(battle_key, None) # Clean up

        print("Main data analysis loop finished.")
        timestamp_str = Datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"replay_analysis_{timestamp_str}"

        xml_filename = f"{base_filename}.replayscript.xml"
        xml_filepath = working_dir / xml_filename

        json_filename = f"{base_filename}.replayscript.json"
        json_filepath = working_dir / json_filename

        print(f"Saving OverlayData to XML: {xml_filepath}")
        overlay_data.save_to_xml(str(xml_filepath)) # save_to_xml expects string path

        print(f"Saving OverlayData to JSON: {json_filepath}")
        overlay_data.save_to_json(str(json_filepath)) # save_to_json expects string path

        print("Analysis complete. OverlayData saved.")
        return str(xml_filepath)


if __name__ == '__main__':
    print("--- ReplayAnalyzer Demonstration ---")

    # 1. Setup Mocks/Placeholders
    class MockAppSettings:
        def __init__(self, working_dir_name="temp_replay_analyzer_output"):
            self.working_folder = Path.cwd() / working_dir_name
            # Ensure temp working folder exists for the demo
            self.working_folder.mkdir(parents=True, exist_ok=True)
            print(f"Demo working folder: {self.working_folder.resolve()}")

    # Using PyIrSdkManager, which has its own internal mock if pyirsdk is not available.
    from .pyirsdk_manager import PyIrSdkManager, PYIRSDK_AVAILABLE, IRSDK_TRK_LOC_ON_TRACK, IRSDK_TRK_LOC_ON_PIT_ROAD, IRSDK_TRK_LOC_IN_PIT_STALL
    if not PYIRSDK_AVAILABLE:
        from .pyirsdk_manager import pyirsdk as mock_pyirsdk_module

    mock_settings = MockAppSettings()
    pyir_manager = PyIrSdkManager() # Will use MockIRSDK if real not found

    # Configure the mock PyIrSdkManager for the demo to simulate a more complete race scenario
    if hasattr(pyir_manager, 'ir_sdk') and hasattr(pyir_manager.ir_sdk, '_mock_data'):
        mock_sdk = pyir_manager.ir_sdk
        print("Configuring MockIRSDK for ReplayAnalyzer __main__ demo...")

        # Detailed SessionInfo for driver list population
        mock_sdk._mock_data['SessionInfo'] = {
            'WeekendInfo': {
                'TrackName': 'Demo Test Track',
                'TrackDisplayName': 'Demo Track',
                'SessionLaps': '20', # Example total laps
                'NumStarters': 3,
            },
            'SessionInfo': {
                'Sessions': [{'SessionNum': 2, 'SessionType': 'Race', 'ResultsOfficial': 0}]
            },
            'DriverInfo': {
                'DriverCarIdx': 0, # Player is CarIdx 0
                'Drivers': [
                    {'CarIdx': 0, 'UserName': 'Player (You)', 'CarNumber': 'P1', 'CarIsPaceCar': 0, 'TeamID': 0},
                    {'CarIdx': 1, 'UserName': 'AI Opponent Alpha', 'CarNumber': 'A1', 'CarIsPaceCar': 0, 'TeamID': 0},
                    {'CarIdx': 2, 'UserName': 'AI Opponent Bravo', 'CarNumber': 'B2', 'CarIsPaceCar': 0, 'TeamID': 0},
                    # Add a pace car to test filtering
                    {'CarIdx': 3, 'UserName': 'Pace Car', 'CarNumber': 'PC', 'CarIsPaceCar': 1, 'TeamID': 0},
                ]
            }
        }
        # Simulate telemetry for these 4 cars (3 racers, 1 pace car)
        num_mock_cars = 4
        mock_sdk._mock_data.update({
            'CarIdxLap': [1, 1, 0, 0], # Player & Alpha on lap 1, Bravo on lap 0
            'CarIdxLapCompleted': [0, 0, -1, -1],
            'CarIdxLapDistPct': [0.1, 0.05, 0.95, -1.0],
            'CarIdxTrackSurface': [IRSDK_TRK_LOC_ON_TRACK] * num_mock_cars, # Default to on track
            'CarIdxClassPosition': [1, 2, 3, 0],
            'CarIdxBestLapTime': [-1.0] * num_mock_cars,
            'CarIdxLastLapTime': [-1.0] * num_mock_cars,
            'CarIdxSessionFlags': [0] * num_mock_cars,
            'CarIdxOnPitRoad': [False] * num_mock_cars, # Default to not on pit road
            'CarIdxSteer': [0.0] * num_mock_cars,
            'CarIdxRPM': [3000.0] * num_mock_cars,
            'CarIdxGear': [3] * num_mock_cars,
        })

        # Timelines for SessionState and SessionFlags
        mock_sdk._session_state_timeline = {
            0.0: 1,  # GetInCar
            1.0: 3,  # ParadeLaps (for a very short time in this demo)
            2.0: 5,  # Racing (this should be detected as RaceStart by ReplayAnalyzer)
            # Max analysis duration is 10s from settings, pre-roll 1s.
            # So, analysis runs from SessionTime ~1s to ~11s.
            10.5: 6, # CoolDown (RaceEnd)
        }
        # IRSDK_CHECKERED_FLAG_VALUE = 0x00000004
        mock_sdk._session_flags_timeline = {
            10.2: 0x00000004 # Checkered flag
        }

        # Simulate an incident for the player
        mock_sdk._mock_data['PlayerCarMyIncidentCount'] = 0
        # ReplayAnalyzer's incident check is every 2s of SessionTime.
        # If race starts at T=2s, first check at T=~2s + 2s = ~4s.
        # To make incident appear: PlayerCarMyIncidentCount should change.
        # This dynamic change is better handled by tests. Here, let's pre-set it.
        pyir_manager._last_player_incident_count = 0
        mock_sdk._mock_data['PlayerCarMyIncidentCount'] = 2

        # --- Configure Car Telemetry Timeline for Pit Stop Demo ---
        # Car 1 (AI Opponent Alpha) will perform a pit stop.
        # Car 0 (Player) and Car 2 (AI Bravo) will set some lap times.
        # Race Start at T=2.0s. Analysis pre-roll 1s (starts T=1.0s). Max duration 10s (ends T=12.0s).

        # Timeline for Car 0 (Player)
        # T=2.5s: Crosses S/F, posts lap time 90.5s
        # T=5.5s: Crosses S/F, posts lap time 88.0s (PB and Session Best)
        # Timeline for Car 1 (AI Alpha) - Pit Stop
        # T=3.0s: Enters pit road
        # T=4.0s: Enters pit stall
        # T=7.0s: Exits pit stall
        # T=8.0s: Exits pit road
        # Timeline for Car 2 (AI Bravo)
        # T=3.5s: Crosses S/F, posts lap time 92.0s
        # T=6.5s: Crosses S/F, posts lap time 87.0s (New Session Best, PB for Bravo)

        mock_sdk._car_telemetry_timeline = {
            # Car 1 (Alpha) pit stop sequence
            3.0: { 1: { 'CarIdxOnPitRoad': True, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD } },
            4.0: { 1: { 'CarIdxTrackSurface': IRSDK_TRK_LOC_IN_PIT_STALL } },
            7.0: { 1: { 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_PIT_ROAD } },
            8.0: { 1: { 'CarIdxOnPitRoad': False, 'CarIdxTrackSurface': IRSDK_TRK_LOC_ON_TRACK } },

            # Car 0 (Player) lap times
            # Note: To ensure these are picked up as 'new', CarIdxLap should also increment,
            # or our "new lap" detection needs to be robust. The current simplified detection
            # relies on CarIdxLastLapTime changing from its previous value for that car.
            # We'll also update CarIdxLapCompleted to assist this.
            2.5: { 0: { 'CarIdxLastLapTime': 90.5, 'CarIdxLapCompleted': 0 } }, # Player completes lap 1
            5.5: { 0: { 'CarIdxLastLapTime': 88.0, 'CarIdxLapCompleted': 1 } }, # Player completes lap 2

            # Car 2 (Bravo) lap times
            3.5: { 2: { 'CarIdxLastLapTime': 92.0, 'CarIdxLapCompleted': 0 } }, # Bravo completes lap 1
            6.5: { 2: { 'CarIdxLastLapTime': 87.0, 'CarIdxLapCompleted': 1 } }, # Bravo completes lap 2
        }
        print(f"Mock SDK Car Telemetry Timeline configured for pit stop and fastest laps: {mock_sdk._car_telemetry_timeline}")

        # Adjust settings for a quick demo run
        mock_settings.max_analysis_duration_seconds = 10
        mock_settings.analysis_pre_roll_seconds = 1
        mock_settings.analysis_replay_speed = 1
        mock_settings.fastest_lap_event_duration_seconds = 3.0 # Shorter for demo
        print(f"Demo settings: Max Duration={mock_settings.max_analysis_duration_seconds}s, Pre-roll={mock_settings.analysis_pre_roll_seconds}s, FL Event Duration: {mock_settings.fastest_lap_event_duration_seconds}s")

    analyzer = ReplayAnalyzer(iracing_manager=pyir_manager, settings=mock_settings)

    # 3. Define a dummy abort_check function
    abort_flag = False
    # Example: abort after a certain number of checks or time
    # def check_if_aborted(): global abort_flag; return abort_flag
    # For this demo, let's not abort:
    def check_if_aborted(): return False

    print("\nRunning analyse_race()...")
    # In a real app, this might run in a separate thread
    output_xml_path_str = analyzer.analyse_race(abort_check=check_if_aborted)

    # 4. Check results
    if output_xml_path_str:
        output_xml_path = Path(output_xml_path_str)
        print(f"\nAnalysis finished. Output XML script: {output_xml_path.resolve()}")
        assert output_xml_path.exists(), f"Output XML file {output_xml_path} was not created."

        # Check for JSON file as well
        output_json_path = output_xml_path.with_suffix(".json") # Assumes .replayscript.xml -> .replayscript.json
                                                                # Corrected: base_filename.json
        json_path_expected = mock_settings.working_folder / (output_xml_path.stem.replace(".replayscript", "") + ".json")
        # The actual json filename is base_filename.replayscript.json, so stem is base_filename.replayscript
        json_path_actual = output_xml_path.with_name(output_xml_path.stem.replace('.replayscript','') + '.replayscript.json')

        assert json_path_actual.exists(), f"Output JSON file {json_path_actual} was not created."
        print(f"Output JSON script also created: {json_path_actual.resolve()}")

        print("\n--- Verifying Pit Stop Event and Driver Status/Count (from XML) ---")
        # For verification, we'd typically load and parse the XML or JSON.
        # For this demo, we'll rely on the print statements during analysis (if enabled)
        # or manual inspection of the output files.
        # A more robust test would be in a separate test file.
        # We can check the analyzer's internal state for a quick check here though.

        # Pit Stop Verification (from previous subtask, ensure it still works)
        pit_events_found = [ev for ev in analyzer.overlay_data.race_events if ev.interest == 'PitStop']
        if pit_events_found:
            print(f"\nFound {len(pit_events_found)} PitStop events in OverlayData:")
            for ev in pit_events_found:
                print(f"  - {ev.details}")
        else:
            print("\nNo PitStop events were recorded in OverlayData.")

        # Fastest Lap Verification
        fastest_lap_pb_events = [ev for ev in analyzer.overlay_data.race_events if ev.interest == 'FastestLap_DriverPB']
        fastest_lap_session_events = [ev for ev in analyzer.overlay_data.race_events if ev.interest == 'FastestLap_Session']

        print(f"\nFound {len(fastest_lap_pb_events)} Driver PB Fastest Lap events:")
        for ev in fastest_lap_pb_events: print(f"  - {ev.details}")

        print(f"\nFound {len(fastest_lap_session_events)} Session Fastest Lap events:")
        for ev in fastest_lap_session_events: print(f"  - {ev.details}")

        print("\nOverall Session Fastest Laps recorded in overlay_data.fastest_laps:")
        if analyzer.overlay_data.fastest_laps:
            for fl in analyzer.overlay_data.fastest_laps:
                print(f"  - Time: {fl.lap_time:.3f}s by {fl.driver.user_name} (CarIdx: {fl.driver.car_idx}) at SessionTime: {fl.start_time:.2f}s")
        else:
            print("  None recorded.")

        # Check final leaderboard for best lap times
        if analyzer.overlay_data.leader_boards:
            last_lb = analyzer.overlay_data.leader_boards[-1]
            print("\nDriver Best Lap Times in final leaderboard:")
            for d_lb in last_lb.drivers:
                pb_time_str = f"{d_lb.best_lap_time:.3f}s" if d_lb.best_lap_time else "N/A"
                last_lap_time_str = f"{d_lb.last_lap_time:.3f}s" if d_lb.last_lap_time else "N/A"
                print(f"  - {d_lb.user_name} (CarIdx: {d_lb.car_idx}): PB: {pb_time_str}, Last Lap: {last_lap_time_str}")

        print("\n--- Generated XML content (first few lines) ---")
        with open(output_xml_path, 'r', encoding='utf-8') as f:
            for _ in range(10):
                line = f.readline()
                if not line: break
                print(line.strip())
        print("--------------------------------------------")

        # 5. Clean up (optional, but good for tests)
        # try:
        #     print(f"\nCleaning up generated files in {mock_settings.working_folder}...")
        #     output_xml_path.unlink()
        #     json_path_actual.unlink()
        #     try:
        #         mock_settings.working_folder.rmdir()
        #         print(f"Removed directory: {mock_settings.working_folder}")
        #     except OSError:
        #         print(f"Directory {mock_settings.working_folder} not empty or couldn't be removed (this is okay for demo).")
        # except Exception as e:
        #     print(f"Error during cleanup: {e}")
    else:
        print("\nAnalysis did not complete or was aborted.")

    print("\nReplayAnalyzer Demonstration finished.")


