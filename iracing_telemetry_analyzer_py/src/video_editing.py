"""
Provides functions for selecting highlight segments from race event data.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set, Optional, Callable # Added Callable
from enum import Enum

# Assuming these can be imported. If not, their structure needs to be known.
from .replay_data import OverlayData, RaceEvent
from .app_settings import AppSettings


@dataclass
class VideoEdit:
    """Represents a continuous segment of video to keep."""
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        return round(self.end_time - self.start_time, 3)

    def __repr__(self):
        return f"VideoEdit(start={self.start_time:.2f}s, end={self.end_time:.2f}s, dur={self.duration:.2f}s)"

# Enum for interest levels, similar to C# InterestState and categories
class InterestCategory(Enum):
    FIRST_LAP = "FirstLap"
    LAST_LAP = "LastLap"
    RESTART = "Restart" # Could be from RaceEvent.Interest = "Restart" or derived
    INCIDENT = "Incident"
    BATTLE = "Battle"
    OVERTAKE = "Overtake" # Often part of other events (e.g. Incident with_overtake=True)
    # Generic might not be used for highlights unless specifically chosen
    # Generic = "GenericInfo" # From RaceEvent.Interest

    # Categories for selection priority
    PRIMARY = "Primary" # e.g. Incidents with overtakes
    SECONDARY = "Secondary" # e.g. Regular incidents, major battles
    TERTIARY = "Tertiary" # e.g. Other battles, overtakes not in incidents
    BACKGROUND = "Background" # e.g. First/Last laps, context


# --- Helper Functions ---

def _get_duration(event: RaceEvent) -> float:
    return event.end_time - event.start_time

def _normalise_battle_events(battle_events: List[RaceEvent], preferred_duration: float = 10.0) -> List[RaceEvent]:
    """
    Normalizes battle event durations.
    If a battle is longer than preferred_duration, it might be split or trimmed conceptually.
    For now, let's assume it might cap the considered duration or adjust start/end for selection.
    C# logic: if > 10s, trim to 10s around the point of most interest (not implemented here, just cap for now).
    This function will primarily cap the duration for selection purposes if needed,
    or it could return new RaceEvent instances if modification is required.
    For simplicity, we'll just use their original times for now but could cap their 'score' later.
    """
    # This is a placeholder for more complex battle normalization.
    # The C# version tries to find the most "interesting" part of a long battle.
    # For now, we'll just return them as is, selection logic will handle duration limits.
    return battle_events


def _get_events_by_interest(
    all_events: List[RaceEvent],
    target_interests: Set[str],
    with_overtake: Optional[bool] = None
) -> List[RaceEvent]:
    """Filters events by a set of interest strings and optionally by 'with_overtake' flag."""
    filtered = []
    for event in all_events:
        if event.interest in target_interests:
            if with_overtake is None or event.with_overtake == with_overtake:
                filtered.append(event)
    return filtered


def _get_total_duration(events: List[RaceEvent]) -> float:
    return sum(_get_duration(e) for e in events)


def _select_top_events_for_duration(
    events: List[RaceEvent],
    allocated_duration: float,
    max_event_duration: Optional[float] = None # Max duration for a single event to contribute
) -> List[RaceEvent]:
    """
    Selects events from the list, trying to fill the allocated_duration.
    Events are typically pre-sorted by importance.
    """
    selected_events: List[RaceEvent] = []
    current_duration = 0.0
    # Sort events: those with overtakes first, then by duration (longer might be more interesting, or shorter for variety)
    # This simple sort might need to be more nuanced based on C# scoring.
    # C# has a more complex scoring (InterestScore). Let's assume pre-sorted or sort simply for now.
    # For now, let's assume events are somewhat prioritized coming in.

    sorted_events = sorted(events, key=lambda e: (e.with_overtake, _get_duration(e)), reverse=True)


    for event in sorted_events:
        event_dur = _get_duration(event)
        if max_event_duration is not None:
            event_dur = min(event_dur, max_event_duration)

        if current_duration + event_dur <= allocated_duration:
            selected_events.append(event)
            current_duration += event_dur
        else:
            # Try to fit a part of the event or a shorter event?
            # C# logic might involve slicing events (_slice_event_selection).
            # For now, if an event doesn't fit, we skip it and try the next smaller one.
            # This is simpler than slicing.
            if event_dur <= (allocated_duration - current_duration): # If this specific event can fit
                 selected_events.append(event)
                 current_duration += event_dur
                 break # Filled duration
            # If we want to strictly fill, we might need to find an event that exactly fits the remainder.
            # Or, if we are okay going slightly over with the last event.
            # C# _SliceEventSelection suggests partial events are okay.
            # This simplified version doesn't slice.

    return selected_events

# --- Main Highlight Function ---

def get_highlight_segments_to_keep(
    overlay_data: OverlayData,
    settings: AppSettings
) -> List[VideoEdit]:
    """
    Analyzes race events from OverlayData and AppSettings to determine
    video segments to keep for a highlight reel.

    Args:
        overlay_data: The OverlayData containing all race events.
        settings: Application settings, including highlight duration targets.

    Returns:
        A list of VideoEdit objects representing segments to keep, sorted by start time.
    """
    if not overlay_data.race_events:
        return []

    all_race_events = sorted(overlay_data.race_events, key=lambda e: e.start_time)

    target_total_duration = float(settings.highlight_video_target_duration_seconds) # Ensure float

    # Category Ratios (inspired by C# _categoryTimes, values are illustrative)
    # These define rough proportions of the total highlight duration for each category.
    category_ratios = {
        InterestCategory.PRIMARY: 0.40,  # Incidents with overtakes
        InterestCategory.SECONDARY: 0.30, # Other incidents, major battles
        InterestCategory.TERTIARY: 0.20,  # Other battles, standalone overtakes
        InterestCategory.BACKGROUND: 0.10 # First/Last laps, context setting
    }

    # 1. Categorize Events
    # Primary: Incidents with overtakes
    primary_events = _get_events_by_interest(all_race_events, {"Incident"}, with_overtake=True)

    # Secondary: Incidents without overtakes, plus significant battles
    secondary_incidents = _get_events_by_interest(all_race_events, {"Incident"}, with_overtake=False)
    battle_events = _get_events_by_interest(all_race_events, {"Battle", "HardBattle"}) # Assuming "HardBattle"
    battle_events_normalized = _normalise_battle_events(battle_events) # Placeholder
    secondary_events = secondary_incidents + battle_events_normalized # Could add other types like "Rivalry"

    # Tertiary: Standalone overtakes (not part of incidents), other minor events
    # This requires identifying overtakes that are not already part of an incident.
    # For simplicity, let's assume RaceEvent.Interest = "Overtake" exists for standalone ones.
    tertiary_overtakes = _get_events_by_interest(all_race_events, {"Overtake"})
    # Filter out overtakes already captured if they are part of an "Incident" with_overtake=True
    # This is complex; for now, assume "Overtake" interest is distinct.
    tertiary_events = tertiary_overtakes # Could add "Spin", "OffTrack" if they are separate interests

    # Background: First lap, last lap, restarts
    # Assuming specific interest types or derivation (e.g. based on RaceLapNumber)
    # C# logic for first/last lap events is more complex (e.g. _GetAllFirstAndLastLapEvents)
    # For now, let's use placeholder interest types if they exist, or skip if too complex for this pass.
    first_lap_events = _get_events_by_interest(all_race_events, {"FirstLap", "RaceStart"}) # Example types
    last_lap_events = _get_events_by_interest(all_race_events, {"LastLap", "RaceFinish"})   # Example types
    restart_events = _get_events_by_interest(all_race_events, {"Restart"})
    background_events = first_lap_events + last_lap_events + restart_events

    # This categorization is simplified. C# uses "InterestLevels" which might be more dynamic.

    # 2. Select Events per Category based on Duration Allocation
    all_selected_events: List[RaceEvent] = []

    # Primary selection
    alloc_primary_dur = target_total_duration * category_ratios[InterestCategory.PRIMARY]
    selected_primary = _select_top_events_for_duration(primary_events, alloc_primary_dur, max_event_duration=20) # Cap long incidents
    all_selected_events.extend(selected_primary)

    # Secondary selection (ensure no overlaps with primary)
    remaining_duration_for_secondary = target_total_duration * category_ratios[InterestCategory.SECONDARY]
    # Filter out events already captured by primary selection (based on time overlap)
    secondary_candidates = [
        se for se in secondary_events
        if not any(_events_overlap(se, pe) for pe in all_selected_events)
    ]
    selected_secondary = _select_top_events_for_duration(secondary_candidates, remaining_duration_for_secondary, max_event_duration=15)
    all_selected_events.extend(selected_secondary)

    # Tertiary selection
    remaining_duration_for_tertiary = target_total_duration * category_ratios[InterestCategory.TERTIARY]
    tertiary_candidates = [
        te for te in tertiary_events
        if not any(_events_overlap(te, pe) for pe in all_selected_events)
    ]
    selected_tertiary = _select_top_events_for_duration(tertiary_candidates, remaining_duration_for_tertiary, max_event_duration=10)
    all_selected_events.extend(selected_tertiary)

    # Background selection (fill remaining, or its ratio)
    # Sum of durations from primary, secondary, tertiary
    used_duration = _get_total_duration(all_selected_events)
    alloc_background_dur = max(0, target_total_duration * category_ratios[InterestCategory.BACKGROUND], target_total_duration - used_duration) # try to fill

    background_candidates = [
        bge for bge in background_events
        if not any(_events_overlap(bge, pe) for pe in all_selected_events)
    ]
    selected_background = _select_top_events_for_duration(background_candidates, alloc_background_dur, max_event_duration=30) # Allow longer context clips
    all_selected_events.extend(selected_background)

    # 3. Sort all selected events by start time to prepare for merging
    if not all_selected_events:
        return []

    # Ensure unique events (if an event could fit multiple categories and was added twice)
    # Using dict from_keys to preserve order while ensuring uniqueness by object ID if they are hashable
    # Or more simply, convert to set and back to list then sort if RaceEvent is hashable
    # For now, assume selection process avoids duplicates or they are fine if they represent different aspects.
    # A simpler way to ensure uniqueness if events are hashable: list(set(all_selected_events))
    # However, dataclasses are not hashable by default if they contain lists.
    # Let's assume our selection logic tries to avoid adding true duplicates.

    # Sort by start time
    unique_selected_events = []
    seen_ids = set()
    for e in sorted(all_selected_events, key=lambda ev: ev.start_time):
        if id(e) not in seen_ids: # Crude check for object uniqueness if not hashable by value
            unique_selected_events.append(e)
            seen_ids.add(id(e))

    if not unique_selected_events:
        return []

    # 4. Merge overlapping or adjacent RaceEvents into VideoEdit segments
    merged_edits: List[VideoEdit] = []
    current_edit_start = unique_selected_events[0].start_time
    current_edit_end = unique_selected_events[0].end_time

    for i in range(1, len(unique_selected_events)):
        next_event = unique_selected_events[i]
        # Merge if next_event starts before or exactly at current_edit_end (or slightly after, allowing small gaps)
        # C# logic might have a small tolerance for merging (e.g. MergeEventsWithinSeconds)
        merge_tolerance = 0.5 # seconds, example
        if next_event.start_time <= current_edit_end + merge_tolerance:
            current_edit_end = max(current_edit_end, next_event.end_time)
        else:
            # Gap is too large, finalize current edit and start a new one
            merged_edits.append(VideoEdit(start_time=current_edit_start, end_time=current_edit_end))
            current_edit_start = next_event.start_time
            current_edit_end = next_event.end_time

    # Add the last edit segment
    merged_edits.append(VideoEdit(start_time=current_edit_start, end_time=current_edit_end))

    return merged_edits


def _events_overlap(event1: RaceEvent, event2: RaceEvent, tolerance: float = 0.1) -> bool:
    """Checks if two events overlap in time, with a small tolerance."""
    # True if event1 starts during event2 OR event2 starts during event1
    # (event1.start_time <= event2.end_time and event1.end_time >= event2.start_time)
    # Add tolerance:
    return (event1.start_time <= event2.end_time + tolerance and
            event1.end_time >= event2.start_time - tolerance)


# --- Main for Demonstration ---
if __name__ == '__main__':
    print("--- VideoEditing Demonstration ---")

    # Mock AppSettings
    class MockAppSettings:
        def __init__(self):
            self.highlight_video_target_duration_seconds = 60 # Target 1 minute highlight
            # Other settings that might be relevant if used by helpers
            # self.some_other_setting = "value"

    mock_settings = MockAppSettings()

    # Create dummy OverlayData with RaceEvents
    dummy_events = [
        # Early incidents
        RaceEvent(start_time=5.0, end_time=10.0, interest='Incident', with_overtake=True, position=1, race_lap_number=1), # Primary
        RaceEvent(start_time=12.0, end_time=16.0, interest='Incident', with_overtake=False, position=3, race_lap_number=1),# Secondary
        # Battle sequence
        RaceEvent(start_time=20.0, end_time=28.0, interest='Battle', with_overtake=False), # Secondary/Tertiary
        RaceEvent(start_time=27.0, end_time=32.0, interest='Overtake', with_overtake=True), # Tertiary (overlaps with battle end)
        # Mid-race lull, then another incident
        RaceEvent(start_time=50.0, end_time=53.0, interest='Incident', with_overtake=True, position=2, race_lap_number=5), # Primary
        # Generic info, usually not for highlights unless nothing else
        RaceEvent(start_time=60.0, end_time=62.0, interest='GenericInfo', with_overtake=False),
        # Last lap events
        RaceEvent(start_time=80.0, end_time=85.0, interest='LastLap', with_overtake=False), # Background
        RaceEvent(start_time=83.0, end_time=88.0, interest='Battle', with_overtake=True, position=1), # Secondary/Tertiary (overlaps lastlap)
        RaceEvent(start_time=90.0, end_time=95.0, interest='RaceFinish', with_overtake=False), # Background
    ]
    # Add some "FirstLap" events for context
    dummy_events.insert(0, RaceEvent(start_time=0.0, end_time=5.0, interest='FirstLap', with_overtake=False)) # Background
    dummy_events.insert(1, RaceEvent(start_time=1.0, end_time=3.0, interest='RaceStart', with_overtake=False)) # Background (overlaps)


    dummy_overlay_data = OverlayData(race_events=dummy_events)
    # Populate other OverlayData fields if necessary for the functions, but RaceEvents are key here.

    print(f"Target highlight duration: {mock_settings.highlight_video_target_duration_seconds}s")
    print(f"Total events provided: {len(dummy_events)}")
    for i, event in enumerate(dummy_events):
        print(f"  Event {i}: start={event.start_time:.1f}, end={event.end_time:.1f}, interest='{event.interest}', overtake={event.with_overtake}, duration={_get_duration(event):.1f}")


    highlight_segments = get_highlight_segments_to_keep(dummy_overlay_data, mock_settings)

    print("\n--- Resulting VideoEdit Segments (to KEEP) ---")
    if highlight_segments:
        total_kept_duration = 0
        for i, segment in enumerate(highlight_segments):
            print(f"Segment {i+1}: {segment}")
            total_kept_duration += segment.duration
        print(f"Total duration of kept segments: {total_kept_duration:.2f}s")
    else:
        print("No segments selected for highlights.")

    # Example of more targeted test for merging
    print("\n--- Testing Merging Logic ---")
    test_merge_events = [
        RaceEvent(start_time=1, end_time=3, interest="Test"),
        RaceEvent(start_time=2, end_time=4, interest="Test"), # Overlaps with previous
        RaceEvent(start_time=4.2, end_time=5, interest="Test"), # Adjacent (within 0.5s tolerance)
        RaceEvent(start_time=10, end_time=12, interest="Test"), # Separate
    ]
    # Temporarily set all_selected_events for this mini-test within the demo
    # This part of the demo requires manual execution of the merge logic,
    # as _select_top_events_for_duration and category selection is complex.
    # The main call above already tests the full pipeline.

    # To directly test merging part of get_highlight_segments_to_keep:
    # We'd sort test_merge_events, then apply the merging loop.
    # This is what the main function does with `unique_selected_events`.
    # Let's simulate that part:

    # Simulate step 4 of get_highlight_segments_to_keep
    sorted_test_merge_events = sorted(test_merge_events, key=lambda ev: ev.start_time)
    merged_test_edits: List[VideoEdit] = []
    if sorted_test_merge_events:
        current_edit_start = sorted_test_merge_events[0].start_time
        current_edit_end = sorted_test_merge_events[0].end_time
        merge_tolerance = 0.5
        for i in range(1, len(sorted_test_merge_events)):
            next_event = sorted_test_merge_events[i]
            if next_event.start_time <= current_edit_end + merge_tolerance:
                current_edit_end = max(current_edit_end, next_event.end_time)
            else:
                merged_test_edits.append(VideoEdit(start_time=current_edit_start, end_time=current_edit_end))
                current_edit_start = next_event.start_time
                current_edit_end = next_event.end_time
        merged_test_edits.append(VideoEdit(start_time=current_edit_start, end_time=current_edit_end))

    print("Test merge events:")
    for e in test_merge_events: print(f"  {e.start_time}-{e.end_time}")
    print("Merged test edits:")
    for s in merged_test_edits: print(f"  {s}")
    # Expected: VideoEdit(start=1.00s, end=5.00s, dur=4.00s), VideoEdit(start=10.00s, end=12.00s, dur=2.00s)


    print("\nVideoEditing Demonstration finished.")

```
