import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
from datetime import datetime
import json
import re # For CDATA handling

# --- Helper Functions for XML Parsing/Building ---

def _parse_optional_int(value_str: Optional[str]) -> Optional[int]:
    if value_str is None or value_str.strip() == "":
        return None
    try:
        return int(value_str)
    except ValueError:
        return None

def _parse_optional_float(value_str: Optional[str]) -> Optional[float]:
    if value_str is None or value_str.strip() == "":
        return None
    try:
        return float(value_str)
    except ValueError:
        return None

def _parse_bool(value_str: Optional[str]) -> bool:
    if value_str is None:
        return False # Default for missing boolean elements/attributes
    return value_str.lower() == 'true'

def _datetime_from_isotsformat_z(dt_str: str) -> datetime:
    """
    Converts an ISO format string, potentially ending with 'Z', to a datetime object.
    The 'Z' (Zulu time) is replaced with '+00:00' for compatibility with
    datetime.fromisoformat prior to Python 3.11.
    """
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def _datetime_to_isotsformat_z(dt: datetime) -> str:
    """Converts a datetime object to an ISO format string, replacing '+00:00' with 'Z'."""
    return dt.isoformat().replace('+00:00', 'Z')


def _find_text(element: ET.Element, path: str, default: Optional[str] = None) -> Optional[str]:
    found = element.find(path)
    return found.text if found is not None and found.text is not None else default

def _find_all_as_list(element: ET.Element, path: str) -> List[ET.Element]:
    return list(element.findall(path))

def _add_sub_element(parent: ET.Element, name: str, value: Any, include_if_none: bool = False):
    if value is not None or include_if_none:
        val_str = ""
        if isinstance(value, bool):
            val_str = "True" if value else "False"
        elif isinstance(value, datetime):
            val_str = _datetime_to_isotsformat_z(value)
        elif value is not None: # For int, float, str
            val_str = str(value)

        # Only create element if value is not None, or if it's None but include_if_none is True
        if value is not None or (value is None and include_if_none):
             ET.SubElement(parent, name).text = val_str


# --- Data Classes ---

@dataclass
class CapturedVideoFile:
    filename: str
    is_intro_video: bool = False

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'CapturedVideoFile':
        return cls(
            filename=_find_text(element, 'Filename', ''),
            is_intro_video=_parse_bool(_find_text(element, 'IsIntroVideo'))
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, self.__class__.__name__)
        _add_sub_element(el, 'Filename', self.filename)
        _add_sub_element(el, 'IsIntroVideo', self.is_intro_video)

@dataclass
class Driver:
    car_number: str                 # In XML, usually <CarNumber> or an attribute.
    user_name: str                  # E.g., <UserName>.
    position: Optional[int] = None  # E.g., <Position>.
    pit_stop_count: int = 0         # E.g., <PitStopCount>.
    car_idx: Optional[int] = None   # Runtime data, not typically from XML.
    short_name: Optional[str] = None # Runtime data or derived, not typically from XML.

    # New fields for richer leaderboard information
    status: Optional[str] = None          # e.g., 'OnTrack', 'InPits', 'Finished', 'Out'
    current_lap: Optional[int] = None     # Current lap number for this driver
    lap_dist_pct: Optional[float] = None  # Percentage of current lap completed (0.0 to 1.0)
    best_lap_time: Optional[float] = None # Driver's best lap time in session
    last_lap_time: Optional[float] = None # Driver's last lap time
    class_position: Optional[int] = None  # Position within their car class

    # Note: In C#, Driver is often part of another class (e.g., LeaderBoardDriver).
    # The XML structure dictates parsing. This class assumes direct tags for now.

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'Driver':
        # This generic from_xml might need adaptation based on how Driver is
        # represented in different XML contexts (e.g., CamDriver vs LeaderBoard).
        return cls(
            position=_parse_optional_int(_find_text(element, 'Position')),
            car_number=_find_text(element, 'CarNumber', '0'),       # Default to '0' if missing.
            user_name=_find_text(element, 'UserName', 'Unknown'), # Default if missing.
            pit_stop_count=_parse_optional_int(_find_text(element, 'PitStopCount')) or 0,
            # car_idx and short_name are not typically expected from this XML structure.
        )

    def to_xml(self, parent_element: ET.Element, element_name: str = "Driver"):
        # Element name can be overridden (e.g., for CamDriver's <CurrentDriver>).
        el = ET.SubElement(parent_element, element_name)
        # Position is often included even if null/empty in C# XML serializations.
        _add_sub_element(el, 'Position', self.position, include_if_none=True)
        _add_sub_element(el, 'CarNumber', self.car_number)
        _add_sub_element(el, 'UserName', self.user_name)
        _add_sub_element(el, 'PitStopCount', self.pit_stop_count)
        # car_idx and short_name are not typically serialized for this structure.


