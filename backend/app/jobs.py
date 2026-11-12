"""Durable background jobs, stored in Postgres.

Why Postgres and not Redis/Celery: the app already depends on it, and a job row is written in the
same transaction as the work it describes (the uploaded file, the queued answer), so a request can
never commit its data but lose its job, or the other way round.

Lifecycle of a job row:

    queued --claim--> running --ok--> done
       ^                 |
       |                 +--temporary failure, attempts left--> queued (run_after = now + backoff)
       |                 +--file must wait for an earlier one-> queued (attempt not counted)
       |                 +--permanent failure / out of attempts--> failed
       +--- heartbeat lost (worker crashed or was killed) ----+  (re-queued, or failed if out of attempts)

- Claiming uses SELECT ... FOR UPDATE SKIP LOCKED, so any number of worker threads and processes
  can share the queue without taking the same job twice.
- While a job runs, a heartbeat thread refreshes heartbeat_at. A job whose heartbeat is older than
  RFP_JOB_LEASE_S is taken back by `reap()` and retried, so a crash or deploy loses nothing.
- What a job does to the customer's data (marking a file "failed", say) is the handler's business,
  in app.pipeline; this module only schedules and records.
"""

import logging
import os
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .config import settings
from .db import worker_session
from .llm import LLMError
from .models import Job

log = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


class Defer(Exception):
    """Raised by a handler that cannot run yet (e.g. an addendum waiting for its base file).
    The job goes back to the queue without using up an attempt."""

    def __init__(self, seconds: float = 5):
        super().__init__(f"deferred for {seconds}s")
        self.seconds = seconds


def is_temporary(e: BaseException) -> bool:
    """Failures worth retrying later: AI provider unreachable/overloaded, database hiccups."""
    return (isinstance(e, LLMError) and e.retryable) or isinstance(e, OperationalError)


@dataclass
class JobRun:
    """What a handler knows about the job it is running."""

    id: int
    org_id: int
    kind: str
    target_id: int
    attempt: int  # 1-based
    max_attempts: int

    def will_retry(self, e: BaseException) -> bool:
        return is_temporary(e) and self.attempt < self.max_attempts

    def retry_delay(self) -> float:
        return settings.job_retry_base_s * 4 ** (self.attempt - 1)


@dataclass
class Handler:
    run: Callable[[int, int, JobRun], None]  # (org_id, target_id, job)
    # Called when the job is given up after its worker vanished, so the customer's row
    # does not stay "processing" forever: (org_id, target_id, message).
    abandon: Callable[[int, int, str], None]


HANDLERS: dict[str, Handler] = {}  # filled by app.pipeline (register())


def register(kind: str, run, abandon) -> None:
    HANDLERS[kind] = Handler(run, abandon)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- enqueue (inside the caller's transaction)


def enqueue(s: Session, org_id: int, kind: str, target_id: int) -> None:
    """Add a job in the caller's transaction (commits with it). A job for the same target that
    is already queued or running is not duplicated."""
    s.execute(
        insert(Job)
        .values(org_id=org_id, kind=kind, target_id=target_id, status="queued", attempts=0,
                max_attempts=settings.job_max_attempts, run_after=_now(), created_at=_now())
        .on_conflict_do_nothing(index_elements=["kind", "target_id"],
                                index_where=text("status IN ('queued', 'running')"))
    )


# ---------------------------------------------------------------- claim / finish


_CLAIM = text("""
    UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_by = :worker,
                    heartbeat_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = 'queued' AND run_after <= now() + make_interval(secs => :ahead)
        ORDER BY run_after, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, org_id, kind, target_id, attempts, max_attempts
""")


def claim(worker: str = WORKER_ID, ahead_s: float = 0) -> JobRun | None:
    with worker_session() as s:
        row = s.execute(_CLAIM, {"worker": worker, "ahead": ahead_s}).first()
        s.commit()
    return JobRun(*row) if row else None


def _finish(job: JobRun, status: str, error: str | None = None, delay: float = 0, uncount: bool = False) -> None:
    with worker_session() as s:
        j = s.get(Job, job.id)
        if j is None:
            return
        j.status = status
        j.last_error = error[:2000] if error else j.last_error
        j.locked_by = None
        if status == "queued":
            j.run_after = _now() + timedelta(seconds=delay)
            if uncount:
                j.attempts -= 1
        else:
            j.finished_at = _now()
        s.commit()


def _heartbeat(job_id: int, stop: threading.Event) -> None:
    every = max(settings.job_lease_s / 4, 0.05)
    while not stop.wait(every):
        try:
            with worker_session() as s:
                s.execute(text("UPDATE jobs SET heartbeat_at = now() WHERE id = :id AND status = 'running'"),
                          {"id": job_id})
                s.commit()
        except Exception:  # noqa: BLE001 - a missed beat is not fatal; the lease is 4 beats long
            log.warning("heartbeat failed for job %s", job_id, exc_info=True)


def run(job: JobRun) -> str:
    """Run one claimed job to completion; returns its new status."""
    handler = HANDLERS.get(job.kind)
    if handler is None:
        _finish(job, "failed", f"Unknown job kind {job.kind!r}")
        return "failed"
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(job.id, stop), daemon=True, name=f"heartbeat-{job.id}")
    beat.start()
    try:
        handler.run(job.org_id, job.target_id, job)
    except Defer as d:
        _finish(job, "queued", None, delay=d.seconds, uncount=True)
        return "deferred"
    except Exception as e:  # noqa: BLE001 - every failure is recorded on the job
        if job.will_retry(e):
            log.warning("job %s (%s) failed on attempt %d, retrying: %s", job.id, job.kind, job.attempt, e)
            _finish(job, "queued", str(e), delay=job.retry_delay())
            return "retrying"
        log.error("job %s (%s) failed: %s", job.id, job.kind, e, exc_info=not isinstance(e, LLMError))
        _finish(job, "failed", str(e))
        return "failed"
    finally:
        stop.set()
    _finish(job, "done")
    return "done"


