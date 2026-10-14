"""Pipeline (pure logic, testable) and Engine (threads + lifecycle)."""
import queue
import subprocess
import threading
import time
import uuid
from collections import deque

import numpy as np

from . import audio as audio_mod
from .detect import MentionDetector, tokens
from .summarize import summarize as default_summarize

TEAMS_PROCESSES = ("ms-teams.exe", "teams.exe")


class Pipeline:
    """Audio chunk -> transcript -> mention detection -> summary -> event.

    Everything is held in memory; only finished alert events go to the store.
    """

    def __init__(self, cfg, transcribe, emit, store=None, summarize_fn=default_summarize,
                 run_async=True):
        self.cfg = cfg
        self.transcribe = transcribe
        self.emit = emit
        self.store = store
        self.summarize_fn = summarize_fn
        self.run_async = run_async
        self.detector = MentionDetector(cfg["names"], cfg["fuzzy_threshold"])
        self.reset()

    def reset(self) -> None:
        self.context = deque()
        self.prev_text = ""
        self.pending = None
        self.last_mention = -1e18
        self.last_sound = time.time()
        self.chunks = 0

    def process(self, ts: float, audio: np.ndarray) -> None:
        self.tick(ts)
        self.chunks += 1
        rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
        if rms < self.cfg["silence_rms"]:
            return
        self.last_sound = ts
        text = self.transcribe(audio)
        if not text:
            return
        self.emit({"type": "transcript", "text": text})
        if self.pending:
            self.pending["parts"].append(text)
        combined = (self.prev_text + " " + text).strip()
        boundary = len(tokens(self.prev_text))
        new_hits = [h for h in self.detector.find(combined) if h[1] > boundary]
        if new_hits and not self.pending and ts - self.last_mention >= self.cfg["cooldown_seconds"]:
            self._start_mention(ts, combined, text)
        self.context.append((ts, text))
        while self.context and ts - self.context[0][0] > self.cfg["context_seconds"]:
            self.context.popleft()
        self.prev_text = text

    def _start_mention(self, ts, combined, text):
        self.last_mention = ts
        snippet = self.detector.snippet(combined)
        before = " ".join(t for _, t in self.context)
        self.pending = {
            "id": uuid.uuid4().hex[:8], "ts": ts, "snippet": snippet,
            "parts": [text], "before": before,
            "deadline": ts + self.cfg["post_roll_seconds"],
        }
        self.emit({"type": "mention", "id": self.pending["id"], "ts": ts, "snippet": snippet})

    def tick(self, now: float) -> None:
        if self.pending and now >= self.pending["deadline"]:
            p, self.pending = self.pending, None
            if self.run_async:
                threading.Thread(target=self._finalize, args=(p,), daemon=True).start()
            else:
                self._finalize(p)

    def _finalize(self, p) -> None:
        context = (p["before"] + " " + " ".join(p["parts"])).strip()
        snippet = self.detector.snippet(context)
        name = self.cfg["names"][0] if self.cfg["names"] else "the user"
        summary, source = self.summarize_fn(self.cfg, name, context, snippet)
        event = {"id": p["id"], "ts": p["ts"], "snippet": snippet,
                 "summary": summary, "source": source}
        if self.cfg["save_events"] and self.store:
            self.store.add(event)
        self.emit({"type": "summary", **event})


def teams_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=10, creationflags=0x08000000).stdout.lower()
    except Exception:
        return True
    return any(p in out for p in TEAMS_PROCESSES)


class Engine:
    def __init__(self, cfg, emit, store=None):
        self.cfg = cfg
        self.emit = emit
        self.store = store
        self.state = "stopped"
        self.q = queue.Queue(maxsize=cfg["queue_max_chunks"])
        self.dropped = 0
        self.transcriber = None
        self.pipeline = None
        self.worker = None
        self.capture = None
        self.cap_stop = threading.Event()
        self.stop_all = threading.Event()
        self.teams_seen = False
        self.teams_gone_since = None
        self.last_teams_check = 0.0

    def _set(self, state, msg=""):
        self.state = state
        self.emit({"type": "status", "state": state, "msg": msg})

    def _drop(self):
        self.dropped += 1

    def start(self):
        if self.state in ("loading", "listening"):
            return
        if self.state == "paused" and self.worker and self.worker.is_alive():
            self.pipeline.reset()
            self._start_capture()
            self._set("listening")
            return
        self.stop_all.clear()
        self._set("loading", "Loading speech model...")
        self.worker = threading.Thread(target=self._work, daemon=True)
        self.worker.start()

    def _start_capture(self):
        self.cap_stop = threading.Event()
        stop = self.cap_stop

        def run():
            try:
                audio_mod.capture_loop(self.cfg, self.q, stop, self._drop)
            except Exception as e:
                self.emit({"type": "error", "msg": f"Audio capture failed: {e}"})
                threading.Thread(target=self.stop, daemon=True).start()

        self.capture = threading.Thread(target=run, daemon=True)
        self.capture.start()

    def _halt_capture(self):
        self.cap_stop.set()
        if self.capture and self.capture is not threading.current_thread():
            self.capture.join(timeout=5)
        self.capture = None
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    def pause(self):
        if self.state != "listening":
            return
        self._halt_capture()
        if self.pipeline:
            self.pipeline.reset()
        self._set("paused", "Capture paused; buffers cleared.")

    def stop(self):
        if self.state == "stopped":
            return
        self.stop_all.set()
        self._halt_capture()
        if self.worker and self.worker is not threading.current_thread():
            self.worker.join(timeout=10)
        if self.pipeline:
            self.pipeline.reset()
        self.transcriber = None
        self._set("stopped", "Stopped; memory cleared.")

    def _work(self):
        try:
            if self.transcriber is None:
                from .stt import Transcriber
                self.transcriber = Transcriber(self.cfg)
            self.pipeline = Pipeline(self.cfg, self.transcriber.transcribe, self.emit, self.store)
        except Exception as e:
            self.emit({"type": "error", "msg": f"Could not load speech model: {e}. "
                                               "Run setup.bat / download-models first."})
            self._set("stopped")
            return
        self.teams_seen, self.teams_gone_since = False, None
        self._start_capture()
        self._set("listening")
        while not self.stop_all.is_set():
            try:
                ts, chunk = self.q.get(timeout=1)
            except queue.Empty:
                self.pipeline.tick(time.time())
                self._watchdog()
                continue
            try:
                self.pipeline.process(ts, chunk)
            except Exception as e:
                self.emit({"type": "error", "msg": f"Processing error: {e}"})
            self.emit({"type": "stats", "chunks": self.pipeline.chunks, "dropped": self.dropped})
            self._watchdog()

    def _watchdog(self):
        if self.state != "listening":
            return
        limit = self.cfg["auto_stop_silence_minutes"] * 60
        if limit and time.time() - self.pipeline.last_sound > limit:
            self.emit({"type": "notice", "msg": "No audio for a long time; capture stopped automatically."})
            threading.Thread(target=self.stop, daemon=True).start()
            return
        if self.cfg["stop_when_teams_closed"] and time.time() - self.last_teams_check > 20:
            self.last_teams_check = time.time()
            if teams_running():
                self.teams_seen, self.teams_gone_since = True, None
            elif self.teams_seen:
                self.teams_gone_since = self.teams_gone_since or time.time()
                if time.time() - self.teams_gone_since > 60:
                    self.emit({"type": "notice", "msg": "Teams closed; capture stopped automatically."})
                    threading.Thread(target=self.stop, daemon=True).start()
