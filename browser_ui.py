import http.server
import json
import mimetypes
import socket
import socketserver
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from engine import PiperEngine
from settings import load_settings, save_settings
from utils import list_voices, list_audio_sinks


PROJECT_ROOT = Path(__file__).parent
STATIC_DIR = PROJECT_ROOT / "static"
ASSETS_DIR = PROJECT_ROOT / "assets"


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class BrowserRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, app=None, **kwargs):
        self.app = app
        super().__init__(*args, **kwargs)

    def _set_json_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

    def _set_html_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._set_html_headers()
            self.wfile.write(self.app.html_page().encode("utf-8"))
            return

        if parsed.path.startswith("/static/"):
            self.app.serve_static(self, parsed.path[len("/static/"):])
            return

        if parsed.path.startswith("/assets/"):
            self.app.serve_asset(self, parsed.path[len("/assets/"):])
            return

        if parsed.path == "/api/status":
            data = {
                "settings": self.app.settings,
                "voices": list_voices(),
                "sinks": list_audio_sinks(),
                "local_ip": get_local_ip(),
                "port": self.app.port,
            }
            self._set_json_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if parsed.path == "/api/history":
            self._set_json_headers()
            self.wfile.write(json.dumps({"history": self.app.history}).encode("utf-8"))
            return

        if parsed.path == "/api/favorites":
            self._set_json_headers()
            self.wfile.write(json.dumps({"favorites": self.app.favorites}).encode("utf-8"))
            return

        if parsed.path == "/api/presets":
            self._set_json_headers()
            self.wfile.write(json.dumps({"presets": self.app.presets}).encode("utf-8"))
            return

        if parsed.path == "/api/recents":
            self._set_json_headers()
            self.wfile.write(json.dumps(self.app.recents).encode("utf-8"))
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        data = {}

        if self.headers.get("Content-Type", "").startswith("application/json"):
            try:
                data = json.loads(raw_body or "{}")
            except json.JSONDecodeError:
                data = {}
        else:
            for pair in raw_body.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    data[key] = value

        if parsed.path == "/api/speak":
            text = data.get("text", "").strip()
            if text:
                self.app.update_settings(data)
                self.app.speak(text)
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if parsed.path == "/api/stop":
            self.app.stop()
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if parsed.path == "/api/settings":
            self.app.update_settings(data)
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True, "settings": self.app.settings}).encode("utf-8"))
            return

        if parsed.path == "/api/favorite/add":
            name = data.get("name", "").strip()
            text = data.get("text", "").strip()
            if name and text:
                self.app.favorites[name] = text
                self.app.save_favorites()
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            else:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"ok": False, "error": "Name and text required"}).encode("utf-8"))
            return

        if parsed.path == "/api/favorite/remove":
            name = data.get("name", "").strip()
            if name and name in self.app.favorites:
                del self.app.favorites[name]
                self.app.save_favorites()
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            else:
                self._set_json_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Favorite not found"}).encode("utf-8"))
            return

        if parsed.path == "/api/history/clear":
            self.app.history = []
            self.app.save_history()
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if parsed.path == "/api/preset/save":
            name = data.get("name", "").strip()
            if name:
                self.app.presets[name] = {
                    "voice": data.get("voice"),
                    "speed": data.get("speed"),
                    "noise": data.get("noise"),
                    "noise_w": data.get("noise_w"),
                    "sentence_silence": data.get("sentence_silence"),
                }
                self.app.save_presets()
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            else:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"ok": False, "error": "Name required"}).encode("utf-8"))
            return

        if parsed.path == "/api/preset/load":
            name = data.get("name", "").strip()
            if name and name in self.app.presets:
                preset = self.app.presets[name]
                self.app.settings.update(preset)
                save_settings(self.app.settings)
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True, "preset": preset}).encode("utf-8"))
            else:
                self._set_json_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Preset not found"}).encode("utf-8"))
            return

        if parsed.path == "/api/preset/delete":
            name = data.get("name", "").strip()
            if name and name in self.app.presets:
                del self.app.presets[name]
                self.app.save_presets()
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            else:
                self._set_json_headers(404)
                self.wfile.write(json.dumps({"ok": False, "error": "Preset not found"}).encode("utf-8"))
            return

        if parsed.path == "/api/shutdown":
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            threading.Thread(target=self.app.shutdown, daemon=True).start()
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # suppress default HTTP logging
        return


