"""
Logging utility for applications（基于 loguru）。

对外仍暴露 get_logger() / logger，用法与之前的标准库封装完全兼容
（logger.info/debug/warning/error，支持 error(..., exc_info=True) 与 %-占位符），
但文件轮转、压缩、清理全部交给 loguru，不再自维护 Handler 与外部打包脚本。

三种轮转模式（由 settings.LOG_ROTATE_MODE / LOG_ROTATE_BY_TIME 决定）：
  time  —— 常驻进程按时间(整点对齐)+大小「谁先到谁切」，历史文件自动压成 .gz
  size  —— 常驻进程按大小切，历史文件自动压成 .gz
  dated —— oneshot 短命任务：文件名内嵌日期 xxx.<date>.log，进程内轮转触发不了，
           改由「文件名日期 + 启动时压缩历史日 + retention 清理」保证不撑盘

命名契约：活动文件 <name>.log（time/size）或 <name>.<date>.log（dated）；
历史文件由 loguru 生成，均自动 gz 压缩、按 LOG_BACKUP_COUNT 清理。
"""

import gzip
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger as _loguru_logger
from schedule_core.config.settings import core_settings as settings


# loguru 原生 format（等价于原 stdlib 格式：时间 - 名称 - 级别 - [模块:行] - 消息）
_LOGURU_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} - {extra[logger_name]} - {level: <8} - "
    "[{name}:{line}] - {message}"
)

# 模块级：sink 只配置一次（loguru 是全局单例，重复 add 会重复写）
_configured = False


