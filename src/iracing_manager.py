"""
Defines the interface for interacting with the iRacing simulation.

This module provides an abstract base class (or a regular class with
NotImplementedError) that outlines the methods required for connecting to iRacing,
retrieving telemetry and session data, and controlling replay functions.
Concrete implementations of this interface will handle the actual SDK interactions.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Callable

# Using ABC for a more formal interface definition,
# but methods will still raise NotImplementedError in a base concrete class
# or could be left as pure abstract methods.
# For this task, a regular class with NotImplementedError is also fine.
# Let's go with ABC and @abstractmethod for clarity of intent.


class IRacingManagerInterface(ABC):
    """
    Interface for managing interactions with the iRacing simulation.

    This class defines a contract for services that provide iRacing data
    and control, such as connecting to the sim, fetching telemetry,
    session information, and controlling replays.
    """

    @abstractmethod
    def connect(self) -> None:
        """
        Establishes a connection to the iRacing simulation.
        This typically involves initializing the SDK and verifying that iRacing is running.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnects from the iRacing simulation and cleans up SDK resources.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Checks if currently connected to the iRacing simulation and the SDK is active.

        Returns:
            bool: True if connected, False otherwise.
        """
        pass

    @abstractmethod
    def get_latest_data_sample(self) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest telemetry data sample from iRacing.

        The structure of the returned dictionary will depend on the specific SDK
        and the data available (e.g., speed, RPM, gear, lap times, session status).
        A more specific Pydantic or dataclass model could be used in a concrete
        implementation.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the latest telemetry data,
                                       or None if no new data is available or not connected.
        """
        pass

    @abstractmethod
    def get_session_data(self) -> Optional[Dict[str, Any]]: # Or Optional[str] for raw XML
        """
        Retrieves static session information from iRacing.

        This data typically includes details about the track, weather, drivers,
        car setup, etc. It's similar to the iRacingSDK's SessionData string (often XML).
        The return type could be a parsed dictionary/object or the raw string.

        Returns:
            Optional[Dict[str, Any]]: A dictionary or object representing the session data,
                                       or None if not available or not connected.
                                       Alternatively, could return Optional[str] if providing raw XML.
        """
        pass

    @abstractmethod
    def replay_move_to_frame(self, frame_number: int) -> None:
        """
        Moves the iRacing replay to a specific frame number.

        Args:
            frame_number: The target frame number in the replay.
        """
        pass

    @abstractmethod
    def replay_set_speed(self, speed_multiplier: int) -> None:
        """
        Sets the playback speed of the iRacing replay.

        Args:
            speed_multiplier: The desired speed multiplier (e.g., 1 for normal,
                              2 for double speed, 0 for pause if supported, etc.).
        """
        pass

    @abstractmethod
    def replay_get_current_frame(self) -> Optional[int]:
        """
        Gets the current frame number of the iRacing replay.

        Returns:
            Optional[int]: The current replay frame number, or None if not available.
        """
        pass

    @abstractmethod
    def replay_get_session_time(self) -> Optional[float]:
        """
        Gets the current simulation time within the replay.

        Returns:
            Optional[float]: The current session time in seconds, or None if not available.
        """
        pass

    @abstractmethod
    def is_replay_playing(self) -> bool:
        """
        Checks if the iRacing replay is currently playing.

        Returns:
            bool: True if the replay is playing, False otherwise (e.g., paused, stopped).
        """
        pass

    @abstractmethod
    def get_incidents(self, wait_time_seconds: float, max_incidents: int) -> List[Dict[str, Any]]:
        """
        Retrieves a list of incidents that occurred during the session or replay.
        This method might involve some form of polling or event listening depending on SDK capabilities.

        Args:
            wait_time_seconds: Time to wait or monitor for incidents.
            max_incidents: Maximum number of incidents to return.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents
                                   an incident. The structure of these dictionaries is
                                   a placeholder and would be defined by the concrete implementation.
        """
        pass

    @abstractmethod
    def focus_iracing_window(self) -> None:
        """
        Brings the iRacing simulation window to the foreground.
        This is equivalent to Win32 SetForegroundWindow.
        """
        pass

    @abstractmethod
    def wait_for_iracing_to_start(self, abort_check: Callable[[], bool]) -> bool:
        """
        Waits for the iRacing simulation to start and the SDK to become active.

        This method should periodically check for iRacing's presence.
        The `abort_check` callable provides a mechanism to interrupt the waiting process.

        Args:
            abort_check: A function that returns True if the waiting should be aborted.

        Returns:
            bool: True if iRacing started and SDK is active, False if the operation
                  was aborted via `abort_check`.
        """
        pass


