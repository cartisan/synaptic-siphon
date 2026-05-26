"""Synthesized sound effects used by the generator."""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def heart_thump(
    n_samples: int,
    sample_rate: int,
    bpm: float,
    fundamental_hz: float,
    beat_decay: float,
) -> np.ndarray:
    """A slow lub-dub heartbeat of a large creature.

    Each cycle is a louder ``lub`` followed by a softer ``dub`` ~150 ms later.
    Each beat is a sine at ``fundamental_hz`` with an exponential decay envelope.
    """
    n = n_samples
    out = np.zeros(n, dtype=np.float32)
    if n == 0 or bpm <= 0:
        return out

    seconds_per_cycle = 60.0 / bpm
    cycle_samples = int(seconds_per_cycle * sample_rate)
    if cycle_samples <= 0:
        return out

    beat_len = int(min(beat_decay * 4.0, seconds_per_cycle * 0.9) * sample_rate)
    if beat_len <= 0:
        return out
    t = np.arange(beat_len, dtype=np.float32) / sample_rate
    envelope = np.exp(-t / max(beat_decay, 1e-3)).astype(np.float32)
    lub = np.sin(2.0 * np.pi * fundamental_hz * t).astype(np.float32) * envelope
    dub = np.sin(2.0 * np.pi * (fundamental_hz * 1.2) * t).astype(np.float32) * envelope * 0.6
    dub_offset_samples = int(0.15 * sample_rate)

    for start in range(0, n, cycle_samples):
        end = min(start + beat_len, n)
        out[start:end] += lub[: end - start]
        dub_start = start + dub_offset_samples
        if dub_start < n:
            dub_end = min(dub_start + beat_len, n)
            out[dub_start:dub_end] += dub[: dub_end - dub_start]

    peak = float(np.max(np.abs(out)))
    if peak > 0.0:
        out /= peak
    return out


def bubbles(
    n_samples: int,
    sample_rate: int,
    density: float,
    brightness_hz: float,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Sparse Poisson-timed bubble bursts: rising chirps with a noise tail."""
    if rng is None:
        rng = np.random.default_rng()
    n = n_samples
    out = np.zeros(n, dtype=np.float32)
    if n == 0 or density <= 0:
        return out

    duration_s = n / sample_rate
    expected = max(1, int(duration_s * density * 1.5))
    intervals = rng.exponential(scale=1.0 / density, size=expected)
    onsets = np.cumsum(intervals)
    onsets = onsets[onsets < duration_s]

    for onset_s in onsets:
        start = int(onset_s * sample_rate)
        burst_len = int(rng.uniform(0.04, 0.12) * sample_rate)
        if burst_len <= 0 or start >= n:
            continue
        burst_len = min(burst_len, n - start)
        t = np.arange(burst_len, dtype=np.float32) / sample_rate
        f0 = float(rng.uniform(80.0, max(120.0, brightness_hz * 0.25)))
        f1 = float(rng.uniform(max(f0 + 50.0, brightness_hz * 0.5), brightness_hz))
        phase = 2.0 * np.pi * (f0 * t + 0.5 * (f1 - f0) / max(t[-1], 1e-6) * t * t)
        chirp = np.sin(phase).astype(np.float32)
        env = np.exp(-t * float(rng.uniform(15.0, 35.0))).astype(np.float32)
        noise_tail = rng.standard_normal(burst_len).astype(np.float32) * 0.15 * env
        burst = (chirp * env + noise_tail) * float(rng.uniform(0.4, 1.0))
        out[start : start + burst_len] += burst

    peak = float(np.max(np.abs(out)))
    if peak > 0.0:
        out /= peak
    return out


def lowpass(
    samples: np.ndarray,
    sample_rate: int,
    cutoff_hz: float,
    order: int,
) -> np.ndarray:
    """Zero-phase Butterworth low-pass. Returns float32."""
    nyquist = sample_rate / 2.0
    if cutoff_hz >= nyquist * 0.999:
        return samples.astype(np.float32, copy=False)
    sos = butter(order, cutoff_hz, btype="low", fs=sample_rate, output="sos")
    return sosfiltfilt(sos, samples).astype(np.float32)