class InterceptHandler(logging.Handler):
    """把标准库 logging（如 SQLAlchemy 的 SQL_ECHO）转发到 loguru。

    这样第三方库通过 stdlib logging 打出的日志也统一进 loguru 的文件与 stdout。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # 定位到真正的调用点（跳过 logging 内部帧）
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        (_loguru_logger
            .opt(depth=depth, exception=record.exc_info)
            .bind(logger_name=record.name)
            .log(level, record.getMessage()))


class _LoggerProxy:
    """兼容包装：吸收 stdlib 风格的 exc_info=/%-args/extra=，转成 loguru 语义。

    使既有调用（logger.error(f"...", exc_info=True)、logger.error("%s", x)）无需改动。
    未覆盖的属性（bind/opt/add/remove 等）透传给 loguru。
    """

    def __init__(self, lg):
        object.__setattr__(self, "_lg", lg)

    def _emit(self, level, message, args, kwargs):
        exc = kwargs.pop("exc_info", None)
        kwargs.pop("stacklevel", None)
        extra = kwargs.pop("extra", None)
        lg = self._lg
        if extra:
            lg = lg.bind(**extra)
        if args:
            try:
                message = message % args
            except Exception:
                message = " ".join([str(message), *(str(a) for a in args)])
        exception = exc if exc else False
        lg.opt(depth=2, exception=exception).log(level, message)

    def debug(self, message, *args, **kw):
        self._emit("DEBUG", message, args, kw)

    def info(self, message, *args, **kw):
        self._emit("INFO", message, args, kw)

    def warning(self, message, *args, **kw):
        self._emit("WARNING", message, args, kw)

    warn = warning

    def error(self, message, *args, **kw):
        self._emit("ERROR", message, args, kw)

    def critical(self, message, *args, **kw):
        self._emit("CRITICAL", message, args, kw)

    def exception(self, message, *args, **kw):
        kw.setdefault("exc_info", True)
        self._emit("ERROR", message, args, kw)

    def setLevel(self, *_a, **_k):
        # 兼容 stdlib 接口；loguru 的级别在 sink 上统一控制，这里忽略即可
        pass

    def __getattr__(self, name):
        return getattr(self._lg, name)


def _resolve_mode() -> str:
    mode = (settings.LOG_ROTATE_MODE or "").strip().lower()
    if mode in ("time", "size", "dated"):
        return mode
    return "time" if settings.LOG_ROTATE_BY_TIME else "size"


def _next_boundary(dt: datetime, interval: str) -> datetime:
    """给定时间点，返回下一个「整点」边界（对齐到 interval）。"""
    i = (interval or "H").upper()
    if i == "S":
        return dt.replace(microsecond=0) + timedelta(seconds=1)
    if i == "M":
        return dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if i == "D":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _make_time_size_rotation(interval: str, max_bytes: int):
    """loguru rotation 回调：时间(整点对齐) 或 大小，谁先到谁切。"""
    state = {"next": None}

    def should_rotate(message, file) -> bool:
        now = message.record["time"]
        if state["next"] is None:
            state["next"] = _next_boundary(now, interval)
        if now >= state["next"]:
            state["next"] = _next_boundary(now, interval)
            return True
        if max_bytes and max_bytes > 0 and file.tell() + len(message) > max_bytes:
            return True
        return False

    return should_rotate


def _maintain_dated(log_path: Path, backup_days: int) -> None:
    """dated 模式启动时维护历史文件：压缩跨天明文 + 按天数清理。

    dated 用含 {time} 的 sink，loguru 有两个针对 oneshot 的局限，这里补上：
      1) 进程内没有 rotation 事件，compression 触发不到「跨天」旧文件 —— 启动时
         主动把非今天的明文压成 .gz；
      2) loguru 的 retention 对含 {time} 的 sink 不清理历史 —— 启动时按「保留天数」
         自行删除过期的历史文件（.log / .gz / 当天大小分片一并按其日期归组）。
    """
    stem, suffix = log_path.stem, log_path.suffix  # offline_log , .log
    parent = log_path.parent
    today = datetime.now().strftime("%Y-%m-%d")

    # 1) 压缩非今天、未压缩的历史明文
    for p in parent.glob(f"{stem}.*{suffix}"):
        if today in p.name:  # 今天的活动文件/分片交给 loguru
            continue
        gz = p.with_name(p.name + ".gz")
        if gz.exists():
            continue
        try:
            with open(p, "rb") as fin, gzip.open(gz, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            p.unlink()
        except OSError:
            pass

    # 2) 按天清理：文件名首个日期段即归属日，保留最近 backup_days 天
    if not backup_days or backup_days <= 0:
        return
    pat = re.compile(re.escape(stem) + r"\.(\d{4}-\d{2}-\d{2})")
    by_date: dict = {}
    for p in parent.glob(f"{stem}.*"):
        m = pat.match(p.name)
        if m:
            by_date.setdefault(m.group(1), []).append(p)
    for d in sorted(by_date)[:-backup_days]:
        for p in by_date[d]:
            try:
                p.unlink()
            except OSError:
                pass


def _add_file_sink(log_path: Path, mode: str, common: dict,
                   max_bytes: int, backup_count: int, interval: str,
                   filter_fn=None) -> None:
    """按模式为一个文件路径添加 loguru 文件 sink（可带 filter 做业务分流）。"""
    extra = {"filter": filter_fn} if filter_fn is not None else {}
    rot_size = max_bytes if max_bytes and max_bytes > 0 else None
    if mode == "dated":
        # 文件名内嵌日期，不依赖进程存活即可按天分文件；当天超限再按大小切。
        # 注意：loguru 对含 {time} 的 sink 不做 retention，历史清理与跨天压缩由
        # _maintain_dated 在启动时接管（backup_count 在 dated 下语义为「保留天数」）。
        _maintain_dated(log_path, backup_count)
        sink = str(log_path.with_name(
            f"{log_path.stem}.{{time:YYYY-MM-DD}}{log_path.suffix}"))
        _loguru_logger.add(sink, rotation=rot_size, compression="gz", **common, **extra)
    elif mode == "size":
        _loguru_logger.add(str(log_path), rotation=rot_size, retention=backup_count,
                           compression="gz", **common, **extra)
    else:  # time：时间(整点)+大小 谁先到谁切
        _loguru_logger.add(str(log_path),
                           rotation=_make_time_size_rotation(interval, max_bytes),
                           retention=backup_count, compression="gz", **common, **extra)


def _configure(log_file: str) -> None:
    """配置 loguru 的 stdout 与文件 sink（进程内只执行一次）。"""
    global _configured
    if _configured:
        return

    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = settings.LOG_DIR / log_file
    mode = _resolve_mode()
    level = settings.LOG_LEVEL
    max_bytes = settings.LOG_MAX_BYTES
    backup_count = settings.LOG_BACKUP_COUNT
    interval = settings.LOG_ROTATE_INTERVAL

    _loguru_logger.remove()  # 清掉 loguru 默认的 stderr sink

    # 控制台（stdout）：全量输出（不分流），交给 systemd/journald 采集
    _loguru_logger.add(
        sys.stdout, level=level, format=_LOGURU_FORMAT,
        backtrace=False, diagnose=False,
    )

    common = dict(
        level=level, format=_LOGURU_FORMAT, encoding="utf-8",
        backtrace=False, diagnose=False, enqueue=False,
    )

    # 业务分流：LOG_MODULE_ROUTES 里每个模块关键字各写 <关键字>.log，按 record["name"]
    #（调用模块名，如 rktv_job.tasks.push_notice）过滤，业务代码无需改动。
    # 典型用于 callback_server：一个进程分发多个业务 handler，按业务落到各自文件。
    routes = [r.strip() for r in (settings.LOG_MODULE_ROUTES or "").split(",") if r.strip()]
    for key in routes:
        biz_path = log_path.with_name(f"{key}{log_path.suffix}")
        _add_file_sink(biz_path, mode, common, max_bytes, backup_count, interval,
                       filter_fn=(lambda r, k=key: k in r["name"]))

    # 主文件：有分流时排除已路由模块，只留框架自身与未分类日志
    main_filter = (lambda r: not any(k in r["name"] for k in routes)) if routes else None
    _add_file_sink(log_path, mode, common, max_bytes, backup_count, interval,
                   filter_fn=main_filter)

    # 把标准库 logging（SQLAlchemy 等第三方库）接入 loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    _configured = True


def get_logger(name="schedule_core", log_file=None):
    """获取日志记录器（对外接口保持兼容）。

    Args:
        name: 日志记录器名称（写入日志的 logger_name 字段）
        log_file: 日志文件名，默认 settings.LOG_FILE 或 f"{name}.log"

    Returns:
        _LoggerProxy：用法与标准库 Logger 兼容（info/debug/warning/error，
        支持 exc_info= 与 %-占位符）。
    """
    if log_file is None:
        log_file = settings.LOG_FILE or f"{name}.log"
    _configure(log_file)
    return _LoggerProxy(_loguru_logger.bind(logger_name=name))


# 默认日志记录器
logger = get_logger()
