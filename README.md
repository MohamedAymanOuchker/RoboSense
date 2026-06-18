# RoboSense

> A focused, self-hostable telemetry backend + dashboard for robots and embedded devices. Flash the included ESP32 firmware and watch live sensor data in 5 minutes. ROS2 example included.

RoboSense is an open-source telemetry layer for robots and embedded devices. A
device POSTs sensor readings over HTTP; RoboSense stores them as time-series data
in TimescaleDB and shows them on a clean live dashboard.

> **Status:** under active construction. Milestones 1–2 are complete (foundation,
> plus auth + device management with per-device API keys). Ingestion, dashboard,
> and the ESP32 / ROS2 examples are landing milestone by milestone — see the
> [Roadmap](#roadmap).

<!-- A dashboard screenshot will live here once Milestone 5 ships. -->

## Architecture

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

A single FastAPI service backed by PostgreSQL + TimescaleDB. No microservices,
no message queues — the right amount of architecture for the job.

## Quickstart

Requires [Docker](https://docs.docker.com/get-docker/) and Docker Compose.

```bash
git clone <this-repo> robosense
cd robosense
make up
```

Then open:

- API root — http://localhost:8000
- Interactive API docs — http://localhost:8000/docs
- Liveness — http://localhost:8000/api/health
- Database readiness — http://localhost:8000/api/health/db

`make up` copies `.env.example` to `.env` on first run, builds the images, and
starts the database and backend. Stop everything with `make down`.

## Local development

`make` targets wrap Docker Compose:

| Command       | What it does                                              |
| ------------- | -------------------------------------------------------- |
| `make up`     | Build and start the stack (db + backend) in the background |
| `make down`   | Stop the stack (keeps the database volume)               |
| `make logs`   | Follow logs from all services                            |
| `make test`   | Run the backend test suite inside the container          |
| `make lint`   | Run `ruff` lint inside the container                     |
| `make clean`  | Stop the stack and delete the database volume            |

**No `make` (e.g. on Windows)?** Run the underlying commands directly:

```bash
# first time only
cp .env.example .env            # or: copy .env.example .env   (Windows)

docker compose up -d --build    # == make up
docker compose exec backend pytest -q   # == make test
docker compose down             # == make down
```

## API

Full interactive docs (with schemas and examples) are at `/docs`. Endpoints
available today:

| Method | Path | Auth | Purpose |
| ------ | ---- | ---- | ------- |
| `POST` | `/api/auth/register` | — | Create a dashboard user |
| `POST` | `/api/auth/login` | — | Exchange credentials for a JWT |
| `GET`  | `/api/auth/me` | JWT | Current user |
| `POST` | `/api/devices` | JWT | Create a device (returns its API key **once**) |
| `GET`  | `/api/devices` | JWT | List your devices |
| `GET`/`PATCH`/`DELETE` | `/api/devices/{id}` | JWT | Get / rename / delete a device |
| `POST` | `/api/devices/{id}/regenerate-key` | JWT | Rotate a device's API key |

Passwords are hashed with Argon2; device API keys are random tokens stored only
as a SHA-256 hash and shown exactly once. Telemetry ingestion (`X-API-Key`) and
querying land in Milestone 3.

## Tech stack

- **Backend:** Python 3.13, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 (async), asyncpg
- **Database:** PostgreSQL + TimescaleDB (telemetry stored as a hypertable)
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + Recharts _(M5)_
- **Firmware:** ESP32 (Arduino / PlatformIO) _(M4)_
- **ROS2:** `rclpy` bridge node _(M6)_
- **Dev/CI:** Docker Compose, Makefile, pytest, ruff, GitHub Actions

## Running tests

```bash
make test            # inside the running stack
# or, against a local Postgres/Timescale on :5432:
cd backend && pip install -e ".[dev]" && pytest -q
```

## Roadmap

- [x] **M1** — Foundation: Docker Compose, TimescaleDB, FastAPI healthchecks, CI
- [x] **M2** — Auth (JWT) + device management with per-device API keys
- [ ] **M3** — Telemetry ingest + time-bucketed query API + seed script
- [ ] **M4** — ESP32 firmware example (WiFi, POST loop, reconnect handling)
- [ ] **M5** — Next.js dashboard: live + historical charts, threshold alerts
- [ ] **M6** — ROS2 bridge example + OpenAPI / docs polish
- [ ] **M7** _(stretch)_ — anomaly flag (rolling z-score)

## How it compares

Production fleet platforms like [Foxglove](https://foxglove.dev/),
[InOrbit](https://www.inorbit.ai/), and [Formant](https://formant.io/) are mature,
feature-rich, and the right call for operating fleets at scale. RoboSense is not
trying to compete with them. It is the minimal, self-hostable option for
individuals, students, and early prototypes who want a clean telemetry backend +
dashboard they fully own, running in minutes on their own machine.

## Contributing

Issues and pull requests are welcome. Commits follow
[Conventional Commits](https://www.conventionalcommits.org/). Run `make lint` and
`make test` before opening a PR.

## License

[MIT](LICENSE)
