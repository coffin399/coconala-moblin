from pathlib import Path
import os
import sys
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel
import ctranslate2
import sentencepiece as spm
from huggingface_hub import snapshot_download


def create_model(device_mode: str = "cpu", quality: str = "normal") -> WhisperModel:
    """Create a kotoba-whisper-v2.2-faster model for translation.

    device_mode: "cpu" or "cuda". Defaults to CPU.
    quality: str
        One of "ultra_low", "low", "normal", "high", "ultra_high".

    Note: The underlying model is always RoachLin/kotoba-whisper-v2.2-faster
    (a CTranslate2 export). The quality preset only affects decoding settings,
    not which checkpoint is loaded.
    """
    device_mode = (device_mode or "cpu").lower()
    quality = (quality or "normal").lower()

    # Safety gate: by default, even if "cuda" is選択, 実際のロードは CPU に強制。
    # CUDA を本当に使いたい場合だけ MST_ENABLE_CUDA=1 を環境変数で明示する。
    use_cuda = device_mode == "cuda" and os.environ.get("MST_ENABLE_CUDA") == "1"
    if use_cuda:
        device = "cuda"
        # The model card example uses float32 on CUDA; keep it for accuracy.
        compute_type = "float32"
    else:
        device = "cpu"
        # On CPU we keep everything int8 for memory/latency.
        compute_type = "int8"

    # Fixed model id for kotoba-whisper-v2.2-faster.
    model_id = "RoachLin/kotoba-whisper-v2.2-faster"

    # Use a cache directory under the current Python environment so that
    # models stay inside the venv (e.g. .venv/models/faster-whisper).
    env_root = Path(sys.prefix)
    cache_root = env_root / "models" / "faster-whisper"
    cache_root.mkdir(parents=True, exist_ok=True)

    # Debug: log which model is being used and where it is cached.
    print(
        f"[model] creating kotoba-whisper-v2.2-faster model_id={model_id!r} "
        f"device={device!r} compute_type={compute_type!r} cache_root={str(cache_root)!r}"
    )

    try:
        model = WhisperModel(
            model_id,
            device=device,
            compute_type=compute_type,
            download_root=str(cache_root),
        )
        return model
    except Exception as exc:  # noqa: BLE001
        # If CUDA initialisation fails (missing cudnn DLL, invalid handle, etc.),
        # fall back to CPU so the process does not crash (for environments
        # without a proper CUDA/cuDNN setup).
        if device == "cuda":
            print(
                f"[model warning] CUDA initialisation failed ({exc!r}); "
                "falling back to CPU (int8).",
            )
            fallback_device = "cpu"
            fallback_compute_type = "int8"
            print(
                f"[model] retrying on device={fallback_device!r} "
                f"compute_type={fallback_compute_type!r}",
            )
            model = WhisperModel(
                model_id,
                device=fallback_device,
                compute_type=fallback_compute_type,
                download_root=str(cache_root),
            )
            return model
        raise


_ja_en_translator: Optional[ctranslate2.Translator] = None
_ja_en_sp_src: Optional[spm.SentencePieceProcessor] = None
_ja_en_sp_tgt: Optional[spm.SentencePieceProcessor] = None


