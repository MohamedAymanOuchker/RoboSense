# RoboSense — Build Brief for Claude Code

> Hand this file to Claude Code as the project root `CLAUDE.md`. Read it fully before writing any code. Follow the build order. Do not skip ahead.

---

## 0. What this project is (read this first — it changes every decision)

RoboSense is an **open-source, self-hostable telemetry layer for robots and embedded devices**. A device POSTs sensor readings over HTTP; RoboSense stores them as time-series data and shows them on a clean live dashboard.

**This is a portfolio piece and an open-source credibility project. It is NOT a startup or a SaaS.** That single fact overrides everything else:

- Optimize for **signal density** — a reviewer (robotics/embedded employer, research group) should look at the repo for 90 seconds and conclude "this person is a strong engineer who has actually touched hardware."
- Optimize for **a quickstart that works on the first try** — someone clones the repo and sees real data flowing in under 5 minutes.
- A **small thing that fully works** beats a large thing that mostly works. When in doubt, cut scope, not quality.
- The single most important differentiator is the **working ESP32 hardware example**. Most software engineers cannot build this credibly. Over-invest here. Do not let it become a stubbed TODO.

If a decision trades polish-of-the-core against breadth-of-features, always choose polish-of-the-core.

---

## 1. Non-goals (do NOT build these)

Explicitly out of scope. Do not add them even if they seem helpful:

- ❌ No pricing tiers, billing, plans, or usage metering.
- ❌ No multi-tenant org/team/role management. One user owns their own devices. That's it.
- ❌ No teleoperation, remote command-and-control, or actuator control.
- ❌ No fleet orchestration, traffic management, or mission planning.
- ❌ No mobile app.
- ❌ No Kubernetes, microservices, message queues, or "scalable" architecture. A single FastAPI service + Postgres is correct.
- ❌ No speculative "Phase 2 / Future" features. If it's not in Section 5, don't build it.

Scope creep is the primary failure mode for this project. Resist it.

---

## 2. Target audience & framing

Primary audience: **robotics/embedded employers and research groups**, plus the open-source robotics/maker community (GitHub).

The README and demo are the product surface they actually see. Treat the README as a first-class deliverable, not an afterthought.

Positioning line to use in the README:
> "A focused, self-hostable telemetry backend + dashboard for robots and embedded devices. Flash the included ESP32 firmware and watch live sensor data in 5 minutes. ROS2 example included."

Honest framing — do NOT overclaim. Enterprise-grade platforms (Foxglove, InOrbit, Formant) exist for production fleets. RoboSense is a clean, minimal, self-hostable alternative for individuals, students, and early prototypes. State this plainly in the README; it reads as maturity, not weakness.

---

## 3. Tech stack (fixed — do not substitute)

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x (async).
- **Database:** PostgreSQL + TimescaleDB extension (telemetry is a hypertable). This is the right tool for time-series; use it properly.
- **Auth:** Simple JWT for the dashboard user (register/login). Per-device **API keys** for ingestion. Nothing fancier.
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind CSS. Charts via Recharts.
- **Firmware example:** ESP32 (Arduino framework). Single `.ino` plus a documented PlatformIO option.
- **ROS2 example:** Python `rclpy` node that bridges a topic to the ingestion API.
- **Dev/deploy:** Docker Compose brings up Postgres+Timescale, backend, and frontend with one command. Provide a `Makefile` with `make up`, `make seed`, `make test`.
- **Tests:** pytest for backend. At minimum cover auth, device CRUD, ingestion, and query endpoints.
- **CI:** GitHub Actions running lint + tests on push.

> **To lead with ROS2 instead of ESP32:** swap the emphasis in Sections 0, 2, and the README, and reorder Milestone 5 before Milestone 4. The architecture does not change.

---

## 4. Architecture

```
Device (ESP32 / ROS2 node / anything that can POST)
        │  HTTPS POST /api/telemetry  (X-API-Key header)
        ▼
FastAPI ingest endpoint ── validate ──► TimescaleDB hypertable (telemetry)
        ▲                                        │
        │ JWT-protected REST API                 │ time-bucketed queries
        ▼                                        ▼
Next.js dashboard ◄──── live + historical charts, device pages, alerts
```

Data model (keep it this simple):

- `users`: id, email, password_hash, created_at
- `devices`: id, user_id (FK), name, api_key (unique, hashed at rest), created_at
- `telemetry`: time (timestamptz), device_id (FK), sensor_name (text), value (double) — **hypertable, partitioned on `time`**, index on (device_id, sensor_name, time desc)

Telemetry payload accepted at ingest (flexible sensor keys):
```json
{ "device_id": "robot001", "temperature": 24.5, "battery": 87, "speed": 0.72 }
```
Server fans the flat key/value pairs into individual `telemetry` rows. Reject unknown/missing device or bad API key with proper 4xx codes.

---

## 5. MVP feature set (this is the whole scope)

