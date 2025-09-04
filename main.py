"""
A simple TCP server that accepts JSON and stores them in a PostgreSQL database.
"""

import asyncio
import configparser
import json
import os
import signal

import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.types.json import Json

# read config
config = configparser.ConfigParser()
config.read(os.path.expanduser("~/.watergate"))

# database
DATABASE_HOST = config["database"]["host"]
DATABASE_PORT = int(config["database"]["port"])
DATABASE_NAME = config["database"]["name"]
DATABASE_USER = config["database"]["user"]
DATABASE_PASSWORD = config["database"]["password"]
DATABASE_URL = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"

# app
WATERGATE_HOST = config["app"]["host"]
WATERGATE_PORT = int(config["app"]["port"])

REQUIRED_FIELDS = ["user_id", "event_type"]
OPTIONAL_FIELDS = ["props"]


def coerce_record(obj):
    if not isinstance(obj, dict):
        raise ValueError("Expected a JSON object")

    # validate event_type
    et = obj.get("event_type")
    if not isinstance(et, str) or not et.strip():
        raise ValueError("event_type must be a non-empty string")
    et = et.strip()
    # validate user_id
    uid = None
    if "user_id" not in obj or not obj["user_id"]:
        raise ValueError("user_id must be a non-empty string")
    uid = str(obj["user_id"])
    # validate props
    props = obj.get("props") or {}
    if not isinstance(props, dict):
        raise ValueError("props must be an object (if provided)")

    # unknown top-level keys are merged into props
    known = set(REQUIRED_FIELDS + OPTIONAL_FIELDS)
    extras = {k: v for k, v in obj.items() if k not in known}
    merged_props = {**extras, **props}

    return {"event_type": et.strip(), "user_id": uid, "props": merged_props}


class JSONSocketServer:
    def __init__(self, pool):
        self.pool = pool
        self.server = None
        self._shutdown = asyncio.Event()

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info("peername")
        peer_ip = peer[0] if isinstance(peer, tuple) and len(peer) >= 1 else None

        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    print(f"[>] Got: {line}")
                    obj = json.loads(line)
                    rec = coerce_record(obj)
                except Exception as e:
                    writer.write(f"ERROR: {e}\0".encode())
                    await writer.drain()
                    continue

                try:
                    async with self.pool.connection() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute(
                                """
                                INSERT INTO wiretaps (event_type, user_id, source_ip, props)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (rec["event_type"], rec["user_id"], peer_ip, Json(rec["props"])),
                            )
                    writer.write(b"OK\0")
                    await writer.drain()
                except Exception as e:
                    writer.write(f"ERROR: {e}\0".encode())
                    await writer.drain()
        except asyncio.CancelledError:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, WATERGATE_HOST, WATERGATE_PORT)
        sockets = ", ".join(str(s.getsockname()) for s in (self.server.sockets or []))
        print(f"@('_')@ listening on {sockets}")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown.set)

        async with self.server:
            await self._shutdown.wait()
            self.server.close()
            await self.server.wait_closed()


async def main():
    # psycopg3 async pool
    pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=5, timeout=10, open=False)
    await pool.open()
    try:
        server = JSONSocketServer(pool)
        await server.start()
    finally:
        await pool.close()


def run_migrations():
    with open("migrations.sql", "rt") as f:
        migrations = f.read()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(migrations)
            conn.commit()


if __name__ == "__main__":
    run_migrations()
    asyncio.run(main())
