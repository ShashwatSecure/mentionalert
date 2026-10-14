"""Local speech-to-text with faster-whisper (CPU, int8). Models live in ./models."""
import numpy as np

from .config import MODELS_DIR


def download_model(name: str) -> None:
    """One-time download (the only step that needs internet)."""
    from faster_whisper import WhisperModel
    MODELS_DIR.mkdir(exist_ok=True)
    WhisperModel(name, device="cpu", compute_type="int8", download_root=str(MODELS_DIR))


class Transcriber:
    def __init__(self, cfg: dict):
        from faster_whisper import WhisperModel
        self.cfg = cfg
        self.model = WhisperModel(
            cfg["whisper_model"], device="cpu", compute_type="int8",
            download_root=str(MODELS_DIR), local_files_only=True,
        )
        # Biases recognition toward the configured names.
        self.prompt = "Meeting discussion. Names: " + ", ".join(cfg["names"]) + "."

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio.astype(np.float32),
            language=self.cfg["language"] or None,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=self.prompt,
        )
        return " ".join(s.text.strip() for s in segments).strip()
