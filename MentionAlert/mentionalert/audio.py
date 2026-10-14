"""System-audio loopback capture (what you hear), mono 16 kHz, in memory only."""
import queue
import threading
import time

import numpy as np

SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.5


def list_speakers() -> list[str]:
    import soundcard as sc
    default = sc.default_speaker().name
    return [f"{s.name}{'  (default)' if s.name == default else ''}" for s in sc.all_speakers()]


def pick_speaker(name_part: str):
    import soundcard as sc
    if name_part:
        for s in sc.all_speakers():
            if name_part.lower() in s.name.lower():
                return s
        raise RuntimeError(f"No speaker matching '{name_part}'. Run: list-devices")
    return sc.default_speaker()


def capture_loop(cfg: dict, out: queue.Queue, stop: threading.Event, on_drop=None) -> None:
    """Push (timestamp, float32 mono audio) chunks onto a bounded queue.

    When the queue is full the oldest chunk is dropped, so memory never grows.
    """
    import ctypes
    import warnings

    import soundcard as sc
    warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)
    ctypes.windll.ole32.CoInitializeEx(None, 0)  # COM must be initialised in every thread
    try:
        _capture(cfg, out, stop, on_drop, sc)
    finally:
        ctypes.windll.ole32.CoUninitialize()


def _capture(cfg, out, stop, on_drop, sc) -> None:
    speaker = pick_speaker(cfg["speaker_name"])
    mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    block = int(SAMPLE_RATE * BLOCK_SECONDS)
    per_chunk = max(1, int(cfg["chunk_seconds"] / BLOCK_SECONDS))
    with mic.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
        while not stop.is_set():
            parts = []
            for _ in range(per_chunk):
                if stop.is_set():
                    return
                parts.append(rec.record(numframes=block)[:, 0])
            chunk = np.concatenate(parts).astype(np.float32)
            item = (time.time(), chunk)
            try:
                out.put_nowait(item)
            except queue.Full:
                try:
                    out.get_nowait()
                except queue.Empty:
                    pass
                out.put_nowait(item)
                if on_drop:
                    on_drop()
