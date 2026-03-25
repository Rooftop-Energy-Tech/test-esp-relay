
# WebSocket API Reference

## Connection

| Parameter | Value |
|-----------|-------|
| Host | `46.202.164.183` |
| Port | `8087` |
| Path | `/ws?role=gateway` |
| Protocol | WebSocket (RFC 6455) |
| Frame type | Text (JSON) |
| Gateway ID | `gw-01` |
| Auth token | `change-me` |

The gateway connects automatically on boot via a LilyGo T-A7670E cellular modem (SIM7600, Maxis Malaysia APN). If the connection drops, it retries every **5 seconds**.

---

## Message Format

All messages are UTF-8 JSON text frames. Every message — both inbound (server → gateway) and outbound (gateway → server) — carries a `"type"` field that identifies the operation.

```json
{ "type": "<message-type>", ... }
```

---

## Inbound Messages (Server → Gateway)

### `config`

Replaces the entire device list and bus settings in one operation.

```json
{
  "type": "config",
  "baudRate": 9600,
  "interval": 1000,
  "devices": [
    {
      "slaveId": 1,
      "name": "Power Logger",
      "baudRate": 9600,
      "enabled": true,
      "slaveIdRegister": 0,
      "registers": [
        { "address": 20, "label": "Voltage A", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" },
        { "address": 21, "label": "Voltage B", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" },
        { "address": 22, "label": "Voltage C", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" }
      ]
    }
  ]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `baudRate` | uint32 | 9600 | RS485 bus baud rate (1200–115200) |
| `interval` | uint32 | 1000 | Polling interval in milliseconds (100–60000) |
| `devices` | array | — | List of device configs (max 8) |

**Response:** [`config`](#config-1) (echoes back the applied configuration)

---

### `getConfig`

Requests the gateway to return its current configuration.

```json
{ "type": "getConfig" }
```

**Response:** [`config`](#config-1)

---

### `addDevice`

Adds a single device to the active device list without affecting others.

```json
{
  "type": "addDevice",
  "device": {
    "slaveId": 2,
    "name": "Genset",
    "baudRate": 9600,
    "enabled": true,
    "slaveIdRegister": 0,
    "registers": [
      { "address": 1000, "label": "RPM",              "scaleFactor": 1.0, "functionCode": 4, "dataType": "S16" },
      { "address": 1018, "label": "Voltage L1-N",     "scaleFactor": 1.0, "functionCode": 4, "dataType": "U16" },
      { "address": 1284, "label": "Controller Mode",  "scaleFactor": 1.0, "functionCode": 3, "dataType": "U16" },
      { "address": 1286, "label": "Engine State",     "scaleFactor": 1.0, "functionCode": 3, "dataType": "U16" }
    ]
  }
}
```

**Response:** [`config`](#config-1) (full updated configuration)

---

### `removeDevice`

Removes a device from the active list by slave ID.

```json
{
  "type": "removeDevice",
  "slaveId": 2
}
```

**Response:** [`config`](#config-1) (full updated configuration)

---

### `updateDevice`

Replaces the configuration of an existing device identified by `slaveId`.

```json
{
  "type": "updateDevice",
  "slaveId": 2,
  "device": {
    "slaveId": 2,
    "name": "Genset (updated)",
    "baudRate": 9600,
    "enabled": true,
    "slaveIdRegister": 0,
    "registers": [
      { "address": 1000, "label": "RPM", "scaleFactor": 1.0, "functionCode": 4, "dataType": "S16" }
    ]
  }
}
```

**Response:** [`config`](#config-1) (full updated configuration)

---

### `writeRegister`

Writes a single 16-bit value to a holding register on a device using Modbus FC 0x10.

```json
{
  "type": "writeRegister",
  "slaveId": 1,
  "address": 50,
  "value": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `slaveId` | uint8 | Target device Modbus address (1–247) |
| `address` | uint16 | Register address (0-based) |
| `value` | uint16 | Value to write |

**Response:** [`writeResult`](#writeresult)

---

### `gensetCommand`

Executes a ComAp MRS16 genset control command using the 3-step Modbus sequence:
1. Writes a U32 argument to registers 4207–4208.
2. Writes the command code to register 4209.
3. Reads back registers 4207–4208 and verifies the controller's return value.

#### Named commands

```json
{
  "type": "gensetCommand",
  "slaveId": 1,
  "command": "start"
}
```

| `command` | Argument | Cmd code | Expected return |
|-----------|----------|----------|-----------------|
| `"start"` | `0x01FE0000` | `0x01` | `0x000001FF` |
| `"stop"` | `0x02FD0000` | `0x01` | `0x000002FE` |
| `"faultReset"` | `0x08F70000` | `0x01` | `0x000008F8` |
| `"hornReset"` | `0x04FB0000` | `0x01` | `0x000004FC` |

#### Raw command (advanced)

Omit `"command"` and supply raw values instead:

```json
{
  "type": "gensetCommand",
  "slaveId": 1,
  "argument": 33423360,
  "cmdCode": 1,
  "expectedReturn": 511
}
```

**Response:** [`gensetResult`](#gensetresult)

---

### `changeSlaveId`

Changes the Modbus slave ID of a device — writes the new ID to the device's physical register and updates the gateway's internal configuration.

```json
{
  "type": "changeSlaveId",
  "currentSlaveId": 1,
  "newSlaveId": 3,
  "slaveIdRegister": 0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `currentSlaveId` | uint8 | Current slave address of the target device |
| `newSlaveId` | uint8 | Desired new slave address |
| `slaveIdRegister` | uint16 | Optional override for the register that stores the slave ID. Falls back to the value configured on the device. |

**Response:** [`writeResult`](#writeresult) followed by [`config`](#config-1)

---

## Outbound Messages (Gateway → Server)

### `data`

Published automatically after every successful Modbus poll (default every 1 second). Contains readings from all enabled devices.

```json
{
  "type": "data",
  "devices": [
    {
      "slaveId": 1,
      "name": "Power Logger",
      "readings": [
        { "label": "Voltage A", "value": 231.4 },
        { "label": "Voltage B", "value": 230.1 },
        { "label": "Voltage C", "value": null }
      ]
    }
  ]
}
```

`"value"` is `null` when the register read failed (timeout or CRC error).

---

### `config`

Sent in response to `config`, `getConfig`, `addDevice`, `removeDevice`, `updateDevice`, and `changeSlaveId`. Reflects the full state of the gateway after the operation.

```json
{
  "type": "config",
  "baudRate": 9600,
  "interval": 1000,
  "devices": [
    {
      "slaveId": 1,
      "name": "Power Logger",
      "slaveIdRegister": 0,
      "baudRate": 9600,
      "enabled": true,
      "registers": [
        { "address": 20, "label": "Voltage A", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" }
      ]
    }
  ]
}
```

---

### `writeResult`

Response to `writeRegister` and `changeSlaveId`.

```json
{
  "type": "writeResult",
  "success": true,
  "slaveId": 1,
  "address": 50,
  "value": 1
}
```

For `changeSlaveId`, the fields are `previousSlaveId` and `newSlaveId` instead:

```json
{
  "type": "writeResult",
  "success": true,
  "previousSlaveId": 1,
  "newSlaveId": 3
}
```

---

### `gensetResult`

Response to `gensetCommand`. `"success"` is `true` only if the controller acknowledged the command with the expected return value.

```json
{
  "type": "gensetResult",
  "success": true,
  "slaveId": 1,
  "command": "start"
}
```

---

### `error`

Sent when a command cannot be executed.

```json
{
  "type": "error",
  "message": "Invalid slave ID"
}
```

| Possible messages |
|---|
| `"Invalid JSON"` |
| `"Unknown command type"` |
| `"Invalid slave ID"` |
| `"Invalid device configuration"` |
| `"Failed to add device (full or duplicate ID)"` |
| `"Device not found"` |
| `"Failed to update device"` |
| `"Write to device failed (no response)"` |
| `"Invalid slave ID range"` |
| `"Unknown genset command"` |
| `"Invalid configuration"` |
| `"Missing slaveId"` |

---

## Device Config Object

Used inside `config`, `addDevice`, and `updateDevice`.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `slaveId` | uint8 | `1` | 1–247, unique | Modbus slave address |
| `name` | string | `"Device"` | max 31 chars | Human-readable label |
| `baudRate` | uint32 | `9600` | 1200–115200 | Per-device baud rate |
| `enabled` | bool | `true` | — | When `false`, device is skipped during polling |
| `slaveIdRegister` | uint16 | `0` | — | Register used by `changeSlaveId` |
| `registers` | array | — | max 8 entries | Registers to poll |

---

## Register Entry Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `address` | uint16 | — | Modbus register address (0-based) |
| `label` | string | `"Unknown"` | Label for this reading in `data` output |
| `scaleFactor` | float | `100.0` | Raw value is **divided** by this before publishing |
| `functionCode` | uint8 | `3` | `3` = holding registers (FC 0x03), `4` = input registers (FC 0x04) |
| `dataType` | string | `"U16"` | See table below |

### Data types

| Value | Width | Signed | Notes |
|-------|-------|--------|-------|
| `"U16"` | 16-bit | No | 1 register |
| `"S16"` | 16-bit | Yes | 1 register |
| `"U32"` | 32-bit | No | 2 registers, low word first (Sungrow convention) |
| `"S32"` | 32-bit | Yes | 2 registers, low word first (Sungrow convention) |

---

## Device Quick-Reference

### Power Logger

| Register | Label | FC | Data type | Scale |
|----------|-------|----|-----------|-------|
| 20 | Voltage A | 3 | U16 | 100.0 |
| 21 | Voltage B | 3 | U16 | 100.0 |
| 22 | Voltage C | 3 | U16 | 100.0 |

### ComAp MRS16 Genset Controller

| Register | Label | FC | Data type | Scale |
|----------|-------|----|-----------|-------|
| 1000 | RPM | 4 | S16 | 1.0 |
| 1018 | Voltage L1-N | 4 | U16 | 1.0 |
| 1284 | Controller Mode | 3 | U16 | 1.0 |
| 1286 | Engine State | 3 | U16 | 1.0 |

Controller Mode values: `0` = OFF, `1` = MAN, `2` = AUTO

Engine State values: `0`=Init, `1`=Ready, `2`=NotReady, `3`=Prestart, `4`=Cranking, `5`=Pause, `6`=Starting, `7`=Running, `8`=Loaded, `9`=Soft unload, `10`=Cooling, `11`=Stop, `12`=Shutdown, `13`=Ventil, `14`=EmergMan, `15`=Soft load, `16`=WaitStop, `17`=SDVentil

### Sungrow SG12KTL-M Inverter

| Register | Label | FC | Data type | Scale |
|----------|-------|----|-----------|-------|
| 5021 | Phase A Current | 4 | U16 | 10.0 |
| 5022 | Phase B Current | 4 | U16 | 10.0 |
| 5023 | Phase C Current | 4 | U16 | 10.0 |
| 5030 | Total Active Power | 4 | U32 | 1.0 |
| 5032 | Total Reactive Power | 4 | S32 | 1.0 |
| 5034 | Power Factor | 4 | S16 | 1000.0 |

> **Note:** Registers 5030–5033 use two-register reads. When using U32/S32, set `"address"` to the first register of the pair (e.g. `5030` for Active Power). The gateway reads two consecutive registers automatically.

---

## Example: Configuring All Three Devices

```json
{
  "type": "config",
  "baudRate": 9600,
  "interval": 2000,
  "devices": [
    {
      "slaveId": 1,
      "name": "Power Logger",
      "baudRate": 9600,
      "enabled": true,
      "slaveIdRegister": 0,
      "registers": [
        { "address": 20, "label": "Voltage A", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" },
        { "address": 21, "label": "Voltage B", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" },
        { "address": 22, "label": "Voltage C", "scaleFactor": 100.0, "functionCode": 3, "dataType": "U16" }
      ]
    },
    {
      "slaveId": 2,
      "name": "Genset",
      "baudRate": 9600,
      "enabled": true,
      "slaveIdRegister": 0,
      "registers": [
        { "address": 1000, "label": "RPM",             "scaleFactor": 1.0, "functionCode": 4, "dataType": "S16" },
        { "address": 1018, "label": "Voltage L1-N",    "scaleFactor": 1.0, "functionCode": 4, "dataType": "U16" },
        { "address": 1284, "label": "Controller Mode", "scaleFactor": 1.0, "functionCode": 3, "dataType": "U16" },
        { "address": 1286, "label": "Engine State",    "scaleFactor": 1.0, "functionCode": 3, "dataType": "U16" }
      ]
    },
    {
      "slaveId": 3,
      "name": "Inverter",
      "baudRate": 9600,
      "enabled": true,
      "slaveIdRegister": 0,
      "registers": [
        { "address": 5030, "label": "Active Power",   "scaleFactor": 1.0,    "functionCode": 4, "dataType": "U32" },
        { "address": 5032, "label": "Reactive Power", "scaleFactor": 1.0,    "functionCode": 4, "dataType": "S32" },
        { "address": 5034, "label": "Power Factor",   "scaleFactor": 1000.0, "functionCode": 4, "dataType": "S16" },
        { "address": 5021, "label": "Phase A Current","scaleFactor": 10.0,   "functionCode": 4, "dataType": "U16" },
        { "address": 5022, "label": "Phase B Current","scaleFactor": 10.0,   "functionCode": 4, "dataType": "U16" },
        { "address": 5023, "label": "Phase C Current","scaleFactor": 10.0,   "functionCode": 4, "dataType": "U16" }
      ]
    }
  ]
}
```
