#!/usr/bin/env python3
"""Loopback-only T16 browser relay for Plane's private T480 WSL endpoint.

The relay is deliberately fixed to the Plane web port.  It accepts no target,
remote command, or bind-address argument.  Every client connection is carried
over the reviewed T16 Windows SSH transport and a fixed T480 PowerShell-to-WSL
stream, so the Plane proxy can remain bound to the T480 WSL loopback.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import plane_adapter
from scripts.t480_adapter import LOCAL_CONFIG_PATH, TRANSPORT_SETTINGS
from t480_core import build_ssh_command, resolve_ssh_target

STATE_PATH = ROOT / ".plane-t16-relay.local.json"
LOCAL_HOST = "127.0.0.1"


class RelayError(RuntimeError):
    pass


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _remote_bridge_powershell(remote_port: int) -> str:
    # This remote program only connects to the fixed Plane proxy loopback and
    # copies bytes between stdio and that TCP socket.  No caller input becomes
    # a remote command or endpoint.
    bridge = """import os,socket,threading
s=socket.create_connection(('127.0.0.1',""" + str(remote_port) + """),10)
def uplink():
 try:
  while True:
   d=os.read(0,65536)
   if not d: s.shutdown(socket.SHUT_WR); return
   s.sendall(d)
 except OSError: pass
threading.Thread(target=uplink,daemon=True).start()
while True:
 d=s.recv(65536)
 if not d: break
 os.write(1,d)
