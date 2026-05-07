from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ProductImportJob:
    job_id: str
    status: str
    row_count: int
    processed: int = 0
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


_jobs: dict[str, ProductImportJob] = {}
_lock = asyncio.Lock()


async def create_job(*, row_count: int, created_estimate: int, updated_estimate: int) -> ProductImportJob:
    # We initialize with known estimates so the UI can show expected totals immediately.
    job_id = uuid4().hex
    job = ProductImportJob(
        job_id=job_id,
        status="queued",
        row_count=row_count,
        created=created_estimate,
        updated=updated_estimate,
    )
    async with _lock:
        _jobs[job_id] = job
    return job


async def get_job(job_id: str) -> ProductImportJob | None:
    async with _lock:
        return _jobs.get(job_id)


async def set_job_running(job_id: str) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.status = "running"
            job.created = 0
            job.updated = 0


async def add_job_progress(job_id: str, *, processed: int, created: int, updated: int) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.processed += processed
            job.created += created
            job.updated += updated


async def complete_job(job_id: str) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.status = "completed"


async def fail_job(job_id: str, error: str) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is not None:
            job.status = "failed"
            job.errors.append(error)
