#!/usr/bin/env bash
set -e

echo "==> Installing system dependencies..."
brew install portaudio
echo ""
echo "==> (Optional) Installing BlackHole for virtual meeting capture..."
echo "    Skip with Ctrl+C, or press Enter to install."
read -r -p "Install BlackHole 2ch? [y/N] " response
if [[ "$response" =~ ^[Yy]$ ]]; then
    brew install blackhole-2ch
fi

echo ""
echo "==> Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo ""
echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

echo ""
echo "==> Done!"
echo ""
echo "Next steps:"
echo "  1. source .venv/bin/activate"
echo "  2. Set your HuggingFace token (required for speaker diarization):"
echo "       export HF_TOKEN=hf_your_token_here"
echo "     Accept model licenses at:"
echo "       https://hf.co/pyannote/speaker-diarization-3.1"
echo "       https://hf.co/pyannote/segmentation-3.0"
echo "  3. Start LM Studio and load a chat model"
echo "  4. Run: meeting-notes"
echo ""
echo "To skip speaker diarization: meeting-notes --no-diarize"
echo "To list audio devices:       meeting-notes --list-devices"
