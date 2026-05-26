"""Audio IO and shaping helpers shared by the recorder and generator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from pydub import AudioSegment


def load_wav(path: Path | str) -> tuple[np.ndarray, int]:
    """Load a WAV as float32 mono (averaging channels if needed)."""
    samples, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    return samples.astype(np.float32, copy=False), sr


def save_wav(path: Path | str, samples: np.ndarray, sample_rate: int) -> None:
    sf.write(str(path), samples.astype(np.float32, copy=False), sample_rate, subtype="PCM_16")


def trim_silence(
    samples: np.ndarray,
    sample_rate: int,
    threshold_db: float,
    silence_min_ms: int,
) -> np.ndarray:
    """Trim leading/trailing silence using a windowed RMS detector.

    Anything quieter than ``threshold_db`` for at least ``silence_min_ms``
    at the head or tail of the buffer is dropped.
    """
    if samples.size == 0:
        return samples

    frame_size = max(1, int(sample_rate * silence_min_ms / 1000))
    n_frames = samples.size // frame_size
    if n_frames == 0:
        return samples

    trimmed_view = samples[: n_frames * frame_size].reshape(n_frames, frame_size)
    rms = np.sqrt(np.mean(trimmed_view.astype(np.float64) ** 2, axis=1) + 1e-12)
    rms_db = 20.0 * np.log10(rms + 1e-12)
    loud = rms_db > threshold_db
    if not loud.any():
        return np.zeros(0, dtype=samples.dtype)

    first = int(np.argmax(loud))
    last = int(n_frames - 1 - np.argmax(loud[::-1]))
    start = first * frame_size
    end = (last + 1) * frame_size
    return samples[start:end]


def _first_silence_frame(
    samples: np.ndarray,
    window_start: int,
    window_end: int,
    frame_size: int,
    threshold_db: float,
) -> int | None:
    """Return the sample index of the first silent frame inside the window, or None."""
    window_end = min(window_end, samples.size)
    if window_end - window_start < frame_size:
        return None
    n_frames = (window_end - window_start) // frame_size
    view = samples[window_start : window_start + n_frames * frame_size].reshape(
        n_frames, frame_size
    )
    rms = np.sqrt(np.mean(view.astype(np.float64) ** 2, axis=1) + 1e-12)
    rms_db = 20.0 * np.log10(rms + 1e-12)
    silent = rms_db <= threshold_db
    if not silent.any():
        return None
    return window_start + int(np.argmax(silent)) * frame_size


def split_into_chunks(
    samples: np.ndarray,
    sample_rate: int,
    min_chunk_seconds: int,
    max_chunk_seconds: int,
    threshold_db: float,
    silence_min_ms: int,
    drop_last_short: bool,
) -> list[np.ndarray]:
    """Split into chunks of at least ``min_chunk_seconds``, cutting at the next
    silent gap when possible, and hard-capping at ``max_chunk_seconds``."""
    if samples.size == 0:
        return []
    min_size = min_chunk_seconds * sample_rate
    max_size = max_chunk_seconds * sample_rate
    frame_size = max(1, int(sample_rate * silence_min_ms / 1000))

    chunks: list[np.ndarray] = []
    pos = 0
    while pos < samples.size:
        remaining = samples.size - pos
        if remaining < min_size:
            if not drop_last_short:
                chunks.append(samples[pos:])
            break
        if remaining <= max_size:
            chunks.append(samples[pos:])
            break
        window_start = pos + min_size
        window_end = pos + max_size
        split_at = _first_silence_frame(
            samples, window_start, window_end, frame_size, threshold_db
        )
        if split_at is None:
            split_at = window_end
        chunks.append(samples[pos:split_at])
        pos = split_at
    return chunks


def crossfade_concat(
    clips: list[np.ndarray],
    sample_rate: int,
    crossfade_ms: int,
) -> np.ndarray:
    """Concatenate float32 mono clips with equal-power cosine crossfades."""
    if not clips:
        return np.zeros(0, dtype=np.float32)
    if len(clips) == 1:
        return clips[0].astype(np.float32, copy=False)

    fade_len = int(sample_rate * crossfade_ms / 1000)
    out = clips[0].astype(np.float32, copy=True)
    for nxt in clips[1:]:
        nxt = nxt.astype(np.float32, copy=False)
        actual_fade = min(fade_len, out.size, nxt.size)
        if actual_fade <= 0:
            out = np.concatenate([out, nxt])
            continue
        t = np.linspace(0.0, np.pi / 2.0, actual_fade, dtype=np.float32)
        fade_out = np.cos(t)
        fade_in = np.sin(t)
        tail = out[-actual_fade:] * fade_out + nxt[:actual_fade] * fade_in
        out = np.concatenate([out[:-actual_fade], tail, nxt[actual_fade:]])
    return out


def to_mp3(
    samples: np.ndarray,
    sample_rate: int,
    path: Path | str,
    bitrate: str,
) -> None:
    """Encode a float32 mono numpy array to MP3 via pydub (ffmpeg)."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    segment = AudioSegment(
        data=pcm.tobytes(),
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )
    segment.export(str(path), format="mp3", bitrate=bitrate)
