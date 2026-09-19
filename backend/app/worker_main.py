"""Standalone QC worker entrypoint: `python -m app.worker_main`.

Polls the Redis QC queue (or an in-process fallback) and runs the QC pipeline
for each voice note id. Run this alongside the FastAPI backend in production;
in local dev the FastAPI process also spins up an in-process worker.
"""
from __future__ import annotations

import asyncio
import logging
import os

from .config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("carib.worker")


async def main() -> None:
    from .workers.qc_queue import dequeue_qc
    from .workers.qc import run_qc_for_note
    log.info("QC worker started (redis_url=%s)", settings.redis_url)
    while True:
        try:
            vid = await dequeue_qc(timeout=5.0)
            if vid is None:
                continue
            log.info("dequeued qc for note %s", vid)
            await run_qc_for_note(vid)
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("worker iteration failed")


if __name__ == "__main__":
    # In standalone mode we don't want the FastAPI in-process worker to also run.
    os.environ.setdefault("CARIB_DISABLE_INPROC_QC", "1")
    asyncio.run(main())

