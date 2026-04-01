# CLAUDE.md — Meeting Notes App

## Project Purpose

A fully local CLI tool that records microphone audio, transcribes it in real time using `faster-whisper`, and generates a meeting summary with action items via a local LLM served by LM Studio on exit.

See `SPEC.md` for the full specification.

---

## Project Structure

```
meeting_notes/
├── main.py          # Entry point, orchestrator, signal handling
├── audio.py         # AudioCapture — sounddevice InputStream wrapper
├── transcriber.py   # Transcriber — faster-whisper worker thread
├── summarizer.py    # Summarizer — LM Studio via openai client
├── display.py       # TerminalUI — Rich Live display
└── config.py        # Config dataclass + argparse CLI
```

---

## Architecture

Three-thread model:
1. **Main thread** — Rich Live UI, signal handling (SIGINT)
2. **Audio thread** — sounddevice callback pushing PCM frames to `audio_queue`
3. **Transcription thread** — blocking faster-whisper calls, appends to `transcript_buffer`

Summarization runs synchronously on the main thread after audio/transcription threads are stopped.

---

## Key Conventions

- **Audio format:** 16000 Hz, mono, float32 — Whisper's native format, no resampling needed
- **Chunk size:** 30 seconds of audio per transcription call (configurable via `--chunk-duration`)
- **Chunk overlap:** 2-second overlap between chunks to avoid word cutoff at boundaries
- **Thread safety:** `transcript_buffer` protected by `threading.Lock`; display reads a snapshot copy
- **Output files:** `notes/YYYY-MM-DD_HH-MM.txt` (raw, written incrementally) and `notes/YYYY-MM-DD_HH-MM_summary.txt` (written at exit)
- **LM Studio model name:** Use `"local-model"` — LM Studio ignores this and routes to whatever is loaded
- **No asyncio:** Threading + queues only. sounddevice and faster-whisper are both callback/blocking-based; asyncio adds complexity without benefit here.

---

## LM Studio Requirements

- LM Studio must be running at `http://localhost:1234` (default) with a chat model loaded
- App verifies connectivity via `GET /v1/models` at startup
- Only one model needed: a text LLM for summarization (faster-whisper handles STT in-process)

---

## Dependencies

System: `portaudio` (via Homebrew)

Python packages (see `pyproject.toml`):
- `faster-whisper` — STT
- `sounddevice` — audio capture
- `openai` — LM Studio client
- `rich` — terminal UI
- `numpy` — audio buffers

---

## Setup & Run

```bash
brew install portaudio
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
meeting-notes
```

---

## Error Handling Rules

- Microphone permission denied → print actionable message, exit with code 1
- LM Studio unreachable at startup → warn, continue recording (summarization will fall back)
- LM Studio unreachable at summary time → save raw transcript, print it, exit cleanly
- LM Studio running but no model loaded → catch 400/503, print message, save raw transcript
- First Ctrl+C → graceful shutdown (drain queue, summarize)
- Second Ctrl+C → immediate exit
