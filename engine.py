import subprocess
import threading
from pathlib import Path

from utils import SUPPORTED_AUDIO_EXTENSIONS


class PiperEngine:
    def __init__(self):
        self.voice_dir = Path(__file__).parent / "voices"
        self.audio_dir = Path(__file__).parent / "audio"
        self.current_process = None
        self.play_process = None
        self.mute = False
        self.lock = threading.Lock()
        self.pipewire = self._is_pipewire()
        self.sox = self._has_sox()

    def _is_pipewire(self) -> bool:
        try:
            subprocess.check_output(["pw-cli", "info"], stderr=subprocess.DEVNULL, timeout=2)
            return True
        except Exception:
            return False

    def _has_sox(self) -> bool:
        try:
            subprocess.check_output(["sox", "--version"], stderr=subprocess.DEVNULL, timeout=2)
            return True
        except Exception:
            return False

    def stop(self):
        with self.lock:
            if self.current_process and self.current_process.poll() is None:
                try:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=0.5)
                except:
                    self.current_process.kill()

            if self.play_process and self.play_process.poll() is None:
                try:
                    self.play_process.terminate()
                    self.play_process.wait(timeout=0.5)
                except:
                    self.play_process.kill()

        try:
            subprocess.run(["pkill", "-9", "-f", "piper-tts"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "-f", "pw-play"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def set_mute(self, state: bool):
        self.mute = state
        if state:
            self.stop()

    def _build_play_cmd(self, output_device: str):
        play_cmd = ["pw-play" if self.pipewire else "paplay"]

        if output_device != "default":
            if self.pipewire:
                play_cmd += ["--target", output_device]
            else:
                play_cmd += ["--device", output_device]

        return play_cmd

    def _apply_volume(self, input_file: Path, output_file: Path, volume: float):
        if volume == 1.0:
            return input_file

        if not self.sox:
            print("SoX not found; volume control skipped")
            return input_file

        sox_cmd = [
            "sox",
            str(input_file),
            str(output_file),
            "vol",
            str(volume),
        ]
        sox_proc = subprocess.run(
            sox_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if sox_proc.returncode != 0:
            print(f"SoX error: {sox_proc.stderr.strip()}")
            return input_file

        if output_file.is_file():
            return output_file

        return input_file

    def find_clip_path(self, clip_name: str):
        name = clip_name.strip()
        if not name:
            return None

        if name.startswith("!"):
            name = name[1:].strip()
        if not name:
            return None

        normalized_name = name.lower().lstrip("!")

        if self.audio_dir.exists():
            for entry in self.audio_dir.iterdir():
                if (
                    entry.is_file()
                    and entry.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
                    and (
                        entry.stem.lower().lstrip("!") == normalized_name
                        or entry.name.lower().lstrip("!") == normalized_name
                    )
                ):
                    return entry

        candidate = Path(name)
        if candidate.suffix:
            exact_path = self.audio_dir / candidate.name
            if exact_path.is_file():
                return exact_path
        else:
            candidate_stem = candidate.stem.lower().lstrip("!")
            for ext in SUPPORTED_AUDIO_EXTENSIONS:
                exact_path = self.audio_dir / f"{candidate_stem}{ext}"
                if exact_path.is_file():
                    return exact_path
                exact_path = self.audio_dir / f"!{candidate_stem}{ext}"
                if exact_path.is_file():
                    return exact_path

        return None

    def _play_file(self, input_file: Path, settings: dict, tmp_adjusted: Path):
        output_device = settings.get("output_device", "default")
        volume = settings.get("volume", 1.0)

        playback_file = self._apply_volume(input_file, tmp_adjusted, volume)
        play_cmd = self._build_play_cmd(output_device)
        play_cmd.append(str(playback_file))

        self.play_process = subprocess.Popen(play_cmd)
        self.play_process.wait()

    def _run(self, text: str, settings: dict):
        if self.mute or not text.strip():
            return

        command = text.strip()
        if command.startswith("!"):
            clip_path = self.find_clip_path(command[1:])
            if not clip_path:
                print(f"Clip not found: {command[1:].strip()}")
                return
            self._run_clip(clip_path, settings)
            return

        self._run_tts(text, settings)

    def _run_clip(self, clip_path: Path, settings: dict):
        tmp_adjusted = Path("/tmp/piper_clip_adjusted.wav")
        try:
            self._play_file(clip_path, settings, tmp_adjusted)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.current_process = None
            self.play_process = None
            if tmp_adjusted.exists():
                try:
                    tmp_adjusted.unlink()
                except:
                    pass

    def _run_tts(self, text: str, settings: dict):
        voice = settings.get("voice", "en_GB-cori-high")
        speed = settings.get("speed", 1.0)
        noise = settings.get("noise", 0.5)
        noise_w = settings.get("noise_w", noise)
        sentence_silence = settings.get("sentence_silence", 0.0)
        volume = settings.get("volume", 1.0)
        output_device = settings.get("output_device", "default")

        model_path = self.voice_dir / f"{voice}.onnx"
        tmp_wav = Path("/tmp/piper_output.wav")
        tmp_adjusted = Path("/tmp/piper_output_adjusted.wav")

        if not model_path.is_file():
            print(f"Model not found: {model_path}")
            return

        piper_cmd = [
            "piper-tts",
            "--model", str(model_path),
            "--length_scale", str(speed),
            "--noise_scale", str(noise),
            "--noise_w", str(noise_w),
            "--sentence_silence", str(sentence_silence),
            "--output_file", str(tmp_wav),
        ]

        try:
            # Generate audio
            proc = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.current_process = proc
            _, stderr = proc.communicate(input=text, timeout=30)

            if proc.returncode != 0:
                print(f"Piper error: {stderr.strip()}")
                return

            if not tmp_wav.is_file():
                print("WAV file not created!")
                return

            self._play_file(tmp_wav, settings, tmp_adjusted)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.current_process = None
            self.play_process = None
            if tmp_wav.exists():
                try:
                    tmp_wav.unlink()
                except:
                    pass
            if tmp_adjusted.exists():
                try:
                    tmp_adjusted.unlink()
                except:
                    pass
