"""Cron 调度器，用于异步和周期性任务。

支持：
- 一次性延迟任务
- 周期性任务（类 cron 调度）
- 后台任务执行

任务在此注册并在网关内异步执行。
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
    """一个计划性或周期性任务。"""

    job_id: str
    agent_name: str
    content: str
    interval_seconds: int = 0  # 0 = 一次性
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
    """简单的进程内 Cron 作业调度器。

    使用 asyncio 事件循环进行计时。作业持久化到
    data/cron/jobs.json。
    """

    def __init__(self):
        CRON_DIR.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, CronJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._task_callback: Optional[Callable[[str, str], Coroutine]] = None

    def set_task_callback(self, cb: Callable[[str, str], Coroutine]):
        """设置 Cron 作业触发时要执行的回调。
        调用参数为 (agent_name, content)。
        """
        self._task_callback = cb

    # ── 作业持久化 ────────────────────────────────────────────────

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

    # ── 作业管理 ─────────────────────────────────────────────────

    def add_job(
        self,
        agent_name: str,
        content: str,
        interval_seconds: int = 0,
        job_id: Optional[str] = None,
    ) -> str:
        """添加一个 Cron 作业。返回 job_id。"""
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
        """移除一个 Cron 作业。未找到则返回 False。"""
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

    # ── 调度器循环 ─────────────────────────────────────────────────

    async def start(self):
        """启动调度器循环。"""
        self._load_jobs()
        self._running = True
        logger.info("Scheduler started")

        while self._running:
            now = asyncio.get_event_loop().time()

            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if job.next_run and job.next_run <= now:
                    # 触发作业
                    logger.info(f"Firing cron job {job.job_id} → {job.agent_name}")
                    if self._task_callback:
                        try:
                            await self._task_callback(job.agent_name, job.content)
                        except Exception:
                            logger.exception(f"Cron job {job.job_id} failed")

                    # 为周期性作业重新调度
                    if job.interval_seconds > 0:
                        job.next_run = now + job.interval_seconds
                    else:
                        # 一次性作业：触发后禁用
                        job.enabled = False
                    self._save_jobs()

            await asyncio.sleep(1)

    async def stop(self):
        """停止调度器。"""
        self._running = False
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        logger.info("Scheduler stopped")


# 单例
scheduler = Scheduler()
