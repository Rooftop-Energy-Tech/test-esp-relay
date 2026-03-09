import asyncio
import json
import os
import sys
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import websockets

PORT = int(os.environ.get("PORT", 8080))

gateway_ws = None
client_ws = None


def parse_request(path):
    parsed = urlparse(path)
    params = parse_qs(parsed.query)
    role = params.get("role", [None])[0]
    return parsed.path, role


async def process_request(connection, request):
    path, role = parse_request(request.path)

    if path == "/health":
        return connection.respond(
            HTTPStatus.OK,
            json.dumps({
                "status": "ok",
                "gateway_connected": gateway_ws is not None,
                "client_connected": client_ws is not None,
            }),
        )
    if path != "/ws":
        return connection.respond(HTTPStatus.NOT_FOUND, "Not found\n")
    if role not in ("gateway", "client"):
        return connection.respond(HTTPStatus.BAD_REQUEST, "Missing or invalid ?role= (gateway|client)\n")


async def handle_connection(ws):
    global gateway_ws, client_ws

    _, role = parse_request(ws.request.path)

    if role == "gateway":
        if gateway_ws is not None:
            print("[relay] Rejecting gateway — one is already connected")
            await ws.close(1008, "Another gateway is already connected")
            return
        gateway_ws = ws
        print("[relay] Gateway connected")
        try:
            async for message in ws:
                print(f"[gateway -> relay] {message}")
                if client_ws is not None:
                    await client_ws.send(message)
                    print(f"[relay -> client] {message}")
        except websockets.ConnectionClosed:
            pass
        finally:
            gateway_ws = None
            print("[relay] Gateway disconnected")

    elif role == "client":
        if client_ws is not None:
            print("[relay] Rejecting client — one is already connected")
            await ws.close(1008, "Another client is already connected")
            return
        client_ws = ws
        print("[relay] Client connected")
        try:
            async for message in ws:
                print(f"[client -> relay] {message}")
                if gateway_ws is not None:
                    await gateway_ws.send(message)
                    print(f"[relay -> gateway] {message}")
                else:
                    await ws.send(json.dumps({"error": "No gateway connected"}))
        except websockets.ConnectionClosed:
            pass
        finally:
            client_ws = None
            print("[relay] Client disconnected")


async def stdin_loop():
    loop = asyncio.get_event_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        text = line.strip()
        if not text:
            continue
        if gateway_ws is None:
            print("[relay] No gateway connected, message dropped")
            continue
        try:
            await gateway_ws.send(text)
            print(f"[stdin -> gateway] {text}")
        except websockets.ConnectionClosed:
            print("[relay] Gateway disconnected while sending")


async def main():
    async with websockets.serve(
        handle_connection,
        "0.0.0.0",
        PORT,
        process_request=process_request,
    ):
        print(f"Listening on 0.0.0.0:{PORT}")
        await stdin_loop()


if __name__ == "__main__":
    asyncio.run(main())
