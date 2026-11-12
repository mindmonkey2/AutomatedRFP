"""Run background jobs in a separate process.

    python -m app.worker              # run until stopped (Ctrl+C / SIGTERM waits for running jobs)
    python -m app.worker --threads 1  # one job at a time, e.g. for a single local GPU
    python -m app.worker --once       # run what is due now, then exit (cron / debugging)

Run as many worker processes as you like, on one machine or several: they share the Postgres
queue safely. Set RFP_EMBEDDED_WORKER=false on the API servers when you do.
"""

import argparse
import logging
import signal
import sys
import threading

from . import jobs, pipeline  # noqa: F401 - importing pipeline registers the job handlers
from .config import settings
from .db import check_role


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--threads", type=int, default=settings.worker_threads, help="jobs run at once")
    ap.add_argument("--once", action="store_true", help="run due jobs, then exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    check_role()

    if args.once:
        n = jobs.run_until_idle()
        logging.info("ran %d job(s)", n)
        return 0

    worker = jobs.Worker(args.threads).start()
    stopping = threading.Event()

    def on_signal(signum, _frame):
        if stopping.is_set():
            logging.warning("second signal: exiting now; running jobs will be retried by another worker")
            sys.exit(1)
        stopping.set()
        logging.info("stopping: finishing running jobs (signal again to exit at once)")

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    stopping.wait()
    worker.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
