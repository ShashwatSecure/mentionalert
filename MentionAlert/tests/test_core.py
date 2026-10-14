import time

import numpy as np
import pytest

from mentionalert import netguard
from mentionalert.detect import MentionDetector
from mentionalert.engine import Pipeline
from mentionalert.store import EventStore
from mentionalert.summarize import FALLBACK, extractive, summarize

CFG = {
    "names": ["Alex Morgan", "Alex"], "fuzzy_threshold": 0.84, "silence_rms": 0.004,
    "context_seconds": 45, "post_roll_seconds": 8, "cooldown_seconds": 30,
    "ollama_enabled": False, "ollama_url": "http://127.0.0.1:1", "ollama_model": "x",
    "ollama_timeout_seconds": 1, "save_events": True,
}


def test_exact_and_possessive():
    d = MentionDetector(CFG["names"])
    assert d.find("Alex, can you take this?")
    assert d.find("that is Alex's item")


def test_fuzzy_asr_error():
    d = MentionDetector(CFG["names"])
    assert d.find("Alex Morgann can you update us")


def test_no_false_positive():
    d = MentionDetector(CFG["names"])
    assert not d.find("Let's discuss the shipping schedule and what happened last week")


def test_short_name_needs_exact():
    d = MentionDetector(["Ravi"])
    assert d.find("Ravi, over to you")
    assert not d.find("Ravin and Rana were there")


def test_snippet_has_following_sentence():
    d = MentionDetector(CFG["names"])
    s = d.snippet("Okay thanks. Alex, can you update the budget? We need it Friday.")
    assert "budget" in s and "Friday" in s


def test_snippet_has_three_sentences_before_and_two_after():
    d = MentionDetector(CFG["names"])
    text = ("One. Two. Three. Alex, please review this. Five. Six. Seven.")
    assert d.snippet(text) == "One. Two. Three. Alex, please review this. Five. Six."


def loud():
    return np.full(16000, 0.1, dtype=np.float32)


def run_pipeline(texts, **over):
    cfg = {**CFG, **over}
    events, it = [], iter(texts)
    p = Pipeline(cfg, lambda a: next(it), events.append, store=None,
                 summarize_fn=lambda c, n, ctx, snip: (extractive(snip), "fallback"), run_async=False)
    t = 1000.0
    for _ in texts:
        p.process(t, loud())
        t += 5
    p.tick(t + 100)
    return events


def test_pipeline_alert_and_summary():
    ev = run_pipeline(["Moving on to the budget.", "Alex, can you update the budget?", "Need it Friday."])
    types = [e["type"] for e in ev if e["type"] != "transcript"]
    assert types == ["mention", "summary"]
    assert "budget" in [e for e in ev if e["type"] == "summary"][0]["summary"]


def test_name_split_across_chunks():
    ev = run_pipeline(["Next we need", "Alex Morgan to confirm"])
    assert any(e["type"] == "mention" for e in ev)


def test_cooldown_suppresses_repeat():
    ev = run_pipeline(["Alex please check.", "Alex again?"])
    assert sum(e["type"] == "mention" for e in ev) == 1


def test_silence_skips_transcription():
    calls = []
    p = Pipeline(CFG, lambda a: calls.append(1) or "x", lambda e: None, run_async=False)
    p.process(1.0, np.zeros(16000, dtype=np.float32))
    assert not calls


def test_store_encrypts_and_purges(tmp_path):
    s = EventStore(tmp_path, retention_hours=24)
    now = time.time()
    s.add({"ts": now, "summary": "secret-new"})
    s.add({"ts": now - 25 * 3600, "summary": "secret-old"})
    assert b"secret" not in s.events_path.read_bytes()
    assert s.purge_expired(now) == 1
    assert [e["summary"] for e in s.list()] == ["secret-new"]
    s.delete_all()
    assert s.list() == [] and not s.events_path.exists()


def test_store_persists_across_instances(tmp_path):
    EventStore(tmp_path).add({"ts": time.time(), "summary": "hello"})
    assert EventStore(tmp_path).list()[0]["summary"] == "hello"


def test_fallbacks():
    assert extractive("") == FALLBACK
    assert summarize(CFG, "Alex", "ctx", "Alex do it.")[1] == "fallback"


def test_netguard_blocks_external():
    import socket
    netguard.enable()
    try:
        with pytest.raises(PermissionError):
            socket.create_connection(("93.184.216.34", 80), timeout=1)
        with pytest.raises(PermissionError):
            socket.getaddrinfo("example.com", 80)
    finally:
        netguard.disable()
