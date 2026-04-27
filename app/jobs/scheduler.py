from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api.v1.outreach.reviews import monitor_and_respond
from app.core.logging import get_logger

log = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


async def _safe_review_monitor() -> None:
    try:
        res = await monitor_and_respond()
        log.info("scheduled_review_monitor_done", scanned=res.clients_scanned, responded=res.reviews_responded)
    except Exception as e:
        log.warning("scheduled_review_monitor_failed", err=str(e))


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _safe_review_monitor,
        trigger=IntervalTrigger(hours=4),
        id="review_monitor",
        replace_existing=True,
    )
    _scheduler.start()
    log.info("scheduler_started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler_stopped")
