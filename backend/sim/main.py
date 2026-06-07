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
    use_cohorts = False if args.legacy else None
    await sim_runner.start(
        args.api_url,
        n_posters=args.posters,
        n_investors=args.investors,
        cadence_s=args.cadence_s,
        use_cohorts=use_cohorts,
    )
    from backend.sim import cohorts as sim_cohorts

    if use_cohorts is False:
        investor_note = (
            f"legacy investors={args.investors if args.investors is not None else SIM_INVESTORS}"
        )
    else:
        n = sim_cohorts.total_investor_count(sim_cohorts.default_cohorts())
        investor_note = f"cohort investors={n}"
    logger.info(
        "sim running posters=%s %s poster_cadence_s=%s api=%s",
        args.posters if args.posters is not None else SIM_POSTERS,
        investor_note,
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
        help="Seconds between poster loop iterations (investors use cohort cadences when enabled)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Disable role cohorts; use SIM_INVESTORS + SIM_INVESTOR_MODE for all investors",
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
