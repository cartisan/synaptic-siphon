"""siphon-record: hold SPACE to record, release to save, ESC to quit."""

from __future__ import annotations

import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from pynput import keyboard

from .audio import save_wav, split_into_chunks, trim_silence
from .config import Config, RecorderConfig

RECORDINGS_DIR = Path("recordings")


class Recorder:
    def __init__(self, cfg: RecorderConfig) -> None:
        self.cfg = cfg
        self._buffer_lock = threading.Lock()
        self._current_blocks: list[np.ndarray] = []
        self._is_recording = threading.Event()
        self._takes: queue.Queue[np.ndarray] = queue.Queue()
        self._stop = threading.Event()

    def _audio_callback(self, indata, _frames, _time, status) -> None:
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        if self._is_recording.is_set():
            with self._buffer_lock:
                self._current_blocks.append(indata[:, 0].copy())

    def _on_press(self, key) -> bool | None:
        if key == keyboard.Key.space:
            if not self._is_recording.is_set():
                with self._buffer_lock:
                    self._current_blocks = []
                self._is_recording.set()
                print("  recording…", flush=True)
        elif key == keyboard.Key.esc:
            print("  exiting.", flush=True)
            self._stop.set()
            return False
        return None

    def _on_release(self, key) -> None:
        if key == keyboard.Key.space and self._is_recording.is_set():
            self._is_recording.clear()
            with self._buffer_lock:
                blocks = self._current_blocks
                self._current_blocks = []
            if blocks:
                take = np.concatenate(blocks).astype(np.float32, copy=False)
                self._takes.put(take)

    def _process_take(self, samples: np.ndarray) -> None:
        cfg = self.cfg
        trimmed = trim_silence(
            samples,
            sample_rate=cfg.sample_rate,
            threshold_db=cfg.silence_threshold_db,
            silence_min_ms=cfg.silence_min_ms,
        )
        if trimmed.size == 0:
            print("  (only silence — nothing saved)", flush=True)
            return
        chunks = split_into_chunks(
            trimmed,
            sample_rate=cfg.sample_rate,
            chunk_seconds=cfg.chunk_seconds,
            drop_last_short=cfg.drop_last_short_chunk,
        )
        if not chunks:
            duration = trimmed.size / cfg.sample_rate
            print(
                f"  (clip was {duration:.1f}s, shorter than chunk size — nothing saved)",
                flush=True,
            )
            return

        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for i, chunk in enumerate(chunks, start=1):
            path = RECORDINGS_DIR / f"rec-{stamp}-{i:02d}.wav"
            save_wav(path, chunk, cfg.sample_rate)
        total_s = trimmed.size / cfg.sample_rate
        print(f"  saved {len(chunks)} chunk(s) ({total_s:.1f}s after trim)", flush=True)

    def run(self) -> None:
        print(
            f"siphon-record  |  hold SPACE to record  |  ESC to quit  "
            f"|  {self.cfg.sample_rate} Hz, {self.cfg.channels} ch",
            flush=True,
        )
        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        listener.start()
        try:
            with sd.InputStream(
                samplerate=self.cfg.sample_rate,
                channels=self.cfg.channels,
                dtype="float32",
                callback=self._audio_callback,
            ):
                while not self._stop.is_set():
                    try:
                        take = self._takes.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    self._process_take(take)
        finally:
            listener.stop()
            listener.join()


def main() -> None:
    cfg = Config.load()
    Recorder(cfg.recorder).run()


if __name__ == "__main__":
    main()
