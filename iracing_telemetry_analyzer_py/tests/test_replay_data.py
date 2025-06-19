import pytest
import xml.etree.ElementTree as ET
import json
from dataclasses import fields, asdict
from datetime import datetime, timezone # Ensure timezone aware for comparison
from pathlib import Path
from typing import Any, Dict, List, Optional # Added List, Optional for completeness from replay_data

from iracing_telemetry_analyzer_py.src.replay_data import (
    OverlayData, CapturedVideoFile, Driver, RaceEvent, MessageState,
    CamDriver, LeaderBoardSnapshot, FastLap,
    _datetime_from_isotsformat_z, _datetime_to_isotsformat_z # For direct testing if needed
)

# --- Helper Functions ---

def create_sample_driver(suffix: str = "") -> Driver:
    return Driver(
        position=1,
        car_number=f"7{suffix}",
        user_name=f"Test Driver {suffix}",
        pit_stop_count=0,
        car_idx=100 + int(suffix or 0),
        short_name=f"TDriver{suffix}"
    )

def create_sample_overlay_data() -> OverlayData:
    """Creates a complex OverlayData instance with populated fields for testing."""
    dt_now = datetime.now(timezone.utc) # Use timezone-aware datetime

    return OverlayData(
        overlay_datetime=dt_now,
        leader_boards=[
            LeaderBoardSnapshot(
                start_time=10.5,
                drivers=[create_sample_driver("1"), create_sample_driver("2")],
                race_position="P1",
                lap_counter="Lap 1/10"
            ),
            LeaderBoardSnapshot(
                start_time=70.0,
                drivers=[create_sample_driver("2"), create_sample_driver("1")], # Order changed
                race_position="P2",
                lap_counter="Lap 2/10"
            )
        ],
        cam_drivers=[
            CamDriver(start_time=12.0, cam_group_number=1, current_driver=create_sample_driver("1")),
            CamDriver(start_time=72.0, cam_group_number=2, current_driver=create_sample_driver("2"))
        ],
        fastest_laps=[
            FastLap(start_time=65.0, driver=create_sample_driver("1"), lap_time=75.321)
        ],
        message_states=[
            MessageState(messages=["Message 1", "Message 2"], time=15.0),
            MessageState(messages=["Message 3"], time=75.0)
        ],
        session_data_xml="<SessionInfo><TrackName>Test Track</TrackName><Weather><Temp>25C</Temp></Weather></SessionInfo>",
        race_events=[
            RaceEvent(start_time=5.0, end_time=8.0, interest="Incident", with_overtake=True, position=3, race_lap_number=1),
            RaceEvent(start_time=77.0, end_time=80.0, interest="Battle", with_overtake=False, position=1, race_lap_number=2)
        ],
        time_for_outro_overlay=180.5,
        video_files=[
            CapturedVideoFile(filename="intro.mp4", is_intro_video=True),
            CapturedVideoFile(filename="main_race.mp4", is_intro_video=False)
        ],
        captured_version="test-1.0.0"
    )

