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
