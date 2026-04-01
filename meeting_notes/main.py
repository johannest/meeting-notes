import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path

from rich.console import Console

from .audio import AudioCapture, list_input_devices, resolve_device
from .config import parse_args
from .display import TerminalUI
from .summarizer import Summarizer
from .transcriber import Transcriber


def main() -> None:
    config = parse_args()

    if config.list_devices:
        list_input_devices()
        sys.exit(0)

    console = Console()

    # Validate HF token for diarization
    if not config.no_diarize and not config.hf_token:
        console.print(
            "[red]HuggingFace token not found.[/red]\n"
            "Speaker diarization requires a free HuggingFace account and model access.\n\n"
            "  1. Create an account at https://huggingface.co\n"
            "  2. Accept model licenses:\n"
            "       https://hf.co/pyannote/speaker-diarization-3.1\n"
            "       https://hf.co/pyannote/segmentation-3.0\n"
            "  3. Generate a token at https://hf.co/settings/tokens\n"
            "  4. Set: export HF_TOKEN=hf_your_token_here\n\n"
            "[yellow]Or run with --no-diarize to skip speaker identification.[/yellow]"
        )
        sys.exit(1)

    # Resolve audio device
    try:
        device = resolve_device(config.device)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    # Check LM Studio connectivity (warn but don't exit)
    summarizer = Summarizer(config.lm_studio_url)
    lm_error = summarizer.check_connection()
    if lm_error:
        console.print(f"[yellow]Warning: {lm_error}[/yellow]")
        console.print("[dim]Recording will proceed; summary will be skipped if still unreachable at exit.[/dim]\n")

    # Prepare output directory and session filename
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    transcript_path = output_dir / f"{session_ts}.txt"
    summary_path = output_dir / f"{session_ts}_summary.txt"

    # Build components
    audio = AudioCapture(
        sample_rate=config.sample_rate,
        chunk_duration=config.chunk_duration,
        overlap=config.chunk_overlap,
        device=device,
    )
    transcriber = Transcriber(
        whisper_model=config.whisper_model,
        hf_token=config.hf_token,
        no_diarize=config.no_diarize,
        sample_rate=config.sample_rate,
    )
    ui = TerminalUI(get_transcript=transcriber.get_transcript, no_diarize=config.no_diarize)

    stop_ui = threading.Event()
    shutdown_requested = threading.Event()
    force_quit = threading.Event()

    # Signal handling
    original_sigint = signal.getsignal(signal.SIGINT)

    def handle_sigint(sig, frame):
        if shutdown_requested.is_set():
            # Second Ctrl+C — force quit
            force_quit.set()
            stop_ui.set()
            console.print("\n[red]Force quit.[/red]")
            sys.exit(1)
        shutdown_requested.set()
        stop_ui.set()

    signal.signal(signal.SIGINT, handle_sigint)

    # Model-ready callback (called from transcriber thread)
    model_ready = threading.Event()

    def on_ready(message):
        if message:
            ui.set_status(message)
        else:
            model_ready.set()
            try:
                audio.start()
            except Exception as e:
                console.print(f"\n[red]Failed to open audio device: {e}[/red]")
                if "Permission" in str(e) or "denied" in str(e).lower():
                    console.print(
                        "[yellow]Microphone access denied. Grant permission in:\n"
                        "  System Settings > Privacy & Security > Microphone[/yellow]"
                    )
                stop_ui.set()
                shutdown_requested.set()
                return
            ui.set_recording(True)
            ui.set_status("Recording")

    # Start transcriber (loads models, then starts audio)
    transcriber.start(audio_capture=audio, on_ready=on_ready)

    # Run UI (blocks until stop_ui is set)
    ui.run(stop_ui)

    if force_quit.is_set():
        return

    # Graceful shutdown
    ui.set_recording(False)
    ui.set_status("Stopping...")

    audio.stop()
    transcriber.stop(timeout=60.0)

    final_transcript = transcriber.get_transcript()

    # Save transcript
    with open(transcript_path, "w") as f:
        f.write("\n".join(final_transcript))
    console.print(f"\n[green]Transcript saved:[/green] {transcript_path}")

    # Summarize
    summary = summarizer.summarize(final_transcript, console)
    if summary:
        with open(summary_path, "w") as f:
            f.write(summary)
        console.print(f"[green]Summary saved:[/green] {summary_path}")

    signal.signal(signal.SIGINT, original_sigint)


if __name__ == "__main__":
    main()