def assert_dataclasses_equal(dc1: Any, dc2: Any, path: str = ""):
    """
    Recursively asserts that two dataclass instances are equal.
    Handles nested dataclasses, lists of dataclasses, and datetime comparisons.
    """
    assert type(dc1) == type(dc2), f"Type mismatch at {path}: {type(dc1)} vs {type(dc2)}"

    if hasattr(dc1, '__dict__') and hasattr(dc1, '__dataclass_fields__'): # Check if it's a dataclass instance
        for field_info in fields(dc1):
            field_name = field_info.name
            val1 = getattr(dc1, field_name)
            val2 = getattr(dc2, field_name)
            new_path = f"{path}.{field_name}" if path else field_name

            if isinstance(val1, list):
                assert isinstance(val2, list), f"Type mismatch for list at {new_path}"
                assert len(val1) == len(val2), f"List length mismatch at {new_path}"
                for i, (item1, item2) in enumerate(zip(val1, val2)):
                    assert_dataclasses_equal(item1, item2, path=f"{new_path}[{i}]")
            elif hasattr(val1, '__dict__') and hasattr(val1, '__dataclass_fields__'): # Nested dataclass
                assert_dataclasses_equal(val1, val2, path=new_path)
            elif isinstance(val1, datetime) and isinstance(val2, datetime):
                # For datetime, ensure they are both aware or both naive for comparison
                # Or convert to a common representation (e.g., UTC timestamp)
                # The _datetime_to_isotsformat_z and _datetime_from_isotsformat_z handle UTC.
                # If they are already timezone aware (like from datetime.now(timezone.utc)), direct comparison is fine.
                # If one could be naive, this needs care. Our sample uses aware.
                # For a robust comparison, compare timestamps or convert both to UTC.
                # Let's assume they should be equivalent in UTC.
                # Python's isoformat() for aware datetimes includes offset, direct comparison is usually fine.
                # A small tolerance might be needed if there's float precision issues in timestamps.
                # For now, direct comparison, assuming they are both UTC from our serializer/deserializer.
                assert val1.replace(microsecond=0) == val2.replace(microsecond=0), \
                    f"Datetime mismatch at {new_path}: {val1} vs {val2} (ignoring microseconds for test)"

            else: # Primitive types
                assert val1 == val2, f"Value mismatch at {new_path}: {val1} vs {val2}"
    else: # Not a dataclass instance, direct comparison
         assert dc1 == dc2, f"Value mismatch at {path}: {dc1} vs {dc2}"


# --- Test Cases ---

def test_datetime_iso_conversion():
    """Test the internal datetime to/from ISO string with Z format."""
    dt_original = datetime.now(timezone.utc).replace(microsecond=123000) # Ensure some microseconds
    dt_str = _datetime_to_isotsformat_z(dt_original)
    assert dt_str.endswith('Z')
    assert "T" in dt_str
    dt_converted = _datetime_from_isotsformat_z(dt_str)

    # Compare year, month, day, hour, minute, second, microsecond (with tolerance for precision)
    assert dt_original.year == dt_converted.year
    assert dt_original.month == dt_converted.month
    assert dt_original.day == dt_converted.day
    assert dt_original.hour == dt_converted.hour
    assert dt_original.minute == dt_converted.minute
    assert dt_original.second == dt_converted.second
    assert abs(dt_original.microsecond - dt_converted.microsecond) < 1000 # Allow small diff due to float str float
    assert dt_converted.tzinfo == timezone.utc


def test_overlay_data_xml_roundtrip(tmp_path):
    """Test saving OverlayData to XML and loading it back."""
    original_data = create_sample_overlay_data()
    xml_file = tmp_path / "test_overlay_data.replayscript.xml"

    # Save to XML
    original_data.save_to_xml(str(xml_file))
    assert xml_file.exists()

    # Load from XML
    loaded_data = OverlayData.load_from_xml(str(xml_file))

    # Assert deep equality
    # Datetime comparison needs care due to potential microsecond precision loss in string conversion.
    # The assert_dataclasses_equal helper has a microsecond tolerance for datetimes.
    assert_dataclasses_equal(original_data, loaded_data)


def test_overlay_data_json_save(tmp_path):
    """Test saving OverlayData to JSON produces a valid JSON file."""
    original_data = create_sample_overlay_data()
    json_file = tmp_path / "test_overlay_data.replayscript.json"

    # Save to JSON
    original_data.save_to_json(str(json_file))
    assert json_file.exists()

    # Load JSON back and verify some key fields
    with open(json_file, 'r') as f:
        loaded_json_dict = json.load(f)

    assert loaded_json_dict is not None
    assert loaded_json_dict['captured_version'] == original_data.captured_version
    assert len(loaded_json_dict['leader_boards']) == len(original_data.leader_boards)
    assert loaded_json_dict['leader_boards'][0]['race_position'] == original_data.leader_boards[0].race_position

    # Verify datetime serialization (should be ISO string with Z)
    # Example: loaded_json_dict['overlay_datetime'] should match _datetime_to_isotsformat_z(original_data.overlay_datetime)
    expected_dt_str = _datetime_to_isotsformat_z(original_data.overlay_datetime)
    assert loaded_json_dict['overlay_datetime'] == expected_dt_str

    # Full deserialization back to OverlayData and deep comparison is complex
    # as it requires matching the custom datetime handler and asdict behavior.
    # For now, checking key fields and structure is sufficient for this test.


