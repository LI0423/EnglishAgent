import hashlib
import math
import os
import re
import threading
import wave
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse


_DASHSCOPE_MIME_TYPES = {
    "mp3": "audio/mpeg",
    "pcm": "audio/pcm",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
}

# 各格式的近似码率（字节/秒），用于按音频体积估算时长
_DASHSCOPE_BYTES_PER_SECOND = {
    "mp3": 32000.0,   # 256 kbps
    "pcm": 32000.0,   # 16 kHz * 16 bit * 单声道
    "wav": 44100.0,   # 22.05 kHz * 16 bit * 单声道
    "ogg": 4000.0,    # 32 kbps
}


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
        self._dashscope_available = False
        self._dashscope_api_key = (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("QWEN_KEY")
            or ""
        ).strip()
        self._dashscope_model = os.environ.get("DASHSCOPE_TTS_MODEL", "cosyvoice-v2").strip()
        self._dashscope_voice = os.environ.get("DASHSCOPE_TTS_VOICE", "longxiaochun_v2").strip()
        self._dashscope_format = os.environ.get("DASHSCOPE_TTS_FORMAT", "mp3").strip().lower()
        self._backend = "wave_fallback"
        self._minio = None
        self._minio_loaded = False
        self._minio_bucket = os.environ.get("MINIO_BUCKET", "english-agent")
        self._minio_public_base_url = os.environ.get("MINIO_PUBLIC_BASE_URL", "").rstrip("/")
        self._load_dashscope()
        if not self._dashscope_available:
            self._load_supertonic()
        # MinIO 探测涉及网络 I/O，改为首次使用时懒加载，避免阻塞 import / 服务启动。

    def _load_dashscope(self) -> None:
        if not self._dashscope_api_key:
            return
        try:
            import dashscope  # type: ignore  # noqa: F401
            from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore  # noqa: F401

            self._dashscope_available = True
            self._backend = "dashscope_cosyvoice"
        except Exception:
            self._dashscope_available = False

    def _load_supertonic(self) -> None:
        try:
            from supertonic import TTS  # type: ignore

            auto_download = _env_bool("SUPERTONIC_AUTO_DOWNLOAD", False)
            self._supertonic = TTS(auto_download=auto_download)
            self._backend = "supertonic"
        except Exception:
            self._supertonic = None
            self._backend = "wave_fallback"

    def _load_minio(self) -> None:
        endpoint = (
            os.environ.get("MINIO_ENDPOINT")
            or os.environ.get("MINIO_URL")
            or ""
        ).strip()
        access_key = (
            os.environ.get("MINIO_ACCESS_KEY")
            or os.environ.get("MINIO_ROOT_USER")
            or ""
        ).strip()
        secret_key = (
            os.environ.get("MINIO_SECRET_KEY")
            or os.environ.get("MINIO_ROOT_PASSWORD")
            or ""
        ).strip()
        if not endpoint or not access_key or not secret_key:
            return
        try:
            from minio import Minio  # type: ignore

            parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
            secure = _env_bool("MINIO_SECURE", parsed.scheme == "https")
            minio_endpoint = parsed.netloc or parsed.path
            self._minio = Minio(
                minio_endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
            if not self._minio.bucket_exists(self._minio_bucket):
                self._minio.make_bucket(self._minio_bucket)
        except Exception:
            self._minio = None

    def _ensure_minio(self) -> None:
        """首次真正需要 MinIO 时才做网络探测（双重检查加锁，只尝试一次）。"""
        if self._minio_loaded:
            return
        with self._lock:
            if self._minio_loaded:
                return
            self._minio_loaded = True
            self._load_minio()

    def health(self) -> Dict[str, Any]:
        return {
            "backend": self._backend,
            "supertonic_available": self._supertonic is not None,
            "output_dir": str(self.output_dir),
            "base_url": self.base_url,
            "dashscope_available": self._dashscope_available,
            "dashscope_configured": bool(self._dashscope_api_key),
            "dashscope_model": self._dashscope_model if self._dashscope_available else "",
            "dashscope_voice": self._dashscope_voice if self._dashscope_available else "",
            "dashscope_format": self._dashscope_format if self._dashscope_available else "",
            "minio_enabled": self._minio is not None,
            "minio_bucket": self._minio_bucket if self._minio is not None else "",
        }

    def _audio_extension(self) -> str:
        if self._backend == "dashscope_cosyvoice":
            return self._dashscope_format if self._dashscope_format in _DASHSCOPE_MIME_TYPES else "mp3"
        return "wav"

    def _audio_content_type(self) -> str:
        if self._backend == "dashscope_cosyvoice":
            return _DASHSCOPE_MIME_TYPES.get(self._audio_extension(), "audio/mpeg")
        return "audio/wav"

    def _resolve_voice(self, voice: Optional[str]) -> str:
        if self._backend == "dashscope_cosyvoice":
            safe_voice = str(voice or "").strip()
            if not safe_voice or safe_voice.upper() in {"M1", "M2", "F1", "F2"}:
                return self._dashscope_voice
            return safe_voice
        return str(voice or self.default_voice).strip() or self.default_voice


    def _cache_name(self, text: str, lang: str, voice: str, speed: float) -> str:
        key = f"{text}|{lang}|{voice}|{speed:.3f}|{self._backend}"
        return f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.{self._audio_extension()}"

    def _as_url(self, filename: str) -> str:
        return f"{self.base_url}/{filename}"

    def _minio_object_url(self, object_name: str) -> str:
        if self._minio_public_base_url:
            return f"{self._minio_public_base_url}/{self._minio_bucket}/{object_name}"
        if self._minio is not None:
            return self._minio.presigned_get_object(self._minio_bucket, object_name)
        return ""

    def _word_audio_object_name(self, text: str, lang: str, voice: str, speed: float) -> str:
        key = f"{text.strip().lower()}|{lang}|{voice}|{speed:.3f}|{self._backend}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        # 仅保留安全字符，防止 lang 中的 "/" 或 ".." 污染对象 key。
        safe_lang = re.sub(r"[^a-zA-Z0-9-]+", "-", str(lang or "").lower().replace("_", "-")).strip("-") or "en-us"
        return f"vocabulary/pronunciation/{safe_lang}/{digest}.{self._audio_extension()}"

    def _resolve_audio_format(self):
        from dashscope.audio.tts_v2 import AudioFormat  # type: ignore

        formats = {
            "mp3": AudioFormat.MP3_22050HZ_MONO_256KBPS,
            "pcm": AudioFormat.PCM_16000HZ_MONO_16BIT,
            "wav": AudioFormat.WAV_22050HZ_MONO_16BIT,
            "ogg": AudioFormat.OGG_OPUS_16KHZ_MONO_32KBPS,
        }
        return formats.get(self._audio_extension(), AudioFormat.MP3_22050HZ_MONO_256KBPS)

    def _synthesize_dashscope(self, path: Path, text: str, voice: str) -> None:
        import dashscope  # type: ignore
        from dashscope.audio.tts_v2 import SpeechSynthesizer  # type: ignore

        dashscope.api_key = self._dashscope_api_key
        synth = SpeechSynthesizer(
            model=self._dashscope_model,
            voice=voice,
            format=self._resolve_audio_format(),
        )
        # 不再静默截断文本（此前 [:300] 会把整段听力素材截成残句）；
        # 超长文本若被供应商拒绝，会由上层回退到本地后端。
        audio_bytes = synth.call(text)
        if not audio_bytes:
            response = synth.get_response()
            raise RuntimeError(f"DashScope TTS 合成失败: {response}")
        path.write_bytes(audio_bytes)
        return self._estimate_audio_duration(audio_bytes)

    def _estimate_audio_duration(self, audio_bytes: bytes) -> float:
        """按音频字节数与格式码率估算时长，避免 duration 恒为 0。"""
        bytes_per_second = _DASHSCOPE_BYTES_PER_SECOND.get(self._audio_extension(), 32000.0)
        try:
            return round(len(audio_bytes) / bytes_per_second, 3)
        except Exception:
            return 0.0

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

    def _synthesize_local_fallback(self, path: Path, text: str, lang: str, voice: str, speed: float) -> float:
        if self._supertonic is not None:
            try:
                style = self._supertonic.get_voice_style(voice_name=voice)
                wav, duration_arr = self._supertonic.synthesize(
                    text=text,
                    lang=lang,
                    voice_style=style,
                    speed=speed,
                )
                self._supertonic.save_audio(wav, str(path))
                return float(duration_arr[0]) if hasattr(duration_arr, "__len__") else float(duration_arr)
            except Exception:
                pass
        return self._write_fallback_wave(path, text, speed)

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
        safe_voice = self._resolve_voice(voice)
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
            if self._dashscope_available:
                try:
                    duration = self._synthesize_dashscope(path, clean_text, safe_voice)
                except Exception:
                    # DashScope 失败时回退本地后端，避免整个接口 500。
                    duration = self._synthesize_local_fallback(path, clean_text, safe_lang, safe_voice, safe_speed)
            else:
                duration = self._synthesize_local_fallback(path, clean_text, safe_lang, safe_voice, safe_speed)
            return {
                "audio_url": self._as_url(filename),
                "audio_path": str(path),
                "cached": False,
                "backend": self._backend,
                "duration": round(duration, 3),
            }

    def synthesize_word_audio(
        self,
        *,
        word: str,
        lang: Optional[str] = "en-US",
        voice: Optional[str] = None,
        speed: float = 0.86,
    ) -> Dict[str, Any]:
        clean_word = str(word or "").strip()
        if not clean_word:
            raise ValueError("word不能为空")
        self._ensure_minio()
        safe_lang = str(lang or "en-US").strip() or "en-US"
        safe_voice = self._resolve_voice(voice)
        safe_speed = max(0.7, min(2.0, float(speed or 0.86)))

        object_name = self._word_audio_object_name(clean_word, safe_lang, safe_voice, safe_speed)
        if self._minio is not None:
            try:
                self._minio.stat_object(self._minio_bucket, object_name)
                return {
                    "audio_url": self._minio_object_url(object_name),
                    "object_name": object_name,
                    "cached": True,
                    "storage": "minio",
                    "backend": self._backend,
                }
            except Exception:
                pass

        result = self.synthesize(
            text=clean_word,
            lang=safe_lang,
            voice=safe_voice,
            speed=safe_speed,
        )
        if self._minio is not None:
            try:
                self._minio.fput_object(
                    self._minio_bucket,
                    object_name,
                    str(result.get("audio_path") or ""),
                    content_type=self._audio_content_type(),
                )
                return {
                    "audio_url": self._minio_object_url(object_name),
                    "object_name": object_name,
                    "cached": False,
                    "storage": "minio",
                    "backend": self._backend,
                    "duration": result.get("duration"),
                }
            except Exception:
                pass

        return {
            **result,
            "object_name": "",
            "storage": "local",
        }


_TTS_SINGLETON = LocalTTSService()


def get_tts_service() -> LocalTTSService:
    return _TTS_SINGLETON
