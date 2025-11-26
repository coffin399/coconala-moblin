import sounddevice as sd
import numpy as np
from typing import Optional


DEFAULT_SAMPLE_RATE = 16000


def record_block(
    seconds: float,
    samplerate: int = DEFAULT_SAMPLE_RATE,
    device: Optional[int] = None,
    capture_mode: str = "input",
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
