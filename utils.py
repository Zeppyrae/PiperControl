import subprocess
import os
from pathlib import Path


SUPPORTED_AUDIO_EXTENSIONS = (
    ".wav",
    ".ogg",
    ".oga",
    ".flac",
    ".aiff",
    ".aif",
    ".au",
)


def get_voice_dir():
    base = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base, "voices")


def get_audio_dir():
    base = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(base, "audio")


def list_voices(voice_dir=None):
    if voice_dir is None:
        voice_dir = get_voice_dir()
    if not os.path.exists(voice_dir):
        return []
    return [
        f.replace(".onnx", "")
        for f in os.listdir(voice_dir)
        if f.endswith(".onnx")
    ]


def list_audio_clips(audio_dir=None):
    if audio_dir is None:
        audio_dir = get_audio_dir()

    if not os.path.exists(audio_dir):
        return []

    try:
        clips = {}
        for entry in Path(audio_dir).iterdir():
            if not entry.is_file() or entry.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                continue

            key = entry.stem.lower()
            clips.setdefault(key, entry.stem)

        return [clips[key] for key in sorted(clips)]
    except Exception:
        return []


def list_audio_sinks():
    sinks = ["default"]
    try:
        out = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
        for line in out.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                sinks.append(parts[1])
    except Exception as e:
        print("Failed to list sinks:", e)
    return sinks
