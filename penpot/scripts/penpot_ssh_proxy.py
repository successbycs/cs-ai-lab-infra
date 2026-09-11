#!/usr/bin/env python3
"""Loopback-only TCP proxy to Penpot through the trusted Windows SSH client."""
from __future__ import annotations
import argparse, asyncio, re, signal, sys

SAFE_TARGET = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]*\Z")

async def relay(reader, writer):
    while data := await reader.read(65536):
        writer.write(data)
        await writer.drain()
    writer.close()
    await writer.wait_closed()

async def handle(client_reader, client_writer, target):
    command = "& ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -W 127.0.0.1:9001 " + target
    process = await asyncio.create_subprocess_exec("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        await asyncio.gather(relay(client_reader, process.stdin), relay(process.stdout, client_writer))
    finally:
        if process.returncode is None: process.terminate()
        await process.wait()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--port", type=int, default=19001)
    args = parser.parse_args()
    if not SAFE_TARGET.fullmatch(args.target) or not 1 <= args.port <= 65535: raise SystemExit("invalid proxy target or port")
    server = await asyncio.start_server(lambda r, w: handle(r, w, args.target), "127.0.0.1", args.port)
    print(f"PENPOT_SSH_PROXY_READY bind=127.0.0.1 port={args.port}", flush=True)
    stop = asyncio.Event()
    for value in (signal.SIGINT, signal.SIGTERM): asyncio.get_running_loop().add_signal_handler(value, stop.set)
    async with server: await stop.wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)
