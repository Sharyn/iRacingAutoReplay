"""
Manages the application's overall state and notifies observers of changes.
"""

import enum
from typing import List, Callable, Optional


class AppStates(enum.Enum):
    """
    Defines the possible operational states of the application.
    """
    IDLE = "Idle"
    ANALYZING_REPLAY = "Analyzing Replay"
    CAPTURING_VIDEO = "Capturing Video"
    TRANSCODING_VIDEO = "Transcoding Video"
    ERROR = "Error State"

    def __str__(self):
        return self.value

class AppStateManager:
    """
    Manages the application's current state and notifies registered observers
    upon state changes.
    """

    def __init__(self):
        self._current_state: AppStates = AppStates.IDLE
        self._observers: List[Callable[[AppStates, Optional[str]], None]] = []
        self._last_message: Optional[str] = None # To store the message associated with the current state

    @property
    def current_state(self) -> AppStates:
        """Gets the current application state."""
        return self._current_state

    @property
    def last_message(self) -> Optional[str]:
        """Gets the message associated with the current application state."""
        return self._last_message

    def register_observer(self, callback: Callable[[AppStates, Optional[str]], None]) -> None:
        """
        Registers a callback function to be notified of state changes.

        Args:
            callback: A function that accepts new_state (AppStates) and an
                      optional message (str) as arguments.
        """
        if callback not in self._observers:
            self._observers.append(callback)

    def unregister_observer(self, callback: Callable[[AppStates, Optional[str]], None]) -> None:
        """
        Unregisters a callback function from state change notifications.

        Args:
            callback: The callback function to remove.
        """
        try:
            self._observers.remove(callback)
        except ValueError:
            # Callback not found, ignore.
            pass

    def change_state(self, new_state: AppStates, message: Optional[str] = None, force_notify: bool = False) -> None:
        """
        Changes the application's current state and notifies observers.

        Args:
            new_state: The new state to transition to.
            message: An optional message associated with this state change.
            force_notify: If True, observers will be notified even if the
                          new_state is the same as the current_state.
        """
        if not isinstance(new_state, AppStates):
            # Or raise a TypeError, depending on desired strictness.
            print(
                f"Warning: Attempted to change state to an invalid type: {type(new_state)}. "
                "State not changed."
            )
            return

        # If state and message are the same, and not forced, do nothing.
        # This prevents redundant notifications if the state effectively hasn't changed.
        # Consider if message changes alone (even if state is the same) should always notify.
        # Current logic: if state is same, message must also be same for no notification, unless forced.
        # A more granular check might be:
        # if self._current_state == new_state and not force_notify: return # Ignores message change
        if self._current_state == new_state and self._last_message == message and not force_notify:
            return

        self._current_state = new_state
        self._last_message = message

        # Notify observers
        # Notify observers.
        # Iterate over a copy of the list (list(self._observers)) in case an observer
        # tries to register/unregister itself during the notification loop.
        for observer in list(self._observers):
            try:
                observer(self._current_state, self._last_message)
            except Exception as e:
                # Catch general exceptions from observer callbacks to prevent one misbehaving observer
                # from halting notifications for others.
                observer_name = getattr(observer, '__name__', str(observer))
                print(f"Error notifying observer '{observer_name}': {e}")


if __name__ == '__main__':
    print("--- AppStateManager Demonstration ---")

    # Example observer callback
    def simple_observer(state: AppStates, message: Optional[str]):
        msg_str = f" | Message: '{message}'" if message else ""
        print(f"OBSERVER_1: State changed to {state}{msg_str}")

    def another_observer(state: AppStates, message: Optional[str]):
        if state == AppStates.ERROR:
            print(f"OBSERVER_2: Critical ERROR detected! Message: '{message or 'No details'}'")
        else:
            print(f"OBSERVER_2: Notified of state {state}. Message: '{message or 'N/A'}'")

    # Initialize the state manager
    state_manager = AppStateManager()
    print(f"Initial state: {state_manager.current_state} (Message: '{state_manager.last_message}')")

    # Register observers
    state_manager.register_observer(simple_observer)
    state_manager.register_observer(another_observer)
    print("\nRegistered: simple_observer, another_observer.")

    # Change state
    print("\nChanging state to ANALYZING_REPLAY...")
    state_manager.change_state(AppStates.ANALYZING_REPLAY, "Starting analysis of 'replay.rpy'.")
    print(f"Current state: {state_manager.current_state} (Message: '{state_manager.last_message}')")

    print("\nChanging state to CAPTURING_VIDEO (no message)...")
    state_manager.change_state(AppStates.CAPTURING_VIDEO)
    print(f"Current state: {state_manager.current_state} (Message: '{state_manager.last_message}')")

    print("\nAttempting to change to same state (CAPTURING_VIDEO) with no message (no force_notify)...")
    state_manager.change_state(AppStates.CAPTURING_VIDEO) # Should not re-notify
    print(f"State remains: {state_manager.current_state}")
    print("  (Observers should not have been re-notified if message also same)")

    print("\nAttempting to change to same state (CAPTURING_VIDEO) but with a new message...")
    state_manager.change_state(AppStates.CAPTURING_VIDEO, "Capture progress: 50%")
    print(f"State: {state_manager.current_state} (Message: '{state_manager.last_message}')")
    print("  (Observers should be notified due to message change)")

    print("\nAttempting to change to same state and message, but with force_notify=True...")
    state_manager.change_state(AppStates.CAPTURING_VIDEO, "Capture progress: 50%", force_notify=True)
    print(f"State: {state_manager.current_state} (Message: '{state_manager.last_message}')")
    print("  (Observers should have been re-notified due to force_notify)")

    print("\nChanging state to ERROR...")
    state_manager.change_state(AppStates.ERROR, "Video transcoding failed: FFmpeg not found.")
    print(f"Current state: {state_manager.current_state} (Message: '{state_manager.last_message}')")

    # Unregister an observer
    print("\nUnregistering simple_observer...")
    state_manager.unregister_observer(simple_observer)

    print("\nChanging state to IDLE (simple_observer should not be notified)...")
    state_manager.change_state(AppStates.IDLE, "Operations complete. System idle.")
    print(f"Final state: {state_manager.current_state} (Message: '{state_manager.last_message}')")

    print("\nAppStateManager demonstration finished.")
```
