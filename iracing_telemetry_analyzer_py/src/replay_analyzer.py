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

        print("Focusing iRacing window (simulated)...")
        self.iracing_manager.focus_iracing_window() # Placeholder call

        # Simulate Finding Race Start
        race_start_frame_number = 0  # Assuming race starts at frame 0 for now
        # race_start_session_time = 0.0 # Corresponding session time
        print(f"Moving replay to simulated race start (frame {race_start_frame_number})...")
        self.iracing_manager.replay_move_to_frame(race_start_frame_number) # Placeholder

        # Simulate Initial Incident Analysis (e.g., from a pre-scan or known incidents)
        print("Simulating initial incident scan...")
        overlay_data.race_events.append(
            RaceEvent(start_time=5.0, end_time=10.0, interest='Incident', with_overtake=False, position=3, race_lap_number=1)
        )
        overlay_data.race_events.append(
            RaceEvent(start_time=25.0, end_time=30.0, interest='Incident', with_overtake=True, position=1, race_lap_number=2)
        )

        # Race Situation Analysis Loop (Simulated Data Feed)
        print("Starting simulated race situation analysis loop...")
        # self.iracing_manager.replay_set_speed(16) # Conceptually, speed up replay

        simulated_duration_seconds = 100 # Virtual seconds for the loop
        samples_per_virtual_second = 2 # How many data points to generate per virtual second

        current_sample_time = 0.0
        for i in range(simulated_duration_seconds * samples_per_virtual_second):
            if abort_check():
                print("Analysis aborted by abort_check.")
                # self.iracing_manager.replay_set_speed(0) # Stop replay
                return None

            current_sample_time = i / samples_per_virtual_second # Increment time

            # Simulate Data Processing
            # Add LeaderBoardSnapshot
            drivers_lb = [
                Driver(car_number="22", user_name="Player One (Sim)", position=1, pit_stop_count=0),
                Driver(car_number="4", user_name="Player Two (Sim)", position=2, pit_stop_count=0),
                Driver(car_number="17", user_name="Player Three (Sim)", position=3, pit_stop_count=1),
            ]
            overlay_data.leader_boards.append(
                LeaderBoardSnapshot(
                    start_time=current_sample_time,
                    drivers=drivers_lb,
                    race_position="P1", # Example
                    lap_counter=f"Lap {1 + int(current_sample_time // 60)}/{simulated_duration_seconds // 60 + 1}" # Example
                )
            )

            # Add CamDriver
            if drivers_lb:
                overlay_data.cam_drivers.append(
                    CamDriver(start_time=current_sample_time, cam_group_number=1, current_driver=drivers_lb[0])
                )

            # Add MessageState
            if i % (10 * samples_per_virtual_second) == 0 : # Every 10 virtual seconds
                 overlay_data.message_states.append(
                    MessageState(time=current_sample_time, messages=[f"Commentary at {current_sample_time:.1f}s"])
                )

            # Add FastLap (conditionally)
            if i == (15 * samples_per_virtual_second): # At 15 virtual seconds
                if drivers_lb:
                    overlay_data.fastest_laps.append(
                        FastLap(start_time=current_sample_time, driver=drivers_lb[0], lap_time=75.5)
                    )

            # Add generic RaceEvent (e.g., for general info or non-critical events)
            overlay_data.race_events.append(
                RaceEvent(start_time=current_sample_time, end_time=current_sample_time + 0.5, interest='GenericInfo', with_overtake=False)
            )

            # Simulate time passing for the loop iteration itself (not for replay time)
            # time.sleep(0.001) # Keep this very short or remove if simulation is primary goal

            if i % (20 * samples_per_virtual_second) == 0: # Print progress every 20 virtual seconds
                print(f"  Analysis loop progress: {current_sample_time:.1f} / {simulated_duration_seconds:.1f} virtual seconds")


        # self.iracing_manager.replay_set_speed(0) # Stop replay
        print("Simulated analysis loop finished.")

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
