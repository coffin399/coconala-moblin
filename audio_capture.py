import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd


DEFAULT_SAMPLE_RATE = 16000


def _resolve_ffmpeg_binary() -> str:
    env_value = os.environ.get("MST_FFMPEG")
    if env_value:
        return env_value

    try:
        import imageio_ffmpeg  # type: ignore[import]

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    env_root = Path(sys.prefix)
    candidates = [
        env_root / "ffmpeg" / "bin" / "ffmpeg.exe",
        env_root / "ffmpeg" / "bin" / "ffmpeg",
        env_root / "bin" / "ffmpeg",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    return "ffmpeg"


def record_block(
    seconds: float,
    samplerate: int = DEFAULT_SAMPLE_RATE,
    device: Optional[int] = None,
    capture_mode: str = "input",
    srt_url: Optional[str] = None,
) -> np.ndarray:
    """Record a mono audio block from the given input or loopback device.

    Parameters
    ----------
    seconds: float
        Duration of the recording in seconds.
    samplerate: int
        Sample rate in Hz.
    device: Optional[int]
        sounddevice device index. If None, use system default.
        When capture_mode == "input", this is treated as an input device.
        When capture_mode == "loopback", this is treated as an output device
        (system output is used if None).
    capture_mode: str
        "input"   -> capture from an input device (existing behaviour)
        "loopback" -> capture system playback using WASAPI loopback when
                      available (Windows only). Falls back to input capture
                      if loopback is not available.
    """
    frames = int(seconds * samplerate)

    if capture_mode == "srt":
        if not srt_url:
            print("[srt] capture_mode='srt' ですが srt_url が指定されていません。")
            return np.zeros(0, dtype="float32")
        ffmpeg_bin = _resolve_ffmpeg_binary()
        audio_bytes = b""
        for attempt in range(3):
            try:
                proc = subprocess.run(
                    [
                        ffmpeg_bin,
                        "-loglevel",
                        "error",
                        "-i",
                        srt_url,
                        "-vn",
                        "-acodec",
                        "pcm_s16le",
                        "-ac",
                        "1",
                        "-ar",
                        str(samplerate),
                        "-t",
                        str(seconds),
                        "-f",
                        "s16le",
                        "pipe:1",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
            except FileNotFoundError as exc:
                print(f"[srt] ffmpeg バイナリが見つかりませんでした: {ffmpeg_bin!r} ({exc!r})")
                return np.zeros(0, dtype="float32")
            except Exception as exc:
                print(f"[srt] ffmpeg 実行中に予期しない例外が発生しました (attempt={attempt + 1}): {exc!r}")
                continue
            audio_bytes = proc.stdout or b""
            if proc.returncode != 0 or not audio_bytes:
                stderr_txt = ""
                if proc.stderr:
                    try:
                        stderr_txt = proc.stderr.decode(errors="ignore")
                    except Exception:
                        stderr_txt = "<stderr decode failed>"
                    if len(stderr_txt) > 500:
                        stderr_txt = stderr_txt[:500] + "..."
                print(
                    f"[srt] ffmpeg 実行に失敗しました (attempt={attempt + 1}, returncode={proc.returncode}). "
                    f"stderr={stderr_txt!r}"
                )
                audio_bytes = b""
                continue
            break

        if not audio_bytes:
            print("[srt] 複数回リトライしましたが、SRT から音声データを取得できませんでした。")
            return np.zeros(0, dtype="float32")
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype("float32") / 32768.0
        if audio.size == 0:
            return audio
        if audio.size < frames:
            pad = np.zeros(frames - audio.size, dtype="float32")
            audio = np.concatenate([audio, pad])
        elif audio.size > frames:
            audio = audio[:frames]
        return audio

    if capture_mode == "loopback":
        # Prefer capturing from the default output device when none is
        # specified. On Windows with WASAPI, this combined with
        # WasapiSettings(loopback=True) records system playback.
        output_device = device
        if output_device is None:
            try:
                default_in, default_out = sd.default.device  # type: ignore[misc]
                output_device = default_out
            except Exception:  # noqa: BLE001
                output_device = None

        extra_settings = None
        try:
            wasapi_cls = getattr(sd, "WasapiSettings", None)
        except Exception:  # noqa: BLE001
            wasapi_cls = None

        if wasapi_cls is not None:
            try:
                extra_settings = wasapi_cls(loopback=True)
            except TypeError:
                extra_settings = None

        try:
            audio = sd.rec(
                frames,
                samplerate=samplerate,
                channels=2,
                dtype="float32",
                device=output_device,
                extra_settings=extra_settings,  # type: ignore[arg-type]
            )
            sd.wait()
            if audio.ndim == 2 and audio.shape[1] > 1:
                audio_mono = audio.mean(axis=1).astype("float32", copy=False)
            else:
                audio_mono = audio.reshape(-1)
            return audio_mono
        except Exception:  # noqa: BLE001
            # Fallback to normal input capture if loopback capture fails
            pass

    audio = sd.rec(
        frames,
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return audio.reshape(-1)
