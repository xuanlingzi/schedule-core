"""
使用 TaskScheduler 的简单示例
"""

import asyncio
import time
from datetime import datetime

from schedule_core import TaskScheduler, logger


class SimpleTask:
    """简单任务示例"""

    def __init__(self, name):
        self.name = name

    async def execute(self):
        """执行任务"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"任务 {self.name} 在 {current_time} 执行")


async def main():
    """主函数"""
    # 创建调度器
    scheduler = TaskScheduler()

    # 添加每分钟执行一次的任务
    task1 = SimpleTask("每分钟任务")
    await scheduler.add_task(task1, cron_expression="* * * * *")

    # 添加每5秒执行一次的任务（无cron表达式的情况）
    task2 = SimpleTask("频繁任务")
    await scheduler.add_task(task2, allow_concurrent=True)

    # 启动调度器
    logger.info("启动任务调度器...")

    # 在后台运行调度器
    scheduler_task = asyncio.create_task(scheduler.start())

    try:
        # 运行5分钟后停止
        await asyncio.sleep(300)
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止调度器...")
    finally:
        # 停止调度器
        await scheduler.stop()
        # 等待调度器任务完成
        await scheduler_task
        logger.info("调度器已停止")


if __name__ == "__main__":
    asyncio.run(main())
