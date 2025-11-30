import argparse
import logging
import threading
import time
import webbrowser
from typing import Optional

import numpy as np
import webrtcvad
import sounddevice as sd
from flask import Flask, jsonify, redirect, render_template, request, url_for

from audio_capture import record_block, DEFAULT_SAMPLE_RATE
from stt_translate import create_model, translate_segment


app = Flask(__name__)


class _SuppressTranscriptLogFilter(logging.Filter):
    """Filter out Werkzeug access log lines for /transcript polling.

    The settings page polls /transcript every秒, which clutters the console.
    This filter keeps other access logs intact while hiding those lines.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        msg = record.getMessage()
        # Return False to suppress records containing the /transcript path.
        return "/transcript" not in msg


logging.getLogger("werkzeug").addFilter(_SuppressTranscriptLogFilter())


MAX_VISIBLE_LINES = 3


class TranscriptBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._text = ""

    def append(self, new_text: str) -> None:
        if not new_text:
            return
        with self._lock:
            if self._text:
                self._text += "\n"
            self._text += new_text

            # Keep only the last MAX_VISIBLE_LINES logical lines so that
            # the output tab never accumulates more than N lines of text.
            lines = [ln for ln in self._text.splitlines() if ln.strip() != ""]
            if len(lines) > MAX_VISIBLE_LINES:
                lines = lines[-MAX_VISIBLE_LINES :]
            self._text = "\n".join(lines)

    def get(self) -> str:
        with self._lock:
            return self._text

    def clear(self) -> None:
        with self._lock:
            self._text = ""


transcript_buffer = TranscriptBuffer()


worker_thread: Optional[threading.Thread] = None
worker_stop_event: Optional[threading.Event] = None
worker_lock = threading.Lock()
worker_config: dict | None = None


def _apply_vad_filter(audio: np.ndarray, sample_rate: int, vad_level: int) -> np.ndarray:
    try:
        vad_level_int = int(vad_level)
    except (TypeError, ValueError):
        return audio
    if vad_level_int <= 0:
        return audio
    if audio.size == 0:
        return audio

    vad_level_int = max(0, min(3, vad_level_int))
    vad = webrtcvad.Vad(vad_level_int)

    clipped = np.clip(audio, -1.0, 1.0)
    int16_audio = (clipped * 32768.0).astype(np.int16, copy=False)

    frame_duration_ms = 30
    frame_length = int(sample_rate * frame_duration_ms / 1000)
    if frame_length <= 0:
        return audio

    total = (int16_audio.size // frame_length) * frame_length
    if total <= 0:
        return audio

    int16_audio = int16_audio[:total]
    frames = int16_audio.reshape(-1, frame_length)

    speech_frames: list[np.ndarray] = []
    for frame in frames:
        if vad.is_speech(frame.tobytes(), sample_rate):
            speech_frames.append(frame)

    if not speech_frames:
        return np.empty((0,), dtype=np.float32)

    stacked = np.concatenate(speech_frames)
    return stacked.astype(np.float32) / 32768.0


def worker_loop(
    device_mode: str,
    audio_device: Optional[int],
    segment_seconds: float,
    quality: str,
    stop_event: threading.Event,
    mode: str,
    language: Optional[str],
    capture_mode: str = "loopback",
    vad_level: int = 0,
    srt_url: Optional[str] = None,
) -> None:
    model = create_model(device_mode, quality=quality)
    sample_rate = DEFAULT_SAMPLE_RATE

    while not stop_event.is_set():
        try:
            audio = record_block(
                segment_seconds,
                samplerate=sample_rate,
                device=audio_device,
                capture_mode=capture_mode,
                srt_url=srt_url,
            )
            # Sanitize audio to avoid NaNs / infs / absurd amplitudes propagating into faster-whisper.
            if audio.size == 0:
                continue

            # Replace NaNs / infs with safe finite values.
            if not np.isfinite(audio).all():
                audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

            # Basic sanity checks on amplitude.
            max_abs = float(np.max(np.abs(audio)))
            # Treat small amplitudes as silence to avoid spurious
            # transcriptions (e.g. translating background noise to "I'm sorry").
            # The threshold is intentionally a bit conservative for noisy
            # environments so that quiet background sounds are skipped.
            if np.isfinite(max_abs) and max_abs < 6e-3:
                # Low enough that this is effectively silence; skip.
                time.sleep(0.05)
                continue

            # If the amplitude is astronomically large, consider this segment corrupt and skip it.
            if not np.isfinite(max_abs) or max_abs > 1000.0:
                print(
                    "[worker warning] audio segment looks corrupt (max_abs=%.4e), skipping"
                    % max_abs,
                )
                time.sleep(0.1)
                continue

            # Optionally normalise if slightly >1.0, to keep within a reasonable range.
            if max_abs > 1.0:
                audio = audio / max_abs

            # Debug: basic stats of the captured audio block
            try:
                print(
                    "[worker] captured",
                    audio.shape[0],
                    "samples, min=%.4f max=%.4f mean=%.4f"
                    % (float(audio.min()), float(audio.max()), float(audio.mean())),
                )
            except Exception as capture_exc:  # noqa: BLE001
                print(f"[worker debug] failed to summarise audio block: {capture_exc!r}")
            audio_filtered = _apply_vad_filter(audio, sample_rate, vad_level)
            if audio_filtered.size == 0:
                time.sleep(0.05)
                continue
            audio = audio_filtered
            text = translate_segment(
                model,
                audio,
                sample_rate=sample_rate,
                mode=mode,
                language=language,
                quality=quality,
            )
            print(f"[worker] transcript: {text!r}")
            if text:
                transcript_buffer.append(text)
        except Exception as exc:  # noqa: BLE001
            # Keep going even if one segment fails.
            print(f"[worker error] {exc!r}")
            time.sleep(1.0)


def start_worker(
    device_mode: str,
    audio_device: Optional[int],
    segment_seconds: float,
    quality: str,
    mode: str = "translate",
    language: Optional[str] = None,
    capture_mode: str = "loopback",
    vad_level: int = 0,
    srt_url: Optional[str] = None,
) -> None:
    global worker_thread, worker_stop_event, worker_config
    with worker_lock:
        if worker_stop_event is not None:
            worker_stop_event.set()
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=1.0)

        stop_event = threading.Event()
        worker_stop_event = stop_event
        worker_config = {
            "device_mode": device_mode,
            "audio_device": audio_device,
            "segment_seconds": segment_seconds,
            "quality": quality,
            "mode": mode,
            "language": language,
            "capture_mode": capture_mode,
            "vad_level": vad_level,
            "srt_url": srt_url,
        }

        def _run() -> None:
            worker_loop(
                device_mode,
                audio_device,
                segment_seconds,
                quality,
                stop_event,
                mode,
                language,
                capture_mode,
                vad_level,
                srt_url,
            )

        worker_thread = threading.Thread(target=_run, daemon=True)
        worker_thread.start()


def stop_worker() -> None:
    global worker_thread, worker_stop_event
    with worker_lock:
        if worker_stop_event is not None:
            worker_stop_event.set()
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=1.0)
        worker_thread = None
        worker_stop_event = None


@app.route("/")
def root() -> str:
    return redirect(url_for("settings"))


@app.route("/settings")
def settings() -> str:
    return render_template("settings.html")


@app.route("/display")
def display() -> str:
    return render_template("display.html")


@app.route("/transcript")
def get_transcript():  # type: ignore[override]
    return jsonify({"text": transcript_buffer.get()})


@app.route("/api/transcript/clear", methods=["POST"])
def clear_transcript():  # type: ignore[override]
    """Clear the current transcript text buffer."""
    transcript_buffer.clear()
    return jsonify({"ok": True})


@app.route("/api/devices")
def api_devices():  # type: ignore[override]
    """List input audio devices for the Web UI.

    Returns a JSON array of {index, name, is_default} objects.
    """
    try:
        devices = sd.query_devices()
        default_input = None
        try:
            default_input = sd.default.device[0]
        except Exception:  # noqa: BLE001
            default_input = None

        items = []
        for idx, dev in enumerate(devices):
            try:
                if dev.get("max_input_channels", 0) > 0:
                    items.append(
                        {
                            "index": idx,
                            "name": str(dev.get("name", f"Device {idx}")),
                            "is_default": bool(default_input is not None and idx == default_input),
                        }
                    )
            except Exception:  # noqa: BLE001
                continue
        return jsonify({"devices": items})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": repr(exc)}), 500


@app.route("/api/worker", methods=["GET", "POST"])
def api_worker():  # type: ignore[override]
    """Get or control the audio worker.

    GET: returns running state and current config.
    POST: {action: "start"|"stop", audio_device?: int|null}
    """
    global worker_config

    if request.method == "GET":
        with worker_lock:
            running = worker_thread is not None and worker_thread.is_alive()
            cfg = worker_config or {}
        return jsonify({"running": running, "config": cfg})

    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).lower()

    if action == "stop":
        stop_worker()
        return jsonify({"ok": True, "running": False})

    if action == "start":
        with worker_lock:
            cfg = worker_config or {
                "device_mode": "cpu",
                "audio_device": None,
                "segment_seconds": 8.0,
                "quality": "ultra_low",
                "mode": "translate",
                "language": None,
                "capture_mode": "loopback",
                "vad_level": 0,
                "srt_url": None,
            }

        audio_device_value = data.get("audio_device")
        audio_device: Optional[int]
        if audio_device_value in (None, ""):
            audio_device = None
        else:
            try:
                audio_device = int(audio_device_value)
            except (TypeError, ValueError):
                return jsonify({"error": "invalid audio_device"}), 400

        mode_value = str(data.get("mode") or cfg.get("mode") or "translate")
        language_value = data.get("language", cfg.get("language", None))
        quality_value = str(data.get("quality") or cfg.get("quality") or "ultra_low")
        device_mode_value = str(data.get("device_mode") or cfg.get("device_mode") or "cpu")
        capture_mode_value = str(data.get("capture_mode") or cfg.get("capture_mode") or "loopback")
        vad_level_raw = data.get("vad_level", cfg.get("vad_level", 0))
        try:
            vad_level_value = int(vad_level_raw)
        except (TypeError, ValueError):
            vad_level_value = 0
        if vad_level_value < 0:
            vad_level_value = 0
        if vad_level_value > 3:
            vad_level_value = 3

        srt_url_value_raw = data.get("srt_url", cfg.get("srt_url", None))
        srt_url_value: Optional[str]
        if srt_url_value_raw is None:
            srt_url_value = None
        else:
            srt_url_value = str(srt_url_value_raw).strip()
            if srt_url_value == "":
                srt_url_value = None

        if capture_mode_value == "srt" and not srt_url_value:
            return jsonify({"error": "srt_url is required when capture_mode is 'srt'"}), 400

        start_worker(
            device_mode_value,
            audio_device,
            float(cfg.get("segment_seconds", 8.0)),
            quality_value,
            mode_value,
            language_value,
            capture_mode_value,
            vad_level_value,
            srt_url_value,
        )
        return jsonify({"ok": True, "running": True})

    return jsonify({"error": "invalid action"}), 400


def parse_args():
    parser = argparse.ArgumentParser(description="moblin-smart-translation server")
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Inference device (cpu or cuda). Default: cpu",
    )
    parser.add_argument(
        "--audio-device",
        type=int,
        default=None,
        help="sounddevice input device index. If omitted, use system default (set VB-Cable as default)",
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=8.0,
        help="Length of each audio segment in seconds. Shorter = lower latency, higher CPU load",
    )
    parser.add_argument(
        "--quality",
        choices=["ultra_low", "low", "normal", "high", "ultra_high"],
        default="normal",
        help=(
            "Quality/latency preset: ultra_low, low, normal, high, ultra_high. "
            "Lower = faster & lighter, higher = slower & more accurate."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="Flask bind host")
    parser.add_argument("--port", type=int, default=5000, help="Flask bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Open default browser to the settings page shortly after startup.
    url = f"http://{args.host}:{args.port}/settings"

    def _open_browser() -> None:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    threading.Timer(1.0, _open_browser).start()

    # Debug=False でできるだけ軽く。
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
