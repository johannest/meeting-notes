import threading
from typing import List, Optional, Tuple

import numpy as np


class Transcriber:
    """
    Worker thread that pulls audio chunks from AudioCapture, runs speaker
    diarization (optional) and faster-whisper transcription, then appends
    annotated lines to a shared transcript buffer.
    """

    def __init__(self, whisper_model: str, hf_token: Optional[str], no_diarize: bool, sample_rate: int):
        self.whisper_model_size = whisper_model
        self.hf_token = hf_token
        self.no_diarize = no_diarize
        self.sample_rate = sample_rate

        self._transcript: List[str] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._audio_capture = None

        # Speaker registry: maps pyannote speaker id (str) -> "Speaker N"
        self._speaker_map: dict = {}
        self._speaker_counter = 0

        # Loaded lazily in worker thread to avoid blocking main thread at import time
        self._whisper = None
        self._diarization_pipeline = None

    def load_models(self, progress_callback=None) -> None:
        """Load Whisper and pyannote models. Call from worker thread."""
        from faster_whisper import WhisperModel

        if progress_callback:
            progress_callback("Downloading/loading Whisper model...")
        self._whisper = WhisperModel(self.whisper_model_size, device="auto", compute_type="int8")

        if not self.no_diarize:
            if progress_callback:
                progress_callback("Downloading/loading speaker diarization model...")
            from pyannote.audio import Pipeline
            import torch

            self._diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )
            # Use MPS (Apple Silicon) if available, else CPU
            if torch.backends.mps.is_available():
                self._diarization_pipeline.to(torch.device("mps"))

    def start(self, audio_capture, on_ready=None) -> None:
        self._audio_capture = audio_capture
        self._thread = threading.Thread(target=self._run, args=(on_ready,), daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 60.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def get_transcript(self) -> List[str]:
        with self._lock:
            return list(self._transcript)

    def line_count(self) -> int:
        with self._lock:
            return len(self._transcript)

    def _run(self, on_ready=None) -> None:
        self.load_models(progress_callback=on_ready)
        if on_ready:
            on_ready(None)  # signal ready

        while not self._stop_event.is_set():
            chunk = self._audio_capture.get_chunk(timeout=1.0)
            if chunk is None:
                continue
            lines = self._process_chunk(chunk)
            if lines:
                with self._lock:
                    self._transcript.extend(lines)

        # Drain remaining chunks after stop signal
        while True:
            chunk = self._audio_capture.get_chunk(timeout=0.1)
            if chunk is None:
                break
            lines = self._process_chunk(chunk)
            if lines:
                with self._lock:
                    self._transcript.extend(lines)

    def _process_chunk(self, audio: np.ndarray) -> List[str]:
        if self.no_diarize or self._diarization_pipeline is None:
            return self._transcribe_plain(audio)
        return self._transcribe_with_diarization(audio)

    def _transcribe_plain(self, audio: np.ndarray) -> List[str]:
        segments, _ = self._whisper.transcribe(audio, language=None, vad_filter=True)
        lines = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                lines.append(text)
        return lines

    def _transcribe_with_diarization(self, audio: np.ndarray) -> List[str]:
        import torch
        import soundfile as sf
        import io

        # pyannote needs a file-like object or path; write to in-memory WAV
        buf = io.BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="FLOAT")
        buf.seek(0)

        # Run diarization
        waveform = torch.tensor(audio).unsqueeze(0)  # [1, samples]
        diarization = self._diarization_pipeline(
            {"waveform": waveform, "sample_rate": self.sample_rate}
        )

        # Build speaker segments: [(start_sample, end_sample, label), ...]
        speaker_segments: List[Tuple[int, int, str]] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            start = int(turn.start * self.sample_rate)
            end = int(turn.end * self.sample_rate)
            if end > start:
                speaker_segments.append((start, end, speaker))

        if not speaker_segments:
            return self._transcribe_plain(audio)

        lines = []
        for start, end, pyannote_id in speaker_segments:
            segment_audio = audio[start:end]
            if len(segment_audio) < self.sample_rate // 4:  # skip < 250ms
                continue
            whisper_segs, _ = self._whisper.transcribe(segment_audio, language=None, vad_filter=True)
            text = " ".join(s.text.strip() for s in whisper_segs).strip()
            if text:
                label = self._resolve_speaker(pyannote_id)
                lines.append(f"[{label}]: {text}")
        return lines

    def _resolve_speaker(self, pyannote_id: str) -> str:
        if pyannote_id not in self._speaker_map:
            self._speaker_counter += 1
            self._speaker_map[pyannote_id] = f"Speaker {self._speaker_counter}"
        return self._speaker_map[pyannote_id]
