import redis
from schedule_core.config.settings import core_settings as settings

# 创建Redis连接
cache = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True,
)
