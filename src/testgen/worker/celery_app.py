"""Celery application: background processing for slow LLM generation jobs
(DESIGN.md §7). Module-level construction is Celery's own convention (`celery
-A testgen.worker.celery_app worker` finds this object) -- one deliberate
exception to this codebase's usual lazy-settings pattern.
"""

from celery import Celery

from testgen.platform.config import get_settings

_settings = get_settings()

celery_app = Celery("testgen", broker=_settings.redis_url, backend=_settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
