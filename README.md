# Schedule Core

一个用于 Python 应用程序的核心调度库，提供任务调度、数据库操作、缓存管理等功能。

## 特性

- 基于 SQLAlchemy 的数据库操作
- Redis 缓存支持
- 基于 croniter 的任务调度
- RabbitMQ 消息队列集成
- 配置管理
- 日志系统

## 安装

```bash
pip install schedule-core
```

## 快速开始

```python
from schedule_core import TaskScheduler, logger

# 创建调度器
scheduler = TaskScheduler()

# 添加任务
@scheduler.task(cron="*/5 * * * *")
async def my_task():
    logger.info("执行任务...")

# 启动调度器
scheduler.start()
```

## 开发

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/schedule-core.git
cd schedule-core
```

2. 创建虚拟环境：

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装开发依赖：

```bash
pip install -e ".[dev]"
```

4. 运行测试：

```bash
pytest
```

## 文档

- [API 文档](docs/api/README.md)
- [使用指南](docs/guides/README.md)
- [示例代码](examples/README.md)

## 许可证

MIT License
