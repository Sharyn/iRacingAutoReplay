import pyirsdk
import time

print(f"pyirsdk version: {getattr(pyirsdk, '__version__', 'unknown')}")
print(f"dir(pyirsdk): {dir(pyirsdk)}")

ir_sdk = None
try:
    print("Attempting to instantiate pyirsdk.IRSDK()...")
    # Common instantiation patterns might be pyirsdk.IRSDK() or pyirsdk.Client()
    # Trying with IRSDK() as it's a common name for iRacing SDK objects.
    ir_sdk = pyirsdk.IRSDK()
    print("Successfully instantiated pyirsdk.IRSDK()")
    print(f"Type of ir_sdk object: {type(ir_sdk)}")
    print(f"dir(ir_sdk) before check_iracing/startup: {dir(ir_sdk)}")

    # Try to check if iRacing is running/connected
    # Common methods: is_connected, is_initialized, check_iracing, status
    # Common attributes: connected, status
    # Based on some public examples, `check_iracing()` might be a thing,
    # and data might be available as attributes after this or via ir_sdk['VarName']

    is_active = False
    # pyirsdk's main interaction point is the IRSDK object.
    # It typically tries to connect to the sim when instantiated or when startup() is called.
    # The status of the connection is often checked by looking at specific variables
    # that only get populated if the sim is running.

    # According to pyirsdk documentation/examples, startup() initializes the link
    # and returns True if successful.
    if hasattr(ir_sdk, 'startup'):
        print("Calling ir_sdk.startup()...")
        is_active = ir_sdk.startup(test_file=None, dump_to=None) # test_file for offline testing
        print(f"ir_sdk.startup() returned: {is_active}")
    else:
        print("Could not find ir_sdk.startup(). Trying to check status vars directly.")
        # If startup() isn't the way, check for a status variable directly.
        # Often, attempting to access a variable like 'SessionTime' would fail or return None/default
        # if not connected.
        # Some SDKs have an explicit ir_sdk.is_connected property/method.
        # pyirsdk updates its internal state, and you access variables like ir_sdk['SessionTime']
        # Let's assume if startup() was successful, it's "active".
        # If iRacing is not running, startup() should return False or ir_sdk values will be defaults.
        # A common check is `if ir_sdk['is_initialized'] and ir_sdk['is_connected']` but these are vars.
        # For pyirsdk, the result of startup() is the primary indicator initially.
        # If startup() is False, then values like ir_sdk['SessionTime'] will typically be their default (e.g. 0 or None).
        # The library itself handles the memory mapping.

    if is_active:
        print("SDK seems active (iRacing is likely running and data is available).")

        # Wait for a moment for data to be available if needed by the SDK
        # time.sleep(0.1) # May not be needed if startup() blocks until ready or data is polled

        print("Attempting to access common telemetry variables...")
        # Common telemetry variables
        vars_to_check = [
            'SessionTime', 'ReplayFrameNum', 'IsReplayPlaying',
            'PlayerCarIdx', 'Speed', 'RPM', 'Gear',
            'WeekendInfo', 'SessionInfo', 'CameraInfo', 'CarSetup' # Some common session/setup data keys
        ]
        telemetry_data = {}
        for var in vars_to_check:
            try:
                # pyirsdk uses dictionary-like access for telemetry variables
                telemetry_data[var] = ir_sdk[var]
            except Exception as e_var:
                telemetry_data[var] = f'Error accessing {var}: {e_var}'
        print(f"Sample Telemetry & Session Data Keys Access: {telemetry_data}")

        # Specifically for SessionInfo, which is often a large YAML or JSON string
        if 'SessionInfo' in telemetry_data and not isinstance(telemetry_data['SessionInfo'], str):
             # If it's not an error string, it means it was accessed.
             # It's usually a large YAML string that pyirsdk parses into a dict.
            session_info_dict = telemetry_data['SessionInfo']
            if session_info_dict and hasattr(session_info_dict, 'get'):
                track_name = session_info_dict.get('WeekendInfo', {}).get('TrackDisplayName', 'N/A')
                print(f"Track Name from SessionInfo: {track_name}")
                print(f"SessionInfo dict (first few keys): {{ {', '.join(list(session_info_dict.keys())[:5])}... }}")
            else:
                print(f"SessionInfo was accessed but not a dict as expected: {type(session_info_dict)}")

        # Replay control methods
        # pyirsdk uses broadcast_msg for replay control.
        # Example: ir_sdk.broadcast_msg(pyirsdk.BroadcastMsg.REPLAY_SET_PLAY_SPEED, 1, 0) # speed, unused, unused
        # Example: ir_sdk.broadcast_msg(pyirsdk.BroadcastMsg.REPLAY_SEARCH, pyirsdk.ReplaySearchMode.TO_FRAME, frame_num)
        if hasattr(pyirsdk, 'BroadcastMsg') and hasattr(ir_sdk, 'broadcast_msg'):
            print("Found replay control capabilities (broadcast_msg).")
            print(f"  Example: pyirsdk.BroadcastMsg.REPLAY_SET_PLAY_SPEED = {pyirsdk.BroadcastMsg.REPLAY_SET_PLAY_SPEED}")
            print(f"  Example: pyirsdk.ReplaySearchMode.TO_FRAME = {pyirsdk.ReplaySearchMode.TO_FRAME}")
        else:
            print("Could not find replay control capabilities (broadcast_msg).")

    else:
        print("SDK does not seem active. iRacing is likely not running or data is not available.")
        print("This is expected if iRacing is not running in the execution environment.")

except Exception as e:
    print(f"An error occurred during pyirsdk exploration: {e}")
finally:
    if ir_sdk and hasattr(ir_sdk, 'shutdown'):
        print("Attempting to call ir_sdk.shutdown()...")
        ir_sdk.shutdown()
        print("ir_sdk.shutdown() called.")
    elif ir_sdk and hasattr(ir_sdk, 'close'): # Some SDKs use close()
        print("Attempting to call ir_sdk.close()...")
        ir_sdk.close()
        print("ir_sdk.close() called.")

```