class BrowserApp:

    def __init__(self, port: int = 8080):
        self.port = port
        self.static_dir = STATIC_DIR
        self.settings = load_settings()
        self.engine = PiperEngine()
        self.tts_thread = None
        self.server = None
        self.thread = None
        self.history = self.load_history()
        self.favorites = self.load_favorites()
        self.presets = self.load_presets()
        self.recents = self.load_recents()

    def load_history(self):
        history_path = Path(__file__).parent / "history.json"
        if history_path.exists():
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history = json.load(f) or []
                    if not isinstance(history, list):
                        return []
                    history = [
                        item for item in history
                        if isinstance(item, dict) and item.get("text")
                    ]
                    history.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
                    return history[:10]
            except Exception:
                return []
        return []

    def save_history(self):
        history_path = Path(__file__).parent / "history.json"
        try:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(self.history[:10], f, indent=2)
        except Exception as e:
            print(f"Failed to save history: {e}")

    def load_favorites(self):
        favorites_path = Path(__file__).parent / "favorites.json"
        if favorites_path.exists():
            try:
                with open(favorites_path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
            except Exception:
                return {}
        return {}

    def save_favorites(self):
        favorites_path = Path(__file__).parent / "favorites.json"
        try:
            with open(favorites_path, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, indent=2)
        except Exception as e:
            print(f"Failed to save favorites: {e}")

    def add_to_history(self, text: str):
        from datetime import datetime
        text = text.strip()
        if not text:
            return

        self.history = [
            item for item in self.history
            if item.get("text") != text
        ]
        self.history.insert(0, {
            "text": text,
            "timestamp": datetime.now().isoformat(),
        })
        self.history = self.history[:10]
        self.save_history()

    def load_presets(self):
        presets_path = Path(__file__).parent / "presets.json"
        if presets_path.exists():
            try:
                with open(presets_path, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
            except Exception:
                return {}
        return {}

    def save_presets(self):
        presets_path = Path(__file__).parent / "presets.json"
        try:
            with open(presets_path, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            print(f"Failed to save presets: {e}")

    def load_recents(self):
        recents_path = Path(__file__).parent / "recents.json"
        if recents_path.exists():
            try:
                with open(recents_path, "r", encoding="utf-8") as f:
                    return json.load(f) or {"voices": [], "devices": []}
            except Exception:
                return {"voices": [], "devices": []}
        return {"voices": [], "devices": []}

    def save_recents(self):
        recents_path = Path(__file__).parent / "recents.json"
        try:
            with open(recents_path, "w", encoding="utf-8") as f:
                json.dump(self.recents, f, indent=2)
        except Exception as e:
            print(f"Failed to save recents: {e}")

    def add_recent_voice(self, voice: str):
        if voice in self.recents["voices"]:
            self.recents["voices"].remove(voice)
        self.recents["voices"].insert(0, voice)
        self.recents["voices"] = self.recents["voices"][:3]  # Keep last 3
        self.save_recents()

    def add_recent_device(self, device: str):
        if device in self.recents["devices"]:
            self.recents["devices"].remove(device)
        self.recents["devices"].insert(0, device)
        self.recents["devices"] = self.recents["devices"][:3]  # Keep last 3
        self.save_recents()

    def update_settings(self, data: dict):
        if "voice" in data:
            self.settings["voice"] = data["voice"]
            self.add_recent_voice(data["voice"])
        if "speed" in data:
            try:
                self.settings["speed"] = float(data["speed"])
            except (TypeError, ValueError):
                pass
        if "noise" in data:
            try:
                self.settings["noise"] = float(data["noise"])
            except (TypeError, ValueError):
                pass
        if "noise_w" in data:
            try:
                self.settings["noise_w"] = float(data["noise_w"])
            except (TypeError, ValueError):
                pass
        if "sentence_silence" in data:
            try:
                self.settings["sentence_silence"] = float(data["sentence_silence"])
            except (TypeError, ValueError):
                pass
        if "volume" in data:
            try:
                self.settings["volume"] = float(data["volume"])
            except (TypeError, ValueError):
                pass
        if "output_device" in data:
            self.settings["output_device"] = data["output_device"]
            self.add_recent_device(data["output_device"])
        if "mute" in data:
            self.settings["mute"] = bool(data["mute"])
            self.engine.set_mute(self.settings["mute"])

        save_settings(self.settings)

    def speak(self, text: str):
        if self.settings.get("mute") or not text:
            return

        if self.tts_thread and self.tts_thread.is_alive():
            return

        self.add_to_history(text)

        self.tts_thread = threading.Thread(
            target=self.engine._run,
            args=(text, self.settings),
            daemon=True,
        )
        self.tts_thread.start()

    def stop(self):
        self.engine.stop()

    def shutdown(self):
        self.stop()
        self.stop_server()

    def html_page(self) -> str:
        return self.read_static_text("index.html")

    def read_static_text(self, relative_path: str) -> str:
        path = self._safe_static_path(relative_path)
        return path.read_text(encoding="utf-8")

    def serve_static(self, handler, relative_path: str):
        try:
            path = self._safe_static_path(relative_path)
        except ValueError:
            handler.send_error(403, "Forbidden")
            return
        if not path.exists() or not path.is_file():
            handler.send_error(404, "Not Found")
            return

        content_type, _ = mimetypes.guess_type(path.name)
        handler.send_response(200)
        handler.send_header("Content-Type", content_type or "application/octet-stream")
        handler.send_header("Content-Length", str(path.stat().st_size))
        handler.end_headers()
        with open(path, "rb") as f:
            handler.wfile.write(f.read())

    def serve_asset(self, handler, relative_path: str):
        try:
            path = self._safe_asset_path(relative_path)
        except ValueError:
            handler.send_error(403, "Forbidden")
            return
        if not path.exists() or not path.is_file():
            handler.send_error(404, "Not Found")
            return

        content_type, _ = mimetypes.guess_type(path.name)
        handler.send_response(200)
        handler.send_header("Content-Type", content_type or "application/octet-stream")
        handler.send_header("Content-Length", str(path.stat().st_size))
        handler.end_headers()
        with open(path, "rb") as f:
            handler.wfile.write(f.read())

    def _safe_static_path(self, relative_path: str) -> Path:
        candidate = (self.static_dir / relative_path).resolve()
        static_root = self.static_dir.resolve()
        if candidate != static_root and static_root not in candidate.parents:
            raise ValueError("Invalid static path")
        return candidate

    def _safe_asset_path(self, relative_path: str) -> Path:
        candidate = (ASSETS_DIR / relative_path).resolve()
        asset_root = ASSETS_DIR.resolve()
        if candidate != asset_root and asset_root not in candidate.parents:
            raise ValueError("Invalid asset path")
        return candidate

    def start(self):
        if self.server:
            return False

        handler = lambda *args, **kwargs: BrowserRequestHandler(*args, app=self, **kwargs)
        requested_port = self.port
        last_error = None

        for candidate_port in range(requested_port, requested_port + 10):
            try:
                self.server = socketserver.ThreadingTCPServer(("", candidate_port), handler)
                self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                self.thread.start()
                self.port = candidate_port
                if candidate_port != requested_port:
                    print(f"[warn] Port {requested_port} was busy. Using fallback port {candidate_port}.")
                return True
            except OSError as exc:
                last_error = exc
                self.server = None
                self.thread = None
                if candidate_port == requested_port:
                    print(f"[warn] Could not bind server on port {candidate_port}: {exc}")

        print(f"[error] Could not bind server on ports {requested_port}-{requested_port + 9}: {last_error}")
        return False

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.thread = None

    def run(self):
        print("[1/4] Preparing browser control...")
        if not self.start():
            print(f"[error] Failed to start browser control on port {self.port}")
            return

        local_url = f"http://127.0.0.1:{self.port}"
        lan_url = f"http://{get_local_ip()}:{self.port}"
        print(f"[2/4] Browser control server is running on port {self.port}")
        print(f"      Local:   {local_url}")
        print(f"      Network: {lan_url}")
        print("[3/4] Attempting to open your default browser...")
        try:
            opened = webbrowser.open(local_url)
            if opened:
                print("[ok] Browser launch request sent successfully.")
            else:
                print("[warn] Browser did not open automatically.")
                print(f"       Open this address manually: {local_url}")
        except Exception as exc:
            print(f"[warn] Browser launch failed: {exc}")
            print(f"       Open this address manually: {local_url}")

        print("[4/4] Server is ready. Press Ctrl+C to stop.")
        try:
            self.thread.join()
        except KeyboardInterrupt:
            print("\n[stop] Shutting down browser control...")
        finally:
            self.stop_server()


def main(port: int = 8080):
    app = BrowserApp(port=port)
    app.run()


if __name__ == "__main__":
    main()