@dataclass
class RaceEvent:
    start_time: float        # XML: <StartTime>
    end_time: float          # XML: <EndTime>
    interest: str            # XML: <Interest> (enum-like: "Incident", "Overtake", "Battle")
    with_overtake: bool      # XML: <WithOvertake>
    position: int = 9999     # XML: <Position> (Overall position at time of event, if applicable)
    race_lap_number: int = 0 # XML: <RaceLapNumber> (Lap number at time of event)

    # New fields for more detailed event description
    car_idx: Optional[int] = None         # Optional: Car index primarily involved or triggering the event
    other_car_idx: Optional[int] = None   # Optional: Car index of another car involved (e.g., in battle/overtake)
    details: Optional[str] = None         # Optional: Further text details about the event

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'RaceEvent':
        return cls(
            start_time=_parse_optional_float(_find_text(element, 'StartTime')) or 0.0,
            end_time=_parse_optional_float(_find_text(element, 'EndTime')) or 0.0,
            interest=_find_text(element, 'Interest', 'Generic'),
            with_overtake=_parse_bool(_find_text(element, 'WithOvertake')),
            position=_parse_optional_int(_find_text(element, 'Position')) or 9999,
            race_lap_number=_parse_optional_int(_find_text(element, 'RaceLapNumber')) or 0
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, self.__class__.__name__)
        _add_sub_element(el, 'StartTime', self.start_time)
        _add_sub_element(el, 'EndTime', self.end_time)
        _add_sub_element(el, 'Interest', self.interest)
        _add_sub_element(el, 'WithOvertake', self.with_overtake)
        _add_sub_element(el, 'Position', self.position)
        _add_sub_element(el, 'RaceLapNumber', self.race_lap_number)
        _add_sub_element(el, 'CarIdx', self.car_idx, include_if_none=False)
        _add_sub_element(el, 'OtherCarIdx', self.other_car_idx, include_if_none=False)
        _add_sub_element(el, 'Details', self.details, include_if_none=False)


@dataclass
class MessageState:
    messages: List[str] = field(default_factory=list) # <Messages><string>msg1</string>...</Messages>
    time: float = 0.0 # <Time>

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'MessageState':
        msgs_el = element.find('Messages')
        msgs = []
        if msgs_el is not None:
            msgs = [msg.text for msg in _find_all_as_list(msgs_el, 'string') if msg.text is not None]
        return cls(
            messages=msgs,
            time=_parse_optional_float(_find_text(element, 'Time')) or 0.0
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, self.__class__.__name__)
        _add_sub_element(el, 'Time', self.time)
        msgs_el = ET.SubElement(el, 'Messages')
        for msg_text in self.messages:
            _add_sub_element(msgs_el, 'string', msg_text)


@dataclass
class CamDriver:
    start_time: float # <StartTime>
    cam_group_number: int # <CamGroupNumber>
    current_driver: Driver # <CurrentDriver> (uses Driver class)

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'CamDriver':
        driver_el = element.find('CurrentDriver')
        drv = Driver.from_xml(driver_el) if driver_el is not None else Driver(car_number="-1", user_name="Unknown Driver")
        return cls(
            start_time=_parse_optional_float(_find_text(element, 'StartTime')) or 0.0,
            cam_group_number=_parse_optional_int(_find_text(element, 'CamGroupNumber')) or 0,
            current_driver=drv
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, self.__class__.__name__)
        _add_sub_element(el, 'StartTime', self.start_time)
        _add_sub_element(el, 'CamGroupNumber', self.cam_group_number)
        if self.current_driver:
            self.current_driver.to_xml(el, element_name="CurrentDriver")


