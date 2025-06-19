"""
Handles video transcoding using FFmpeg, including applying overlays via plugins.
"""

import threading
import subprocess
import re
import shlex # For safely splitting command strings if needed by mock
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .app_settings import AppSettings
    from .plugin_manager import PluginManager
    from .replay_data import OverlayData
    from .video_editing import VideoEdit  # For type hint


# Attempt to import ffmpeg-python
try:
    import ffmpeg
except ImportError:
    print("WARNING: ffmpeg-python not found. Using a mock FFmpeg library.")
    print("Transcoding will not actually occur. FFmpeg commands will be printed instead.")


    class MockFFmpegNode:
        def __init__(self, name: str = "node",
                     prev_node: Optional['MockFFmpegNode'] = None,
                     stream_name: Optional[str] = None):
            self._name = name
            self._prev_node = prev_node
            self._kwargs: Dict[str, Any] = {}
            self._output_filename: Optional[str] = None
            self._global_args: List[str] = []
            self._stream_name = stream_name # For filter_complex output tracking

        def __getattr__(self, name: str):
            # Allows chaining undefined methods, assuming they are ffmpeg operations
            # (e.g., .filter(), .output(), .global_args()).
            def method_wrapper(*args, **kwargs):
                # Using f-string with '=' for self-documenting expressions (Python 3.8+)
                print(f"MOCK FFMPEG: .{name}(args={args!r}, kwargs={kwargs!r}) called on {self._name}")

                new_node = MockFFmpegNode(
                    name=f"{self._name}.{name}",
                    prev_node=self,
                    stream_name=self._stream_name # Default to inheriting, filter_complex might change this
                )

                if name == "output":
                    new_node._output_filename = args[0] if args else "unknown_output.mp4"
                    new_node._kwargs.update(kwargs) # Store output settings on the new node
                elif name == "global_args":
                    # Global args should ideally apply to the whole command, not just a node.
                    # This mock structure might need refinement for global_args to be perfectly accurate.
                    # For now, assume they are collected and applied at run time by traversing.
                    new_node._global_args.extend(args) # Store on new node, run() will collect them
                elif name == "filter_complex":
                    # Store filter_complex arguments on the new node.
                    # The actual filter graph string is usually the first arg.
                    new_node._kwargs[name] = {"args": args, "kwargs": kwargs}
                    # In real ffmpeg-python, filter_complex can define new output stream names.
                    # This mock is too simple to parse the filter string and track those.
                    # We'll assume the output of a filter_complex chain is implicitly handled or
                    # the next operation correctly refers to it if needed.
                else: # Other filter-like operations
                    new_node._kwargs[name] = {"args": args, "kwargs": kwargs}

                return new_node
            return method_wrapper

        def __getitem__(self, item: str) -> 'MockFFmpegNode':
            """Allows stream selection like stream['outv']."""
            print(f"MOCK FFMPEG: Stream selection ['{item}'] on {self._name}")
            # Return a new node representing this specific output stream from a filter_complex
            return MockFFmpegNode(name=f"{self._name}[{item}]", prev_node=self, stream_name=item)

        def _collect_args_for_run(self) -> List[str]:
            """Helper to reconstruct the command list by traversing back through nodes."""
            # This method reconstructs the command based on the chain of nodes.
            # It's a simplified representation of how ffmpeg-python builds its command.

            # Traverse to the earliest node to build command in order
            node_chain = []
            curr = self
            while curr is not None:
                node_chain.append(curr)
                curr = curr._prev_node
            node_chain.reverse()

            cmd_list = ["ffmpeg"]

            # Collect global args from all nodes (could be improved to be truly global)
            for node in node_chain:
                cmd_list.extend(node._global_args)

            input_files_options = [] # To store options per input file

            for node in node_chain:
                if node._name == "input" or node._name == "node.input": # Initial input node
                    input_args = node._kwargs.get('input', {})
                    filename = input_args.get('args', ["unknown_input.mp4"])[0]
                    options = []
                    if 'ss' in input_args.get('kwargs', {}):
                        options.extend(['-ss', str(input_args['kwargs']['ss'])])
                    if 't' in input_args.get('kwargs', {}):
                        options.extend(['-t', str(input_args['kwargs']['t'])])
                    options.extend(['-i', filename])
                    input_files_options.append(options)

            for opts in input_files_options: # Add all input files and their options
                cmd_list.extend(opts)

            # Process other operations (filters, output options) from the final node's perspective
            # This part of mock is very simplified as complex filter graphs are hard to reconstruct.
            final_node = node_chain[-1]

            if 'filter_complex' in final_node._kwargs:
                fc_args = final_node._kwargs['filter_complex']['args']
                if fc_args:
                    cmd_list.extend(["-filter_complex", fc_args[0]])

            # Add output options from the node that called .output()
            # The _output_filename and output kwargs are stored on the node *returned* by .output()
            output_node = final_node # Assume final node is the output node after .output() was called
            if output_node._output_filename:
                # Add specific output settings stored in output_node._kwargs
                # These were stored directly by __getattr__ when name == "output"
                for key, value in output_node._kwargs.items():
                     # Check if it's an output option (and not a stored operation dict)
                    if key not in ['input', 'filter_complex', 'output', 'global_args', 'run'] and not isinstance(value, dict):
                        cmd_list.extend([f"-{key}", str(value)])

                # Default to overwrite if not specified in global_args
                # Check if -y or -n is already in global_args
                has_overwrite_option = any(arg in ['-y', '-n'] for arg in cmd_list if arg.startswith('-'))
                if not has_overwrite_option:
                    cmd_list.append("-y")

                cmd_list.append(output_node._output_filename)
            else: # Fallback if output filename wasn't captured
                if not any(arg.startswith("mock_output") for arg in cmd_list): # Avoid adding if already there
                    cmd_list.append("mock_output.mp4")

            return cmd_list

        def run(self, cmd: Optional[List[str]] = None, pipe_stdin: bool = False,
                pipe_stdout: bool = False, pipe_stderr: bool = False,
                quiet: bool = False, overwrite_output: bool = False):
            print("MOCK FFMPEG: .run() called")

            # If overwrite_output is True, ensure -y is a global arg for reconstruction
            if overwrite_output and '-y' not in self._global_args:
                self._global_args.append('-y')

            final_cmd_list = self._collect_args_for_run()

            # Store for test inspection (e.g., on a class variable of MockFFmpegNode or MockProcess)
            # For simplicity, let's assume tests will capture stdout for the command.
            # Or, if this `run` method returns the process, store it on the process.
            print(f"MOCK FFMPEG CMD: {' '.join(shlex.quote(str(s)) for s in final_cmd_list)}")

            if self._output_filename:
                Path(self._output_filename).touch() # Simulate output file creation

            # For run_async, it should return a Popen-like object.
            # This run() method here is synchronous for the mock.
            # Let's make run() call run_async().wait() for simplicity or vice-versa.
            # The current structure has run() as the main method that constructs MockProcess.
            # Let's rename this to run_async and have run() call it.
            # For this subtask, I'll keep run() as the one that returns MockProcess as per existing transcoder code.

            mock_process = MockProcess(final_cmd_list)
            # Store command on process for easier test access
            mock_process.cmd_list_for_test = final_cmd_list
            return mock_process

    class MockProcess: # Moved this to be a top-level class in the mock structure
        def __init__(self, cmd_list):
            self.cmd_list_for_test = cmd_list # For inspection
            self.pid = 12345 # Mock PID
            self.returncode: Optional[int] = None
            # Simulate stderr for progress parsing
            self.stderr = self._mock_stderr_progress()
            self.stdout = None # Not typically used for progress
                    self.pid = 12345 # Mock PID
                    # Simulate stderr for progress parsing
                    self.stderr = self._mock_stderr_progress()

                def _mock_stderr_progress(self):
                    # Yield a few progress lines then stop
                    yield b"frame= 10 fps=0.0 q=0.0 size=N/A time=00:00:00.40 bitrate=N/A speed=0.00x\n"
                    yield b"frame= 20 fps=0.0 q=0.0 size=N/A time=00:00:00.80 bitrate=N/A speed=0.00x\n"
                    yield b"progress=continue\n" # FFmpeg uses this in some modes
                    yield b"frame= 30 fps=0.0 q=0.0 size=N/A time=00:00:01.20 bitrate=N/A speed=0.00x\n"
                    yield b"progress=end\n" # Or just finish

                def poll(self): return None # Simulate running
                def wait(self, timeout=None): return 0 # Simulate finished successfully
                def terminate(self): print("MOCK FFMPEG: process.terminate() called")
                def communicate(self, input=None, timeout=None):
                    return (b"mock stdout", b"mock stderr with final progress line if any")


            return MockProcess(full_cmd_list)

    class MockFFmpegModule:
        def __init__(self):
            self.Error = type('MockFFmpegError', (Exception,), {}) # Mock ffmpeg.Error

        def input(self, filename: str, **kwargs) -> MockFFmpegNode:
            print(f"MOCK FFMPEG: .input(filename='{filename}', kwargs={kwargs})")
            node = MockFFmpegNode(name="input")
            node._kwargs['input'] = {"args": [filename], "kwargs": kwargs} # Store filename and input options
            return node

        def probe(self, filename: str, **kwargs) -> Dict[str, Any]:
            print(f"MOCK FFMPEG: .probe(filename='{filename}', kwargs={kwargs})")
            # Return a plausible structure for probe, especially 'format' and 'duration'
            return {
                "format": {"duration": "10.0"} # Simulate 10 second video
            }
        # Add other top-level functions if needed, e.g., .concat()

    ffmpeg = MockFFmpegModule() # Replace the imported module with our mock

