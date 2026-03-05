# Test Relay Server — Implementation Plan (Python)

A minimal WebSocket relay to test the ESP32 gateway connection. Single file, no framework, runs locally or on any VPS with a public IP.

## What It Does

```
┌──────────────┐     ws://      ┌─────────────────┐     stdin/stdout     ┌──────────────┐
│  ESP32 + SIM │ ──────────────▶│  Test Relay      │◀─────────────────── │  You (CLI)   │
│  (Gateway)   │◀──────────────│  (Python)        │───────────────────▶│              │
└──────────────┘  /gateway?...  └─────────────────┘  type JSON commands  └──────────────┘
```

- Accepts the ESP32's WebSocket connection on `/gateway?id=<ID>&token=<TOKEN>`
- Prints every message the gateway sends (data, config, errors) to stdout
- Lets you type JSON commands in the terminal and forwards them to the gateway
- Validates the token from query params (matches `Config.hpp` `RELAY_TOKEN`)

## Requirements

- Python 3.11+
- `websockets` library (`pip install websockets`)
- A machine reachable by the ESP32 (public IP, or same network for local testing)

## Single File

```
relay-server/
├── test_relay.py    # Everything in one file
└── README.md        # How to run it
```

No project scaffold, no multiple modules. One file you can `scp` to a VPS and run.

## ESP32 Config to Match

The relay must match these values from `Config.hpp`:

| Config constant | Default       | Relay must listen on          |
|-----------------|---------------|-------------------------------|
| `RELAY_HOST`    | (your VPS IP) | `0.0.0.0` (all interfaces)    |
| `RELAY_PORT`    | `8080`        | Port `8080`                   |
| `GATEWAY_ID`    | `gw-01`       | Accept any ID, log it         |
| `RELAY_TOKEN`   | `change-me`   | Validate against env or flag  |

The ESP32 connects to: `ws://<HOST>:8080/gateway?id=gw-01&token=change-me`

## Connection Handling

### WebSocket upgrade (`/gateway`)

1. Parse query params `id` and `token` from the request path
2. Validate token — reject with HTTP 401 if wrong
3. Accept connection, print `Gateway connected: gw-01`
4. Start two concurrent tasks:
   - **Receive loop**: read messages from gateway, print to stdout
   - **Send loop**: read lines from stdin, send to gateway
5. On disconnect: print `Gateway disconnected`, wait for reconnection

### Health check (`/health`)

- HTTP GET returns `200 OK` with `{"status":"ok","gateway_connected":true/false}`
- Useful for verifying the relay is running before powering on the ESP32

## Message Flow

### Gateway → Relay (printed to stdout)

```
[gw-01 →] {"type":"config","baudRate":9600,"interval":1000,"devices":[]}
[gw-01 →] {"type":"data","devices":[{"slaveId":8,"name":"Device A","readings":[...]}]}
[gw-01 →] {"type":"writeResult","success":true,"slaveId":8,"address":0,"value":30}
[gw-01 →] {"type":"error","message":"Device not found"}
```

### You → Relay → Gateway (typed in terminal)

```
> {"type":"getConfig"}
> {"type":"addDevice","device":{"slaveId":8,"name":"Test","registers":[{"address":20,"label":"Voltage","scaleFactor":100}]}}
> {"type":"writeRegister","slaveId":8,"address":0,"value":30}
> {"type":"removeDevice","slaveId":8}
```

## Implementation Steps

| Step | Description                                                       |
|------|-------------------------------------------------------------------|
| 1    | Create `test_relay.py` with WebSocket server on port 8080         |
| 2    | Parse `/gateway?id=...&token=...` from upgrade request path       |
| 3    | Validate token, reject 401 on mismatch                            |
| 4    | Receive loop: print gateway messages to stdout with prefix        |
| 5    | Send loop: read stdin lines asynchronously, forward to gateway    |
| 6    | Handle disconnect/reconnect gracefully (gateway reconnects every 5s) |
| 7    | Add `/health` HTTP endpoint                                       |

## How to Run

```bash
# Install dependency
pip install websockets

# Run on default port 8080
python test_relay.py

# Or override port and token
RELAY_TOKEN=my-secret PORT=9090 python test_relay.py
```

## How to Test

| # | Test                            | Steps                                                              | Expected                                           |
|---|---------------------------------|--------------------------------------------------------------------|-----------------------------------------------------|
| 1 | Relay starts                    | `python test_relay.py`                                             | Prints `Listening on 0.0.0.0:8080`                  |
| 2 | Health check                    | `curl http://localhost:8080/health`                                | `{"status":"ok","gateway_connected":false}`          |
| 3 | Gateway connects                | Power on ESP32 (or use `websocat ws://localhost:8080/gateway?id=gw-01&token=change-me`) | Prints `Gateway connected: gw-01` |
| 4 | Receive data                    | Wait for ESP32 to poll Modbus                                      | Prints `[gw-01 →] {"type":"data",...}`               |
| 5 | Send command                    | Type `{"type":"getConfig"}` in terminal                            | Gateway responds with config, printed to stdout      |
| 6 | Add device                      | Type `addDevice` JSON in terminal                                  | Gateway confirms with config broadcast               |
| 7 | Auth rejection                  | `websocat ws://localhost:8080/gateway?id=x&token=wrong`            | Connection rejected                                  |
| 8 | Reconnection                    | Ctrl+C relay, restart it                                           | ESP32 reconnects within 5s (`RELAY_RECONNECT_INTERVAL_MS`) |

## ESP32 Config Changes for Testing

Update `Config.hpp` before flashing:

```cpp
constexpr const char* RELAY_HOST  = "YOUR_VPS_IP";  // or local IP for LAN testing
constexpr uint16_t    RELAY_PORT  = 8080;
constexpr const char* GATEWAY_ID  = "gw-01";
constexpr const char* RELAY_TOKEN = "change-me";
```

If testing over cellular, the relay must be on a publicly reachable IP (VPS, cloud VM, or port-forwarded home network).