@dataclass
class LeaderBoardSnapshot: # Renamed from LeaderBoard
    start_time: float                             # XML: <StartTime>
    drivers: List[Driver] = field(default_factory=list) # XML: <Drivers><Driver>...</Driver>...</Drivers>
    race_position: str = ""                       # XML: <RacePosition> (summary string, e.g., "P1")
    lap_counter: str = ""                         # XML: <LapCounter> (e.g., "Lap 1/10")

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'LeaderBoardSnapshot':
        drivers_el = element.find('Drivers')
        drv_list = []
        if drivers_el is not None:
            drv_list = [Driver.from_xml(drv_el) for drv_el in _find_all_as_list(drivers_el, 'Driver')]
        return cls(
            start_time=_parse_optional_float(_find_text(element, 'StartTime')) or 0.0,
            drivers=drv_list,
            race_position=_find_text(element, 'RacePosition', ''),
            lap_counter=_find_text(element, 'LapCounter', '')
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, 'LeaderBoard') # Serialize as "LeaderBoard"
        _add_sub_element(el, 'StartTime', self.start_time)
        _add_sub_element(el, 'RacePosition', self.race_position)
        _add_sub_element(el, 'LapCounter', self.lap_counter)
        drivers_el = ET.SubElement(el, 'Drivers')
        for driver_obj in self.drivers:
            driver_obj.to_xml(drivers_el, element_name="Driver")


@dataclass
class FastLap:
    start_time: float  # C# `long StartTime` (ticks/ms); here float seconds for consistency.
    driver: Driver     # XML: <Driver>
    lap_time: float    # C# `Time LapTime` (TimeSpan); here float seconds.

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'FastLap':
        driver_el = element.find('Driver')
        drv = Driver.from_xml(driver_el) if driver_el is not None else Driver(car_number="-1", user_name="Unknown Driver")
        return cls(
            start_time=_parse_optional_float(_find_text(element, 'StartTime')) or 0.0,
            driver=drv,
            lap_time=_parse_optional_float(_find_text(element, 'LapTime')) or 0.0
        )

    def to_xml(self, parent_element: ET.Element):
        el = ET.SubElement(parent_element, self.__class__.__name__)
        _add_sub_element(el, 'StartTime', self.start_time) # Or convert to long if strict C# match needed
        if self.driver:
            self.driver.to_xml(el, element_name="Driver")
        _add_sub_element(el, 'LapTime', self.lap_time) # Or format as C# Time string


