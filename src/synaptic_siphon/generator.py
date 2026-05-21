"""siphon-generate: stitch random recordings into an effected story MP3."""

from __future__ import annotations

import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

from . import audio, effects
from .config import Config, GeneratorConfig

RECORDINGS_DIR = Path("recordings")
STORIES_DIR = Path("stories")


def _select_clips(cfg: GeneratorConfig, paths: list[Path], rng: random.Random) -> list[Path]:
    upper = min(cfg.max_clips, len(paths))
    n = rng.randint(cfg.min_clips, upper)
    chosen = rng.sample(paths, n)
    rng.shuffle(chosen)
    return chosen


def _load_clips(paths: list[Path]) -> tuple[list[np.ndarray], int]:
    clips: list[np.ndarray] = []
    sr: int | None = None
    for p in paths:
        samples, file_sr = audio.load_wav(p)
        if sr is None:
            sr = file_sr
        elif file_sr != sr:
            raise RuntimeError(
                f"sample-rate mismatch: {p} is {file_sr} Hz but earlier clips were {sr} Hz"
            )
        clips.append(samples)
    assert sr is not None
    return clips, sr


def _peak_normalize(samples: np.ndarray, target_dbfs: float = -1.0) -> np.ndarray:
    peak = float(np.max(np.abs(samples)))
    if peak <= 0.0:
        return samples
    target = 10.0 ** (target_dbfs / 20.0)
    return (samples * (target / peak)).astype(np.float32)


def generate(cfg: GeneratorConfig) -> Path:
    paths = sorted(RECORDINGS_DIR.glob("*.wav"))
    if len(paths) < cfg.min_clips:
        raise RuntimeError(
            f"need at least {cfg.min_clips} recordings, found {len(paths)} in {RECORDINGS_DIR}/"
        )

    seed = cfg.random_seed if cfg.random_seed != 0 else None
    pyrng = random.Random(seed)
    nprng = np.random.default_rng(seed)

    chosen = _select_clips(cfg, paths, pyrng)
    clips, sr = _load_clips(chosen)
    base = audio.crossfade_concat(clips, sr, cfg.crossfade_ms)
    duration_s = base.size / sr

    mix = base.copy()
    if cfg.heart.volume > 0.0:
        heart = effects.heart_thump(
            duration_s=duration_s,
            sample_rate=sr,
            bpm=cfg.heart.bpm,
            fundamental_hz=cfg.heart.fundamental_hz,
            beat_decay=cfg.heart.beat_decay,
        )
        mix = mix + heart[: mix.size] * cfg.heart.volume

    if cfg.bubbles.volume > 0.0:
        bubs = effects.bubbles(
            duration_s=duration_s,
            sample_rate=sr,
            density=cfg.bubbles.density,
            brightness_hz=cfg.bubbles.brightness_hz,
            rng=nprng,
        )
        mix = mix + bubs[: mix.size] * cfg.bubbles.volume

    mix = effects.lowpass(
        mix,
        sample_rate=sr,
        cutoff_hz=cfg.lowpass.cutoff_hz,
        order=cfg.lowpass.order,
    )
    mix = _peak_normalize(mix, target_dbfs=-1.0)

    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = STORIES_DIR / f"story-{stamp}.mp3"
    audio.to_mp3(mix, sr, out_path, bitrate=cfg.output_bitrate)

    print(
        f"wrote {out_path}  ({len(chosen)} clips, {duration_s:.1f}s)",
        flush=True,
    )
    return out_path


def main() -> None:
    cfg = Config.load()
    try:
        generate(cfg.generator)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
