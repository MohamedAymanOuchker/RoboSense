/*
 * RoboSense — ESP32 telemetry firmware
 * ------------------------------------------------------------------------
 * Samples a few sensors and POSTs them to a RoboSense backend's ingest API.
 *
 * The point of interest is resilience: robots roam and their networks drop.
 * This firmware
 *   - reconnects to WiFi without blocking the main loop (exponential backoff),
 *   - keeps an NTP-synced clock so readings carry an accurate capture time,
 *   - buffers readings in RAM while offline and resends them — with their
 *     ORIGINAL timestamps — once connectivity returns. (That is exactly why the
 *     backend's POST /api/telemetry accepts an optional `timestamp`.)
 *
 * Out of the box it runs on a bare ESP32 dev board with no extra wiring, using
 * the chip's internal temperature sensor plus WiFi/heap/uptime metrics. Define
 * USE_DHT22 (and wire a DHT22) for real ambient temperature + humidity.
 *
 * Boards: classic ESP32 (esp32dev). See README.md for flashing.
 */

#include <HTTPClient.h>
#include <WiFi.h>
#include <time.h>

// ---------------------------------------------------------------------------
// Configuration
//
// Edit the placeholders below, OR leave them and inject real values from
// platformio.ini `build_flags` (each is guarded with #ifndef). Keeping secrets
// out of the source file is the recommended approach for a real deployment.
// ---------------------------------------------------------------------------
#ifndef WIFI_SSID
#define WIFI_SSID "your-wifi-ssid"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "your-wifi-password"
#endif
// Base URL of your RoboSense backend (no trailing slash), e.g. a machine on
// your LAN running `make up`. Use the host's IP, not "localhost".
#ifndef ROBOSENSE_HOST
#define ROBOSENSE_HOST "http://192.168.1.50:8000"
#endif
// A device API key from the dashboard (or printed by `make seed`).
#ifndef ROBOSENSE_API_KEY
#define ROBOSENSE_API_KEY "rsk_paste_your_device_api_key_here"
#endif
#ifndef DEVICE_NAME
#define DEVICE_NAME "esp32-rover"
#endif
// Sampling / send cadence in milliseconds.
#ifndef POST_INTERVAL_MS
#define POST_INTERVAL_MS 5000
#endif

// Optional DHT22 ambient sensor. Uncomment to enable and wire data -> DHT_PIN.
// #define USE_DHT22
#ifndef DHT_PIN
#define DHT_PIN 4
#endif

#ifdef USE_DHT22
#include <DHT.h>
static DHT dht(DHT_PIN, DHT22);
#endif

// ---------------------------------------------------------------------------
// Offline ring buffer
// ---------------------------------------------------------------------------
struct Reading {
  time_t ts;         // unix epoch seconds; 0 if the clock isn't synced yet
  float temperature; // deg C
  float humidity;    // %RH (only valid when has_humidity)
  float battery;     // %
  int rssi;          // WiFi RSSI in dBm (0 when offline)
  uint32_t uptime_s; // seconds since boot
  uint32_t free_heap; // bytes
  bool has_humidity;
};

static const size_t BUFFER_CAPACITY = 120; // ~10 min at a 5 s cadence
static Reading g_buffer[BUFFER_CAPACITY];
static size_t g_buf_head = 0;  // index of the next write
static size_t g_buf_count = 0; // number of queued readings

static void bufferPush(const Reading &r) {
  g_buffer[g_buf_head] = r;
  g_buf_head = (g_buf_head + 1) % BUFFER_CAPACITY;
  if (g_buf_count < BUFFER_CAPACITY) {
    g_buf_count++; // grow
  }
  // When full, the slot we just overwrote was the oldest (drop-oldest policy);
  // g_buf_count stays at capacity and the oldest index advances on its own.
}

static size_t bufferOldest() {
  return (g_buf_head + BUFFER_CAPACITY - g_buf_count) % BUFFER_CAPACITY;
}

// ---------------------------------------------------------------------------
// WiFi (non-blocking reconnect with backoff) + NTP
// ---------------------------------------------------------------------------
static unsigned long g_last_reconnect = 0;
static unsigned long g_reconnect_backoff_ms = 1000;
static const unsigned long RECONNECT_BACKOFF_MAX_MS = 30000;

static bool g_sntp_started = false;
static bool g_time_synced = false;

static void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    g_reconnect_backoff_ms = 1000; // reset backoff once healthy
    return;
  }
  const unsigned long now = millis();
  if (now - g_last_reconnect < g_reconnect_backoff_ms) {
    return; // still within the backoff window; don't block
  }
  g_last_reconnect = now;
  Serial.printf("[wifi] offline; reconnect attempt (backoff %lus)\n",
                g_reconnect_backoff_ms / 1000);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  g_reconnect_backoff_ms =
      min(g_reconnect_backoff_ms * 2, RECONNECT_BACKOFF_MAX_MS);
}

