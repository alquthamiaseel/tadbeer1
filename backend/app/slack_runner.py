"""Entry point for the Slack listener: `python -m app.slack_runner`.

A separate process from the API on purpose. The listener holds a long-lived
WebSocket, and running it under uvicorn's autoreloader would reconnect on every
file save. Keeping them apart also means a Slack outage cannot take the
dashboard down with it.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.integrations.slack import start_socket_mode

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)


def main() -> None:
    try:
        asyncio.run(start_socket_mode())
    except KeyboardInterrupt:
        logging.getLogger("pmfyp").info("Slack listener stopped")


if __name__ == "__main__":
    main()
