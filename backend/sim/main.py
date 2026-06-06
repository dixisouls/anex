"""Run simulation loops outside the API process (preferred for heavy load)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from backend.config import API_URL, SIM_CADENCE_S, SIM_INVESTORS, SIM_POSTERS
from backend.sim import runner as sim_runner

logger = logging.getLogger(__name__)


async def _run(args: argparse.Namespace) -> None:
    await sim_runner.start(
        args.api_url,
        n_posters=args.posters,
        n_investors=args.investors,
        cadence_s=args.cadence_s,
    )
    logger.info(
        "sim running posters=%s investors=%s cadence_s=%s api=%s",
        args.posters if args.posters is not None else SIM_POSTERS,
        args.investors if args.investors is not None else SIM_INVESTORS,
        args.cadence_s if args.cadence_s is not None else SIM_CADENCE_S,
        args.api_url,
    )
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await sim_runner.stop()
    logger.info("sim stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Agent Bazaar external sim runner")
    parser.add_argument("--api-url", default=API_URL, help="API base URL")
    parser.add_argument("--posters", type=int, default=None, help="Number of poster sim users")
    parser.add_argument("--investors", type=int, default=None, help="Number of investor sim users")
    parser.add_argument(
        "--cadence-s",
        type=float,
        default=None,
        dest="cadence_s",
        help="Seconds between loop iterations per sim user",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
