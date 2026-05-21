"""TOML-backed configuration for the recorder and generator CLIs."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecorderConfig:
    sample_rate: int
    channels: int
    chunk_seconds: int
    silence_threshold_db: float
    silence_min_ms: int
    drop_last_short_chunk: bool


@dataclass(frozen=True)
class HeartConfig:
    volume: float
    bpm: float
    fundamental_hz: float
    beat_decay: float


@dataclass(frozen=True)
class BubblesConfig:
    volume: float
    density: float
    brightness_hz: float


@dataclass(frozen=True)
class LowpassConfig:
    cutoff_hz: float
    order: int


@dataclass(frozen=True)
class GeneratorConfig:
    min_clips: int
    max_clips: int
    crossfade_ms: int
    output_bitrate: str
    random_seed: int
    heart: HeartConfig
    bubbles: BubblesConfig
    lowpass: LowpassConfig


@dataclass(frozen=True)
class Config:
    recorder: RecorderConfig
    generator: GeneratorConfig

    @classmethod
    def load(cls, path: Path | str = "config.toml") -> Config:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"config file not found at {path.resolve()} — "
                "copy the one from the project root or recreate it"
            )
        with path.open("rb") as f:
            raw = tomllib.load(f)

        rec = raw["recorder"]
        gen = raw["generator"]
        return cls(
            recorder=RecorderConfig(
                sample_rate=rec["sample_rate"],
                channels=rec["channels"],
                chunk_seconds=rec["chunk_seconds"],
                silence_threshold_db=rec["silence_threshold_db"],
                silence_min_ms=rec["silence_min_ms"],
                drop_last_short_chunk=rec["drop_last_short_chunk"],
            ),
            generator=GeneratorConfig(
                min_clips=gen["min_clips"],
                max_clips=gen["max_clips"],
                crossfade_ms=gen["crossfade_ms"],
                output_bitrate=gen["output_bitrate"],
                random_seed=gen["random_seed"],
                heart=HeartConfig(**gen["heart"]),
                bubbles=BubblesConfig(**gen["bubbles"]),
                lowpass=LowpassConfig(**gen["lowpass"]),
            ),
        )
