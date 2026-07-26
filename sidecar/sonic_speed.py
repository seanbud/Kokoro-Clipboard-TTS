"""Streaming, pitch-preserving speech-rate control backed by vendored Sonic."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
import sys
from typing import Optional

import numpy as np


MIN_PLAYBACK_SPEED = 0.5
MAX_PLAYBACK_SPEED = 2.0


def native_library_filename(system: Optional[str] = None) -> str:
    system = system or platform.system()
    if system == "Windows":
        return "sonic_kctts.dll"
    if system == "Darwin":
        return "libsonic_kctts.dylib"
    return "libsonic_kctts.so"


def native_library_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "native" / native_library_filename()
    return Path(__file__).resolve().parent / "native" / native_library_filename()


def load_sonic_library(path: Optional[Path] = None):
    library_path = path or native_library_path()
    if not library_path.is_file():
        raise RuntimeError(f"Sonic DSP library is missing: {library_path}")
    library = ctypes.CDLL(os.fspath(library_path))
    float_pointer = ctypes.POINTER(ctypes.c_float)
    library.kctts_sonic_create.argtypes = [ctypes.c_int, ctypes.c_int]
    library.kctts_sonic_create.restype = ctypes.c_void_p
    library.kctts_sonic_destroy.argtypes = [ctypes.c_void_p]
    library.kctts_sonic_destroy.restype = None
    library.kctts_sonic_set_speed.argtypes = [ctypes.c_void_p, ctypes.c_float]
    library.kctts_sonic_set_speed.restype = None
    library.kctts_sonic_write_float.argtypes = [
        ctypes.c_void_p,
        float_pointer,
        ctypes.c_int,
    ]
    library.kctts_sonic_write_float.restype = ctypes.c_int
    library.kctts_sonic_read_float.argtypes = [
        ctypes.c_void_p,
        float_pointer,
        ctypes.c_int,
    ]
    library.kctts_sonic_read_float.restype = ctypes.c_int
    library.kctts_sonic_flush.argtypes = [ctypes.c_void_p]
    library.kctts_sonic_flush.restype = ctypes.c_int
    library.kctts_sonic_available.argtypes = [ctypes.c_void_p]
    library.kctts_sonic_available.restype = ctypes.c_int
    return library


class SonicSpeedProcessor:
    """Own one stateful Sonic stream for a playback session."""

    def __init__(
        self,
        sample_rate: int = 24_000,
        channels: int = 1,
        initial_speed: float = 1.0,
        library_path: Optional[Path] = None,
    ) -> None:
        if sample_rate <= 0 or channels <= 0:
            raise ValueError("sample_rate and channels must be positive")
        self.sample_rate = sample_rate
        self.channels = channels
        self._library = load_sonic_library(library_path)
        self._stream = self._library.kctts_sonic_create(sample_rate, channels)
        if not self._stream:
            raise RuntimeError("Sonic could not create a processing stream")
        self._speed = 1.0
        self.set_speed(initial_speed)

    @property
    def speed(self) -> float:
        return self._speed

    def set_speed(self, speed: float) -> None:
        speed = float(speed)
        if not MIN_PLAYBACK_SPEED <= speed <= MAX_PLAYBACK_SPEED:
            raise ValueError(
                f"speed must be between {MIN_PLAYBACK_SPEED} and {MAX_PLAYBACK_SPEED}"
            )
        if speed != self._speed:
            self._library.kctts_sonic_set_speed(self._stream, speed)
            self._speed = speed

    def process(self, audio, speed: Optional[float] = None) -> np.ndarray:
        if self._stream is None:
            raise RuntimeError("Sonic stream is closed")
        if speed is not None:
            self.set_speed(speed)
        frames = np.asarray(audio, dtype=np.float32)
        if frames.ndim == 1:
            frames = frames.reshape(-1, 1)
        if frames.ndim != 2 or frames.shape[1] != self.channels:
            raise ValueError(f"audio must have shape (frames, {self.channels})")
        frames = np.ascontiguousarray(frames)
        pointer = frames.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        if not self._library.kctts_sonic_write_float(
            self._stream,
            pointer,
            frames.shape[0],
        ):
            raise RuntimeError("Sonic rejected an audio buffer")
        return self._drain()

    def flush(self) -> np.ndarray:
        if self._stream is None:
            return np.empty((0, self.channels), dtype=np.float32)
        if not self._library.kctts_sonic_flush(self._stream):
            raise RuntimeError("Sonic failed to flush buffered audio")
        return self._drain()

    def _drain(self) -> np.ndarray:
        chunks = []
        while True:
            available = self._library.kctts_sonic_available(self._stream)
            if available <= 0:
                break
            output = np.empty((available, self.channels), dtype=np.float32)
            pointer = output.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            received = self._library.kctts_sonic_read_float(
                self._stream,
                pointer,
                available,
            )
            if received <= 0:
                break
            chunks.append(output[:received].copy())
        if not chunks:
            return np.empty((0, self.channels), dtype=np.float32)
        return np.concatenate(chunks, axis=0)

    def close(self) -> None:
        if self._stream is not None:
            self._library.kctts_sonic_destroy(self._stream)
            self._stream = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
