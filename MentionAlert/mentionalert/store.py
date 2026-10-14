"""Encrypted, auto-expiring local storage of alert events.

Only the matched snippet and the summary are stored (never audio, never the
full transcript). The encryption key is protected with Windows DPAPI, so it
can only be unwrapped by this Windows user account on this PC.
"""
import ctypes
import json
import time
from ctypes import wintypes
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import DATA_DIR


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI operation failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


class EventStore:
    def __init__(self, data_dir: Path = DATA_DIR, retention_hours: float = 24):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.key_path = self.dir / "key.bin"
        self.events_path = self.dir / "events.enc"
        self.retention_s = retention_hours * 3600
        self._fernet = Fernet(self._load_key())

    def _load_key(self) -> bytes:
        if self.key_path.exists():
            return _dpapi(self.key_path.read_bytes(), protect=False)
        key = Fernet.generate_key()
        self.key_path.write_bytes(_dpapi(key, protect=True))
        return key

    def add(self, event: dict) -> None:
        line = self._fernet.encrypt(json.dumps(event).encode("utf-8"))
        with self.events_path.open("ab") as f:
            f.write(line + b"\n")

    def list(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        out = []
        for line in self.events_path.read_bytes().splitlines():
            try:
                out.append(json.loads(self._fernet.decrypt(line)))
            except (InvalidToken, ValueError):
                continue
        return out

    def purge_expired(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        events = self.list()
        keep = [e for e in events if now - e.get("ts", 0) < self.retention_s]
        removed = len(events) - len(keep)
        if removed:
            self.events_path.unlink(missing_ok=True)
            for e in keep:
                self.add(e)
        return removed

    def delete_all(self) -> None:
        self.events_path.unlink(missing_ok=True)
        self.key_path.unlink(missing_ok=True)
        self._fernet = Fernet(self._load_key())
