"""
Unit tests for the scheduler module.
"""

import pytest
from schedule_core.core.scheduler import TaskScheduler


def test_task_scheduler_initialization():
    """Test TaskScheduler initialization."""
    scheduler = TaskScheduler()
    assert scheduler is not None
    assert isinstance(scheduler, TaskScheduler)


@pytest.mark.asyncio
async def test_task_scheduler_add_task():
    """Test adding a task to the scheduler."""
    scheduler = TaskScheduler()

    async def test_task():
        return "Task executed"

    await scheduler.add_task(test_task, cron_expression="*/5 * * * *")
    assert len(scheduler.tasks) == 1
    assert scheduler.tasks[0].func == test_task
    assert scheduler.tasks[0].cron_expression == "*/5 * * * *"
