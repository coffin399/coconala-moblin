import numpy as np
from faster_whisper import WhisperModel


def create_model(device_mode: str = "cpu") -> WhisperModel:
    """Create a Whisper model for translation.

    device_mode: "cpu" or "cuda". Defaults to CPU.
    """
    device_mode = device_mode.lower()
    if device_mode == "cuda":
        device = "cuda"
        compute_type = "float16"
    else:
        device = "cpu"
        compute_type = "int8"

    # "tiny" is the smallest and lightest model. Good for CPU usage.
    model_size = "tiny"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return model


def translate_segment(
    model: WhisperModel,
    audio: np.ndarray,
    sample_rate: int = 16000,
    mode: str = "translate",
    language: str | None = None,
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
    """
    if audio.size == 0:
        return ""

    # faster-whisper accepts numpy arrays directly.
    task = "translate" if mode == "translate" else "transcribe"
    lang_arg = None if language in (None, "", "auto") else language
    segments, _info = model.transcribe(
        audio,
        task=task,
        language=lang_arg,  # auto-detect if None
        beam_size=1,
        best_of=1,
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
