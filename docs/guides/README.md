# 使用指南

## 快速入门

### 安装

```bash
pip install schedule-core
```

### 基本使用

1. 创建任务调度器：

```python
from schedule_core import TaskScheduler

scheduler = TaskScheduler()
```

2. 定义任务：

```python
async def my_task():
    print("执行任务...")
```

3. 添加任务到调度器：

```python
await scheduler.add_task(my_task, cron_expression="*/5 * * * *")
```

4. 启动调度器：

```python
await scheduler.start()
```

## 配置

### 环境变量

创建 `.env` 文件并设置以下配置：

```env
# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/dbname

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# RabbitMQ配置
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# 日志配置
LOG_LEVEL=INFO
LOG_DIR=logs
```

## 最佳实践

### 1. 任务定义

- 使用异步函数定义任务
- 添加适当的错误处理
- 记录任务执行日志

```python
from schedule_core import logger

async def my_task():
    try:
        logger.info("开始执行任务...")
        # 任务逻辑
        logger.info("任务执行完成")
    except Exception as e:
        logger.error(f"任务执行失败: {str(e)}")
        raise
```

### 2. 数据库操作

- 使用上下文管理器处理数据库会话
- 正确处理事务

```python
from schedule_core import get_db

async def process_data():
    db = next(get_db())
    try:
        # 数据库操作
        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
```

### 3. 缓存使用

- 设置适当的过期时间
- 使用有意义的键名

```python
from schedule_core import cache

# 设置缓存，1小时过期
cache.set("user:1", user_data, ex=3600)

# 获取缓存
user_data = cache.get("user:1")
```

### 4. 消息队列

- 使用上下文管理器
- 正确处理消息确认

```python
from schedule_core import RabbitMQClient

async def publish_message():
    with RabbitMQClient() as client:
        await client.publish_message(
            exchange_name="events",
            exchange_type="topic",
            routing_key="user.created",
            message={"user_id": 1}
        )
```

## 常见问题

### 1. 任务不执行

- 检查 cron 表达式是否正确
- 确认调度器是否已启动
- 查看日志文件中的错误信息

### 2. 数据库连接问题

- 验证数据库配置是否正确
- 检查数据库服务是否运行
- 确认网络连接是否正常

### 3. 缓存问题

- 确认 Redis 服务是否运行
- 检查缓存键是否正确
- 验证缓存配置是否正确

### 4. 消息队列问题

- 检查 RabbitMQ 服务是否运行
- 验证连接参数是否正确
- 确认交换机是否存在
