import argparse
import threading
import time
from typing import Optional

from flask import Flask, jsonify, render_template

from audio_capture import record_block, DEFAULT_SAMPLE_RATE
from stt_translate import create_model, translate_segment


app = Flask(__name__)


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

    def get(self) -> str:
        with self._lock:
            return self._text


transcript_buffer = TranscriptBuffer()


def worker_loop(device_mode: str, audio_device: Optional[int], segment_seconds: float) -> None:
    model = create_model(device_mode)
    sample_rate = DEFAULT_SAMPLE_RATE

    while True:
        try:
            audio = record_block(segment_seconds, samplerate=sample_rate, device=audio_device)
            text = translate_segment(model, audio, sample_rate=sample_rate)
            if text:
                transcript_buffer.append(text)
        except Exception as exc:  # noqa: BLE001
            # Keep going even if one segment fails.
            transcript_buffer.append(f"[worker error: {exc!r}]")
            time.sleep(1.0)


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/transcript")
def get_transcript():  # type: ignore[override]
    return jsonify({"text": transcript_buffer.get()})


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
    parser.add_argument("--host", default="127.0.0.1", help="Flask bind host")
    parser.add_argument("--port", type=int, default=5000, help="Flask bind port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    worker = threading.Thread(
        target=worker_loop,
        args=(args.device, args.audio_device, args.segment_seconds),
        daemon=True,
    )
    worker.start()

    # Debug=False でできるだけ軽く。
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
