import asyncio
import json
import os
import sys
from http import HTTPStatus
import websockets

PORT = int(os.environ.get("PORT", 8080))

gateway_ws = None


async def health_check(connection, request):
    if request.path == "/health":
        return connection.respond(
            HTTPStatus.OK,
            json.dumps({"status": "ok", "gateway_connected": gateway_ws is not None}),
        )
    if request.path != "/gateway":
        return connection.respond(HTTPStatus.NOT_FOUND, "Not found\n")


async def handle_gateway(ws):
    global gateway_ws

    if gateway_ws is not None:
        print("[relay] Rejecting connection — a gateway is already connected")
        await ws.close(1008, "Another gateway is already connected")
        return

    gateway_ws = ws
    print("[relay] Gateway connected")

    try:
        async for message in ws:
            print(f"[gateway ->] {message}")
    except websockets.ConnectionClosed:
        pass
    finally:
        gateway_ws = None
        print("[relay] Gateway disconnected")


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
            print(f"[-> gateway] {text}")
        except websockets.ConnectionClosed:
            print("[relay] Gateway disconnected while sending")


async def main():
    async with websockets.serve(
        handle_gateway,
        "0.0.0.0",
        PORT,
        process_request=health_check,
    ):
        print(f"Listening on 0.0.0.0:{PORT}")
        await stdin_loop()


if __name__ == "__main__":
    asyncio.run(main())
