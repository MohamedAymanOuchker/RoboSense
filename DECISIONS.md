# Decisions

Running log of non-obvious choices made while building RoboSense, per the
"prefer the smaller, simpler, more-polished interpretation" rule in `CLAUDE.md`.

## M1 — Foundation

- **Compose ships `db` + `backend` only (frontend added in M5).** The brief's
  architecture includes the Next.js frontend in the one-command stack, but the
  frontend does not exist until Milestone 5. Adding it now would mean a broken
  build target. The frontend service will be added to `docker-compose.yml` in M5.

- **`make` is the canonical task runner; Windows users get documented
  equivalents.** The brief mandates a `Makefile` (`make up/seed/test`). The dev
  machine is Windows without `make`, but the repo's audience is mostly
  Linux/macOS, so the Makefile stays as the primary interface. The README's
  "Local development" section lists the underlying `docker compose ...` commands
  for anyone without `make`.

- **Pinned to current-latest dependency versions (June 2026).** FastAPI 0.137.2,
  SQLAlchemy 2.0.51, Pydantic 2.13.4, Uvicorn 0.49.0, asyncpg 0.31.0,
  TimescaleDB image `2.28.0-pg17`, Python 3.13. Versions were verified against
  PyPI / Docker Hub at build time so the quickstart builds cleanly on first try.

- **Two health endpoints.** `/api/health` is a cheap liveness probe (no DB
  dependency) used by the container healthcheck; `/api/health/db` is a readiness
  probe that confirms database connectivity. Keeping liveness DB-free avoids a
  restart loop if the DB is briefly unavailable.

- **Backend installed as an editable package (`pip install -e`).** Lets the
  docker-compose source mount provide hot-reload in development without
  reinstalling, and keeps imports as clean absolute `app.*` paths.

## M2 — Auth + devices

- **Two hashing strategies, on purpose.** Passwords use **Argon2**
  (`argon2-cffi`) — slow and memory-hard to resist offline brute force. Device
  **API keys** are high-entropy random tokens, so they are hashed with
  **SHA-256**: this lets ingestion (M3) authenticate a device with a single
  indexed equality lookup instead of an Argon2 verify per row. A fast hash is
  safe precisely because the input isn't guessable. Only hashes are stored; the
  plaintext key is shown exactly once (on create / regenerate).

- **Auth via JSON + `HTTPBearer`, not OAuth2 password form.** `/api/auth/login`
  takes a JSON body and returns a JWT; protected routes use FastAPI's
  `HTTPBearer`. This avoids the `python-multipart` dependency and keeps the
  Swagger "Authorize" flow simple (paste a bearer token). Pinned `PyJWT`.

- **Schema created on app startup, no migration tool.** A FastAPI lifespan calls
  `Base.metadata.create_all`. For a single-service, self-hostable app this keeps
  the quickstart to one command with no separate migrate step; Alembic would be
  extra surface for no benefit at this scale. (The M3 Timescale hypertable is
  created with explicit SQL alongside this.)

- **Tests use a dedicated `<dbname>_test` database, auto-created if missing.**
  Originally the suite shared the app's database and its teardown `drop_all`
  silently wiped dev data. Tests now provision and target a separate database,
  so the schema can be dropped/recreated per test without touching dev or CI
  application data. A `NullPool` engine avoids cross-event-loop connection reuse
  in function-scoped async tests.

- **JWT secret default lengthened to ≥32 bytes.** PyJWT warns on HMAC keys
  shorter than 32 bytes; the dev default is now long enough to be warning-free,
  while still clearly a "change me" placeholder.

## M3 — Telemetry engine

- **Composite primary key `(time, device_id, sensor_name)` + a descending
  `(device_id, sensor_name, time)` index.** TimescaleDB requires the partitioning
  column (`time`) in any unique constraint, so a surrogate key is impossible
  without dragging `time` along anyway. The composite PK also dedupes a sensor's
  reading at an instant; the extra DESC index serves the hot "recent readings for
  a device/sensor" path. The hypertable is created with explicit SQL
  (`create_hypertable`) in the shared `prepare_database`, reused by app startup
  and the tests so they can't drift.