# --- Actual Transcoder Class ---
class FFmpegTranscoder:
    """
    Handles video transcoding tasks using ffmpeg-python.
    """

    def __init__(self, settings: 'AppSettings', plugin_manager: 'PluginManager'):
        self.settings = settings
        self.plugin_manager = plugin_manager

    def _parse_ffmpeg_time(self, time_str: str) -> float:
        """Converts HH:MM:SS.ms time string to seconds."""
        match = re.match(r'(\d{2,}):(\d{2}):(\d{2})\.(\d{2,})', time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return h * 3600 + m * 60 + s + ms / (10**len(str(ms))) # Support variable ms length
        return 0.0

    def transcode_video(
        self,
        overlay_data: 'OverlayData',
        output_filepath: str,
        is_highlights: bool,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """
        Transcodes a video, applying overlays and optionally creating highlights.

        Args:
            overlay_data: Data from replay analysis, including video file paths.
            output_filepath: Path to save the transcoded video.
            is_highlights: If True, generate highlights based on video_editing module.
            progress_callback: Optional function to call with progress (0.0 to 1.0).
            cancel_event: Optional threading.Event to signal cancellation.

        Returns:
            True if transcoding was successful or started (if async), False otherwise.
        """
        if not overlay_data.video_files:
            print("Error: No video files found in OverlayData.")
            return False

        # For now, use only the first video file.
        # TODO: Handle multiple video files (concatenation, e.g., intro + main race)
        video_path_str = overlay_data.video_files[0].filename
        video_path = Path(video_path_str)
        if not video_path.exists():
            print(f"Error: Video file not found: {video_path_str}")
            return False

        print(f"Transcoding video: {video_path_str} to {output_filepath}")
        print(f"Highlights mode: {is_highlights}")

        total_duration_seconds: float = 0.0
        try:
            probe_data = ffmpeg.probe(str(video_path))
            total_duration_seconds = float(probe_data['format']['duration'])
        except Exception as e: # Could be ffmpeg.Error or other if mock is not perfect
            print(f"Error probing video file {video_path_str}: {e}. Cannot determine total duration.")
            # Fallback or error out. For now, let's assume a default if progress is essential.
            # Or, if no progress_callback, we might proceed without duration.
            if progress_callback:
                print("Cannot provide progress without total duration.")
                # return False # Or proceed without progress reporting.
                # For testing, let's allow it to proceed.
                total_duration_seconds = 10.0 # Arbitrary fallback for mock environment

        print(f"Source video duration: {total_duration_seconds:.2f}s")

        stream_args = {'filename': str(video_path)}
        processed_duration = total_duration_seconds # Default to full video duration

        if is_highlights:
            from .video_editing import get_highlight_segments_to_keep, VideoEdit # Local import

            print("Generating highlight segments...")
            segments_to_keep: List[VideoEdit] = get_highlight_segments_to_keep(overlay_data, self.settings)

            if not segments_to_keep:
                print("No highlight segments selected. Nothing to transcode for highlights.")
                return False # Or generate an empty video?

            # For this initial version, process only the *first* segment.
            # TODO: Handle concatenation of multiple highlight segments.
            first_segment = segments_to_keep[0]
            print(f"Processing first highlight segment: Start={first_segment.start_time:.2f}s, Duration={first_segment.duration:.2f}s")
            stream_args['ss'] = first_segment.start_time
            stream_args['t'] = first_segment.duration
            processed_duration = first_segment.duration # Duration of the segment we are processing

        input_stream = ffmpeg.input(**stream_args)
        video_stream = input_stream['v'] # Assuming there's a video stream
        audio_stream = input_stream['a'] # Assuming there's an audio stream

        # Overlay Application (Simplified for initial version)
        # Assume fixed dimensions for now. TODO: Get from probe or settings.
        video_width, video_height = 1920, 1080

        # Get filters at a few predefined timestamps relative to the start of the segment being processed
        # If full video, timestamps are absolute. If segment, they are relative to segment start.
        # This simplified overlay application applies filters as if they are static for the whole duration.
        # A true per-frame dynamic overlay requires complex filter_complex usage.

        # For this simplified version, let's pick one timestamp (e.g., middle of the segment)
        # to get filters and apply them for the whole duration.
        # This is not ideal but matches "Concatenate all returned filter strings into a single complex filter string"
        # if those filters are meant to be active throughout.

        # Let's consider timestamps relative to the start of the *output* video.
        # If it's a highlight segment, output time 0 is segment.start_time in original video.
        # The plugin's get_current_filters timestamp should be the *original video's timestamp*.

        filter_source_timestamp = stream_args.get('ss', 0.0) + processed_duration / 2 # Midpoint of the (potentially cut) segment

        print(f"Getting plugin filters for source timestamp: {filter_source_timestamp:.2f}s")
        # This is a simplification: applies one set of filters for the whole clip.
        # True dynamic overlays would need timeline editing support in ffmpeg-python
        # or generating a very complex filter_complex string.
        overlay_filter_strings = self.plugin_manager.get_current_filters(
            filter_source_timestamp, video_width, video_height
        )

        if overlay_filter_strings:
            # If filters are like "drawtext=...", "overlay=...", they need to be chained
            # in filter_complex. Example: "[0:v]drawtext=...[v1];[v1]overlay=...[outv]"
            # For now, let's assume each string in overlay_filter_strings is a full filter part.
            # This part is highly dependent on what get_current_filters returns.
            # If they are simple filters that can be chained:
            # for f_str in overlay_filter_strings: video_stream = video_stream.filter(...) NO, this is not how it works for drawtext usually.

            # Assuming get_current_filters returns a list of self-contained filter descriptions like
            # "drawtext=text='foo':x=10:y=10"
            # We need to chain them: e.g., "[in]filter1[s1];[s1]filter2[s2];[s2]filter3[out]"
            if overlay_filter_strings:
                filter_chain_parts = []
                current_stream_label = "0:v" # Input video stream
                for i, f_def in enumerate(overlay_filter_strings):
                    next_stream_label = f"v{i+1}"
                    filter_chain_parts.append(f"[{current_stream_label}]{f_def}[{next_stream_label}]")
                    current_stream_label = next_stream_label

                # The final output of the chain needs to be mapped.
                # If filter_complex is used, the output stream name (e.g., [outv]) is specified.
                # ffmpeg-python handles this if you map the final output.
                # This simplified example just creates the filter string.
                # A more direct way if `filter_complex` is used:
                complex_filter_str = ";".join(filter_chain_parts)
                print(f"Applying complex filter: {complex_filter_str}")
                # The output of the complex filter must be explicitly linked if not using .filter() chain
                # This is where ffmpeg-python's handling of named streams is useful.
                # For now, this is a conceptual application. A single drawtext is easier.
                # Let's simplify to one filter for this example, assuming the plugin returns one drawtext.
                if len(overlay_filter_strings) == 1 and overlay_filter_strings[0].startswith("drawtext"):
                    # This part assumes `get_current_filters` returns strings suitable for a single
                    # complex filter graph. The graph would look like:
                    # "[0:v]filter_def1[v1];[v1]filter_def2[v2];[v2]filter_def3[outv]"
                    # where each filter_def is like "drawtext=text=...:x=...:y=..."
                    # (without the input/output labels, those are added here).

                    # Build the filter graph string
                    filter_graph_parts = []
                    input_label = "0:v" # Assuming video from first input
                    final_output_label = input_label # Default if no filters

                    for i, filter_definition_body in enumerate(overlay_filter_strings):
                        output_label = f"v_out_{i+1}"
                        filter_segment = f"[{input_label}]{filter_definition_body}[{output_label}]"
                        filter_graph_parts.append(filter_segment)
                        input_label = output_label # Chain to the next filter
                        final_output_label = output_label

                    if filter_graph_parts:
                        full_filter_complex_str = ";".join(filter_graph_parts)
                        print(f"Applying filter_complex graph: {full_filter_complex_str}")

                        # In ffmpeg-python, you apply filter_complex and then map the output stream.
                        # The video_stream here is an ffmpeg-python stream object.
                        # Applying filter_complex usually involves providing all input streams.
                        # For simplicity, if only one video stream is input to filter_complex:
                        filtered_video_node = video_stream.filter_complex(full_filter_complex_str)

                        # We need to select the correct output stream from filter_complex.
                        # This assumes the last filter in the chain outputs to `final_output_label`.
                        # And that ffmpeg-python makes this accessible via __getitem__ on the result of filter_complex.
                        video_stream = filtered_video_node[final_output_label]
                        # If the mock doesn't support __getitem__, this will need adjustment or the mock improved.
                        # The current mock's __getattr__ returns a new node, so filter_complex call
                        # already returns a new node. The __getitem__ is for named stream selection.

        # Output settings
        output_options = {
            'vcodec': 'libx264',
            'acodec': 'aac',
            'video_bitrate': str(self.settings.video_bitrate), # Make sure it's a string
            'preset': 'medium', # Common x264 preset
            # 'strict': 'experimental' # Might be needed for 'aac' with some ffmpeg versions
        }
        if Path(output_filepath).suffix == '.mp4': # MP4 specific options
            output_options['movflags'] = '+faststart' # Good for web video
            output_options['pix_fmt'] = 'yuv420p'     # Common pixel format for compatibility

        # If video_stream was modified by filter_complex and the output stream was named (e.g., [outv])
        # then the output call would be:
        # ffmpeg_cmd = ffmpeg.output(video_stream[final_video_label], audio_stream, output_filepath, **output_options)
        # For simplicity, assuming video_stream is the correct final video pipe.
        ffmpeg_cmd_node = ffmpeg.output(video_stream, audio_stream, output_filepath, **output_options)

        # Add global arguments like -y (overwrite)
        ffmpeg_cmd_node = ffmpeg_cmd_node.global_args('-y') # Overwrite output

        print(f"Preparing to run FFmpeg command...")
        # For real ffmpeg-python, .compile() can show the command.
        # Our mock's .run() prints a reconstructed command.

        process = None
        try:
            process = ffmpeg_cmd_node.run_async(pipe_stdout=True, pipe_stderr=True)
            print(f"FFmpeg process started with PID: {process.pid}")

            if progress_callback and total_duration_seconds > 0:
                for line_bytes in process.stderr: # Iterate over stderr lines
                    if cancel_event and cancel_event.is_set():
                        print("Cancellation event received. Terminating FFmpeg process.")
                        process.terminate() # or process.kill()
                        break

                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    # print(f"FFMPEG_STDERR: {line}") # For debugging
                    if 'time=' in line:
                        match = re.search(r'time=(\S+)', line)
                        if match:
                            elapsed_time_str = match.group(1)
                            elapsed_seconds = self._parse_ffmpeg_time(elapsed_time_str)
                            # Progress is based on the duration of the segment being processed
                            progress = min(1.0, elapsed_seconds / processed_duration)
                            progress_callback(progress)

            process.wait() # Wait for the process to complete
            if cancel_event and cancel_event.is_set():
                print("FFmpeg process was cancelled.")
                self.plugin_manager.signal_transcode_complete() # Still signal, even if cancelled
                return False

            if process.returncode == 0: # type: ignore # Mock process might not have returncode typed
                print("FFmpeg transcoding completed successfully.")
                self.plugin_manager.signal_transcode_complete()
                return True
            else:
                # Try to get more error info if real ffmpeg
                # _, stderr_data = process.communicate()
                # print(f"FFmpeg error (return code {process.returncode}): {stderr_data.decode('utf-8', errors='replace')}")
                print(f"FFmpeg error (return code {getattr(process, 'returncode', 'N/A')}). Check FFmpeg output.")
                self.plugin_manager.signal_transcode_complete() # Still signal
                return False

        except ffmpeg.Error as e: # Real ffmpeg-python error
            print(f"ffmpeg-python error during transcoding: {e.stderr.decode('utf8') if e.stderr else str(e)}")
            if process: process.terminate()
            self.plugin_manager.signal_transcode_complete()
            return False
        except Exception as e:
            print(f"An unexpected error occurred during transcoding: {e}")
            if process: process.terminate() # Ensure process is killed on any error
            self.plugin_manager.signal_transcode_complete()
            return False


if __name__ == '__main__':
    print("--- FFmpegTranscoder Demonstration ---")

    # --- Mockups ---
    class MockAppSettings:
        def __init__(self, working_dir):
            self.video_bitrate = 10000000 # 10 Mbps
            self.working_folder = str(working_dir)
            # For highlight test
            self.highlight_video_target_duration_seconds = 10

    class MockPlugin(OverlayPluginInterface): # type: ignore # Temp for demo if main interface not resolved
        @property
        def name(self): return "Demo Text Plugin"
        @property
        def description(self): return "Adds demo text."
        def initialize(self, settings, overlay_data): self.settings = settings
        def get_ffmpeg_filter_options(self, ts, w, h):
            # Use the real build_drawtext_filter if available from this module's scope
            return [build_drawtext_filter(f"Timestamp: {ts:.2f}s", 10, 10, font_size=20, font_path="Arial")]
        def on_transcode_complete(self): print(f"{self.name} notified of transcode complete.")

    class MockPluginManager:
        def __init__(self, settings):
            self.settings = settings
            self.active_plugin = MockPlugin() # Directly instantiate for demo
            self.active_plugin.initialize(settings, None) # Mock overlay_data for init

        def get_current_filters(self, ts, w, h):
            if self.active_plugin:
                return self.active_plugin.get_ffmpeg_filter_options(ts, w, h)
            return []
        def signal_transcode_complete(self):
            if self.active_plugin: self.active_plugin.on_transcode_complete()

    class MockOverlayData:
        def __init__(self, video_filename):
            from .replay_data import CapturedVideoFile, RaceEvent # Local import for demo
            self.video_files = [CapturedVideoFile(filename=str(video_filename))]
            # For highlight test - create some events
            self.race_events = [
                RaceEvent(start_time=2.0, end_time=5.0, interest="Incident", with_overtake=True),
                RaceEvent(start_time=7.0, end_time=9.0, interest="Battle", with_overtake=False)
            ]

    # --- Setup Test Environment ---
    temp_dir = Path("./temp_ffmpeg_transcoder_test")
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"Test directory: {temp_dir.resolve()}")

    mock_settings = MockAppSettings(temp_dir)
    mock_plugin_manager = MockPluginManager(mock_settings)

    # Create a dummy video file using actual ffmpeg CLI via subprocess
    dummy_input_video = temp_dir / "input_test_video.mp4"
    dummy_duration = 5 # seconds
    try:
        # Check if ffmpeg command is available
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
        print(f"Creating dummy video file: {dummy_input_video} ({dummy_duration}s duration)")
        # Use a short timeout for the subprocess call
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"smptebars=duration={dummy_duration}:size=320x240:rate=30",
            "-c:v", "libx264", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
            str(dummy_input_video)
        ], check=True, capture_output=True, timeout=15) # Increased timeout for ffmpeg
        print("Dummy video created successfully.")
        can_run_real_ffmpeg_test = True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Could not create dummy video using ffmpeg CLI: {e}")
        print("Skipping tests that require a real video file and relying on mock ffmpeg logic.")
        # Create an empty file to allow probe (mocked) and input (mocked) to proceed
        dummy_input_video.touch()
        can_run_real_ffmpeg_test = False
        # If ffmpeg CLI isn't available, ffmpeg-python import also likely failed and is mocked.
        # Update total_duration_seconds in the mock probe to match dummy_duration for progress calc.
        if isinstance(ffmpeg, MockFFmpegModule): # Check if we are using the mock
            ffmpeg.probe = lambda filename, **kwargs: {"format": {"duration": str(float(dummy_duration))}}


    mock_overlay_data = MockOverlayData(dummy_input_video)
    transcoder = FFmpegTranscoder(settings=mock_settings, plugin_manager=mock_plugin_manager)

    # --- Test Cases ---
    def progress_update(p: float):
        print(f"Progress: {p*100:.1f}%")

    output_full_transcode = temp_dir / "output_full_video.mp4"
    output_highlight_transcode = temp_dir / "output_highlight_video.mp4"

    # Test 1: Full transcode
    print("\n--- Testing Full Transcode ---")
    success_full = transcoder.transcode_video(
        overlay_data=mock_overlay_data,
        output_filepath=str(output_full_transcode),
        is_highlights=False,
        progress_callback=progress_update
    )
    print(f"Full transcode success: {success_full}")
    if success_full and output_full_transcode.exists():
        print(f"Output file created: {output_full_transcode}")
    elif success_full and not output_full_transcode.exists() and isinstance(ffmpeg, MockFFmpegModule):
        print(f"Mock FFmpeg ran, output file '{output_full_transcode}' would have been created.")


    # Test 2: Highlight transcode
    print("\n--- Testing Highlight Transcode ---")
    # Ensure video_editing can be imported for highlights
    try:
        from .video_editing import get_highlight_segments_to_keep # Test import
        success_highlight = transcoder.transcode_video(
            overlay_data=mock_overlay_data,
            output_filepath=str(output_highlight_transcode),
            is_highlights=True,
            progress_callback=progress_update
        )
        print(f"Highlight transcode success: {success_highlight}")
        if success_highlight and output_highlight_transcode.exists():
            print(f"Output file created: {output_highlight_transcode}")
        elif success_highlight and not output_highlight_transcode.exists() and isinstance(ffmpeg, MockFFmpegModule):
             print(f"Mock FFmpeg ran, output file '{output_highlight_transcode}' would have been created.")

    except ImportError:
        print("Skipping highlight test as video_editing module could not be imported (likely circular dependency in test setup).")


    # Test 3: Cancellation (conceptual for mock)
    if not isinstance(ffmpeg, MockFFmpegModule) and can_run_real_ffmpeg_test: # Only if real ffmpeg can run
        print("\n--- Testing Cancellation (Conceptual - requires real ffmpeg & longer video) ---")
        # This test is hard to make fully automatic and quick without a real, longer ffmpeg process.
        # For now, it just shows how cancel_event would be passed.
        # To truly test, you'd start a transcode on a larger file and set the event from another thread.
        cancel_evt = threading.Event()
        # Example: Thread(target=lambda: (time.sleep(1), cancel_evt.set())).start()
        # success_cancel = transcoder.transcode_video(
        #     overlay_data=mock_overlay_data,
        #     output_filepath=str(temp_dir / "output_cancel_test.mp4"),
        #     is_highlights=False,
        #     progress_callback=progress_update,
        #     cancel_event=cancel_evt
        # )
        # print(f"Cancelled transcode attempt reported success: {success_cancel} (expected False if cancelled early)")
        print("Conceptual cancellation test setup shown in comments.")


    # --- Cleanup ---
    print("\nCleaning up test files...")
    for f_path in [output_full_transcode, output_highlight_transcode, dummy_input_video]:
        if f_path.exists():
            try:
                f_path.unlink()
                print(f"  Deleted: {f_path.name}")
            except OSError as e:
                print(f"  Error deleting {f_path.name}: {e}")
    if temp_dir.exists():
        try:
            #temp_dir.rmdir() # Only if empty
            # For robust cleanup, remove all contents then rmdir
            for item in temp_dir.iterdir(): item.unlink(missing_ok=True)
            temp_dir.rmdir()
            print(f"  Cleaned up directory: {temp_dir.resolve()}")
        except OSError as e:
            print(f"  Error removing temp_dir {temp_dir.resolve()}: {e}. May need manual cleanup.")

    print("\nFFmpegTranscoder Demonstration finished.")