static void syncTimeIfNeeded() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  if (!g_sntp_started) {
    configTime(0, 0, "pool.ntp.org", "time.nist.gov"); // UTC
    g_sntp_started = true;
    Serial.println("[time] SNTP started");
  }
  if (!g_time_synced && time(nullptr) > 1700000000) { // sane epoch (>= 2023)
    g_time_synced = true;
    Serial.println("[time] clock synced (UTC)");
  }
}

static String isoTimestamp(time_t ts) {
  struct tm tm_utc;
  gmtime_r(&ts, &tm_utc);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);
  return String(buf);
}

// ---------------------------------------------------------------------------
// Sensors
// ---------------------------------------------------------------------------
static Reading sampleSensors() {
  Reading r{};
  r.ts = g_time_synced ? time(nullptr) : 0;
  r.uptime_s = millis() / 1000;
  r.rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0;
  r.free_heap = ESP.getFreeHeap();
  r.has_humidity = false;

#ifdef USE_DHT22
  const float t = dht.readTemperature();
  const float h = dht.readHumidity();
  r.temperature = isnan(t) ? temperatureRead() : t;
  if (!isnan(h)) {
    r.humidity = h;
    r.has_humidity = true;
  }
#else
  r.temperature = temperatureRead(); // internal die temperature (rough)
#endif

  // Demo battery curve derived from uptime. Replace with a real ADC read of a
  // battery voltage divider, e.g.:  r.battery = readBatteryPercent(BAT_PIN);
  r.battery = 100.0f - fmodf(r.uptime_s / 36.0f, 100.0f);
  return r;
}

// Hand-built JSON keeps the core build free of a JSON library dependency. The
// payload is flat: every numeric key becomes a sensor on the backend.
static String buildPayload(const Reading &r) {
  String json = "{\"device_id\":\"" DEVICE_NAME "\"";
  if (r.ts > 0) {
    json += ",\"timestamp\":\"" + isoTimestamp(r.ts) + "\"";
  }
  json += ",\"temperature\":" + String(r.temperature, 2);
  if (r.has_humidity) {
    json += ",\"humidity\":" + String(r.humidity, 2);
  }
  json += ",\"battery\":" + String(r.battery, 2);
  json += ",\"rssi\":" + String(r.rssi);
  json += ",\"uptime_s\":" + String(r.uptime_s);
  json += ",\"free_heap\":" + String(r.free_heap);
  json += "}";
  return json;
}

// Returns true on a 2xx response.
static bool sendReading(const Reading &r) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  HTTPClient http;
  const String url = String(ROBOSENSE_HOST) + "/api/telemetry";
  if (!http.begin(url)) {
    return false;
  }
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", ROBOSENSE_API_KEY);

  const int code = http.POST(buildPayload(r));
  http.end();

  if (code >= 200 && code < 300) {
    return true;
  }
  // 401/403 won't be fixed by retrying — surface it loudly so the user fixes
  // the API key rather than silently filling the buffer.
  if (code == 401 || code == 403) {
    Serial.printf("[post] auth rejected (http %d) — check ROBOSENSE_API_KEY\n",
                  code);
  } else {
    Serial.printf("[post] failed (http %d) — will buffer and retry\n", code);
  }
  return false;
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------
static unsigned long g_last_sample = 0;

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("RoboSense ESP32 firmware starting");
  Serial.printf("[cfg] device=%s host=%s\n", DEVICE_NAME, ROBOSENSE_HOST);

#ifdef USE_DHT22
  dht.begin();
#endif

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[wifi] connecting to \"%s\"\n", WIFI_SSID);
}

void loop() {
  ensureWifi();
  syncTimeIfNeeded();

  const unsigned long now = millis();
  if (now - g_last_sample >= POST_INTERVAL_MS) {
    g_last_sample = now;
    const Reading r = sampleSensors();
    if (!sendReading(r)) {
      bufferPush(r);
      Serial.printf("[buffer] queued reading (%u buffered)\n",
                    (unsigned)g_buf_count);
    }
  }

  // Drain the backlog when back online — a few per loop so we never block long.
  if (WiFi.status() == WL_CONNECTED && g_buf_count > 0) {
    int flushed = 0;
    while (g_buf_count > 0 && flushed < 5) {
      const size_t idx = bufferOldest();
      if (!sendReading(g_buffer[idx])) {
        break; // still failing; try again next loop
      }
      g_buf_count--; // pop oldest
      flushed++;
    }
    if (flushed > 0) {
      Serial.printf("[buffer] flushed %d (%u remaining)\n", flushed,
                    (unsigned)g_buf_count);
    }
  }

  delay(10); // brief yield; keeps WiFi/TCP stacks serviced without busy-looping
}
