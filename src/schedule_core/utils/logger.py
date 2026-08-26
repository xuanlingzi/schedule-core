"""
Logging utility for applications.
"""

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from schedule_core.config.settings import core_settings as settings


DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s"


class SizedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """按时间轮转，且单个周期内文件超过 maxBytes 时也轮转（时间/大小谁先到谁切）。

    标准库 TimedRotatingFileHandler 只看时间边界：一个 chatty 的常驻进程在同一
    小时内可以把文件写到远超 LOG_MAX_BYTES 仍不切分。这里在 shouldRollover 里
    追加一层大小判断补上这个缺口。
    """

    def __init__(self, *args, maxBytes: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxBytes = maxBytes

    def shouldRollover(self, record):
        # 时间到点
        if super().shouldRollover(record):
            return 1
        # 大小超限
        if self.maxBytes > 0:
            if self.stream is None:
                self.stream = self._open()
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0

    def rotation_filename(self, default_name: str) -> str:
        # 同一周期内因大小多次轮转会命中相同时间戳文件名，而基类 doRollover 遇到
        # 同名会直接删除旧文件造成丢日志——这里追加序号保证唯一。
        if not os.path.exists(default_name):
            return default_name
        i = 1
        while os.path.exists(f"{default_name}.{i}"):
            i += 1
        return f"{default_name}.{i}"

# strftime 占位符 -> 对应的数字正则片段，用于由 suffix 反推 extMatch
_STRFTIME_TO_REGEX = {
    "%Y": r"\d{4}", "%m": r"\d{2}", "%d": r"\d{2}",
    "%H": r"\d{2}", "%M": r"\d{2}", "%S": r"\d{2}", "%j": r"\d{3}",
}


def _get_rotate_suffix() -> str:
    if settings.LOG_ROTATE_SUFFIX:
        return settings.LOG_ROTATE_SUFFIX

    interval = settings.LOG_ROTATE_INTERVAL.upper()
    if interval == "H":
        return "%Y-%m-%d-%H"
    if interval == "M":
        return "%Y-%m-%d-%H-%M"
    if interval == "S":
        return "%Y-%m-%d-%H-%M-%S"
    return "%Y-%m-%d"


def _suffix_to_extmatch(suffix: str) -> "re.Pattern":
    """由自定义 suffix 反推匹配轮转文件的正则。

    TimedRotatingFileHandler 用 extMatch 识别历史文件以执行 backupCount 清理。
    一旦覆盖了 handler.suffix 却不同步 extMatch，两者分隔符不一致
    （如 suffix "%Y-%m-%d-%H" 用 "-"，默认 extMatch 却用 "_"），
    getFilesToDelete() 将永远匹配不到，导致 backupCount 形同虚设。
    """
    pattern = re.escape(suffix)
    for code, rep in _STRFTIME_TO_REGEX.items():
        pattern = pattern.replace(code, rep)
    return re.compile(r"^" + pattern + r"(\.\w+)?$")


def _resolve_mode() -> str:
    mode = (settings.LOG_ROTATE_MODE or "").strip().lower()
    if mode in ("time", "size", "dated"):
        return mode
    return "time" if settings.LOG_ROTATE_BY_TIME else "size"


def _dated_log_path(log_path: Path) -> Path:
    """activity_mark.log -> activity_mark.2026-08-26.log"""
    date = datetime.now().strftime("%Y-%m-%d")
    return log_path.with_name(f"{log_path.stem}.{date}{log_path.suffix}")


def _cleanup_dated_logs(log_path: Path, backup_count: int) -> None:
    """dated 模式下没有进程内时间轮转，改由启动时按「保留天数」清理历史文件。

    同一天内因大小超限产生的分片（x.2026-08-26.log.1）随该天一并保留/清理。
    """
    if backup_count <= 0:
        return
    stem, suffix = log_path.stem, log_path.suffix
    # 匹配 x.YYYY-MM-DD.log 及其大小分片 x.YYYY-MM-DD.log.N
    pattern = re.compile(
        r"^" + re.escape(stem) + r"\.(\d{4}-\d{2}-\d{2})"
        + re.escape(suffix) + r"(?:\.\d+)?$"
    )
    by_date: dict = {}
    for p in log_path.parent.glob(f"{stem}.*"):
        m = pattern.match(p.name)
        if m:
            by_date.setdefault(m.group(1), []).append(p)
    for date in sorted(by_date)[:-backup_count]:
        for old in by_date[date]:
            try:
                old.unlink()
            except OSError:
                pass


def _create_file_handler(log_file: str) -> logging.Handler:
    log_path = settings.LOG_DIR / log_file
    mode = _resolve_mode()

    if mode == "dated":
        # 每天一个文件（文件名内嵌日期），不依赖进程存活即可切分，适合 oneshot
        # 短命任务；同时 maxBytes>0 时在一天内超限也切分（谁先到谁切）。
        _cleanup_dated_logs(log_path, settings.LOG_BACKUP_COUNT)
        return RotatingFileHandler(
            filename=_dated_log_path(log_path),
            maxBytes=settings.LOG_MAX_BYTES,  # 0 表示当天不按大小切
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )

    if mode == "time":
        # 时间 + 大小组合轮转，补上「同一周期内文件超过 maxBytes 不切」的缺口
        handler = SizedTimedRotatingFileHandler(
            filename=log_path,
            when=settings.LOG_ROTATE_INTERVAL,
            interval=1,
            backupCount=settings.LOG_BACKUP_COUNT,
            maxBytes=settings.LOG_MAX_BYTES,  # 0 表示只按时间切
            encoding="utf-8",
        )
        handler.suffix = _get_rotate_suffix()
        # 覆盖 suffix 后必须同步 extMatch，否则 backupCount 清理失效
        handler.extMatch = _suffix_to_extmatch(handler.suffix)
        return handler

    return RotatingFileHandler(
        filename=log_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )


def get_logger(name="schedule_core", log_file=None):
    """
    获取配置好的日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件名，默认为None，此时使用name.log

    Returns:
        配置好的日志记录器
    """
    # 确保日志目录存在
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 配置日志
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)

    if log_file is None:
        log_file = settings.LOG_FILE or f"{name}.log"

    file_handler = _create_file_handler(log_file)
    file_handler.setLevel(settings.LOG_LEVEL)

    # 创建格式化器，使用更详细的日志格式
    log_format = settings.LOG_FORMAT
    if log_format.lower() == "json":
        log_format = DEFAULT_LOG_FORMAT
    formatter = logging.Formatter(
        fmt=log_format, datefmt=settings.LOG_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # 清除已有的处理器，防止重复添加
    if logger.handlers:
        logger.handlers = []

    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # 设置 propagate 为 False，防止日志向上传播
    logger.propagate = False

    # 确保根日志记录器也使用相同的格式
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(settings.LOG_LEVEL)

    return logger


# 默认日志记录器
logger = get_logger()
