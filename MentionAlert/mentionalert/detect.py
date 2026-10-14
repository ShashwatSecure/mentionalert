import re
from difflib import SequenceMatcher

_WORD = re.compile(r"[a-z0-9']+")


def tokens(text: str) -> list[str]:
    out = []
    for t in _WORD.findall(text.lower().replace("\u2019", "'")):
        t = t.strip("'")
        if t.endswith("'s"):
            t = t[:-2]
        if t:
            out.append(t)
    return out


def _tok_match(pattern: str, tok: str, threshold: float) -> bool:
    if pattern == tok:
        return True
    if len(pattern) < 5:  # short names must match exactly to avoid false alerts
        return False
    return SequenceMatcher(None, pattern, tok).ratio() >= threshold


class MentionDetector:
    def __init__(self, names: list[str], threshold: float = 0.84):
        self.patterns = [tokens(n) for n in names if tokens(n)]
        self.threshold = threshold

    def find(self, text: str) -> list[tuple[int, int]]:
        """Return (start, end) token index ranges where a configured name occurs."""
        toks = tokens(text)
        hits = []
        for pat in self.patterns:
            n = len(pat)
            for i in range(len(toks) - n + 1):
                if all(_tok_match(p, toks[i + j], self.threshold) for j, p in enumerate(pat)):
                    hits.append((i, i + n))
        return sorted(set(hits))

    def snippet(self, text: str, before: int = 3, after: int = 2,
                max_chars: int | None = None) -> str:
        """Return a sentence window around the first detected mention."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for i, s in enumerate(sentences):
            if self.find(s):
                snippet = " ".join(sentences[max(0, i - before):i + after + 1])
                return snippet if max_chars is None else snippet[:max_chars]
        text = text.strip()
        fallback_chars = 500 if max_chars is None else max_chars
        return text[-fallback_chars:]
