import http.server
import json
import hmac
import mimetypes
import ipaddress
import socket
import socketserver
import secrets
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from engine import PiperEngine
from settings import load_settings, save_settings
from utils import list_voices, list_audio_sinks, list_audio_clips


PROJECT_ROOT = Path(__file__).parent
STATIC_DIR = PROJECT_ROOT / "static"
ASSETS_DIR = PROJECT_ROOT / "assets"


def _is_loopback_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value in {"127.0.0.1", "::1", "localhost"}


def _is_private_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and address.is_private and not address.is_loopback


def get_local_ip():
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        fallbacks = []
        ignored_prefixes = (
            "lo", "docker", "br-", "veth", "virbr", "tun", "tap", "wg",
            "tailscale", "zt", "warp", "cloudflare", "utun",
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4 or "inet" not in parts:
                continue

            iface = parts[1]
            if iface.startswith(ignored_prefixes):
                continue

            try:
                ip_value = parts[parts.index("inet") + 1].split("/")[0]
            except (ValueError, IndexError):
                continue

            if _is_private_ipv4(ip_value):
                return ip_value
            fallbacks.append(ip_value)

        if fallbacks:
            return fallbacks[0]
    except Exception:
        pass

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

    def _client_ip(self):
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def _auth_required_for_request(self) -> bool:
        if self.app.host in {"127.0.0.1", "localhost"}:
            return False
        return not _is_loopback_ip(self._client_ip())

    def _request_token(self, parsed, data=None):
        token = self.headers.get("X-Access-Token", "").strip()
        if token:
            return token
        query_token = parse_qs(parsed.query).get("token", [""])[0].strip()
        if query_token:
            return query_token
        if isinstance(data, dict):
            body_token = data.get("token", "")
            if isinstance(body_token, str):
                return body_token.strip()
        return ""

    def _require_auth(self, parsed, data=None):
        if not self._auth_required_for_request():
            return True

        token = self._request_token(parsed, data)
        if token and hmac.compare_digest(token, self.app.access_token):
            return True

        self._set_json_headers(401)
        self.wfile.write(json.dumps({"ok": False, "error": "Authentication required"}).encode("utf-8"))
        return False

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
            if not self._require_auth(parsed):
                return
            data = {
                "settings": self.app.settings,
                "voices": list_voices(),
                "sinks": list_audio_sinks(),
                "clips": list_audio_clips(),
                "local_ip": get_local_ip(),
                "port": self.app.port,
                "network_enabled": self.app.host not in ("127.0.0.1", "localhost"),
                "auth_required": self.app.host not in ("127.0.0.1", "localhost"),
            }
            self._set_json_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if parsed.path == "/api/history":
            if not self._require_auth(parsed):
                return
            self._set_json_headers()
            self.wfile.write(json.dumps({"history": self.app.history}).encode("utf-8"))
            return

        if parsed.path == "/api/favorites":
            if not self._require_auth(parsed):
                return
            self._set_json_headers()
            self.wfile.write(json.dumps({"favorites": self.app.favorites}).encode("utf-8"))
            return

        if parsed.path == "/api/presets":
            if not self._require_auth(parsed):
                return
            self._set_json_headers()
            self.wfile.write(json.dumps({"presets": self.app.presets}).encode("utf-8"))
            return

        if parsed.path == "/api/recents":
            if not self._require_auth(parsed):
                return
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

        if parsed.path == "/api/network/enable":
            if not self._require_auth(parsed):
                return
            data = self.app.enable_network_access()
            self._set_json_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if parsed.path == "/api/speak":
            if not self._require_auth(parsed, data):
                return
            text = data.get("text", "").strip()
            self.app.update_settings(data)
            ok, error = self.app.speak(text)
            if ok:
                self._set_json_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            else:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"ok": False, "error": error}).encode("utf-8"))
            return

        if parsed.path == "/api/stop":
            if not self._require_auth(parsed, data):
                return
            self.app.stop()
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if parsed.path == "/api/settings":
            if not self._require_auth(parsed, data):
                return
            self.app.update_settings(data)
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True, "settings": self.app.settings}).encode("utf-8"))
            return

        if parsed.path == "/api/favorite/add":
            if not self._require_auth(parsed, data):
                return
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
            if not self._require_auth(parsed, data):
                return
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
            if not self._require_auth(parsed, data):
                return
            self.app.history = []
            self.app.save_history()
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return

        if parsed.path == "/api/preset/save":
            if not self._require_auth(parsed, data):
                return
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
            if not self._require_auth(parsed, data):
                return
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
            if not self._require_auth(parsed, data):
                return
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
            if not self._require_auth(parsed, data):
                return
            self._set_json_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            threading.Thread(target=self.app.shutdown, daemon=True).start()
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # suppress default HTTP logging
        return


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class BrowserApp:

    def __init__(self, port: int = 8080, host: str = "127.0.0.1"):
        self.port = port
        self.host = host
        self.access_token = secrets.token_urlsafe(16)
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

    def _restart_for_host(self, target_host: str, rotate_token: bool):
        if rotate_token:
            self.access_token = secrets.token_urlsafe(16)

        def restart():
            time.sleep(0.15)
            self.stop_server()
            self.host = target_host
            self.start()
            if target_host not in ("127.0.0.1", "localhost"):
                print("[ok] Phone access enabled.")
                print(f"      Access code: {self.access_token}")
                print(f"      Network: http://{get_local_ip()}:{self.port}")
            else:
                print("[ok] Phone access disabled.")
                print(f"      Local: http://127.0.0.1:{self.port}")

        threading.Thread(target=restart, daemon=True).start()

    def enable_network_access(self):
        # Flip the virtual switch to "Open"
        self.host = "0.0.0.0"
        
        print(f"\n[network] Phone/LAN access enabled via HTML panel.")
        print(f"          URL: http://{get_local_ip()}:{self.port}")
        print(f"          Access Code: {self.access_token}\n")

        return {
            "ok": True,
            "network_enabled": True,
            "access_token": self.access_token,
            "local_ip": get_local_ip(),
            "port": self.port,
        }

    def disable_network_access(self):
        # Flip the virtual switch to "Closed"
        self.host = "127.0.0.1"
        
        # Cycle the password token so any phone that was connected gets instantly locked out
        self.access_token = secrets.token_urlsafe(16)
        
        print("[network] Phone/LAN access disabled via HTML panel.")
        return {
            "ok": True,
            "network_enabled": False,
            "local_ip": get_local_ip(),
            "port": self.port,
        }

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
            return True, None

        if self.tts_thread and self.tts_thread.is_alive():
            return True, None

        command = text.strip()
        if command.startswith("!"):
            clip_name = command[1:].strip()
            if not clip_name:
                return False, "Clip name required"
            if not self.engine.find_clip_path(clip_name):
                return False, f"Clip not found: {clip_name}"

        self.add_to_history(text)

        self.tts_thread = threading.Thread(
            target=self.engine._run,
            args=(text, self.settings),
            daemon=True,
        )
        self.tts_thread.start()
        return True, None

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
                # FORCE the underlying socket to listen on 0.0.0.0 (all network addresses) from boot
                self.server = ReusableThreadingTCPServer(("0.0.0.0", candidate_port), handler)
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
        launch_url = local_url
        if self.host not in ("127.0.0.1", "localhost"):
            launch_url = f"{local_url}?token={quote(self.access_token)}"
        lan_url = f"http://{get_local_ip()}:{self.port}"
        print(f"[2/4] Browser control server is running on port {self.port}")
        print(f"      Local:   {local_url}")
        if self.host not in ("127.0.0.1", "localhost"):
            print(f"      Network: {lan_url}")
            print(f"      Access code: {self.access_token}")
        else:
            print("      Network: disabled by default")
            print("      Use --host=0.0.0.0 or --network to allow phone/LAN access.")
        print("[3/4] Attempting to open your default browser...")
        try:
            opened = webbrowser.open(launch_url)
            if opened:
                print("[ok] Browser launch request sent successfully.")
            else:
                print("[warn] Browser did not open automatically.")
                print(f"       Open this address manually: {launch_url}")
        except Exception as exc:
            print(f"[warn] Browser launch failed: {exc}")
            print(f"       Open this address manually: {launch_url}")

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
