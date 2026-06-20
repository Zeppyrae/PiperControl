#!/usr/bin/env python3
import sys


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python3 main.py [--port=<port>] [--host=<bind_address>]")
        print("Default host is 127.0.0.1. Use --host=0.0.0.0 to allow phone/LAN access.")
        print("LAN mode prints a random access code that you must enter in the browser.")
        return

    port = 8080
    host = "127.0.0.1"
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=", 1)[1])
            except ValueError:
                pass
        if arg.startswith("--host="):
            host = arg.split("=", 1)[1].strip() or host
        if arg == "--network":
            host = "0.0.0.0"

    print("Starting Piper Browser Control...")
    print(f"Requested port: {port}")
    print(f"Bind host: {host}")
    print("Loading application modules...")
    from browser_ui import BrowserApp

    print("Creating browser control application...")
    app = BrowserApp(port=port, host=host)
    app.run()


if __name__ == "__main__":
    main()