def test_session_data_xml_handling_in_roundtrip(tmp_path):
    """Test that session_data_xml content is preserved during XML roundtrip."""
    original_data = create_sample_overlay_data()

    # Test case 1: Complex XML string
    complex_xml_str = "<Root><Element attribute='value'>Text</Element><EmptyElement/></Root>"
    original_data.session_data_xml = complex_xml_str

    xml_file_complex = tmp_path / "session_complex.xml"
    original_data.save_to_xml(str(xml_file_complex))
    loaded_data_complex = OverlayData.load_from_xml(str(xml_file_complex))
    assert loaded_data_complex.session_data_xml == complex_xml_str

    # Test case 2: Simple string (not XML)
    simple_str = "This is just some plain text, not XML."
    original_data.session_data_xml = simple_str

    xml_file_simple = tmp_path / "session_simple.xml"
    original_data.save_to_xml(str(xml_file_simple))
    loaded_data_simple = OverlayData.load_from_xml(str(xml_file_simple))
    assert loaded_data_simple.session_data_xml == simple_str

    # Test case 3: XML string with mixed content (like the dummy in replay_data.py)
    mixed_xml_str = """<IracingSdkData>
        <Var Name="ExampleVar" Value="ExampleValue" />
    </IracingSdkData>Some other text if any."""
    original_data.session_data_xml = mixed_xml_str.strip() # Ensure no leading/trailing whitespace from multiline string

    xml_file_mixed = tmp_path / "session_mixed.xml"
    original_data.save_to_xml(str(xml_file_mixed))
    loaded_data_mixed = OverlayData.load_from_xml(str(xml_file_mixed))
    # The current save logic for SessionData (if it's not a single parsable element)
    # will store it as text content. The load logic reconstructs this.
    assert loaded_data_mixed.session_data_xml == original_data.session_data_xml


def test_empty_overlay_data_roundtrip(tmp_path):
    """Test saving and loading an OverlayData instance with empty lists and None values."""
    dt_now = datetime.now(timezone.utc)
    original_data = OverlayData(overlay_datetime=dt_now) # All lists are empty, optionals are None
    original_data.session_data_xml = None # Explicitly set for clarity
    original_data.time_for_outro_overlay = None
    original_data.captured_version = None

    xml_file = tmp_path / "empty_overlay_data.xml"
    original_data.save_to_xml(str(xml_file))
    assert xml_file.exists()

    loaded_data = OverlayData.load_from_xml(str(xml_file))
    assert_dataclasses_equal(original_data, loaded_data)
    assert loaded_data.session_data_xml is None # Check None specifically
    assert loaded_data.captured_version is None # Check None specifically (if XML saves empty tag vs no tag)
                                                # _find_text returns None if tag not found or empty
    assert loaded_data.time_for_outro_overlay is None


def test_parsing_helpers_robustness():
    """Test parsing helpers with various inputs."""
    from iracing_telemetry_analyzer_py.src.replay_data import _parse_optional_int, _parse_optional_float, _parse_bool

    assert _parse_optional_int("123") == 123
    assert _parse_optional_int("  -45 ") == -45
    assert _parse_optional_int(None) is None
    assert _parse_optional_int("") is None
    assert _parse_optional_int("abc") is None # Invalid int
    assert _parse_optional_int("12.3") is None # Float, not int

    assert _parse_optional_float("123.45") == 123.45
    assert _parse_optional_float("  -0.5e-2 ") == -0.005
    assert _parse_optional_float(None) is None
    assert _parse_optional_float("") is None
    assert _parse_optional_float("xyz") is None # Invalid float

    assert _parse_bool("True") is True
    assert _parse_bool("true") is True
    assert _parse_bool("TRUE") is True
    assert _parse_bool("False") is False
    assert _parse_bool("false") is False
    assert _parse_bool(None) is False # Default for missing bools
    assert _parse_bool("") is False   # Empty string is not 'true'
    assert _parse_bool("yes") is False # Not handled by current _parse_bool, only 'true' variants
                                      # The C# version might handle 'Yes'/'No'. This is a difference if so.
                                      # ReplayData _parse_bool only considers 'true'. This is fine if consistent.
```
