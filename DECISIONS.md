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