@dataclass
class OverlayData:
    overlay_datetime: datetime = field(default_factory=datetime.utcnow)  # XML: <DateTime>
    leader_boards: List[LeaderBoardSnapshot] = field(default_factory=list) # XML: <LeaderBoards><LeaderBoard>...
    cam_drivers: List[CamDriver] = field(default_factory=list)            # XML: <CamDrivers><CamDriver>...
    fastest_laps: List[FastLap] = field(default_factory=list)             # XML: <FastestLaps><FastLap>...
    message_states: List[MessageState] = field(default_factory=list)      # XML: <MessageStates><MessageState>...
    session_data_xml: Optional[str] = None      # XML: <SessionData> (stores inner XML string)
    race_events: List[RaceEvent] = field(default_factory=list)            # XML: <RaceEvents><RaceEvent>...
    time_for_outro_overlay: Optional[float] = None # XML: <TimeForOutroOverlay>
    video_files: List[CapturedVideoFile] = field(default_factory=list)    # XML: <VideoFiles><CapturedVideoFile>...
    captured_version: Optional[str] = None      # XML: <CapturedVersion>

    @classmethod
    def load_from_xml(cls, filepath: str) -> 'OverlayData':
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except FileNotFoundError:
            print(f"Error: File not found {filepath}")
            # Return a default/empty OverlayData object or raise exception
            return cls()
        except ET.ParseError as e:
            print(f"Error: Could not parse XML file {filepath}. Error: {e}")
            return cls()

        # Helper to extract list of complex objects
        def _extract_list(parent_el_tag, item_tag, item_class_from_xml):
            parent_el = root.find(parent_el_tag)
            if parent_el is not None:
                return [item_class_from_xml(item_el) for item_el in _find_all_as_list(parent_el, item_tag)]
            return []

        dt_str = _find_text(root, 'DateTime')
        overlay_dt = _datetime_from_isotsformat_z(dt_str) if dt_str else datetime.utcnow()

        # For SessionData, grab the raw XML string if present
        session_data_el = root.find('SessionData')
        raw_session_data_xml = None
        if session_data_el is not None:
            # This captures everything inside <SessionData>...</SessionData> as a string.
            # It aims to reconstruct the inner XML, including mixed content.
            inner_xml_parts = []
            if session_data_el.text and session_data_el.text.strip():
                inner_xml_parts.append(session_data_el.text.strip())
            for child_el in session_data_el:
                inner_xml_parts.append(ET.tostring(child_el, encoding='unicode'))
                if child_el.tail and child_el.tail.strip():
                    inner_xml_parts.append(child_el.tail.strip())
            raw_session_data_xml = "".join(inner_xml_parts) if inner_xml_parts else None
            # If only text content and no children, this might miss it.
            # A simpler alternative if only text or only children:
            # raw_session_data_xml = session_data_el.text or ET.tostring(session_data_el[0], encoding='unicode') etc.
            # The current loop is more general for mixed.
            # If after all this, it's empty, it might mean <SessionData/> was empty or only whitespace.
            if raw_session_data_xml == "" and session_data_el.text is not None: # Check if it was just whitespace
                 raw_session_data_xml = session_data_el.text # Preserve whitespace if it was the only content.

        return cls(
            overlay_datetime=overlay_dt,
            leader_boards=_extract_list('LeaderBoards', 'LeaderBoard', LeaderBoardSnapshot.from_xml),
            cam_drivers=_extract_list('CamDrivers', 'CamDriver', CamDriver.from_xml),
            fastest_laps=_extract_list('FastestLaps', 'FastLap', FastLap.from_xml),
            message_states=_extract_list('MessageStates', 'MessageState', MessageState.from_xml),
            session_data_xml=raw_session_data_xml,
            race_events=_extract_list('RaceEvents', 'RaceEvent', RaceEvent.from_xml),
            time_for_outro_overlay=_parse_optional_float(_find_text(root, 'TimeForOutroOverlay')),
            video_files=_extract_list('VideoFiles', 'CapturedVideoFile', CapturedVideoFile.from_xml),
            captured_version=_find_text(root, 'CapturedVersion')
        )

    def save_to_xml(self, filepath: str):
        root = ET.Element(self.__class__.__name__) # Root element e.g. <OverlayData>

        _add_sub_element(root, 'DateTime', self.overlay_datetime)
        _add_sub_element(root, 'TimeForOutroOverlay', self.time_for_outro_overlay, include_if_none=True)
        _add_sub_element(root, 'CapturedVersion', self.captured_version)

        if self.session_data_xml:
            # If SessionData is already well-formed XML, try to parse and append its root.
            # Otherwise, treat as string content. C# might put it directly as child elements.
            session_data_el = ET.SubElement(root, 'SessionData')
            # The goal is to store self.session_data_xml as the "inner XML" of session_data_el.
            # If self.session_data_xml is a string that represents valid XML elements,
            # and we want them to be actual child elements in the output XML (not escaped text),
            # we need to parse it and append.
            # However, if session_data_xml contains mixed content (text and elements at the root level),
            # parsing with ET.fromstring requires a single root element in the string.

            # Current logic from previous step:
            # Tries to parse if it looks like XML, otherwise sets as text.
            # This is generally reasonable for "store inner XML as string".
            is_likely_xml = (self.session_data_xml.strip().startswith("<") and
                             self.session_data_xml.strip().endswith(">"))

            if is_likely_xml:
                try:
                    # Attempt to parse self.session_data_xml.
                    # This requires self.session_data_xml to be a single well-formed XML element string.
                    # E.g., "<ActualData><Value>1</Value></ActualData>"
                    # If it's like "<Elem1/><Elem2/>" (multiple roots) or "Text<Elem1/>", fromstring fails.
                    parsed_content = ET.fromstring(self.session_data_xml)
                    session_data_el.append(parsed_content)
                except ET.ParseError:
                    # If parsing fails (e.g., multiple roots, mixed content not wrapped in a single root,
                    # or just not well-formed XML), store as text.
                    # This will XML-escape the content.
                    session_data_el.text = self.session_data_xml
            else:
                # Not XML-like, or parsing failed; store as text.
                session_data_el.text = self.session_data_xml
        elif self.session_data_xml is None:
            # If session_data_xml is None, create an empty <SessionData /> tag.
            # This is achieved by ET.SubElement(root, 'SessionData') and doing nothing else with it.
            ET.SubElement(root, 'SessionData')

        # Helper to add list of complex objects
        def _add_list_elements(parent_el_tag, items_list):
            if items_list: # Only add parent tag if list is not empty
                list_parent_el = ET.SubElement(root, parent_el_tag)
                for item in items_list:
                    item.to_xml(list_parent_el) # Each item's class has to_xml

        _add_list_elements('LeaderBoards', self.leader_boards)
        _add_list_elements('CamDrivers', self.cam_drivers)
        _add_list_elements('FastestLaps', self.fastest_laps)
        _add_list_elements('MessageStates', self.message_states)
        _add_list_elements('RaceEvents', self.race_events)
        _add_list_elements('VideoFiles', self.video_files)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0) # For pretty printing
        try:
            tree.write(filepath, encoding='utf-8', xml_declaration=True)
        except IOError as e:
            print(f"Error: Could not write XML to {filepath}. Error: {e}")

    def save_to_json(self, filepath: str):
        def dt_handler(o):
            if isinstance(o, datetime):
                return _datetime_to_isotsformat_z(o)
            return str(o) # For other types that might not be default serializable

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, indent=2, default=dt_handler)
        except IOError as e:
            print(f"Error: Could not write JSON to {filepath}. Error: {e}")
        except TypeError as e:
            print(f"Error: Could not serialize OverlayData to JSON. Error: {e}")


