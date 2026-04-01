import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd


def list_input_devices() -> None:
    devices = sd.query_devices()
    print("\nAvailable audio input devices:\n")
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = " (default)" if i == sd.default.device[0] else ""
            print(f"  [{i}] {dev['name']}{marker}")
    print()


def resolve_device(device: Optional[str]) -> Optional[int | str]:
    """Resolve a device name or numeric string to a sounddevice-compatible value."""
    if device is None:
        return None
    if device.isdigit():
        return int(device)
    # Search by name substring
    devices = sd.query_devices()
    matches = [i for i, d in enumerate(devices) if device.lower() in d["name"].lower() and d["max_input_channels"] > 0]
    if not matches:
        available = [f"[{i}] {d['name']}" for i, d in enumerate(devices) if d["max_input_channels"] > 0]
        raise ValueError(
            f"Audio device '{device}' not found.\n"
            f"Available input devices:\n" + "\n".join(f"  {a}" for a in available)
        )
    if len(matches) > 1:
        names = [devices[i]["name"] for i in matches]
        raise ValueError(
            f"Device name '{device}' matches multiple devices: {names}\n"
            "Use a more specific name or the device index (--list-devices to see indices)."
        )
    return matches[0]


class AudioCapture:
    """Captures audio from an input device and enqueues chunks for transcription."""

    def __init__(self, sample_rate: int, chunk_duration: int, overlap: int, device=None):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.device = device

        self._chunk_frames = chunk_duration * sample_rate
        self._overlap_frames = overlap * sample_rate

        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._buffer = np.zeros(0, dtype=np.float32)
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None
        self._stopped = False

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._stopped = True
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        # Flush remaining buffer as a final chunk
        with self._lock:
            if len(self._buffer) > self.sample_rate:  # at least 1 second
                self._queue.put(self._buffer.copy())
                self._buffer = np.zeros(0, dtype=np.float32)

    def get_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _callback(self, indata: np.ndarray, frames: int, time, status) -> None:
        audio = indata[:, 0].copy()
        with self._lock:
            self._buffer = np.concatenate([self._buffer, audio])
            if len(self._buffer) >= self._chunk_frames:
                chunk = self._buffer[: self._chunk_frames].copy()
                # Keep overlap tail for next chunk
                self._buffer = self._buffer[self._chunk_frames - self._overlap_frames :]
                self._queue.put(chunk)
