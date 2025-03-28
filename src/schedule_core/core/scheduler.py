"""
Task scheduler implementation for managing and executing tasks.
"""

import asyncio
from typing import List, Optional
from datetime import datetime
import croniter


class TaskScheduler:
    def __init__(self):
        self.tasks = []
        self.running = False
        self.task_schedules = {}
        self.concurrent_tasks = {}  # 存储任务的并发控制信息

    async def add_task(self, task, cron_expression=None, allow_concurrent=False):
        """Add a task to the scheduler with optional cron schedule and concurrency control."""
        self.tasks.append(task)
        self.concurrent_tasks[task] = allow_concurrent
        if cron_expression:
            self.task_schedules[task] = {
                "cron": cron_expression,
                "next_run": croniter.croniter(cron_expression, datetime.now()).get_next(
                    datetime
                ),
            }

    async def start(self):
        """Start the task scheduler."""
        self.running = True
        while self.running:
            current_time = datetime.now()
            for task in self.tasks:
                try:
                    if task in self.task_schedules:
                        schedule = self.task_schedules[task]
                        if current_time >= schedule["next_run"]:
                            if self.concurrent_tasks[task]:
                                asyncio.create_task(task.execute())
                            else:
                                await task.execute()
                            schedule["next_run"] = croniter.croniter(
                                schedule["cron"], current_time
                            ).get_next(datetime)
                    else:
                        if self.concurrent_tasks[task]:
                            asyncio.create_task(task.execute())
                        else:
                            await task.execute()
                except Exception as e:
                    print(f"Error executing task: {e}")
            await asyncio.sleep(1)  # Prevent CPU overload

    async def stop(self):
        """Stop the task scheduler."""
        self.running = False
