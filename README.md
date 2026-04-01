# meeting-notes

A fully local CLI tool for recording and transcribing meeting audio in real time. Identifies speakers automatically and generates a summary with action items on exit — no cloud services required.

## Features

- Starts recording immediately on launch
- Transcribes speech in real time using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (runs locally, Metal-accelerated on Apple Silicon)
- Identifies and labels speakers as `[Speaker 1]`, `[Speaker 2]`, etc. via [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- Captures both microphone and system audio for virtual meetings (via BlackHole aggregate device)
- On exit: generates a summary + action items via a local LLM served by [LM Studio](https://lmstudio.ai)
- Saves transcript and summary as plain text files

## Requirements

- macOS (Apple Silicon recommended)
- Python 3.9+
- [LM Studio](https://lmstudio.ai) running with a chat model loaded
- Free [HuggingFace](https://huggingface.co) account (for speaker diarization models)

## Setup

```bash
# 1. Install system dependencies
brew install portaudio

# 2. Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 3. Set your HuggingFace token
export HF_TOKEN=hf_your_token_here   # add to ~/.zshrc to persist
```

Accept the pyannote model licenses (one-time, free):
- https://hf.co/pyannote/speaker-diarization-3.1
- https://hf.co/pyannote/segmentation-3.0

Or run `bash setup.sh` to go through all steps interactively.

## Usage

```bash
meeting-notes                          # default: system mic, speaker diarization on
meeting-notes --model small            # higher transcription accuracy
meeting-notes --no-diarize             # plain transcript without speaker labels
meeting-notes --list-devices           # show available audio input devices
meeting-notes --device "Meeting Capture"  # use a specific device (e.g. aggregate)
meeting-notes --output ~/my-notes      # custom output directory
```

Press **Ctrl+C** to stop recording. The app will finish transcribing, generate a summary, and save both files before exiting. Press **Ctrl+C again** to force quit immediately.

## Virtual Meetings (Zoom, Teams, Meet)

To capture both your voice and remote participants, set up a BlackHole aggregate device:

```bash
brew install blackhole-2ch
```

Then in **Audio MIDI Setup** (`/Applications/Utilities/`):
1. Create a **Multi-Output Device**: BlackHole 2ch + your speakers/headphones — set as system output
2. Create an **Aggregate Device**: your microphone + BlackHole 2ch — name it e.g. `Meeting Capture`

In your meeting app, set audio output to the Multi-Output Device. Then run:

```bash
meeting-notes --device "Meeting Capture"
```

## Output

Sessions are saved to `./notes/` (configurable with `--output`):

```
notes/
├── 2026-04-01_09-30.txt          # speaker-annotated transcript
└── 2026-04-01_09-30_summary.txt  # summary + action items
```

Transcript example:
```
[Speaker 1]: Let's get started. The main topic today is the Q2 roadmap.
[Speaker 2]: I think we should prioritise the API rewrite first.
[Speaker 1]: Agreed. Let's also make sure we have capacity for the mobile work.
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--model` | `base` | Whisper model size: `tiny`, `base`, `small` |
| `--url` | `http://localhost:1234/v1` | LM Studio API base URL |
| `--output` | `./notes` | Directory for transcript and summary files |
| `--chunk-duration` | `30` | Audio chunk size in seconds |
| `--device` | system default | Input device name or index |
| `--list-devices` | — | Print available input devices and exit |
| `--no-diarize` | — | Disable speaker diarization |
