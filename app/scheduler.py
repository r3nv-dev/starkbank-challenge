"""Issues a batch of invoices every N hours for a limited number of cycles.

Defaults follow the challenge: 8 batches, 3h apart => runs for 24 hours.
Usage: python -m app.scheduler [--cycles 8] [--interval-hours 3]
"""
import argparse
import logging
import time

from app.config import setup_starkbank
from app.invoices import issue_random_invoices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run(cycles: int, interval_hours: float) -> None:
    setup_starkbank()
    for cycle in range(1, cycles + 1):
        logger.info("cycle %s/%s: issuing invoices", cycle, cycles)
        try:
            issue_random_invoices()
        except Exception:
            logger.exception("cycle %s failed; will retry next cycle", cycle)
        if cycle < cycles:
            time.sleep(interval_hours * 3600)
    logger.info("done: %s cycles completed", cycles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--interval-hours", type=float, default=3)
    args = parser.parse_args()
    run(cycles=args.cycles, interval_hours=args.interval_hours)
