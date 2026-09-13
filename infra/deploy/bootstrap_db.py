"""Make a hosted Postgres ready for BidProof. Idempotent; runs on every boot.

Does what infra/postgres/init/01-databases.sql does for the compose
Postgres, where the entrypoint runs it once on an empty volume. A managed
database (Neon, Supabase, RDS) has no such hook, so this runs as the owner
before migrations:

  * the pgvector extension
  * the RLS-constrained application role, with the password from
    APP_DB_PASSWORD (must match the one inside DATABASE_URL)
  * CONNECT + USAGE grants; table grants live in the migrations

Uses only DATABASE_URL_OWNER and APP_DB_PASSWORD.
"""

import asyncio
import os
import sys
from urllib.parse import urlsplit, urlunsplit

import asyncpg


def _dsn(url: str) -> str:
    # SQLAlchemy URL -> plain libpq DSN.
    parts = urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


async def main() -> int:
    owner_url = os.environ.get("DATABASE_URL_OWNER", "")
    app_password = os.environ.get("APP_DB_PASSWORD", "")
    if not owner_url:
        print("bootstrap: DATABASE_URL_OWNER is not set", file=sys.stderr)
        return 1
    if not app_password:
        print("bootstrap: APP_DB_PASSWORD is not set", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(_dsn(owner_url))
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_roles WHERE rolname = 'bidproof_app'"
        )
        # The password is an identifier-quoted literal; asyncpg cannot bind
        # parameters inside CREATE/ALTER ROLE.
        literal = app_password.replace("'", "''")
        if exists:
            await conn.execute(f"ALTER ROLE bidproof_app WITH LOGIN PASSWORD '{literal}'")
            print("bootstrap: role bidproof_app exists; password synced")
        else:
            await conn.execute(f"CREATE ROLE bidproof_app LOGIN PASSWORD '{literal}'")
            print("bootstrap: role bidproof_app created")
        database = await conn.fetchval("SELECT current_database()")
        await conn.execute(f'GRANT CONNECT ON DATABASE "{database}" TO bidproof_app')
        await conn.execute("GRANT USAGE ON SCHEMA public TO bidproof_app")
        print(f"bootstrap: {database} ready")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
