#!/usr/bin/env python3
"""Bounded loopback-only Penpot relay over the trusted Windows SSH client.

The Penpot MCP endpoint uses long-lived HTTP/SSE streams.  Starting one SSH
process for every HTTP request leaked child processes when a browser or MCP
client disconnected asymmetrically. Windows OpenSSH does not support the Unix
ControlMaster socket required for connection multiplexing, so this compatible
relay instead strictly bounds active channels and always terminates a channel
when either direction closes. A future native Windows tunnel service can
replace this transport without changing the loopback MCP endpoint.
"""
from __future__ import annotations
import argparse, asyncio, re, signal, sys

SAFE_TARGET = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]*\Z")

async def relay(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionResetError:
            pass

def ssh_command(target: str) -> str:
    return (
        "& ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes "
        "-o ExitOnForwardFailure=yes -o ServerAliveInterval=20 "
        "-o ServerAliveCountMax=3 "
        "-W 127.0.0.1:9001 "
        + target
    )


async def handle(client_reader, client_writer, target, semaphore):
    async with semaphore:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            ssh_command(target),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            inbound = asyncio.create_task(relay(client_reader, process.stdin))
            outbound = asyncio.create_task(relay(process.stdout, client_writer))
            _, pending = await asyncio.wait({inbound, outbound}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(inbound, outbound, return_exceptions=True)
        finally:
            if process.returncode is None:
                process.terminate()
            await process.wait()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--port", type=int, default=19001)
    parser.add_argument("--max-clients", type=int, default=4)
    args = parser.parse_args()
    if not SAFE_TARGET.fullmatch(args.target):
        raise SystemExit("invalid proxy target")
    if not 1 <= args.port <= 65535 or not 1 <= args.max_clients <= 16:
        raise SystemExit("invalid proxy port or client limit")
    semaphore = asyncio.Semaphore(args.max_clients)
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, args.target, semaphore),
        "127.0.0.1", args.port,
    )
    print(f"PENPOT_SSH_PROXY_READY bind=127.0.0.1 port={args.port} max_clients={args.max_clients}", flush=True)
    stop = asyncio.Event()
    for value in (signal.SIGINT, signal.SIGTERM): asyncio.get_running_loop().add_signal_handler(value, stop.set)
    async with server:
        await stop.wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)
