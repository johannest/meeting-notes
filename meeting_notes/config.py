import argparse
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    whisper_model: str = "base"
    lm_studio_url: str = "http://localhost:1234/v1"
    output_dir: str = "./notes"
    chunk_duration: int = 30
    chunk_overlap: int = 2
    sample_rate: int = 16000
    device: Optional[str] = None
    no_diarize: bool = False
    list_devices: bool = False
    hf_token: Optional[str] = field(default_factory=lambda: os.environ.get("HF_TOKEN"))


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        prog="meeting-notes",
        description="Record and transcribe meeting audio locally with speaker diarization.",
    )
    parser.add_argument(
        "--model",
        choices=["tiny", "base", "small"],
        default="base",
        dest="whisper_model",
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:1234/v1",
        dest="lm_studio_url",
        help="LM Studio base URL (default: http://localhost:1234/v1)",
    )
    parser.add_argument(
        "--output",
        default="./notes",
        dest="output_dir",
        help="Notes output directory (default: ./notes)",
    )
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=30,
        dest="chunk_duration",
        help="Audio chunk size in seconds (default: 30)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Input device name or index (default: system default)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        dest="list_devices",
        help="Print available audio input devices and exit",
    )
    parser.add_argument(
        "--no-diarize",
        action="store_true",
        dest="no_diarize",
        help="Disable speaker diarization (plain transcript, no speaker labels)",
    )

    args = parser.parse_args()
    return Config(
        whisper_model=args.whisper_model,
        lm_studio_url=args.lm_studio_url,
        output_dir=args.output_dir,
        chunk_duration=args.chunk_duration,
        device=args.device,
        list_devices=args.list_devices,
        no_diarize=args.no_diarize,
    )
