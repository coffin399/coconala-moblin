import numpy as np
from faster_whisper import WhisperModel


def create_model(device_mode: str = "cpu", quality: str = "normal") -> WhisperModel:
    """Create a Whisper model for translation.

    device_mode: "cpu" or "cuda". Defaults to CPU.
    quality: str
        One of "ultra_low", "low", "normal", "high", "ultra_high".
    """
    device_mode = device_mode.lower()
    quality = quality.lower()
    if device_mode == "cuda":
        device = "cuda"
        compute_type = "float16"
    else:
        device = "cpu"
        # On CPU we keep everything int8 for memory/latency.
        compute_type = "int8"

    # Choose model size based on quality preset.
    if quality == "ultra_low":
        model_size = "tiny"
    elif quality == "low":
        model_size = "tiny"
    elif quality == "normal":
        model_size = "base"
    elif quality == "high":
        model_size = "small"
    elif quality == "ultra_high":
        model_size = "medium"
    else:
        # Fallback to tiny to avoid heavy models by accident.
        model_size = "tiny"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return model


def translate_segment(
    model: WhisperModel,
    audio: np.ndarray,
    sample_rate: int = 16000,
    mode: str = "translate",
    language: str | None = None,
    quality: str = "normal",
) -> str:
    """Run speech-to-text for a single audio segment.

    Parameters
    ----------
    model: WhisperModel
        Loaded faster-whisper model.
    audio: np.ndarray
        Float32 mono waveform.
    sample_rate: int
        Sample rate of the waveform.
    mode: str
        "translate" -> translate to English.
        "transcribe" -> transcribe in the original language.
    language: str | None
        Source language code (e.g. "ja", "en"). "auto" or None = auto-detect.
    quality: str
        One of "ultra_low", "low", "normal", "high", "ultra_high".
    """
    if audio.size == 0:
        return ""

    # faster-whisper accepts numpy arrays directly.
    task = "translate" if mode == "translate" else "transcribe"
    quality = quality.lower()

    if quality == "ultra_low":
        beam_size = 1
        best_of = 1
    elif quality == "low":
        beam_size = 2
        best_of = 2
    elif quality == "normal":
        beam_size = 3
        best_of = 3
    elif quality == "high":
        beam_size = 4
        best_of = 4
    elif quality == "ultra_high":
        beam_size = 5
        best_of = 5
    else:
        beam_size = 1
        best_of = 1
    lang_arg = None if language in (None, "", "auto") else language
    segments, _info = model.transcribe(
        audio,
        task=task,
        language=lang_arg,  # auto-detect if None
        beam_size=beam_size,
        best_of=best_of,
        vad_filter=True,
        word_timestamps=False,
        temperature=0.0,
        patience=0,
        suppress_tokens="-1",
        initial_prompt=None,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
        length_penalty=1.0,
        repetition_penalty=1.0,
    )

    texts = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            texts.append(text)

    if not texts:
        return ""

    return " ".join(texts)
