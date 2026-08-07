"""Waveform safety helpers for device-output boundaries."""

from __future__ import annotations

import numpy as np


DEFAULT_FADE_SAMPLES = 120  # 5 ms at the app's 24 kHz output rate.


def sanitize_audio_buffer(audio) -> np.ndarray:
    """Return finite, clipped float32 mono audio safe for device output."""

    result = np.asarray(audio, dtype=np.float32)
    if result.ndim == 1:
        result = result.reshape(-1, 1)
    elif result.ndim != 2 or result.shape[1] != 1:
        raise ValueError("audio output must be mono")
    result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)
    return np.clip(result, -1.0, 1.0).astype(np.float32, copy=False)


def fade_to_silence(
    last_sample,
    sample_count: int = DEFAULT_FADE_SAMPLES,
) -> np.ndarray:
    """Create a short ramp from the current device sample to digital silence."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    sample = np.asarray(last_sample, dtype=np.float32).reshape(1, -1)
    gains = np.linspace(1.0, 0.0, sample_count, dtype=np.float32).reshape(-1, 1)
    return sanitize_audio_buffer(gains * sample)


def fade_from_silence(
    audio,
    sample_count: int = DEFAULT_FADE_SAMPLES,
) -> np.ndarray:
    """Ramp the first output samples up from zero without mutating the input."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    result = sanitize_audio_buffer(audio).copy()
    fade_length = min(sample_count, len(result))
    if fade_length:
        gains = np.linspace(0.0, 1.0, fade_length, dtype=np.float32).reshape(-1, 1)
        result[:fade_length] *= gains
    return result
