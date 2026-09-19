"""QC queue: enqueue + dequeue using Redis (arq-style) with an in-process fallback.

In production this is arq over Redis. For local dev without Redis, we enqueue
to an in-process asyncio.Queue and a co-located worker loop. Either way the
caller just calls await enqueue_qc(voice_note_id).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

import redis as redis_lib

from ..config import settings

logger = logging.getLogger("carib.qc.queue")

_redis = None
_inproc_queue: "asyncio.Queue[str]" = asyncio.Queue()
_inproc_task: Optional[asyncio.Task] = None


def _client():
    global _redis
    if _redis is not None:
        return _redis if _redis is not False else None
    try:
        c = redis_lib.from_url(settings.redis_url, decode_responses=True)
        c.ping()
        _redis = c
        return c
    except Exception:
        _redis = False  # type: ignore[assignment]
        return None


QUEUE_NAME = "carib:qc"


async def enqueue_qc(voice_note_id: str) -> None:
    client = _client()
    if client is not None:
        client.rpush(QUEUE_NAME, voice_note_id)
        logger.info("enqueued qc (redis) for note %s", voice_note_id)
        return
    # in-process fallback
    await _inproc_queue.put(voice_note_id)
    _ensure_inproc_worker()
    logger.info("enqueued qc (inproc) for note %s", voice_note_id)


async def dequeue_qc(timeout: float = 5.0) -> Optional[str]:
    client = _client()
    if client is not None:
        item = client.blpop(QUEUE_NAME, timeout=int(timeout))
        if item is None:
            return None
        _, vid = item
        return vid
    try:
        return await asyncio.wait_for(_inproc_queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def _ensure_inproc_worker() -> None:
    """When running under the FastAPI process (dev), start a background worker."""
    global _inproc_task
    if _inproc_task is not None and not _inproc_task.done():
        return
    if os.environ.get("CARIB_DISABLE_INPROC_QC") == "1":
        return

    async def _loop():
        from .qc import run_qc_for_note
        while True:
            vid = await _inproc_queue.get()
            try:
                await run_qc_for_note(vid)
            except Exception:
                logger.exception("inproc qc failed for %s", vid)

    _inproc_task = asyncio.create_task(_loop())

