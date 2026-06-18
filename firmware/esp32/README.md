# RoboSense ESP32 firmware

Flashable firmware that samples a few sensors and POSTs them to a RoboSense
backend. It is built to behave well on the flaky networks robots actually live
on: non-blocking WiFi reconnect, an NTP-synced clock, and **offline buffering**
that resends readings with their original timestamps once the link returns.

Runs on a **bare ESP32 dev board with no extra wiring** — it reports the chip's
internal temperature plus WiFi signal, free heap, uptime, and a demo battery
curve. Add a DHT22 for real ambient temperature and humidity.

## What it sends

`POST /api/telemetry` with header `X-API-Key: <your key>` and a flat JSON body —
every numeric key becomes a sensor:

```json
{
  "device_id": "esp32-rover",
  "timestamp": "2026-06-18T22:00:00Z",
  "temperature": 24.5,
  "battery": 87.0,
  "rssi": -57,
  "uptime_s": 1234,
  "free_heap": 210443
}
```

`device_id` is just a label — the device is identified by its API key.
`timestamp` is included once the clock is NTP-synced; the backend falls back to
its receive time if it is absent.

## 1. Get a device API key

Either run `make seed` in the repo root (it prints a ready-to-use key), or log
into the dashboard and create a device — the key is shown once on creation.

## 2. Configure

Open [`robosense_esp32.ino`](robosense_esp32.ino) and edit the configuration
block near the top:

```c
#define WIFI_SSID       "your-wifi-ssid"
#define WIFI_PASSWORD   "your-wifi-password"
#define ROBOSENSE_HOST  "http://192.168.1.50:8000"   // your backend's LAN IP
#define ROBOSENSE_API_KEY "rsk_paste_your_device_api_key_here"
#define DEVICE_NAME     "esp32-rover"
```

> Use the backend host's **LAN IP**, not `localhost` — `localhost` on the ESP32
> means the ESP32 itself. Find it with `ipconfig` (Windows) / `ip addr` (Linux).
> The device and the backend must be on the same network.

Prefer to keep secrets out of the source? Set them in
[`platformio.ini`](platformio.ini) `build_flags` instead (each `#define` is
guarded with `#ifndef`).

## 3. Flash

### Option A — PlatformIO (recommended)

```bash
cd firmware/esp32
pio run -t upload      # compile + flash over USB
pio device monitor     # watch the serial log (115200 baud)
```

### Option B — Arduino IDE

1. Install the ESP32 boards: **File → Preferences → Additional Boards Manager
   URLs** → `https://espressif.github.io/arduino-esp32/package_esp32_index.json`,
   then **Tools → Board → Boards Manager** → install "esp32".
2. Open `robosense_esp32.ino`. If the IDE offers to create a sketch folder of
   the same name, accept it.
3. **Tools → Board** → "ESP32 Dev Module"; select the serial **Port**.
4. (Only if you enabled `USE_DHT22`) **Library Manager** → install "DHT sensor
   library" and "Adafruit Unified Sensor".
5. Click **Upload**, then open **Serial Monitor** at 115200 baud.

Expected serial output:

```
RoboSense ESP32 firmware starting
[cfg] device=esp32-rover host=http://192.168.1.50:8000
[wifi] connecting to "your-wifi-ssid"
[time] SNTP started
[time] clock synced (UTC)
```

Within a few seconds the device appears in the dashboard with live data.

## Optional: DHT22 wiring

Uncomment `#define USE_DHT22` in the firmware. Default data pin is `GPIO4`.

| DHT22 pin | ESP32        |
| --------- | ------------ |
| VCC (+)   | 3V3          |
| DATA      | GPIO4        |
| GND (−)   | GND          |

Add a 10 kΩ pull-up resistor between DATA and 3V3.

## How the resilience works

- **WiFi reconnect** — the main loop never blocks on the network. If WiFi drops,
  it retries with exponential backoff (1 s → 30 s) while continuing to sample.
- **Clock** — once online, SNTP syncs the clock so every reading gets an accurate
  UTC capture time.
- **Offline buffer** — when a POST fails (no link, server down, etc.) the reading
  is pushed into a fixed-size RAM ring buffer (drop-oldest when full). When
  connectivity returns, the backlog is drained oldest-first, each reading sent
  with its **original** `timestamp` — so a gap in the network becomes a gap-free
  series in the dashboard rather than a cluster of points at reconnect time.

## Testing without a board

You can exercise the exact HTTP contract this firmware uses against a running
backend (`make up` + `make seed` to get a key):

```bash
curl -X POST http://localhost:8000/api/telemetry \
  -H "X-API-Key: rsk_your_device_api_key" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32-rover","timestamp":"2026-06-18T22:00:00Z","temperature":24.5,"battery":87,"rssi":-57,"uptime_s":1234,"free_heap":210443}'
```

A `201` with `{"status":"accepted","points_written":5,...}` (one row per numeric
sensor) means the firmware's payload will be accepted as-is. The backend stores
it under the reading's own `timestamp`, which is what makes the offline-buffer
resend land at the right point on the timeline.

## HTTPS

The quickstart uses plain HTTP on a trusted LAN. For deployment over the public
internet, terminate TLS at a reverse proxy and switch the client to
`WiFiClientSecure` (set `ROBOSENSE_HOST` to your `https://` URL and provide the
CA certificate).
