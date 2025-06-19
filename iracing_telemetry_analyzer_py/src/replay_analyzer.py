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
        if not self.iracing_manager.is_connected(): # Try to connect if not already
            self.iracing_manager.connect()

        # Use wait_for_iracing_to_start for initial connection robustness
        started = self.iracing_manager.wait_for_iracing_to_start(abort_check)
        if not started:
            print("ERROR: iRacing did not start or connection failed. Aborting analysis.")
            # Ensure replay speed is reset if it was somehow set
            if hasattr(self.iracing_manager, 'replay_set_speed'): # Check if method exists
                self.iracing_manager.replay_set_speed(1) # Set to normal speed as a fallback
            return None

        # For now, assume race start is frame 0 / time 0.
        # TODO: Implement logic to find actual green flag and rewind replay.
        race_start_frame_number = 0
        # race_start_session_time = 0.0 # Not strictly used yet if we just go to frame 0
        print(f"Moving replay to defined race start (frame {race_start_frame_number})...")
        self.iracing_manager.replay_move_to_frame(race_start_frame_number)
        time.sleep(0.5) # Give iRacing a moment to seek

        # Get initial session data
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


        # Main Data Loop (Using SDK Data)
        analysis_speed = getattr(self.settings, 'analysis_replay_speed', 16)
        max_replay_time_to_analyze = getattr(self.settings, 'max_analysis_duration_seconds', 600)

        print(f"Starting main data analysis loop. Replay speed: {analysis_speed}x. Max analysis duration: {max_replay_time_to_analyze}s.")
        if not self.iracing_manager.is_replay_playing(): # Ensure replay is playing
             self.iracing_manager.replay_set_speed(analysis_speed)

        last_session_time = -1.0
        no_new_data_timeout_seconds = 15
        last_data_received_monotonic_time = time.monotonic()
        incident_check_interval_seconds = 2.0 # How often to check for incidents (session time)
        last_incident_check_session_time = -1.0

        loop_iterations = 0
        # Heuristic for max_loop_iterations: if analyzing 10 min (600s) at 60fps data rate
        # this is 36000 data points. If replay is 16x, this is 36000/16 actual loop iterations.
        # Add a safety margin.
        max_loop_iterations = (max_replay_time_to_analyze * 60) * 2


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
                if not self.iracing_manager.is_replay_playing() and last_session_time > 0: # Replay stopped
                    print("Replay is no longer playing and data has been received previously. Ending analysis.")
                    break
                time.sleep(0.05) # Shorter sleep when potentially waiting for data
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

            if current_session_time > max_replay_time_to_analyze:
                print(f"Reached max analysis duration of {max_replay_time_to_analyze}s replay time.")
                break

            if not data_sample.get('IsReplayPlaying', True) and current_session_time > 0:
                print(f"Replay indicates not playing at SessionTime {current_session_time:.2f}s. Ending analysis.")
                break

            # --- Populate OverlayData based on SDK sample & SessionInfo ---
            player_car_idx_sample = data_sample.get('PlayerCarIdx')

            # LeaderBoardSnapshot
            drivers_for_lb: List[Driver] = []
            if session_info_dict and 'DriverInfo' in session_info_dict and 'Drivers' in session_info_dict['DriverInfo']:
                for sdk_driver in session_info_dict['DriverInfo']['Drivers'][:10]: # Limit to first 10 for example
                    drivers_for_lb.append(Driver(
                        car_number=sdk_driver.get('CarNumber', 'N/A'),
                        user_name=sdk_driver.get('UserName', 'Unknown Driver'),
                        position=sdk_driver.get('CarIdx', -1) +1, # Placeholder for live position
                        car_idx=sdk_driver.get('CarIdx', -1)
                    ))
            else: # Fallback to simpler dummy drivers if no session info
                 drivers_for_lb.append(Driver(car_number=str(player_car_idx_sample or "0"), user_name=f"PlayerCar_{player_car_idx_sample or 0}", position=1))
                 drivers_for_lb.append(Driver(car_number="XX", user_name="OtherCar1 (Sim)", position=2))

            overlay_data.leader_boards.append(
                LeaderBoardSnapshot(
                    start_time=current_session_time,
                    drivers=drivers_for_lb,
                    race_position=str(data_sample.get('PlayerCarPosition', 'N/A')), # Example
                    lap_counter=f"L {data_sample.get('PlayerCarLap', 0)}/{session_info_dict.get('WeekendInfo',{}).get('SessionLaps', 'N/A') if session_info_dict else 'N/A'}"
                )
            )

            # CamDriver - focus on player car using info from session_info_dict if possible
            current_player_driver_info = None
            if session_info_dict and player_car_idx_sample is not None:
                sdk_drivers_list = session_info_dict.get('DriverInfo', {}).get('Drivers', [])
                player_info_from_session = next((d for d in sdk_drivers_list if d.get('CarIdx') == player_car_idx_sample), None)
                if player_info_from_session:
                    current_player_driver_info = Driver(
                        car_number=player_info_from_session.get('CarNumber', str(player_car_idx_sample)),
                        user_name=player_info_from_session.get('UserName', f"PlayerCar_{player_car_idx_sample}"),
                        car_idx=player_car_idx_sample
                        # position and pit_stop_count would come from live telemetry ideally
                    )
            if not current_player_driver_info and player_car_idx_sample is not None: # Fallback
                current_player_driver_info = Driver(car_number=str(player_car_idx_sample), user_name=f"PlayerCar_{player_car_idx_sample}", car_idx=player_car_idx_sample)

            if current_player_driver_info:
                overlay_data.cam_drivers.append(
                    CamDriver(start_time=current_session_time,
                              cam_group_number=data_sample.get('CamCameraNumber', 1), # Use SDK CamCameraNumber if available
                              current_driver=current_player_driver_info)
                )

            # MessageState (example: every 30s of session time)
            if int(current_session_time) % 30 == 0 and \
               (len(overlay_data.message_states) == 0 or
                abs(overlay_data.message_states[-1].time - current_session_time) > 1.0): # Avoid multiple per second
                overlay_data.message_states.append(
                    MessageState(time=current_session_time, messages=[f"Live Update: {current_session_time:.1f}s"])
                )

            # FastLap (simplified: if LapLastLapTime is valid and new overall best)
            last_lap_time_sample = data_sample.get('LapLastLapTime')
            if last_lap_time_sample is not None and last_lap_time_sample > 0:
                is_new_fastest = not overlay_data.fastest_laps or \
                                 last_lap_time_sample < min(fl.lap_time for fl in overlay_data.fastest_laps)
                if is_new_fastest and current_player_driver_info:
                    overlay_data.fastest_laps.append(
                        FastLap(start_time=current_session_time, driver=current_player_driver_info, lap_time=float(last_lap_time_sample))
                    )
                    print(f"  New fastest lap recorded: {last_lap_time_sample:.3f}s at session time {current_session_time:.2f}s")

            # Incident Processing (periodically)
            if current_session_time - last_incident_check_session_time >= incident_check_interval_seconds:
                new_incidents = self.iracing_manager.get_incidents(0, 0) # Params not used by basic version
                for inc_dict in new_incidents:
                    overlay_data.race_events.append(
                        RaceEvent(
                            start_time=inc_dict.get('session_time', current_session_time),
                            end_time=inc_dict.get('session_time', current_session_time) + 1.0, # Arbitrary 1s duration
                            interest='PlayerIncident', # From basic get_incidents
                            with_overtake=False, # Cannot determine from basic incident count
                            # position, race_lap_number could be added if available in data_sample
                        )
                    )
                last_incident_check_session_time = current_session_time

            if loop_iterations % 120 == 0:
                print(f"  Analysis loop progress: SessionTime={current_session_time:.2f}s")

        print("Main data analysis loop finished.")
        if self.iracing_manager.is_connected(): # Check before sending command
            self.iracing_manager.replay_set_speed(0) # Pause replay after analysis
            time.sleep(0.5) # Allow SDK to process pause command

        # Saving OverlayData
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

    # Using PlaceholderIRacingManager from iracing_manager (assuming it's in PYTHONPATH or same dir for demo)
    # If not, we'd need to define a local mock here. For this structure, let's assume it can be imported.
    try:
        from .iracing_manager import PlaceholderIRacingManager
    except ImportError: # Fallback if running script directly and imports don't resolve
        print("Could not import PlaceholderIRacingManager, defining a local mock for demo.")
        class PlaceholderIRacingManager: # type: ignore
            def focus_iracing_window(self): print("MOCK IRM: focus_iracing_window()")
            def replay_move_to_frame(self, fn): print(f"MOCK IRM: replay_move_to_frame({fn})")
            def replay_set_speed(self, sp): print(f"MOCK IRM: replay_set_speed({sp})")

    mock_settings = MockAppSettings()
    mock_iracing_manager = PlaceholderIRacingManager()

    # 2. Create ReplayAnalyzer instance
    analyzer = ReplayAnalyzer(iracing_manager=mock_iracing_manager, settings=mock_settings)

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

        print("\n--- Generated XML content (first few lines) ---")
        with open(output_xml_path, 'r', encoding='utf-8') as f:
            for _ in range(10): # Print first 10 lines
                line = f.readline()
                if not line: break
                print(line.strip())
        print("--------------------------------------------")


        # 5. Clean up (optional, but good for tests)
        try:
            print(f"\nCleaning up generated files in {mock_settings.working_folder}...")
            output_xml_path.unlink()
            json_path_actual.unlink()
            # Attempt to remove the directory if empty
            # It might fail if other hidden files are present or due to timing
            try:
                mock_settings.working_folder.rmdir()
                print(f"Removed directory: {mock_settings.working_folder}")
            except OSError:
                print(f"Directory {mock_settings.working_folder} not empty or couldn't be removed (this is okay for demo).")

        except Exception as e:
            print(f"Error during cleanup: {e}")
    else:
        print("\nAnalysis did not complete or was aborted.")

    print("\nReplayAnalyzer Demonstration finished.")

```