"""
    encoded_bridge = base64.b64encode(bridge.encode()).decode("ascii")
    remote_ps = (
        "$ErrorActionPreference='Stop'; $bridge="
        + _ps_quote(encoded_bridge)
        + "; wsl.exe -d Ubuntu -- python3 -c \"import base64;exec(base64.b64decode('$bridge'))\"; exit $LASTEXITCODE"
    )
    return remote_ps


def ssh_bridge_command(target: str, remote_port: int) -> list[str]:
    if not 1 <= remote_port <= 65535:
        raise RelayError("Plane relay remote port is invalid")
    return build_ssh_command(target, _remote_bridge_powershell(remote_port), TRANSPORT_SETTINGS)



def ssh_forward_command(target: str, local_port: int, remote_port: int) -> list[str]:
    """Build the fixed Windows OpenSSH forward used by the Forex T16 client."""
    if not 1 <= local_port <= 65535 or not 1 <= remote_port <= 65535:
        raise RelayError("Plane relay port is invalid")
    safe_target = resolve_ssh_target(TRANSPORT_SETTINGS, [LOCAL_CONFIG_PATH])
    if safe_target != target:
        raise RelayError("Plane relay SSH target changed during setup")
    encoded_target = base64.b64encode(target.encode("utf-8")).decode("ascii")
    return [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        (
            "$target=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + encoded_target
            + "')); $sshArguments=@('-N','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o',"
            "'ExitOnForwardFailure=yes','-o','ConnectTimeout=" + str(TRANSPORT_SETTINGS.connect_timeout_seconds)
            + "','-o','ConnectionAttempts=" + str(TRANSPORT_SETTINGS.connection_attempts)
            + "','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','-L','127.0.0.1:"
            + str(local_port) + ":127.0.0.1:" + str(remote_port)
            + "',$target); & ssh.exe @sshArguments; exit $LASTEXITCODE"
        ),
    ]

def _remote_proxy_port() -> int:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "t480_adapter.py"), "execute", "--operation", "plane_status"],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if result.returncode:
        raise RelayError("T480 Plane status did not pass")
    try:
        payload = json.loads(result.stdout)
        output = str(payload["result"]["stdout"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RelayError("T480 Plane status response was invalid") from exc
    match = re.fullmatch(r"PLANE_STATUS_PASS services=11 proxy_loopback=true proxy_port=([0-9]+)", output.strip())
    if not match or not 1 <= int(match.group(1)) <= 65535:
        raise RelayError("T480 Plane proxy status was invalid")
    return int(match.group(1))


def _validate_settings() -> tuple[str, int, int, str]:
    settings = plane_adapter.load_config()
    parsed = urlsplit(settings["PLANE_ORIGIN"])
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RelayError("Plane relay requires a plain T16 HTTP loopback Plane origin")
    local_port = parsed.port or 80
    try:
        return resolve_ssh_target(TRANSPORT_SETTINGS, [LOCAL_CONFIG_PATH]), local_port, _remote_proxy_port(), settings["PLANE_ORIGIN"]
    except (RuntimeError, ValueError) as exc:
        raise RelayError("T480 SSH target is unavailable") from exc


def _copy_socket_to_stdin(connection: socket.socket, process: subprocess.Popen[bytes]) -> None:
    try:
        while data := connection.recv(65536):
            if process.stdin is not None:
                process.stdin.write(data)
                process.stdin.flush()
    except OSError:
        pass
    finally:
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass


def _discard(stream: object) -> None:
    if hasattr(stream, "read"):
        try:
            stream.read()  # type: ignore[union-attr]
        except OSError:
            pass


class _RelayHandler(socketserver.BaseRequestHandler):
    target = ""
    remote_port = 0

    def handle(self) -> None:
        process = subprocess.Popen(
            ssh_bridge_command(self.target, self.remote_port), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
        )
        incoming = threading.Thread(target=_copy_socket_to_stdin, args=(self.request, process), daemon=True)
        incoming.start()
        stderr = threading.Thread(target=_discard, args=(process.stderr,), daemon=True)
        stderr.start()
        try:
            if process.stdout is not None:
                while data := process.stdout.read(65536):
                    self.request.sendall(data)
        except OSError:
            pass
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


class _RelayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _state() -> dict[str, object] | None:
    try:
        contents = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return contents if isinstance(contents, dict) else None


def _pid_running(pid: object) -> bool:
    return isinstance(pid, int) and pid > 1 and Path(f"/proc/{pid}").exists()


def status() -> dict[str, object]:
    state = _state()
    return {"status": "PASS" if state and _pid_running(state.get("pid")) else "NOT_RUNNING", "origin": state.get("origin") if state else None, "transport": state.get("transport") if state else None}


def serve() -> int:
    target, local_port, remote_port, origin = _validate_settings()
    _RelayHandler.target = target
    _RelayHandler.remote_port = remote_port
    try:
        with _RelayServer((LOCAL_HOST, local_port), _RelayHandler) as server:
            STATE_PATH.write_text(json.dumps({"pid": os.getpid(), "origin": origin}), encoding="utf-8")
            STATE_PATH.chmod(0o600)
            # shutdown() cannot run on the serve_forever thread.  Raising
            # SystemExit lets the context manager release the loopback socket.
            signal.signal(signal.SIGTERM, lambda *_args: (_ for _ in ()).throw(SystemExit))
            signal.signal(signal.SIGINT, lambda *_args: (_ for _ in ()).throw(SystemExit))
            server.serve_forever()
    finally:
        STATE_PATH.unlink(missing_ok=True)
    return 0


def start() -> dict[str, object]:
    target, local_port, remote_port, origin = _validate_settings()
    current = status()
    if current["status"] == "PASS":
        return current
    STATE_PATH.unlink(missing_ok=True)
    process = subprocess.Popen(ssh_forward_command(target, local_port, remote_port), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        try:
            verified = plane_adapter.web_status(plane_adapter.load_config())
        except plane_adapter.PlaneAccessError:
            time.sleep(0.2)
            continue
        STATE_PATH.write_text(json.dumps({"pid": process.pid, "origin": origin, "transport": "windows_openssh_forward"}), encoding="utf-8")
        STATE_PATH.chmod(0o600)
        return {"status": "PASS", "origin": origin, "transport": "windows_openssh_forward", "http_status": verified["http_status"]}
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    STATE_PATH.unlink(missing_ok=True)
    raise RelayError("Plane relay did not start")


def stop() -> dict[str, object]:
    state = _state()
    if state and _pid_running(state.get("pid")):
        os.kill(int(state["pid"]), signal.SIGTERM)
    STATE_PATH.unlink(missing_ok=True)
    return {"status": "STOPPED", "origin": state.get("origin") if state else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("start", "status", "stop", "serve"))
    parser.add_argument("--approve", action="store_true", help="required to start or stop the local relay")
    args = parser.parse_args(argv)
    try:
        if args.operation in {"start", "stop"} and not args.approve:
            raise RelayError(f"{args.operation} requires --approve")
        result = {"serve": lambda: None, "start": start, "status": status, "stop": stop}[args.operation]()
        if args.operation == "serve":
            return serve()
        print(json.dumps(result, sort_keys=True))
        return 0
    except (RelayError, plane_adapter.PlaneAccessError) as exc:
        print(f"CS_AI_LAB_PLANE_RELAY_REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
