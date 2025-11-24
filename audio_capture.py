import sounddevice as sd
import numpy as np
from typing import Optional


DEFAULT_SAMPLE_RATE = 16000


def record_block(seconds: float, samplerate: int = DEFAULT_SAMPLE_RATE, device: Optional[int] = None) -> np.ndarray:
    """Record a mono audio block from the given input device.

    Parameters
    ----------
    seconds: float
        Duration of the recording in seconds.
    samplerate: int
        Sample rate in Hz.
    device: Optional[int]
        sounddevice input device index. If None, use system default.
    """
    frames = int(seconds * samplerate)
    audio = sd.rec(
        frames,
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    return audio.reshape(-1)
