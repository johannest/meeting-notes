# CLAUDE.md — Meeting Notes App

## Project Purpose

A fully local CLI tool that records audio (microphone or aggregate device), transcribes it in real time using `faster-whisper`, identifies speakers via `pyannote.audio` diarization, and generates a meeting summary with action items via a local LLM served by LM Studio on exit.

See `SPEC.md` for the full specification.

---

## Project Structure

```
meeting_notes/
├── main.py          # Entry point, orchestrator, signal handling
├── audio.py         # AudioCapture — sounddevice InputStream wrapper, device listing
├── transcriber.py   # Transcriber — pyannote diarization + faster-whisper worker thread
├── summarizer.py    # Summarizer — LM Studio via openai client
├── display.py       # TerminalUI — Rich Live display
└── config.py        # Config dataclass + argparse CLI
```

---

## Architecture

Three-thread model:
1. **Main thread** — Rich Live UI, signal handling (SIGINT)
2. **Audio thread** — sounddevice callback pushing PCM frames to `audio_queue`
3. **Transcription thread** — per chunk: pyannote diarization → faster-whisper per segment → merge into annotated lines; appends to `transcript_buffer`

Summarization runs synchronously on the main thread after audio/transcription threads are stopped.

---

## Key Conventions

- **Audio format:** 16000 Hz, mono, float32 — Whisper's native format, no resampling needed
- **Chunk size:** 30 seconds of audio per transcription call (configurable via `--chunk-duration`)
- **Chunk overlap:** 2-second overlap between chunks to avoid word cutoff at boundaries
- **Speaker labels:** pyannote IDs (`SPEAKER_00`, `SPEAKER_01`, …) are mapped to `Speaker 1`, `Speaker 2`, … via a session-level registry in `transcriber.py`; labels are stable across chunks
- **Transcript format:** `[Speaker 1]: text` per line; plain text when `--no-diarize` is used
- **Thread safety:** `transcript_buffer` protected by `threading.Lock`; display reads a snapshot copy
- **Output files:** `notes/YYYY-MM-DD_HH-MM.txt` (speaker-annotated, written incrementally) and `notes/YYYY-MM-DD_HH-MM_summary.txt` (written at exit)
- **LM Studio model name:** Use `"local-model"` — LM Studio ignores this and routes to whatever is loaded
- **No asyncio:** Threading + queues only. sounddevice and faster-whisper are both callback/blocking-based; asyncio adds complexity without benefit here.

---

## LM Studio Requirements

- LM Studio must be running at `http://localhost:1234` (default) with a chat model loaded
- App verifies connectivity via `GET /v1/models` at startup
- Only one model needed: a text LLM for summarization (faster-whisper handles STT in-process)

---

## Dependencies

System: `portaudio` (via Homebrew); `blackhole-2ch` (optional, for virtual meeting capture)

Python packages (see `pyproject.toml`):
- `faster-whisper` — STT
- `pyannote.audio` — speaker diarization
- `sounddevice` — audio capture + device listing
- `openai` — LM Studio client
- `rich` — terminal UI
- `numpy` — audio buffers

Environment: `HF_TOKEN` must be set for pyannote model access (free HuggingFace account required).

---

## Setup & Run

```bash
brew install portaudio
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
export HF_TOKEN=hf_your_token_here
meeting-notes
meeting-notes --no-diarize          # skip speaker diarization
meeting-notes --list-devices        # show available audio input devices
meeting-notes --device "Meeting Capture"  # use aggregate device for virtual meetings
```

---

## Error Handling Rules

- Microphone / device permission denied → print actionable message, exit with code 1
- Unknown `--device` name → list available devices, exit with code 1
- `HF_TOKEN` missing or pyannote model not accepted → print HF link, suggest `--no-diarize`, exit with code 1
- LM Studio unreachable at startup → warn, continue recording (summarization will fall back)
- LM Studio unreachable at summary time → save raw transcript, print it, exit cleanly
- LM Studio running but no model loaded → catch 400/503, print message, save raw transcript
- First Ctrl+C → graceful shutdown (drain queue, summarize)
- Second Ctrl+C → immediate exit