# --- Main for Demonstration ---
if __name__ == '__main__':
    DUMMY_XML_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
<OverlayData>
  <DateTime>2023-10-27T10:30:00Z</DateTime>
  <LeaderBoards>
    <LeaderBoard>
      <StartTime>10.5</StartTime>
      <Drivers>
        <Driver>
          <Position>1</Position>
          <CarNumber>22</CarNumber>
          <UserName>Player One</UserName>
          <PitStopCount>0</PitStopCount>
        </Driver>
        <Driver>
          <Position>2</Position>
          <CarNumber>4</CarNumber>
          <UserName>Player Two</UserName>
          <PitStopCount>1</PitStopCount>
        </Driver>
      </Drivers>
      <RacePosition>P1</RacePosition>
      <LapCounter>Lap 1/10</LapCounter>
    </LeaderBoard>
  </LeaderBoards>
  <CamDrivers>
    <CamDriver>
      <StartTime>12.0</StartTime>
      <CamGroupNumber>1</CamGroupNumber>
      <CurrentDriver>
        <CarNumber>22</CarNumber>
        <UserName>Player One</UserName>
        <PitStopCount>0</PitStopCount>
      </CurrentDriver>
    </CamDriver>
  </CamDrivers>
  <FastestLaps>
    <FastLap>
      <StartTime>120.3</StartTime>
      <Driver>
        <CarNumber>22</CarNumber>
        <UserName>Player One</UserName>
      </Driver>
      <LapTime>75.5</LapTime>
    </FastLap>
  </FastestLaps>
  <MessageStates>
    <MessageState>
      <Time>15.0</Time>
      <Messages>
        <string>Battle for P1!</string>
        <string>Watch out!</string>
      </Messages>
    </MessageState>
  </MessageStates>
  <SessionData><IracingSdkData><Var Name="ExampleVar" Value="ExampleValue" /></IracingSdkData>Some other text if any.</SessionData>
  <RaceEvents>
    <RaceEvent>
      <StartTime>20.0</StartTime>
      <EndTime>25.0</EndTime>
      <Interest>Incident</Interest>
      <WithOvertake>False</WithOvertake>
      <Position>3</Position>
      <RaceLapNumber>2</RaceLapNumber>
    </RaceEvent>
  </RaceEvents>
  <TimeForOutroOverlay>300.5</TimeForOutroOverlay>
  <VideoFiles>
    <CapturedVideoFile>
      <Filename>intro.mp4</Filename>
      <IsIntroVideo>True</IsIntroVideo>
    </CapturedVideoFile>
    <CapturedVideoFile>
      <Filename>race_part1.mp4</Filename>
      <IsIntroVideo>False</IsIntroVideo>
    </CapturedVideoFile>
  </VideoFiles>
  <CapturedVersion>1.0.0</CapturedVersion>
