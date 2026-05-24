import hashlib
import math
import os
import threading
import wave
from pathlib import Path
from typing import Any, Dict, Optional


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, str(default))).strip().lower()
    return raw in {"1", "true", "yes", "on"}


class LocalTTSService:
    def __init__(self) -> None:
        self.output_dir = Path(
            os.environ.get(
                "LOCAL_TTS_OUTPUT_DIR",
                str(Path(__file__).resolve().parents[1] / "generated_tts"),
            )
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = os.environ.get("LOCAL_TTS_BASE_URL", "/media/tts").rstrip("/")
        self.default_lang = os.environ.get("LOCAL_TTS_DEFAULT_LANG", "en")
        self.default_voice = os.environ.get("LOCAL_TTS_DEFAULT_VOICE", "M1")
        self._lock = threading.Lock()
        self._supertonic = None
        self._backend = "wave_fallback"
        self._load_supertonic()

    def _load_supertonic(self) -> None:
        try:
            from supertonic import TTS  # type: ignore

            auto_download = _env_bool("SUPERTONIC_AUTO_DOWNLOAD", False)
            self._supertonic = TTS(auto_download=auto_download)
            self._backend = "supertonic"
        except Exception:
            self._supertonic = None
            self._backend = "wave_fallback"

    def health(self) -> Dict[str, Any]:
        return {
            "backend": self._backend,
            "supertonic_available": self._supertonic is not None,
            "output_dir": str(self.output_dir),
            "base_url": self.base_url,
        }

    def _cache_name(self, text: str, lang: str, voice: str, speed: float) -> str:
        key = f"{text}|{lang}|{voice}|{speed:.3f}|{self._backend}"
        return f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.wav"

    def _as_url(self, filename: str) -> str:
        return f"{self.base_url}/{filename}"

    def _write_fallback_wave(self, path: Path, text: str, speed: float) -> float:
        sample_rate = 22050
        base_seconds = max(0.8, min(12.0, len(text) / (14.0 * max(speed, 0.7))))
        frames = int(sample_rate * base_seconds)
        freq = 180.0
        amp = 9000
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for i in range(frames):
                val = int(amp * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
                wf.writeframesraw(val.to_bytes(2, byteorder="little", signed=True))
        return float(base_seconds)

    def synthesize(
        self,
        *,
        text: str,
        lang: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("text不能为空")
        safe_lang = str(lang or self.default_lang).strip() or self.default_lang
        safe_voice = str(voice or self.default_voice).strip() or self.default_voice
        safe_speed = max(0.7, min(2.0, float(speed or 1.0)))
        filename = self._cache_name(clean_text, safe_lang, safe_voice, safe_speed)
        path = self.output_dir / filename

        if path.exists():
            return {
                "audio_url": self._as_url(filename),
                "audio_path": str(path),
                "cached": True,
                "backend": self._backend,
            }

        with self._lock:
            if path.exists():
                return {
                    "audio_url": self._as_url(filename),
                    "audio_path": str(path),
                    "cached": True,
                    "backend": self._backend,
                }
            duration = 0.0
            if self._supertonic is not None:
                try:
                    style = self._supertonic.get_voice_style(voice_name=safe_voice)
                    wav, duration_arr = self._supertonic.synthesize(
                        text=clean_text,
                        lang=safe_lang,
                        voice_style=style,
                        speed=safe_speed,
                    )
                    self._supertonic.save_audio(wav, str(path))
                    duration = float(duration_arr[0]) if hasattr(duration_arr, "__len__") else float(duration_arr)
                except Exception:
                    duration = self._write_fallback_wave(path, clean_text, safe_speed)
            else:
                duration = self._write_fallback_wave(path, clean_text, safe_speed)
            return {
                "audio_url": self._as_url(filename),
                "audio_path": str(path),
                "cached": False,
                "backend": self._backend,
                "duration": round(duration, 3),
            }


_TTS_SINGLETON = LocalTTSService()


def get_tts_service() -> LocalTTSService:
    return _TTS_SINGLETON

