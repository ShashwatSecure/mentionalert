"""Local summaries via Ollama on 127.0.0.1, with an offline extractive fallback."""
import json
import re
import urllib.request

FALLBACK = "Your name was mentioned; review the meeting context."

PROMPT = (
    "Below is a short snippet of a meeting transcript produced by speech recognition "
    "(it may contain errors). The person of interest is called {name}.\n"
    "In ONE or TWO short sentences, say why {name} was referred to: what was asked of "
    "them or said about them. Use ONLY information in the snippet. Do not invent names, "
    "dates, numbers or decisions. If it is unclear, reply exactly: Unclear from the snippet.\n\n"
    "Snippet:\n\"\"\"\n{context}\n\"\"\"\n\nSummary:"
)


def ollama_available(cfg: dict) -> bool:
    try:
        with urllib.request.urlopen(cfg["ollama_url"] + "/api/tags", timeout=2) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
        want = cfg["ollama_model"]
        return any(m == want or m.split(":")[0] == want for m in models)
    except Exception:
        return False


def extractive(snippet: str) -> str:
    snippet = snippet.strip()
    if not snippet:
        return FALLBACK
    return f"Mentioned in: \u201c{snippet[:220]}\u201d"


def summarize(cfg: dict, name: str, context: str, snippet: str) -> tuple[str, str]:
    """Return (summary, source) where source is 'ollama' or 'fallback'."""
    if cfg["ollama_enabled"] and context.strip() and ollama_available(cfg):
        body = json.dumps({
            "model": cfg["ollama_model"],
            "prompt": PROMPT.format(name=name, context=context[-1500:]),
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 90},
        }).encode()
        req = urllib.request.Request(cfg["ollama_url"] + "/api/generate", body,
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=cfg["ollama_timeout_seconds"]) as r:
                text = json.load(r).get("response", "")
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
            if text:
                return text, "ollama"
        except Exception:
            pass
    return extractive(snippet), "fallback"
