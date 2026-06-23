"""Cron scheduler for asynchronous and recurring tasks.

Supports:
- One-shot delayed tasks
- Recurring tasks (cron-like scheduling)
- Background task execution

Tasks are registered here and executed asynchronously within the gateway.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Coroutine, Optional

from ..manager.agent_manager import agent_manager

logger = logging.getLogger(__name__)

DATA_DIR = agent_manager.data_dir
CRON_DIR = DATA_DIR / "cron"


@dataclass
class CronJob:
    """A scheduled or recurring task."""

    job_id: str
    agent_name: str
    content: str
    interval_seconds: int = 0  # 0 = one-shot
    next_run: float = 0.0
    created_at: str = ""
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "agent_name": self.agent_name,
            "content": self.content,
            "interval_seconds": self.interval_seconds,
            "next_run": self.next_run,
            "created_at": self.created_at,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        return cls(
            job_id=data["job_id"],
            agent_name=data["agent_name"],
            content=data["content"],
            interval_seconds=data.get("interval_seconds", 0),
            next_run=data.get("next_run", 0),
            created_at=data.get("created_at", ""),
            enabled=data.get("enabled", True),
        )


class Scheduler:
    """Simple in-process scheduler for cron jobs.

    Uses asyncio event loop for timing. Jobs are persisted to
    data/cron/jobs.json.
    """

    def __init__(self):
        CRON_DIR.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, CronJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._task_callback: Optional[Callable[[str, str], Coroutine]] = None

    def set_task_callback(self, cb: Callable[[str, str], Coroutine]):
        """Set the callback to execute when a cron job fires.
        Called with (agent_name, content).
        """
        self._task_callback = cb

    # ── Job persistence ────────────────────────────────────────────

    def _jobs_path(self) -> Path:
        return CRON_DIR / "jobs.json"

    def _save_jobs(self):
        jobs_data = [j.to_dict() for j in self._jobs.values()]
        self._jobs_path().write_text(json.dumps(jobs_data, indent=2, ensure_ascii=False))

    def _load_jobs(self):
        path = self._jobs_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for item in data:
                    job = CronJob.from_dict(item)
                    if job.enabled:
                        self._jobs[job.job_id] = job
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Invalid cron jobs file: {e}")

    # ── Job management ─────────────────────────────────────────────

    def add_job(
        self,
        agent_name: str,
        content: str,
        interval_seconds: int = 0,
        job_id: Optional[str] = None,
    ) -> str:
        """Add a cron job. Returns the job_id."""
        import uuid

        job_id = job_id or f"cron_{uuid.uuid4().hex[:12]}"

        now = asyncio.get_event_loop().time()
        job = CronJob(
            job_id=job_id,
            agent_name=agent_name,
            content=content,
            interval_seconds=interval_seconds,
            next_run=now + (interval_seconds or 0),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._jobs[job_id] = job
        self._save_jobs()

        logger.info(f"Added cron job {job_id}: {agent_name} every {interval_seconds}s")
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a cron job. Returns False if not found."""
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        self._save_jobs()

        task = self._tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()

        logger.info(f"Removed cron job {job_id}")
        return True

    def list_jobs(self) -> list[CronJob]:
        return list(self._jobs.values())

    # ── Scheduler loop ─────────────────────────────────────────────

    async def start(self):
        """Start the scheduler loop."""
        self._load_jobs()
        self._running = True
        logger.info("Scheduler started")

        while self._running:
            now = asyncio.get_event_loop().time()

            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if job.next_run and job.next_run <= now:
                    # Fire the job
                    logger.info(f"Firing cron job {job.job_id} → {job.agent_name}")
                    if self._task_callback:
                        try:
                            await self._task_callback(job.agent_name, job.content)
                        except Exception:
                            logger.exception(f"Cron job {job.job_id} failed")

                    # Reschedule recurring jobs
                    if job.interval_seconds > 0:
                        job.next_run = now + job.interval_seconds
                    else:
                        # One-shot: disable after firing
                        job.enabled = False
                    self._save_jobs()

            await asyncio.sleep(1)

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        logger.info("Scheduler stopped")


# Singleton
scheduler = Scheduler()
