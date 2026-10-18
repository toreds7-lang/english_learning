"""Kokoro text-to-speech (kokoro-onnx, CPU) with an on-disk clip cache.

Model files are looked up in, in order:
    $KOKORO_DIR
    <project>/models/kokoro/
    ~/.cache/paper-deck/kokoro/      (shared with the paper-deck skill)

Download them once with:
    uv run python -m app.tts --fetch
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "tts"
LOCAL_MODEL_DIR = ROOT / "models" / "kokoro"
SHARED_MODEL_DIR = Path.home() / ".cache" / "paper-deck" / "kokoro"

MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"

# A small, high-quality subset of the Kokoro voices (grades from hexgrad/Kokoro-82M VOICES.md).
VOICES = {
    "af_heart": "American · female (Heart)",
    "af_bella": "American · female (Bella)",
    "am_michael": "American · male (Michael)",
    "am_fenrir": "American · male (Fenrir)",
    "bf_emma": "British · female (Emma)",
    "bm_george": "British · male (George)",
}
DEFAULT_VOICE = "af_heart"
MAX_CHARS = 600


def model_dir() -> Path | None:
    candidates = [Path(p) for p in [os.environ.get("KOKORO_DIR")] if p]
    candidates += [LOCAL_MODEL_DIR, SHARED_MODEL_DIR]
    for d in candidates:
        if (d / MODEL_FILE).exists() and (d / VOICES_FILE).exists():
            return d
    return None


def clean_text(text: str) -> str:
    """Strip the *target* markers used in example sentences and collapse whitespace."""
    text = text.replace("*", "")
    return re.sub(r"\s+", " ", text).strip()[:MAX_CHARS]


class KokoroTTS:
    def __init__(self) -> None:
        self._kokoro = None
        self._lock = threading.Lock()
        self.error: str | None = None

    def status(self) -> dict:
        d = model_dir()
        return {
            "available": d is not None and self.error is None,
            "model_dir": str(d) if d else None,
            "error": self.error,
            "voices": VOICES,
            "default_voice": DEFAULT_VOICE,
        }

    def _load(self):
        if self._kokoro is None:
            d = model_dir()
            if d is None:
                raise RuntimeError("Kokoro model files not found. Run: uv run python -m app.tts --fetch")
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(str(d / MODEL_FILE), str(d / VOICES_FILE))
        return self._kokoro

    def synthesize(self, text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0) -> Path:
        """Return the path of a WAV clip for `text`, rendering it on a cache miss."""
        text = clean_text(text)
        if not text:
            raise ValueError("empty text")
        if voice not in VOICES:
            voice = DEFAULT_VOICE
        speed = round(min(max(speed, 0.5), 1.5), 2)

        key = hashlib.sha1(f"{voice}|{speed}|{text}".encode("utf-8")).hexdigest()[:20]
        out = CACHE_DIR / f"{key}.wav"
        if out.exists():
            return out

        import soundfile as sf

        # One synthesis at a time: the ONNX session already uses every CPU core.
        with self._lock:
            if out.exists():
                return out
            try:
                kokoro = self._load()
            except Exception as exc:  # missing files, broken install
                self.error = str(exc)
                raise
            lang = "en-gb" if voice.startswith("b") else "en-us"
            samples, sr = kokoro.create(text, voice=voice, speed=speed, lang=lang)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".part")
            sf.write(str(tmp), samples, sr, format="WAV", subtype="PCM_16")
            os.replace(tmp, out)
        return out


def fetch_models(dest: Path = LOCAL_MODEL_DIR) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in (MODEL_FILE, VOICES_FILE):
        target = dest / name
        if target.exists():
            print(f"{name}: already present")
            continue
        url = f"{RELEASE}/{name}"
        print(f"downloading {url}")
        tmp = target.with_suffix(target.suffix + ".part")

        def hook(blocks: int, block_size: int, total: int) -> None:
            if total > 0 and blocks % 400 == 0:
                print(f"  {min(blocks * block_size, total) / total:5.1%}", flush=True)

        urllib.request.urlretrieve(url, tmp, reporthook=hook)
        os.replace(tmp, target)
        print(f"{name}: {target.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch_models()
    else:
        print(__doc__)