# ---------------------------------------------------------------- crash recovery


_REAP = text("""
    UPDATE jobs SET
        status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
        finished_at = CASE WHEN attempts >= max_attempts THEN now() END,
        locked_by = NULL, run_after = now(),
        last_error = 'The worker running this job stopped (restart or crash).'
    WHERE status = 'running' AND heartbeat_at < now() - make_interval(secs => :lease)
    RETURNING id, org_id, kind, target_id, status
""")


def reap() -> int:
    """Take back jobs whose worker stopped sending heartbeats. Returns how many."""
    with worker_session() as s:
        rows = s.execute(_REAP, {"lease": settings.job_lease_s}).all()
        s.commit()
    for job_id, org_id, kind, target_id, status in rows:
        log.warning("job %s (%s) lost its worker; %s", job_id, kind, "re-queued" if status == "queued" else "gave up")
        if status == "failed" and kind in HANDLERS:
            try:
                HANDLERS[kind].abandon(org_id, target_id,
                                       "Processing stopped repeatedly (server restarts or crashes). Please try again.")
            except Exception:  # noqa: BLE001
                log.exception("could not mark job %s's target as failed", job_id)
    return len(rows)


# ---------------------------------------------------------------- running


def run_until_idle(max_jobs: int = 1000, ahead_s: float = 0) -> int:
    """Run queued jobs in this thread until none is due (used by tests and `--once`).
    `ahead_s` also runs jobs scheduled up to that many seconds in the future (retries)."""
    reap()
    n = 0
    while n < max_jobs and (job := claim(ahead_s=ahead_s)):
        run(job)
        n += 1
    return n


class Worker:
    """`threads` loops that claim and run jobs until `stop()`; one of them also reaps lost jobs."""

    def __init__(self, threads: int | None = None):
        self.n = max(1, threads or settings.worker_threads)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> "Worker":
        for i in range(self.n):
            t = threading.Thread(target=self._loop, args=(i,), daemon=True, name=f"rfp-worker-{i}")
            t.start()
            self._threads.append(t)
        log.info("job worker %s started with %d thread(s)", WORKER_ID, self.n)
        return self

    def stop(self, wait_s: float | None = None) -> None:
        """Stop claiming new jobs; wait up to `wait_s` for running ones (None = until done)."""
        self._stop.set()
        for t in self._threads:
            t.join(wait_s)

    def _loop(self, index: int) -> None:
        last_reap = 0.0
        while not self._stop.is_set():
            try:
                if index == 0 and (now := _now().timestamp()) - last_reap > settings.job_lease_s / 2:
                    reap()
                    last_reap = now
                job = claim()
                if job is None:
                    self._stop.wait(settings.job_poll_s)
                    continue
                run(job)
            except Exception:  # noqa: BLE001 - e.g. database briefly unavailable: keep the worker alive
                log.exception("worker loop error")
                self._stop.wait(5)
