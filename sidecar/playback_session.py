"""Thread-safe lifecycle state for one TTS playback request."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Optional


@dataclass(frozen=True)
class PlaybackPosition:
    chunk_index: Optional[int]
    sample_offset: int


@dataclass
class PlaybackSession:
    request_id: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    _chunk_index: Optional[int] = None
    _sample_offset: int = 0
    _position_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _pause_acknowledged: bool = False
    _resume_pending: bool = False
    _playback_speed: float = 1.0
    _speed_version: int = 0
    _acknowledged_speed_version: int = 0
    _control_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def cancel(self) -> None:
        self.cancel_event.set()
        self.pause_event.clear()
        with self._control_lock:
            self._resume_pending = False

    def pause(self) -> None:
        if not self.cancel_event.is_set():
            with self._control_lock:
                self._pause_acknowledged = False
                self._resume_pending = False
                self.pause_event.set()

    def resume(self) -> None:
        with self._control_lock:
            if self.pause_event.is_set() and not self.cancel_event.is_set():
                self._resume_pending = True
            self.pause_event.clear()

    def acknowledge_pause(self) -> bool:
        """Return true exactly once after the stream stops for this pause."""
        with self._control_lock:
            if not self.pause_event.is_set() or self._pause_acknowledged:
                return False
            self._pause_acknowledged = True
            return True

    def acknowledge_resume(self) -> bool:
        """Return true exactly once after the stream restarts for this resume."""
        with self._control_lock:
            if self.pause_event.is_set() or not self._resume_pending:
                return False
            self._resume_pending = False
            self._pause_acknowledged = False
            return True

    def set_speed(self, speed: float) -> int:
        speed = float(speed)
        if speed < 0.5 or speed > 2.0:
            raise ValueError("speed must be between 0.5 and 2.0")
        with self._control_lock:
            if speed != self._playback_speed:
                self._playback_speed = speed
                self._speed_version += 1
            return self._speed_version

    def speed_snapshot(self) -> tuple[float, int]:
        with self._control_lock:
            return self._playback_speed, self._speed_version

    def acknowledge_speed(self, version: int) -> bool:
        with self._control_lock:
            if version <= self._acknowledged_speed_version:
                return False
            self._acknowledged_speed_version = version
            return True

    def set_position(self, chunk_index: int, sample_offset: int) -> None:
        with self._position_lock:
            self._chunk_index = chunk_index
            self._sample_offset = max(0, sample_offset)

    def clear_position(self) -> None:
        with self._position_lock:
            self._chunk_index = None
            self._sample_offset = 0

    def position(self) -> PlaybackPosition:
        with self._position_lock:
            return PlaybackPosition(self._chunk_index, self._sample_offset)


class PlaybackSessionController:
    """Owns the active session and prevents stale controls from crossing requests."""

    def __init__(self) -> None:
        self._active: Optional[PlaybackSession] = None
        self._lock = threading.Lock()

    def begin(self, request_id: str, initial_speed: float = 1.0) -> PlaybackSession:
        session = PlaybackSession(request_id=request_id)
        session.set_speed(initial_speed)
        with self._lock:
            if self._active is not None:
                self._active.cancel()
            self._active = session
        return session

    def active(self) -> Optional[PlaybackSession]:
        with self._lock:
            return self._active

    def is_active(self, session: PlaybackSession) -> bool:
        with self._lock:
            return self._active is session

    def clear(self, session: PlaybackSession) -> None:
        with self._lock:
            if self._active is session:
                self._active = None

    def control_target(
        self,
        request_id: str,
    ) -> tuple[Optional[PlaybackSession], Optional[str]]:
        """Return the active target or a stable error code for a stale control."""
        with self._lock:
            active = self._active
            if request_id and active is None:
                return None, "no_active_session"
            if request_id and active is not None and request_id != active.request_id:
                return None, "stale_session"
            return active, None
