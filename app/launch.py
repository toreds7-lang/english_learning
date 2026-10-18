"""One-click launcher (used by run.bat): picks a free port, starts WordStep and opens the
browser. Run with:  uv run python -m app.launch [--host 0.0.0.0] [--port 8000] [--no-browser]

Port choice: try the preferred port, then the ones above it, and let the OS pick one if
all of those are taken. A port counts as free only if it can be bound *and* nothing
answers on it over loopback. The second check matters on Windows, where 127.0.0.1:8000
can still be bound while another server listens on 0.0.0.0:8000 or [::1]:8000 (as Node
does for "localhost"), so the browser would reach the wrong server. The bound socket is
handed straight to uvicorn, so no other program can take the port in between.
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from .tts import fetch_models, model_dir

DEFAULT_PORT = 8000
SCAN = 100            # ports to try upward from the preferred one before asking the OS
PROBE_TIMEOUT = 0.2   # seconds; a server listening on loopback answers far sooner
# Ports from 1024 up that browsers refuse to open (ERR_UNSAFE_PORT).
UNSAFE_PORTS = {1719, 1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566,
                6665, 6666, 6667, 6668, 6669, 6679, 6697, 10080}
WILDCARD = {"0.0.0.0": "127.0.0.1", "::": "::1"}


def family(host: str) -> socket.AddressFamily:
    return socket.AF_INET6 if ":" in host else socket.AF_INET


def bind(host: str, port: int) -> socket.socket | None:
    """A socket bound to host:port, or None if the port is taken or reserved."""
    sock = socket.socket(family(host), socket.SOCK_STREAM)
    if sys.platform == "win32":
        # Without this, Windows lets bind() share a port with another program's socket,
        # and lets another program bind ours later.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ports left in TIME_WAIT
    try:
        sock.bind((host, port))
    except OSError:  # in use, or inside a reserved range (e.g. Hyper-V on Windows)
        sock.close()
        return None
    return sock


def answers(host: str, port: int) -> bool:
    """True if some server accepts TCP connections on host:port."""
    with socket.socket(family(host), socket.SOCK_STREAM) as s:
        s.settimeout(PROBE_TIMEOUT)
        try:
            return s.connect_ex((host, port)) == 0
        except OSError:  # e.g. no IPv6 on this machine
            return False


def probe_hosts(host: str) -> list[str]:
    """Addresses where another server on this port would be reached instead of ours."""
    if host in WILDCARD or host in ("127.0.0.1", "::1", "localhost"):
        return ["127.0.0.1", "::1"]
    return [host]


def claim_port(host: str, preferred: int = DEFAULT_PORT) -> socket.socket:
    """Bind the first free port from `preferred` upward; let the OS choose if none is free."""
    for port in range(preferred, min(preferred + SCAN, 65536)):
        if port in UNSAFE_PORTS:
            continue
        sock = bind(host, port)
        if sock is None:
            continue
        if not any(answers(h, port) for h in probe_hosts(host)):
            return sock
        sock.close()
    sock = bind(host, 0)
    if sock is None:
        raise SystemExit(f"Could not open any port on {host}.")
    return sock


def browse_url(host: str, port: int) -> str:
    host = WILDCARD.get(host, host)
    return f"http://[{host}]:{port}/" if ":" in host else f"http://{host}:{port}/"


def lan_address() -> str | None:
    """This machine's address on the local network (connecting a UDP socket sends nothing)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return None


def announce_when_ready(server: uvicorn.Server, host: str, port: int, open_browser: bool) -> None:
    while not server.started:
        if server.should_exit:
            return
        time.sleep(0.1)
    url = browse_url(host, port)
    print(f"\n  WordStep is running at {url}")
    if host in WILDCARD and (ip := lan_address()):
        print(f"  Other devices on this network: http://{ip}:{port}/")
    print("  Press Ctrl+C to stop.\n", flush=True)
    if open_browser:
        webbrowser.open(url)


def main() -> None:
    ap = argparse.ArgumentParser(description="Start WordStep on a free port and open it in the browser.")
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 lets other devices on the network connect")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help="preferred port; the next free one is used if it is taken")
    ap.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = ap.parse_args()
    if not 1024 <= args.port <= 65535:
        ap.error("--port must be between 1024 and 65535")

    if model_dir() is None:
        print("Downloading the Kokoro voice model (about 340 MB, first run only)...")
        try:
            fetch_models()
        except Exception as exc:  # offline or blocked: the app falls back to the browser's voice
            print(f"Download failed ({exc}). Continuing with the browser's built-in voice.")

    sock = claim_port(args.host, args.port)
    port = sock.getsockname()[1]
    if port != args.port:
        print(f"Port {args.port} is in use, so WordStep will use port {port}.", flush=True)

    server = uvicorn.Server(uvicorn.Config("app.main:app", host=args.host, port=port))
    threading.Thread(target=announce_when_ready, args=(server, args.host, port, not args.no_browser),
                     daemon=True).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
