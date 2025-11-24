import threading
import time
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox

from audio_capture import record_block, DEFAULT_SAMPLE_RATE
from stt_translate import create_model, translate_segment


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

    def clear(self) -> None:
        with self._lock:
            self._text = ""


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("moblin-smart-translation GUI")
        self.geometry("700x420")

        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._buffer = TranscriptBuffer()
        self._model: Optional[object] = None

        self._build_ui()
        self._poll_buffer()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(root)
        controls.pack(fill=tk.X, pady=(0, 8))

        # Device (CPU / GPU)
        ttk.Label(controls, text="Device:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.device_var = tk.StringVar(value="cpu")
        self.device_combo = ttk.Combobox(
            controls,
            textvariable=self.device_var,
            values=["cpu", "cuda"],
            state="readonly",
            width=8,
        )
        self.device_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 12))

        # Mode (translate / transcribe)
        ttk.Label(controls, text="Mode:").grid(row=0, column=2, sticky=tk.W, padx=(0, 4))
        self.mode_var = tk.StringVar(value="translate")
        self.mode_combo = ttk.Combobox(
            controls,
            textvariable=self.mode_var,
            values=["translate", "transcribe"],
            state="readonly",
            width=12,
        )
        self.mode_combo.grid(row=0, column=3, sticky=tk.W, padx=(0, 12))

        # Source language (hint for recognition)
        ttk.Label(controls, text="Source lang:").grid(row=0, column=4, sticky=tk.W, padx=(0, 4))
        self.language_var = tk.StringVar(value="auto")
        self.language_combo = ttk.Combobox(
            controls,
            textvariable=self.language_var,
            values=["auto", "ja", "en", "zh", "fr", "de", "es", "ko"],
            state="readonly",
            width=8,
        )
        self.language_combo.grid(row=0, column=5, sticky=tk.W, padx=(0, 12))

        # Audio device index
        ttk.Label(controls, text="Audio device index (optional):").grid(
            row=1,
            column=0,
            sticky=tk.W,
            padx=(0, 4),
            pady=(4, 0),
            columnspan=2,
        )
        self.audio_device_var = tk.StringVar(value="")
        self.audio_entry = ttk.Entry(controls, textvariable=self.audio_device_var, width=10)
        self.audio_entry.grid(row=1, column=2, sticky=tk.W, pady=(4, 0))

        # Segment seconds
        ttk.Label(controls, text="Segment seconds:").grid(
            row=1,
            column=3,
            sticky=tk.W,
            padx=(8, 4),
            pady=(4, 0),
        )
        self.segment_var = tk.StringVar(value="8.0")
        self.segment_entry = ttk.Entry(controls, textvariable=self.segment_var, width=6)
        self.segment_entry.grid(row=1, column=4, sticky=tk.W, pady=(4, 0))

        # Quality preset
        ttk.Label(controls, text="Quality:").grid(
            row=1,
            column=5,
            sticky=tk.W,
            padx=(8, 4),
            pady=(4, 0),
        )
        self.quality_var = tk.StringVar(value="normal")
        self.quality_combo = ttk.Combobox(
            controls,
            textvariable=self.quality_var,
            values=["ultra_low", "low", "normal", "high", "ultra_high"],
            state="readonly",
            width=12,
        )
        self.quality_combo.grid(row=1, column=6, sticky=tk.W, pady=(4, 0))

        # Start / Stop buttons
        self.start_button = ttk.Button(controls, text="Start", command=self.start_worker)
        self.start_button.grid(row=0, column=6, padx=(16, 4))

        self.stop_button = ttk.Button(controls, text="Stop", command=self.stop_worker, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=7, padx=(4, 0))

        # Status label
        self.status_var = tk.StringVar(value="Idle")
        self.status_label = ttk.Label(root, textvariable=self.status_var)
        self.status_label.pack(anchor=tk.W, pady=(0, 4))

        # Transcript box
        self.text_widget = tk.Text(root, wrap="word", height=16)
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        self.text_widget.configure(state=tk.DISABLED)

    def start_worker(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return

        device = self.device_var.get().lower()
        mode = self.mode_var.get().lower()
        language = self.language_var.get().strip().lower()
        quality = self.quality_var.get().strip().lower()

        try:
            segment_seconds = float(self.segment_var.get())
        except ValueError:
            messagebox.showerror("Error", "Segment seconds must be a number.")
            return

        audio_device: Optional[int]
        audio_text = self.audio_device_var.get().strip()
        if audio_text == "":
            audio_device = None
        else:
            try:
                audio_device = int(audio_text)
            except ValueError:
                messagebox.showerror("Error", "Audio device index must be an integer or empty.")
                return

        self._stop_event.clear()
        self._buffer.clear()
        self._set_running_state(running=True)
        self.status_var.set("Loading model... (this may take a while first time)")

        def worker() -> None:
            try:
                model = create_model(device, quality=quality)
                self._model = model
                self.status_var.set(
                    f"Running: device={device}, mode={mode}, lang={language}, quality={quality}, segment={segment_seconds}s (VB-Cable as input)"
                )
                sample_rate = DEFAULT_SAMPLE_RATE

                while not self._stop_event.is_set():
                    audio = record_block(segment_seconds, samplerate=sample_rate, device=audio_device)
                    text = translate_segment(
                        model,
                        audio,
                        sample_rate=sample_rate,
                        mode=mode,
                        language=language,
                        quality=quality,
                    )
                    if text:
                        self._buffer.append(text)
            except Exception as exc:  # noqa: BLE001
                self.status_var.set(f"Error: {exc!r}")
            finally:
                self._set_running_state(running=False)

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        self.status_var.set("Stopping...")

    def _set_running_state(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        self.device_combo.configure(state="readonly" if not running else "disabled")
        self.mode_combo.configure(state="readonly" if not running else "disabled")
        self.language_combo.configure(state="readonly" if not running else "disabled")
        self.quality_combo.configure(state="readonly" if not running else "disabled")
        self.audio_entry.configure(state=state)
        self.segment_entry.configure(state=state)
        self.start_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_button.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _poll_buffer(self) -> None:
        text = self._buffer.get()
        self.text_widget.configure(state=tk.NORMAL)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert(tk.END, text)
        self.text_widget.configure(state=tk.DISABLED)
        self.after(500, self._poll_buffer)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
