"""Celery application: background processing for slow LLM generation jobs
(DESIGN.md §7). Module-level construction is Celery's own convention (`celery
-A testgen.worker.celery_app worker` finds this object) -- one deliberate
exception to this codebase's usual lazy-settings pattern.
"""

from celery import Celery

from testgen.platform.config import get_settings

_settings = get_settings()

# include= is what actually registers generate_test_cases_task with this app
# -- `tasks.py`'s own `@celery_app.task(...)` decorator only runs once that
# module is imported, and nothing importing just *this* module (celery_app.py)
# would otherwise ever import tasks.py. Confirmed missing live in Phase 11: a
# real `celery -A testgen.worker.celery_app worker` consuming a real enqueued
# task failed with "Received unregistered task of type
# 'testgen.generate_test_cases'" -- no test in this repo had ever started a
# real worker process to consume a real task before (test_requirements_api.py
# and test_worker_tasks.py both call run_generation_for_requirement directly
# instead, by design -- see their own docstrings).
celery_app = Celery(
    "testgen",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["testgen.worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
