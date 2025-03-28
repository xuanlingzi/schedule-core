# API 文档

## 核心模块

### TaskScheduler

任务调度器，用于管理和执行定时任务。

```python
from schedule_core import TaskScheduler

scheduler = TaskScheduler()
await scheduler.add_task(my_task, cron_expression="*/5 * * * *")
await scheduler.start()
```

#### 方法

- `add_task(func, cron_expression)`: 添加定时任务
- `start()`: 启动调度器
- `stop()`: 停止调度器

### Database

数据库操作模块，提供数据库连接和会话管理。

```python
from schedule_core import get_db, Base

# 获取数据库会话
db = next(get_db())
```

### Cache

缓存模块，提供 Redis 缓存操作。

```python
from schedule_core import cache

# 设置缓存
cache.set("key", "value")
# 获取缓存
value = cache.get("key")
```

### RabbitMQ

消息队列模块，提供 RabbitMQ 操作。

```python
from schedule_core import RabbitMQClient

with RabbitMQClient() as client:
    client.publish_message(
        exchange_name="my_exchange",
        exchange_type="topic",
        routing_key="my.routing.key",
        message={"data": "value"}
    )
```

## 配置

### Settings

配置管理模块，用于管理应用程序配置。

```python
from schedule_core import core_settings

# 访问配置
database_url = core_settings.DATABASE_URL
redis_host = core_settings.REDIS_HOST
```
