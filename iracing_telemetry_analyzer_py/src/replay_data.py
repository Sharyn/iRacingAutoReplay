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
    # Handles ISO format, typically ending with 'Z' for UTC
    # datetime.fromisoformat doesn't like 'Z' directly before Python 3.11
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    return datetime.fromisoformat(dt_str)

def _datetime_to_isotsformat_z(dt: datetime) -> str:
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
    car_number: str # In XML, usually an attribute of a parent or a specific tag like <CarNumber>
    user_name: str  # Similar, e.g. <UserName>
    position: Optional[int] = None # <Position>
    pit_stop_count: int = 0 # <PitStopCount>
    car_idx: Optional[int] = None # Not typically in XML, for runtime use
    short_name: Optional[str] = None # Not typically in XML, for runtime use, or derived

    # Note: In C#, Driver is often part of another class like LeaderBoardDriver, CamDriver etc.
    # The XML structure will dictate how this is parsed. For now, assuming direct tags.

    @classmethod
    def from_xml(cls, element: ET.Element) -> 'Driver':
        # This generic from_xml might need to be adapted based on how Driver is represented
        # in different contexts (e.g. CamDriver's Driver vs LeaderBoard's Driver)
        return cls(
            position=_parse_optional_int(_find_text(element, 'Position')),
            car_number=_find_text(element, 'CarNumber', '0'), # Default to '0' if missing
            user_name=_find_text(element, 'UserName', 'Unknown'), # Default if missing
            pit_stop_count=_parse_optional_int(_find_text(element, 'PitStopCount')) or 0,
            # car_idx and short_name are not expected from typical XML for this structure
        )

    def to_xml(self, parent_element: ET.Element, element_name: str = "Driver"):
        # Element name can be overridden e.g. for CamDriver's <CurrentDriver>
        el = ET.SubElement(parent_element, element_name)
        _add_sub_element(el, 'Position', self.position, include_if_none=True) # Often included even if null/empty in C# XML
        _add_sub_element(el, 'CarNumber', self.car_number)
        _add_sub_element(el, 'UserName', self.user_name)
        _add_sub_element(el, 'PitStopCount', self.pit_stop_count)
        # car_idx and short_name are not typically serialized for this structure

