from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subtitle import SubtitleRecord, ExtractionJob
from src.core.time_utils import utc_now


class SubtitleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_subtitle_record(
        self, video_id: str, language: str
    ) -> Optional[SubtitleRecord]:
        q = select(SubtitleRecord).where(
            SubtitleRecord.video_id == video_id, SubtitleRecord.language == language
        )
        res = await self.session.execute(q)
        return res.scalar_one_or_none()

    async def upsert_subtitle_record(
        self,
        *,
        video_id: str,
        language: str,
        title: Optional[str],
        subtitles: list,
        plain_text: str,
        extraction_method: str,
        extraction_duration_ms: int,
        proxy_used: Optional[str],
        ttl_days: int = 30,
    ) -> SubtitleRecord:
        existing = await self.get_subtitle_record(video_id, language)
        expires_at = utc_now() + timedelta(days=ttl_days)
        if existing:
            existing.title = title
            existing.subtitles = subtitles
            existing.plain_text = plain_text
            existing.extraction_method = extraction_method
            existing.extraction_duration_ms = extraction_duration_ms
            existing.extraction_status = "success"
            existing.extraction_error = None
            existing.proxy_used = proxy_used
            existing.expires_at = expires_at
            rec = existing
        else:
            rec = SubtitleRecord(
                video_id=video_id,
                language=language,
                title=title,
                subtitles=subtitles,
                plain_text=plain_text,
                extraction_method=extraction_method,
                extraction_duration_ms=extraction_duration_ms,
                extraction_status="success",
                proxy_used=proxy_used,
                expires_at=expires_at,
            )
            self.session.add(rec)

        await self.session.commit()
        await self.session.refresh(rec)
        return rec

    async def mark_subtitle_failed(
        self,
        *,
        video_id: str,
        language: str,
        extraction_method: str,
        error: str,
    ) -> None:
        existing = await self.get_subtitle_record(video_id, language)
        if existing:
            existing.extraction_status = "failed"
            existing.extraction_method = extraction_method
            existing.extraction_error = error[:500]
        else:
            rec = SubtitleRecord(
                video_id=video_id,
                language=language,
                extraction_method=extraction_method,
                extraction_status="failed",
                extraction_error=error[:500],
            )
            self.session.add(rec)
        await self.session.commit()

    async def get_pending_job(
        self, video_id: str, language: str
    ) -> Optional[ExtractionJob]:
        q = (
            select(ExtractionJob)
            .where(
                ExtractionJob.video_id == video_id,
                ExtractionJob.language == language,
                ExtractionJob.job_status.in_(["queued", "processing"]),
            )
            .order_by(ExtractionJob.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(q)
        return res.scalar_one_or_none()

    async def create_job(
        self,
        *,
        video_id: str,
        language: str,
        job_id: str,
        webhook_url: Optional[str] = None,
    ) -> ExtractionJob:
        job = ExtractionJob(
            video_id=video_id,
            language=language,
            job_id=job_id,
            job_status="queued",
            webhook_url=webhook_url,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_job_by_id(self, job_id: str) -> Optional[ExtractionJob]:
        """Get a job by its RQ job ID."""
        q = select(ExtractionJob).where(ExtractionJob.job_id == job_id)
        res = await self.session.execute(q)
        return res.scalar_one_or_none()

    async def update_job_status(
        self,
        *,
        job_id: str,
        status: str,
        result_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        q = select(ExtractionJob).where(ExtractionJob.job_id == job_id)
        res = await self.session.execute(q)
        job = res.scalar_one_or_none()
        if not job:
            return

        job.job_status = status
        if status == "processing" and not job.started_at:
            job.started_at = utc_now()
        if status in ["completed", "failed", "timeout"]:
            job.completed_at = utc_now()
            if job.started_at:
                job.duration_seconds = (
                    job.completed_at - job.started_at
                ).total_seconds()
        if result_data is not None:
            job.result_data = result_data
        if error_message is not None:
            job.error_message = error_message[:500]
        await self.session.commit()

    async def update_webhook_delivery(
        self,
        *,
        job_id: str,
        delivered: bool,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Update webhook delivery status for a job."""
        q = select(ExtractionJob).where(ExtractionJob.job_id == job_id)
        res = await self.session.execute(q)
        job = res.scalar_one_or_none()
        if not job:
            return

        job.webhook_delivered = delivered
        job.webhook_delivery_status = status
        if error is not None:
            job.webhook_delivery_error = error[:500]
        await self.session.commit()

    async def get_pending_webhook_jobs(self, limit: int = 100) -> list[ExtractionJob]:
        """Get jobs with pending webhooks that need delivery."""
        q = (
            select(ExtractionJob)
            .where(
                ExtractionJob.webhook_url.isnot(None),
                ExtractionJob.webhook_delivered.is_(False),
                ExtractionJob.job_status.in_(["completed", "failed"]),
            )
            .order_by(ExtractionJob.completed_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(q)
        return list(res.scalars().all())

    async def clear_cache_records(self, *, video_id: Optional[str] = None) -> int:
        if video_id:
            stmt = delete(SubtitleRecord).where(SubtitleRecord.video_id == video_id)
        else:
            stmt = delete(SubtitleRecord)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount or 0
