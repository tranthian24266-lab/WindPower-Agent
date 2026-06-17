from __future__ import annotations

import signal
from threading import Event

from app.core.settings import load_settings
from app.jobs.worker_runtime import AgentWorker


def main() -> None:
    settings = load_settings()
    worker = AgentWorker(settings, worker_id="standalone")
    stop_event = Event()

    def _handle_signal(signum, frame) -> None:  # type: ignore[no-untyped-def]
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not stop_event.is_set():
        processed = worker.process_next_job()
        if not processed:
            stop_event.wait(max(settings.worker_poll_interval_ms, 100) / 1000.0)


if __name__ == "__main__":
    main()
