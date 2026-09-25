"""Wait until the MuseScore bridge plugin answers a WebSocket ping.

Used by ``musescore-headless.sh start``. An open port is not proof that the
plugin is up, so this sends the bridge's ``ping`` command and waits for
``pong``. Exits 0 once the bridge answers, 1 on timeout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 2.0
ROUND_TRIP_TIMEOUT_SECONDS = 2.0
PING_COMMAND: dict[str, str] = {"command": "ping"}
PONG_RESULT = "pong"
# Errors that mean the bridge is not (yet) reachable, so polling continues.
UNREACHABLE_ERRORS: tuple[type[Exception], ...] = (
    OSError,
    WebSocketException,
    TimeoutError,
)

logger = logging.getLogger("wait_for_bridge")


async def ping_once(uri: str) -> bool:
    """Return True if the bridge at *uri* answers a ping with ``pong``."""
    try:
        async with websockets.connect(
            uri, open_timeout=ROUND_TRIP_TIMEOUT_SECONDS
        ) as connection:
            await connection.send(json.dumps(PING_COMMAND))
            response_raw = await asyncio.wait_for(
                connection.recv(), timeout=ROUND_TRIP_TIMEOUT_SECONDS
            )
    except UNREACHABLE_ERRORS:
        return False
    try:
        response: dict[str, Any] = json.loads(response_raw)
    except json.JSONDecodeError:
        return False
    return response.get("result") == PONG_RESULT


async def wait_for_bridge(uri: str, timeout_seconds: float) -> bool:
    """Poll *uri* until it answers a ping or *timeout_seconds* elapse."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        if await ping_once(uri):
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, wait for the bridge and return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

    uri = f"ws://{arguments.host}:{arguments.port}"
    if asyncio.run(wait_for_bridge(uri, arguments.timeout)):
        logger.info("bridge answered ping at %s", uri)
        return 0
    logger.error("no pong from %s within %.0f seconds", uri, arguments.timeout)
    return 1


if __name__ == "__main__":
    sys.exit(main())