class PlaceholderIRacingManager(IRacingManagerInterface):
    """
    A placeholder implementation of IRacingManagerInterface.
    All methods raise NotImplementedError, serving as a concrete class that
    can be instantiated for development or testing when actual iRacing
    interaction is not available or needed.
    """

    def connect(self) -> None:
        raise NotImplementedError("connect() is not implemented in PlaceholderIRacingManager")

    def disconnect(self) -> None:
        raise NotImplementedError("disconnect() is not implemented in PlaceholderIRacingManager")

    def is_connected(self) -> bool:
        raise NotImplementedError("is_connected() is not implemented in PlaceholderIRacingManager")

    def get_latest_data_sample(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("get_latest_data_sample() is not implemented in PlaceholderIRacingManager")

    def get_session_data(self) -> Optional[Dict[str, Any]]: # Or Optional[str]
        raise NotImplementedError("get_session_data() is not implemented in PlaceholderIRacingManager")

    def replay_move_to_frame(self, frame_number: int) -> None:
        raise NotImplementedError("replay_move_to_frame() is not implemented in PlaceholderIRacingManager")

    def replay_set_speed(self, speed_multiplier: int) -> None:
        raise NotImplementedError("replay_set_speed() is not implemented in PlaceholderIRacingManager")

    def replay_get_current_frame(self) -> Optional[int]:
        raise NotImplementedError("replay_get_current_frame() is not implemented in PlaceholderIRacingManager")

    def replay_get_session_time(self) -> Optional[float]:
        raise NotImplementedError("replay_get_session_time() is not implemented in PlaceholderIRacingManager")

    def is_replay_playing(self) -> bool:
        raise NotImplementedError("is_replay_playing() is not implemented in PlaceholderIRacingManager")

    def get_incidents(self, wait_time_seconds: float, max_incidents: int) -> List[Dict[str, Any]]:
        raise NotImplementedError("get_incidents() is not implemented in PlaceholderIRacingManager")

    def focus_iracing_window(self) -> None:
        raise NotImplementedError("focus_iracing_window() is not implemented in PlaceholderIRacingManager")

    def wait_for_iracing_to_start(self, abort_check: Callable[[], bool]) -> bool:
        raise NotImplementedError("wait_for_iracing_to_start() is not implemented in PlaceholderIRacingManager")


if __name__ == '__main__':
    # Example of how this might be used (though you can't call methods without them erroring)

    # This would be a concrete implementation using an actual SDK
    # class MyActualIRacingManager(IRacingManagerInterface):
    #     def connect(self) -> None: print("Actually connecting...")
    #     def disconnect(self) -> None: print("Actually disconnecting...")
    #     def is_connected(self) -> bool: return True
    #     # ... implement all other methods ...

    print("IRacingManagerInterface and PlaceholderIRacingManager defined.")
    print("This module provides a contract for iRacing SDK interaction classes.")

    # manager: IRacingManagerInterface = PlaceholderIRacingManager()
    # try:
    #     manager.connect()
    # except NotImplementedError as e:
    #     print(f"Caught expected error: {e}")

    # print("\nTo use this, a concrete class implementing IRacingManagerInterface is needed,")
    # print("which would wrap a specific iRacing Python SDK.")


