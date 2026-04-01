import threading
import time
from typing import Callable, List

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class TerminalUI:
    """
    Rich-based live terminal display. Shows recording status, live transcript,
    and keybinding hints. Updates on a 0.5s tick.
    """

    TAIL_LINES = 20  # transcript lines visible in panel

    def __init__(self, get_transcript: Callable[[], List[str]], no_diarize: bool):
        self._get_transcript = get_transcript
        self._no_diarize = no_diarize
        self._start_time = time.time()
        self._console = Console()
        self._status_message = "Loading models..."
        self._recording = False

    @property
    def console(self) -> Console:
        return self._console

    def set_status(self, message: str) -> None:
        self._status_message = message

    def set_recording(self, recording: bool) -> None:
        self._recording = recording

    def run(self, stop_event: threading.Event) -> None:
        with Live(self._render(), console=self._console, refresh_per_second=2, screen=False) as live:
            while not stop_event.is_set():
                live.update(self._render())
                time.sleep(0.5)
            live.update(self._render())

    def _render(self):
        lines = self._get_transcript()
        elapsed = int(time.time() - self._start_time)
        mm, ss = divmod(elapsed, 60)

        # Status bar
        if self._recording:
            dot = Text("● ", style="bold red")
            dot.append(f"Recording  {mm:02d}:{ss:02d}", style="bold white")
        else:
            dot = Text(self._status_message, style="yellow")

        word_count = sum(len(line.split()) for line in lines)
        mode = "plain" if self._no_diarize else "diarized"
        stats = Text(f"{len(lines)} segments · {word_count} words · {mode}", style="dim")

        status_panel = Panel(
            Columns([dot, stats], expand=True),
            style="bold",
            padding=(0, 1),
        )

        # Transcript panel
        tail = lines[-self.TAIL_LINES :] if len(lines) > self.TAIL_LINES else lines
        transcript_text = Text()
        for line in tail:
            if line.startswith("[Speaker"):
                # Colour each speaker differently
                bracket_end = line.find("]:")
                if bracket_end != -1:
                    speaker = line[: bracket_end + 1]
                    rest = line[bracket_end + 1 :]
                    speaker_num = "".join(filter(str.isdigit, speaker))
                    colours = ["cyan", "green", "yellow", "magenta", "blue", "red"]
                    colour = colours[(int(speaker_num) - 1) % len(colours)] if speaker_num else "cyan"
                    transcript_text.append(speaker + ":", style=f"bold {colour}")
                    transcript_text.append(rest + "\n")
                else:
                    transcript_text.append(line + "\n")
            else:
                transcript_text.append(line + "\n", style="white")

        if not lines:
            transcript_text = Text("Waiting for speech...", style="dim italic")

        transcript_panel = Panel(
            transcript_text,
            title="[bold]Transcript[/bold]",
            border_style="bright_black",
            padding=(0, 1),
        )

        # Hints
        hints = Text("Ctrl+C  stop recording & summarize  ·  Ctrl+C (again)  force quit", style="dim")
        hints_panel = Panel(hints, padding=(0, 1), border_style="bright_black")

        layout = Layout()
        layout.split_column(
            Layout(status_panel, size=3),
            Layout(transcript_panel),
            Layout(hints_panel, size=3),
        )
        return layout
