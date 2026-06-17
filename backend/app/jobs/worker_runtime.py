from __future__ import annotations

import logging
from threading import Event, Thread
from time import sleep
from uuid import uuid4

from app.core.agent_runtime.run_manager import RunManager
from app.core.settings import Settings
from app.jobs.task_handlers import execute_job


LOGGER = logging.getLogger(__name__)


class AgentWorker:
    def __init__(self, settings: Settings, *, worker_id: str | None = None):
        self.settings = settings
        self.run_manager = RunManager(settings.database_path)
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(target=self.run_forever, name=f"agent-worker-{self.worker_id}", daemon=True)
        self._thread.start()

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_seconds)

    def run_forever(self) -> None:
        poll_seconds = max(self.settings.worker_poll_interval_ms, 100) / 1000.0
        while not self._stop_event.is_set():
            processed = self.process_next_job()
            if processed:
                continue
            self._stop_event.wait(poll_seconds)

    def process_next_job(self) -> bool:
        self.run_manager.fail_stale_jobs(stale_timeout_seconds=self.settings.worker_stale_timeout_seconds)
        job = self.run_manager.claim_next_job(
            worker_id=self.worker_id,
            lease_seconds=self.settings.worker_lease_seconds,
        )
        if job is None:
            return False

        run_id = str(job["run_id"])
        job_type = str(job["job_type"])
        payload = job.get("payload") or {}
        try:
            execute_job(self.settings, self.run_manager, job_type, run_id, payload)
            self.run_manager.complete_job(str(job["job_id"]))
            LOGGER.info("Agent worker completed job %s for run %s", job["job_id"], run_id)
        except Exception as exc:
            error_payload = {"type": exc.__class__.__name__, "message": str(exc)}
            self.run_manager.fail_job(str(job["job_id"]), error_payload=error_payload)
            self.run_manager.fail_run(run_id, error_payload=error_payload, current_step=job_type)
            LOGGER.exception("Agent worker failed job %s for run %s", job["job_id"], run_id)
        return True
