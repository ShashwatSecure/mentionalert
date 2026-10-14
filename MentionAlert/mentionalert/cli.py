"""Command line entry points.  Usage: python -m mentionalert <command>"""
import argparse
import sys
import time
import wave

import numpy as np

from . import netguard
from .config import MODELS_DIR, load_config


def cmd_gui(args):
    netguard.enable()
    from .gui import App
    App(load_config()).run()


def cmd_download_models(args):
    """The only step that uses the internet (fetches the Whisper model once)."""
    from .stt import download_model
    cfg = load_config()
    print(f"Downloading Whisper model '{cfg['whisper_model']}' into {MODELS_DIR} ...")
    download_model(cfg["whisper_model"])
    print("Done.")


def cmd_list_devices(args):
    from .audio import list_speakers
    for s in list_speakers():
        print(s)


def cmd_check(args):
    """Verify that the install is complete and fully local."""
    from .summarize import ollama_available
    cfg = load_config()
    netguard.enable()
    ok = True
    try:
        import socket
        socket.create_connection(("1.1.1.1", 53), timeout=2)
        print("FAIL  netguard did not block an external connection")
        ok = False
    except PermissionError:
        print("OK    netguard blocks external network access")
    except Exception as e:
        print(f"OK?   external connection failed ({type(e).__name__})")
    try:
        from .stt import Transcriber
        Transcriber(cfg)
        print(f"OK    Whisper model '{cfg['whisper_model']}' loads from {MODELS_DIR}")
    except Exception as e:
        print(f"FAIL  Whisper model: {e}")
        ok = False
    print("OK    Ollama model ready" if ollama_available(cfg) else
          f"NOTE  Ollama model '{cfg['ollama_model']}' not available: summaries will use the offline fallback")
    from .audio import list_speakers
    try:
        print("OK    Output devices: " + "; ".join(list_speakers()))
    except Exception as e:
        print(f"FAIL  audio devices: {e}")
        ok = False
    print("Names:", cfg["names"])
    return 0 if ok else 1


def cmd_text(args):
    """Test detection + summary on typed text (no audio)."""
    from .detect import MentionDetector
    from .summarize import summarize
    cfg = load_config()
    netguard.enable()
    det = MentionDetector(cfg["names"], cfg["fuzzy_threshold"])
    hits = det.find(args.text)
    print("Mention detected:", bool(hits))
    if hits:
        snip = det.snippet(args.text)
        print("Snippet:", snip)
        summary, source = summarize(cfg, cfg["names"][0], args.text, snip)
        print(f"Summary ({source}):", summary)


def cmd_file(args):
    """Run a WAV file through the full pipeline as if it were live audio."""
    from .engine import Pipeline
    from .stt import Transcriber
    netguard.enable()
    cfg = load_config()
    with wave.open(args.wav, "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        data = np.interp(np.arange(0, len(data), sr / 16000), np.arange(len(data)), data).astype(np.float32)
    events = []
    tr = Transcriber(cfg)
    pipe = Pipeline(cfg, tr.transcribe, lambda e: (events.append(e), print(e)), store=None, run_async=False)
    n = int(cfg["chunk_seconds"] * 16000)
    t0 = time.time()
    for i in range(0, len(data), n):
        pipe.process(t0 + i / 16000, data[i:i + n])
    pipe.tick(t0 + 1e9)
    print("Mentions:", sum(1 for e in events if e["type"] == "mention"))


def main():
    p = argparse.ArgumentParser(prog="mentionalert")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="open the app (default)").set_defaults(fn=cmd_gui)
    sub.add_parser("download-models", help="one-time model download").set_defaults(fn=cmd_download_models)
    sub.add_parser("list-devices", help="list output devices").set_defaults(fn=cmd_list_devices)
    sub.add_parser("check", help="verify the install").set_defaults(fn=cmd_check)
    t = sub.add_parser("text", help="test detection on text")
    t.add_argument("text")
    t.set_defaults(fn=cmd_text)
    f = sub.add_parser("file", help="test the full pipeline on a WAV file")
    f.add_argument("wav")
    f.set_defaults(fn=cmd_file)
    args = p.parse_args()
    if not args.cmd:
        args.fn = cmd_gui
    sys.exit(args.fn(args) or 0)
