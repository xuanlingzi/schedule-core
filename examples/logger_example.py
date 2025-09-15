"""
日志按日期切分示例
"""

import time
from schedule_core.utils.logger import get_logger
from schedule_core.config.settings import core_settings

# 修改配置以测试不同的日志切分方式
# 按天切分
core_settings.LOG_ROTATE_BY_TIME = True
core_settings.LOG_ROTATE_INTERVAL = 'D'  # D=天, H=小时, M=分钟, S=秒
core_settings.LOG_ROTATE_SUFFIX = "%Y-%m-%d"  # 文件后缀格式
core_settings.LOG_BACKUP_COUNT = 30  # 保留30个备份

# 获取日志记录器
logger = get_logger("example_logger", "example.log")

# 写入一些日志
logger.info("这是一条信息日志")
logger.warning("这是一条警告日志")
logger.error("这是一条错误日志")

print("日志已写入到文件。检查 schedule_core/example.log")
print("要测试日志切分，可以将 LOG_ROTATE_INTERVAL 设置为 'S'（秒）并运行此脚本多次")