@dataclass
class RaceEvent:
    start_time: float # <StartTime>
    end_time: float   # <EndTime>
    interest: str     # <Interest> (enum-like: "Incident", "Overtake", "Battle")
    with_overtake: bool # <WithOvertake>
    position: int = 9999  # <Position>
    race_lap_number: int = 0 # <RaceLapNumber>

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
    start_time: float # <StartTime>
    drivers: List[Driver] = field(default_factory=list) # <Drivers><Driver>...</Driver>...</Drivers>
    race_position: str = "" # <RacePosition> (seems like a summary string)
    lap_counter: str = "" # <LapCounter> (e.g. "Lap 1/10")

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
    start_time: float # C# was long StartTime, assuming float seconds consistent with others
    driver: Driver    # <Driver> (uses Driver class)
    lap_time: float   # C# was Time LapTime, assuming float seconds

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
    overlay_datetime: datetime = field(default_factory=datetime.utcnow) # <DateTime>
    leader_boards: List[LeaderBoardSnapshot] = field(default_factory=list) # <LeaderBoards><LeaderBoard>...</LeaderBoard>...</LeaderBoards>
    cam_drivers: List[CamDriver] = field(default_factory=list)
    fastest_laps: List[FastLap] = field(default_factory=list)
    message_states: List[MessageState] = field(default_factory=list)
    session_data_xml: Optional[str] = None # <SessionData> (inner XML string)
    race_events: List[RaceEvent] = field(default_factory=list)
    time_for_outro_overlay: Optional[float] = None # <TimeForOutroOverlay>
    video_files: List[CapturedVideoFile] = field(default_factory=list)
    captured_version: Optional[str] = None # <CapturedVersion>

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
            # Serialize the children of SessionData element to string
            # This captures everything inside <SessionData>...</SessionData>
            children_xml_parts = []
            if session_data_el.text: # Text before first child
                 children_xml_parts.append(session_data_el.text)
            for child in session_data_el:
                children_xml_parts.append(ET.tostring(child, encoding='unicode'))
            raw_session_data_xml = "".join(children_xml_parts).strip()
            if not raw_session_data_xml: # If only text content
                raw_session_data_xml = session_data_el.text


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
            # If SessionData is already well-formed XML, parse it and append its root.
            # Otherwise, treat as string content. For safety, could wrap in CDATA.
            # Current C# seems to put it directly as child elements of <SessionData>
            session_data_parent_el = ET.SubElement(root, 'SessionData')
            try:
                # Attempt to parse the stored XML string and append its children
                # This assumes session_data_xml is a string containing one or more XML elements
                # A wrapper element might be needed if session_data_xml has multiple roots or just text
                # For now, let's assume it's a single root element's content or simple text.
                # A robust way would be to parse it and append its children.
                # If it's literally the content *between* <SessionData> tags:
                # session_data_parent_el.append(ET.fromstring(f"<root_wrapper>{self.session_data_xml}</root_wrapper>"))
                # This is tricky without knowing exact structure of session_data_xml.
                # A simpler approach is to just set it as text, possibly wrapped in CDATA
                # Check if it looks like XML
                if self.session_data_xml.strip().startswith("<") and self.session_data_xml.strip().endswith(">"):
                     # It's XML, try to parse and append. This is the complex part.
                     # The C# code likely uses XmlWriter which handles this seamlessly.
                     # ET is more manual. A common way is to parse the string and append elements.
                     # For now, let's do a simplified version: add it as text.
                     # If it's actual complex XML, it should be parsed and elements added.
                     # This might require a dummy root if session_data_xml itself is not a single element.
                    try:
                        # Try to parse the XML string and append its root element
                        # This assumes self.session_data_xml is a string representing a single XML element
                        # or multiple sibling elements (which is not valid for ET.fromstring directly without a wrapper)
                        # For now, if it's complex, this simple text dump will not be identical to C#
                        # A proper solution would be to parse session_data_xml and append its elements.
                        # For this subtask, "store the inner XML content as a string" implies we might not need to fully re-serialize its structure.
                        # If the C# version stores <SessionData><ActualIracingData>...</ActualIracingData></SessionData>
                        # then self.session_data_xml would be "<ActualIracingData>...</ActualIracingData>"
                        # and we can do:
                        session_data_content_el = ET.fromstring(self.session_data_xml)
                        session_data_parent_el.append(session_data_content_el)
                    except ET.ParseError:
                        # If it's not a single root element, or invalid XML, store as text (CDATA might be good)
                        # To mimic C#'s output which might not use CDATA for this specific field if it writes raw.
                        session_data_parent_el.text = self.session_data_xml # Fallback
                else:
                    # Simple text content, or if parsing failed.
                    session_data_parent_el.text = self.session_data_xml # XML special chars will be escaped.
            except ET.ParseError:
                # If self.session_data_xml is not a single well-formed XML element string,
                # store it as plain text content. XML special characters will be escaped.
                session_data_parent_el.text = self.session_data_xml
            except Exception as e: # Broad catch for other XML manipulation issues
                 session_data_parent_el.text = f"Error processing SessionData for XML output: {e}"
        elif self.session_data_xml is None and ET.SubElement(root, 'SessionData') is not None:
            # If it's None, create an empty SessionData tag if desired by C# structure
            pass


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

    if overlay_data and overlay_data.leader_boards:
        print(f"Loaded OverlayData from: {overlay_data.overlay_datetime}")
        print(f"Captured Version: {overlay_data.captured_version}")
        print(f"Number of LeaderBoardSnapshots: {len(overlay_data.leader_boards)}")
        if overlay_data.leader_boards:
            first_lb = overlay_data.leader_boards[0]
            print(f"  First LeaderBoard Snapshot time: {first_lb.start_time}, Lap: {first_lb.lap_counter}")
            if first_lb.drivers:
                print(f"    First driver in first LeaderBoard: {first_lb.drivers[0].user_name} (Car #{first_lb.drivers[0].car_number})")

        print(f"Number of CamDriver entries: {len(overlay_data.cam_drivers)}")
        if overlay_data.cam_drivers:
             print(f"  First CamDriver target: {overlay_data.cam_drivers[0].current_driver.user_name}")

        print(f"Number of FastestLap entries: {len(overlay_data.fastest_laps)}")
        if overlay_data.fastest_laps:
            print(f"  First FastestLap by: {overlay_data.fastest_laps[0].driver.user_name}, Time: {overlay_data.fastest_laps[0].lap_time}")

        print(f"Number of MessageState entries: {len(overlay_data.message_states)}")
        if overlay_data.message_states and overlay_data.message_states[0].messages:
            print(f"  First message in first MessageState: '{overlay_data.message_states[0].messages[0]}'")

        print(f"SessionData XML: \n{overlay_data.session_data_xml}")

        print(f"Number of RaceEvents: {len(overlay_data.race_events)}")
        if overlay_data.race_events:
            print(f"  First RaceEvent interest: {overlay_data.race_events[0].interest} at {overlay_data.race_events[0].start_time}s")

        print(f"TimeForOutroOverlay: {overlay_data.time_for_outro_overlay}")
        print(f"Number of VideoFiles: {len(overlay_data.video_files)}")
        if overlay_data.video_files:
            print(f"  First VideoFile: {overlay_data.video_files[0].filename} (IsIntro: {overlay_data.video_files[0].is_intro_video})")

        # --- Saving data ---
        saved_xml_filepath = "saved_replay_data.xml"
        print(f"\n--- Saving data to {saved_xml_filepath} ---")
        overlay_data.save_to_xml(saved_xml_filepath)
        print(f"Data saved to {saved_xml_filepath}. Check its content.")

        saved_json_filepath = "saved_replay_data.json"
        print(f"\n--- Saving data to {saved_json_filepath} ---")
        overlay_data.save_to_json(saved_json_filepath)
        print(f"Data saved to {saved_json_filepath}. Check its content.")

        # --- Test loading the saved XML ---
        print(f"\n--- Loading data from {saved_xml_filepath} (the one we just saved) ---")
        reloaded_data = OverlayData.load_from_xml(saved_xml_filepath)
        if reloaded_data and reloaded_data.leader_boards:
             print(f"Successfully reloaded. First driver in first reloaded LeaderBoard: {reloaded_data.leader_boards[0].drivers[0].user_name}")
             assert reloaded_data.leader_boards[0].drivers[0].user_name == overlay_data.leader_boards[0].drivers[0].user_name

    else:
        print("Failed to load or parse OverlayData correctly.")

    print("\nreplay_data.py demonstration finished.")

```
