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


def split_into_chunks(
    samples: np.ndarray,
    sample_rate: int,
    chunk_seconds: int,
    drop_last_short: bool,
) -> list[np.ndarray]:
    chunk_size = chunk_seconds * sample_rate
    if samples.size == 0:
        return []
    chunks: list[np.ndarray] = []
    for start in range(0, samples.size, chunk_size):
        chunk = samples[start : start + chunk_size]
        if chunk.size < chunk_size and drop_last_short:
            continue
        chunks.append(chunk)
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