- **The device is identified by its API key, not the payload.** The flexible
  ingest body may carry a `device_id` label (matching the brief's example) but it
  is ignored — the authenticated `X-API-Key` determines the device. Every other
  top-level key is a `sensor_name: value` pair.

- **Optional client `timestamp`, server time by default.** The brief's payload
  has no timestamp, but accepting an optional one lets a device flush readings it
  buffered during a network drop with their *original* times — directly relevant
  to the ESP32 reconnect story in M4. Absent it, the server stamps receive time.

- **Strict numeric validation; booleans rejected.** Non-numeric sensor values
  return 422 naming the offending keys. `bool` is rejected explicitly (it's an
  `int` subclass) so flags aren't silently stored as 0/1 doubles.

- **Idempotent inserts via `ON CONFLICT DO NOTHING`** on the composite PK, so a
  device retrying after an uncertain network result can't create duplicates.

- **Downsampling via a closed allowlist of bucket sizes and aggregates.** Bucket
  intervals (`1s…1d`) map to `timedelta` objects bound as parameters to
  `time_bucket`, and aggregates are limited to avg/min/max. Nothing from the
  query string is ever interpolated into SQL.

- **`order=asc|desc` query param.** Charts want chronological order (default
  `asc`); the dashboard's "current value"/alert checks want latest-first
  (`desc` + `limit`). Added now so M5 isn't blocked.

- **In-process fixed-window rate limiter, per device.** A single FastAPI process
  owns ingestion (per the non-goals: no queues, no distributed infra), so an
  in-memory limiter is correct. It's exposed as a dependency so tests override it
  deterministically. Default 240 requests / 60s per device, configurable.

- **Seed demo email must pass `EmailStr`.** A live smoke test caught that
  `demo@robosense.local` is rejected by `email-validator` (`.local` is a reserved
  TLD), which would have made the printed demo login unusable. Switched to
  `demo@robosense.dev` and added a regression test asserting the seed credentials
  validate.

## M4 — ESP32 firmware

- **Runs on a bare ESP32 with zero extra hardware.** The default build reports
  the chip's internal temperature plus WiFi RSSI, free heap, uptime, and a demo
  battery curve — all readable on any ESP32 dev board. A guarded `USE_DHT22`
  path adds real ambient temperature/humidity. This maximizes the chance a
  reviewer can flash it and see data without sourcing parts.

- **Offline buffering with original timestamps is the centerpiece.** Readings
  taken while disconnected are queued in a fixed-size RAM ring buffer
  (drop-oldest) and resent oldest-first on reconnect, each carrying its own
  capture time. This is the concrete reason the ingest API accepts an optional
  `timestamp` — the two milestones were designed together so a network gap
  renders as a gap-free series, not a cluster at reconnect.

- **Hand-built JSON, no JSON library on the core path.** The payload is flat, so
  `snprintf`/`String` assembly avoids an ArduinoJson dependency and the heap
  churn that comes with it. ArduinoJson would be over-engineering here.

- **Non-blocking loop throughout.** WiFi reconnect uses exponential backoff
  (1 s → 30 s) and the loop never spins on `while (WiFi.status()...)`; sampling
  continues during outages. This is the behaviour the brief specifically calls
  out as a strong signal.

- **Single `.ino` that also builds under PlatformIO.** `platformio.ini` sets
  `src_dir = .` so the Arduino-IDE-friendly single file in `firmware/esp32/`
  compiles without a `src/` move. Config `#define`s are `#ifndef`-guarded so
  secrets can be injected via `build_flags` instead of edited into the source.

- **Verified two ways without a board.** The firmware was compiled for the real
  `esp32dev` target with PlatformIO (`[SUCCESS]`, flash 70.5%, RAM 15.6%), and
  the exact JSON it emits was POSTed to the running backend — 201, one row per
  numeric sensor, original `timestamp` preserved.

## M5 — Dashboard

- **Client-side auth (JWT in `localStorage`), client-rendered dashboard.** For a
  small self-hosted SPA-style dashboard this is the simplest thing that works:
  an `AuthProvider` keeps the token, the API client attaches it, and dashboard
  routes guard on it. The tradeoff vs. httpOnly cookies + SSR is XSS exposure of
  the token; acceptable here and called out honestly. No secrets are server-rendered.

- **Alerts are evaluated server-side, not in the browser.** Rules live in an
  `alert_rules` table and a `/alerts/status` endpoint compares each rule to the
  sensor's latest reading. This keeps the logic authoritative and unit-testable
  (pytest) rather than reimplemented in the UI; the dashboard just renders status.

- **Added `GET /api/telemetry/latest`** (DISTINCT ON `sensor_name`) so device
  cards and alert checks get a one-shot "current values" snapshot instead of
  pulling full series.

- **CORS middleware** allows the browser dashboard origin to call the API
  (`CORS_ORIGINS`, default `http://localhost:3000`).

- **Root `/` returns 200 via a client-side redirect** rather than a server
  `redirect()` (307). It is friendlier to health-check probes and uptime monitors
  that expect a 200 on `/`, and costs nothing.

- **Frontend runs in dev mode under Compose**, mirroring the backend's
  `--reload`: source is mounted with `node_modules`/`.next` kept as
  container-owned volumes so the host (Windows) install can't shadow them.
  `NEXT_PUBLIC_API_URL` points the browser at the backend.

- **Pinned to current frontend versions (June 2026):** Next 16.2.9, React 19.2.7,
  Tailwind 4.3.1 (CSS-first config via `@tailwindcss/postcss`), Recharts 3.8.1,
  TypeScript 6.0.3. Verified with a real `next build`.

- **Screenshot is a real capture of the running app** (`docs/screenshots/dashboard.png`),
  taken headlessly via the system Edge against live seeded data — not a mockup.

## M6 — ROS 2 bridge + docs polish

- **A real `ament_python` package, not a loose script.** `examples/ros2/telemetry_bridge`
  has `package.xml`, `setup.py`, the resource marker, and a console entry point
  (`ros2 run telemetry_bridge bridge`). A robotics reviewer recognizes this as the
  idiomatic form, and it's `colcon build`-able.

- **ROS topic rate is decoupled from ingest rate.** Subscriptions only store the
  latest value per sensor; a timer (`publish_period`, default 2 s) POSTs the
  accumulated snapshot. This keeps a 100 Hz topic from blowing through the
  per-device rate limit, and is how you'd actually bridge ROS to a telemetry API.

- **Standard-library HTTP, no `requests` dependency.** The node uses
  `urllib.request`, so it runs against a fresh ROS 2 install with nothing to
  `pip install` / `rosdep` first — consistent with the "works first try" goal.

- **Bridges `sensor_msgs/BatteryState` + `std_msgs/Float64`.** One real robotics
  message (battery %/voltage) and one generic numeric mapping cover the common
  cases; extending is a one-callback change documented in the README.

- **Verified without a ROS 2 install.** `py_compile` checks the node, and the
  exact JSON snapshot it emits (`battery`, `voltage`, plus a mapped sensor) was
  POSTed to the running backend — 201, stored correctly.

- **OpenAPI polish.** Added tag descriptions, an MIT license + contact block, a
  richer top-level description, and a worked example body on the ingest schema so
  `/docs` is clean and self-explanatory.

## M7 — Anomaly detection (stretch)

- **Rolling z-score, computed in the database.** `GET /api/telemetry/anomalies`
  uses a SQL window function (`avg`/`stddev_samp`/`count` over
  `ROWS BETWEEN <window> PRECEDING AND 1 PRECEDING`) so each reading is judged
  against its **own trailing history**, excluding itself. Points needing a full
  window with non-zero spread are skipped; the rest are flagged when `|z| >= z`.
  Doing the stats in Postgres (not Python) is both faster and a nicer signal.

- **Flagged on the charts, not just listed.** The dashboard marks anomalies with
  dashed vertical lines at their timestamps plus a per-sensor count, which sidesteps
  the raw-vs-downsampled Y-axis problem (a raw spike's value would distort a chart
  showing bucketed averages). The chart X-axis was switched to a numeric time scale
  so markers align with the line regardless of bucketing.

- **Seed injects a few outliers** so the detector has something obvious to flag in
  the demo (battery is left untouched to preserve the threshold-alert story).

- **Default `z = 5` in the UI** keeps the demo clean (isolates the injected
  spikes); the threshold and window are query parameters on the API.

## Extension, Tier 1A — Continuous aggregate + compression + retention

- **Hourly continuous aggregate (`telemetry_summary`).** Pre-materializes
  avg/min/max/count per device+sensor per hour so long historical queries read a
  small rollup instead of scanning raw rows. Created with
  `materialized_only = false` so a query transparently combines the materialized
  rollup with real-time aggregation of the most recent (not-yet-materialized)
  data — results are always complete, even right after ingest.

- **Applied at startup, outside a transaction, idempotently.** CAGG creation and
  the policy procedures (`add_continuous_aggregate_policy`,
  `add_compression_policy`, `add_retention_policy`) can't run inside a transaction
  block, so `apply_policies()` runs them in autocommit. All use `IF NOT EXISTS` /
  `if_not_exists => true`, and the call is best-effort in the lifespan (a failure
  logs but doesn't stop the API).

- **Compression after 7d, retention after 90d (both configurable, 0 = off).**
  Old raw chunks compress; raw rows past retention are dropped while the rollup is
  kept — so storage stays bounded but history stays queryable at hourly
  resolution.

- **Dashboard long ranges read the rollup.** 24h/7d charts call
  `GET /api/telemetry/summary` (the continuous aggregate); 1h/6h still query raw
  with on-the-fly `time_bucket` (the aggregate's hourly grain is too coarse for
  short views).

- **CAGG kept out of the per-test schema.** It would slow every test and its
  dependency on the hypertable complicates teardown. Tests that need it create it
  in-test (autocommit); conftest drops it (CASCADE, autocommit) before the
  per-test `drop_all` so it can never block schema teardown.