def _ensure_ja_en_translator(
    device: str = "cpu",
) -> tuple[ctranslate2.Translator, spm.SentencePieceProcessor, spm.SentencePieceProcessor]:
    """Lazily download and load the ja→en CTranslate2 model.

    Uses entai2965/sugoi-v4-ja-en-ctranslate2 from Hugging Face Hub and
    caches it under the current Python environment (e.g. .venv/models/ctranslate2).
    """

    global _ja_en_translator, _ja_en_sp_src, _ja_en_sp_tgt
    if _ja_en_translator is not None and _ja_en_sp_src is not None and _ja_en_sp_tgt is not None:
        return _ja_en_translator, _ja_en_sp_src, _ja_en_sp_tgt

    env_root = Path(sys.prefix)
    base_dir = env_root / "models" / "ctranslate2" / "sugoi-v4-ja-en-ctranslate2"
    if not base_dir.exists():
        base_dir.parent.mkdir(parents=True, exist_ok=True)
        print("[ja-en] downloading entai2965/sugoi-v4-ja-en-ctranslate2 ...")
        snapshot_download(
            "entai2965/sugoi-v4-ja-en-ctranslate2",
            local_dir=str(base_dir),
            local_dir_use_symlinks=False,
        )

    sp_dir = base_dir / "spm"
    src_path = sp_dir / "spm.ja.nopretok.model"
    tgt_path = sp_dir / "spm.en.nopretok.model"
    if not src_path.exists() or not tgt_path.exists():
        raise RuntimeError(
            "sentencepiece models not found; expected "
            f"{src_path} and {tgt_path}",
        )

    print(f"[ja-en] loading SentencePiece models from {src_path} and {tgt_path}")
    sp_src = spm.SentencePieceProcessor()
    sp_src.load(str(src_path))
    sp_tgt = spm.SentencePieceProcessor()
    sp_tgt.load(str(tgt_path))

    # CTranslate2 Translator can run on CPU; we keep that as default for safety.
    ct_device = "cpu" if device not in ("cuda",) else "cuda"
    print(f"[ja-en] loading CTranslate2 translator on device={ct_device!r} ...")
    translator = ctranslate2.Translator(str(base_dir), device=ct_device)

    _ja_en_translator = translator
    _ja_en_sp_src = sp_src
    _ja_en_sp_tgt = sp_tgt
    return translator, sp_src, sp_tgt


def _ja_to_en(text: str, device: str = "cpu") -> str:
    """Translate Japanese text to English using the Sugoi v4 ja-en NMT model."""

    text = text.strip()
    if not text:
        return ""

    translator, sp_src, sp_tgt = _ensure_ja_en_translator(device=device)

    # Tokenize to subwords (source side = Japanese).
    pieces = sp_src.encode(text, out_type=str)
    # CTranslate2 expects a list-of-list (batch of token sequences).
    results = translator.translate_batch(
        [pieces],
        beam_size=4,
        max_decoding_length=256,
    )
    if not results or not results[0].hypotheses:
        return ""
    tokens = results[0].hypotheses[0]
    # SentencePiece decode from tokens back to string (target side = English).
    # Tokens may contain special markers; filter them lightly.
    clean_tokens = [t for t in tokens if not t.startswith("<")]
    return sp_tgt.decode(clean_tokens).strip()


def translate_segment(
    model: WhisperModel,
    audio: np.ndarray,
    sample_rate: int = 16000,
    mode: str = "translate",
    language: str | None = None,
    quality: str = "normal",
) -> str:
    """Run speech-to-text for a single audio segment.

    - mode="transcribe" -> return Japanese transcription (kotoba-whisper).
    - mode="translate"  -> Japanese transcription, then offline ja→en translation.
    """
    if audio.size == 0:
        return ""

    quality = (quality or "normal").lower()
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

    # Stage 1: kotoba-whisper for Japanese ASR.
    # Always run in "transcribe" mode with language="ja" to leverage
    # the Japanese-specialised training.
    #
    # NOTE: We keep the call simple and disable VAD so that each audio
    # segment is always transcribed; otherwise short silences can cause
    # "no speech" decisions and the user experience feels like it
    # "stops listening".
    segments, _info = model.transcribe(
        audio,
        task="transcribe",
        language="ja",
        beam_size=beam_size,
        best_of=best_of,
        vad_filter=False,
        word_timestamps=False,
        temperature=0.0,
        condition_on_previous_text=False,
    )

    ja_texts: list[str] = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            ja_texts.append(text)

    if not ja_texts:
        return ""

    ja_full = " ".join(ja_texts)

    # If mode is "transcribe", return Japanese as-is.
    if mode != "translate":
        return ja_full

    # Stage 2: offline Japanese -> English translation.
    # Use device="cpu" here; even if CUDA is available, ASR is the bottleneck.
    en_text = _ja_to_en(ja_full, device="cpu")
    return en_text or ja_full
