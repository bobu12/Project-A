#!/usr/bin/env python3
"""Local launcher for the GCC Markets Dashboard.

Serves this folder over HTTP and opens it in your default browser. Picks a free
port automatically so you never hit "address already in use".

Usage:
    python3 serve.py            # auto-pick a free port
    python3 serve.py 5173       # use a specific port (falls back if taken)
"""
import functools
import http.server
import os
import socket
import socketserver
import sys
import webbrowser

# Ports we try first (in order) before asking the OS for any free one.
PREFERRED_PORTS = [5173, 3000, 8000, 8080, 4321, 8888, 9090]


def is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(requested) -> int:
    candidates = ([requested] if requested else []) + PREFERRED_PORTS
    for port in candidates:
        if is_free(port):
            return port
    # Last resort: let the OS hand us any open ephemeral port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server(socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    requested = None
    if len(sys.argv) > 1:
        try:
            requested = int(sys.argv[1])
        except ValueError:
            print("Port must be a number, e.g. python3 serve.py 5173")
            sys.exit(1)

    port = pick_port(requested)
    if requested and port != requested:
        print(f"Port {requested} was busy — using {port} instead.")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    # Make sure .js is served with a correct, modern MIME type. (extensions_map
    # is a class attribute on the handler, so set it on the base class.)
    http.server.SimpleHTTPRequestHandler.extensions_map[".js"] = "application/javascript"

    url = f"http://localhost:{port}"
    with Server(("127.0.0.1", port), handler) as httpd:
        print("\n  GCC Markets Dashboard")
        print(f"  Serving: {root}")
        print(f"  Open:    {url}")
        print("  Stop:    Ctrl+C\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass  # headless environments: just print the URL above
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
