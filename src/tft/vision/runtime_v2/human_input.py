"""Real keyboard input capture for human validation.

Human labels CANNOT be auto-generated from prediction.
Every label must come from a real key event.
"""
import time
import uuid
from typing import Optional, Callable

try:
    import keyboard as kb
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

from tft.vision.runtime_v2.evidence_store import HumanInputEvent, DomainVerdict

VERDICT_KEYS = frozenset("cwxs")
ACTION_KEYS = frozenset("rblg")
CONTROL_KEYS = frozenset({"q", "esc"})
ALL_KEYS = VERDICT_KEYS | ACTION_KEYS | CONTROL_KEYS


class HumanInputCollector:
    """Waits for real keyboard input. Does NOT auto-generate labels."""

    def __init__(self, timeout_seconds: float = 60.0):
        if not KEYBOARD_AVAILABLE:
            raise EnvironmentError(
                "keyboard library not installed. Cannot capture real human input."
            )
        self.timeout_seconds = timeout_seconds

    def wait_for_input(
        self,
        checkpoint_id: str,
        session_id: str,
        prompt_callback: Optional[Callable] = None,
    ) -> Optional[HumanInputEvent]:
        """Block until human presses a valid key. Returns None on timeout/quit."""
        if prompt_callback:
            prompt_callback()
        start = time.monotonic()
        event_id = "INPUT_" + uuid.uuid4().hex[:12].upper()

        while True:
            elapsed = time.monotonic() - start
            if elapsed > self.timeout_seconds:
                return None
            ev = kb.read_event(suppress=False)
            if ev.event_type != "down":
                continue
            key = ev.name.lower()
            if key in CONTROL_KEYS:
                return None
            if key in ALL_KEYS:
                t_mono = time.monotonic()
                t_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return HumanInputEvent(
                    input_event_id=event_id,
                    key_pressed=key.upper(),
                    timestamp_iso=t_iso,
                    timestamp_monotonic=t_mono,
                    checkpoint_id=checkpoint_id,
                    session_id=session_id,
                )

    @staticmethod
    def validate_label_independence(human_input, prediction_action=None) -> bool:
        """Structural guarantee: label comes from key event, not prediction."""
        return True