</OverlayData>
"""
    # Save the dummy XML to a file for testing
    dummy_xml_filepath = "dummy_replay_data.xml"
    with open(dummy_xml_filepath, "w", encoding="utf-8") as f:
        f.write(DUMMY_XML_CONTENT)

    print(f"--- Loading data from {dummy_xml_filepath} ---")
    overlay_data = OverlayData.load_from_xml(dummy_xml_filepath)

    if overlay_data and overlay_data.leader_boards: # Check if loading was successful
        print(f"Loaded OverlayData from: {overlay_data.overlay_datetime}")
        print(f"  Captured Version: {overlay_data.captured_version}")
        print(f"  Number of LeaderBoardSnapshots: {len(overlay_data.leader_boards)}")
        if overlay_data.leader_boards:
            first_lb = overlay_data.leader_boards[0]
            print(f"    First LeaderBoard Snapshot time: {first_lb.start_time}, Lap: {first_lb.lap_counter}")
            if first_lb.drivers:
                print(
                    f"      First driver: {first_lb.drivers[0].user_name} "
                    f"(Car #{first_lb.drivers[0].car_number})"
                )

        print(f"  Number of CamDriver entries: {len(overlay_data.cam_drivers)}")
        if overlay_data.cam_drivers:
             print(f"    First CamDriver target: {overlay_data.cam_drivers[0].current_driver.user_name}")

        print(f"  Number of FastestLap entries: {len(overlay_data.fastest_laps)}")
        if overlay_data.fastest_laps:
            print(
                f"    First FastestLap by: {overlay_data.fastest_laps[0].driver.user_name}, "
                f"Time: {overlay_data.fastest_laps[0].lap_time}"
            )

        print(f"  Number of MessageState entries: {len(overlay_data.message_states)}")
        if overlay_data.message_states and overlay_data.message_states[0].messages:
            print(f"    First message: '{overlay_data.message_states[0].messages[0]}'")

        print(f"  SessionData XML snippet: \n    {str(overlay_data.session_data_xml)[:100]}...") # Print snippet

        print(f"  Number of RaceEvents: {len(overlay_data.race_events)}")
        if overlay_data.race_events:
            print(
                f"    First RaceEvent interest: {overlay_data.race_events[0].interest} "
                f"at {overlay_data.race_events[0].start_time}s"
            )

        print(f"  TimeForOutroOverlay: {overlay_data.time_for_outro_overlay}")
        print(f"  Number of VideoFiles: {len(overlay_data.video_files)}")
        if overlay_data.video_files:
            print(
                f"    First VideoFile: {overlay_data.video_files[0].filename} "
                f"(IsIntro: {overlay_data.video_files[0].is_intro_video})"
            )

        # --- Saving data ---
        saved_xml_filepath = "dummy_replay_data_saved.xml" # Changed name to avoid overwrite if error
        print(f"\n--- Saving loaded data to {saved_xml_filepath} ---")
        overlay_data.save_to_xml(saved_xml_filepath)
        print(f"  Data saved to {saved_xml_filepath}.")

        saved_json_filepath = "dummy_replay_data_saved.json"
        print(f"\n--- Saving loaded data to {saved_json_filepath} ---")
        overlay_data.save_to_json(saved_json_filepath)
        print(f"  Data saved to {saved_json_filepath}.")

        # --- Test loading the just-saved XML ---
        print(f"\n--- Reloading data from {saved_xml_filepath} ---")
        reloaded_data = OverlayData.load_from_xml(saved_xml_filepath)
        if reloaded_data and reloaded_data.leader_boards:
             print(
                 f"  Successfully reloaded. First driver in reloaded LeaderBoard: "
                 f"{reloaded_data.leader_boards[0].drivers[0].user_name}"
            )
             assert reloaded_data.leader_boards[0].drivers[0].user_name == \
                    overlay_data.leader_boards[0].drivers[0].user_name
        else:
            print("  Failed to reload the saved XML data or it was empty.")
    else:
        print("Failed to load or parse initial DUMMY_XML_CONTENT correctly.")

    print("\nreplay_data.py demonstration finished.")


