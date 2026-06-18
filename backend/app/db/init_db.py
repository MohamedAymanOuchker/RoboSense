"""Schema initialization.

For a single-service, self-hostable app we favour create-on-startup over a
migration tool: it keeps the quickstart to one command with no migrate step.
Importing ``app.models`` registers every table on ``Base.metadata``.
"""

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.db.base import Base
from app.db.session import engine


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