1. **Auth** — register, login, JWT-protected session. Password hashing (bcrypt/argon2).
2. **Device management** — create / list / rename / delete a device; generate + show an API key once on creation; allow regenerate.
3. **Ingestion API** — `POST /api/telemetry` authenticated by `X-API-Key`. Validate, store, rate-limit per device. Return clear errors.
4. **Query API** — `GET /api/telemetry` with `device_id`, `sensor_name`, time range, and downsampling (use Timescale `time_bucket`). Pagination.
5. **Dashboard** — device list, per-device page with live-updating charts (poll or SSE) + historical view with range selector. Make it genuinely clean; this is the screenshot that goes in the README.
6. **Alerts (minimal)** — per-device threshold rule (e.g. battery < 20) that surfaces a visible alert state in the dashboard. No email/SMS — in-app only.
7. **ESP32 firmware example** — real, flashable, with WiFi setup, the POST loop, and **graceful handling of dropped connectivity / reconnect** (robots have flaky networks — showing you handle this is a strong signal).
8. **ROS2 example** — `rclpy` node subscribing to a topic and forwarding to the ingest API.
9. **OpenAPI docs** — FastAPI auto-generates `/docs`; ensure schemas and examples are clean.

**Stretch (only after 1–9 are fully done and polished):** a tiny on-device or server-side anomaly flag (e.g. rolling z-score on a sensor) shown in the dashboard. This plays directly to an embedded-CV background. Do not start it until the core is complete.

---

## 6. Repository structure

```
robosense/
├── README.md                 # first-class deliverable, see Section 8
├── CLAUDE.md                 # this file
├── LICENSE                   # MIT
├── docker-compose.yml
├── Makefile
├── .github/workflows/ci.yml
├── backend/
│   ├── app/ (main, api/, models/, schemas/, db/, core/auth, core/security)
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/ (dashboard routes), components/, lib/
│   ├── package.json
│   └── Dockerfile
├── firmware/
│   └── esp32/ (robosense_esp32.ino, platformio.ini, README.md with wiring + flash steps)
├── examples/
│   └── ros2/ (telemetry_bridge node + README)
└── docs/
    └── screenshots/ (dashboard.png used in README)
```

---

## 7. Build order (follow this sequence — ship each milestone working before moving on)

Work in this order. After each milestone, the repo must be in a runnable, committed state.

- **M1 — Foundation:** repo scaffold, Docker Compose (Postgres+Timescale up), FastAPI hello, healthcheck, CI green, MIT license. `make up` works.
- **M2 — Auth + devices:** users, JWT, device CRUD, API key generation (hashed at rest). Tests pass.
- **M3 — Telemetry engine:** Timescale hypertable, ingest endpoint with API-key auth + rate limit, query endpoint with `time_bucket` downsampling. Seed script generates fake data. Tests pass. **This is the spine — get it solid.**
- **M4 — ESP32 firmware:** real `.ino`, WiFi + POST loop + reconnect handling, documented flash steps. Verify against a running backend (or document the exact test procedure if no board is attached).
- **M5 — Dashboard:** device list, live + historical charts, threshold alerts. Make it clean. Capture `docs/screenshots/dashboard.png`.
- **M6 — ROS2 example + docs polish:** `rclpy` bridge node, OpenAPI examples tidied, README finalized with the 5-minute quickstart and screenshot.
- **M7 (stretch only):** anomaly flag.

Definition of done for each milestone: code runs via `make up`, tests pass in CI, and the relevant section of the README is updated. No milestone is "done" with a broken quickstart.

---

## 8. README requirements (the portfolio surface — do this carefully)

The README must, in order:

1. One-sentence positioning line + a single dashboard screenshot near the top.
2. A **5-minute quickstart** that actually works: `git clone` → `make up` → open dashboard → run seed OR flash ESP32 → see data. Test these steps end to end; a broken quickstart is worse than no quickstart.
3. Architecture diagram (the ASCII one in Section 4 is fine, or render it).
4. Feature list — honest, no overclaiming.
5. "How it compares" — one short, fair paragraph acknowledging Foxglove/InOrbit/Formant exist for production fleets and positioning RoboSense as the minimal self-hostable option. Maturity reads better than bravado.
6. Tech stack, local dev instructions, running tests.
7. Roadmap (short, honest), Contributing, License.

Tone: precise, confident, not salesy. Write like an engineer documenting for other engineers.

---

## 9. How to work (process rules for Claude Code)

- Small, logical commits with clear messages. Conventional Commits style (`feat:`, `fix:`, `docs:`, `test:`).
- Write tests as you build each endpoint, not at the end.
- Keep dependencies minimal and current. Pin versions.
- Validate all inputs with Pydantic; never trust device payloads.
- Secrets via env vars / `.env.example`; never commit real secrets.
- If something in this brief is ambiguous, prefer the **smaller, simpler, more-polished** interpretation, and note the decision in a `DECISIONS.md`.
- When a milestone is complete, stop and summarize what's done and what's next before continuing.

Begin with M1.
