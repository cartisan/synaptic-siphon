from __future__ import annotations

import numpy as np

from synaptic_siphon import audio, generator
from synaptic_siphon.config import (
    BubblesConfig,
    GeneratorConfig,
    HeartConfig,
    LowpassConfig,
)

SAMPLE_RATE = 44100
# 3,774,960 samples at 44,100 Hz round-trips through float seconds as
# 3,774,960 / 44,100 * 44,100 == 3,774,959.9999999995, and int() truncates to
# 3,774,959 — one sample short. effects.heart_thump used to size its output
# array from that float, so `mix + heart[:mix.size]` crashed in generate().
BUG_TRIGGERING_SAMPLES = 3_774_960


def _cfg() -> GeneratorConfig:
    return GeneratorConfig(
        min_clips=1,
        max_clips=1,
        crossfade_ms=0,
        output_bitrate="64k",
        random_seed=1,
        heart=HeartConfig(volume=0.15, bpm=30, fundamental_hz=50.0, beat_decay=0.4),
        bubbles=BubblesConfig(volume=0.10, density=1.2, brightness_hz=1200.0),
        lowpass=LowpassConfig(cutoff_hz=3000.0, order=4),
    )


def test_generate_survives_float_roundtrip_on_base_size(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recordings = tmp_path / "recordings"
    recordings.mkdir()

    rng = np.random.default_rng(0)
    samples = (rng.standard_normal(BUG_TRIGGERING_SAMPLES) * 0.1).astype(np.float32)
    audio.save_wav(recordings / "fixture.wav", samples, SAMPLE_RATE)

    out = generator.generate(_cfg())

    assert out.exists()
    assert out.suffix == ".mp3"
