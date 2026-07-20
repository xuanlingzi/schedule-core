"""
IMAP邮件客户端

用于连接邮箱服务端并维护「已发送」文件夹，定期清理过期邮件以释放邮箱空间。
与 smtp.py 对称：延迟连接、每次操作重连、全局锁串行化。
删除为不可逆操作，因此提供 dry_run 演练模式，且清理默认由上层开关控制。
"""

import imaplib
import threading
from datetime import datetime, timedelta
from typing import List, Optional

from schedule_core.config.settings import core_settings as settings

# 全局锁，串行化 IMAP 操作
_imap_lock = threading.Lock()

# IMAP SEARCH 的日期格式要求英文月份缩写，避免受系统 locale 影响，固定映射
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# 自动探测「已发送」文件夹时的常见名称兜底（按顺序尝试）
_SENT_FALLBACK_NAMES = ["Sent Messages", "Sent", "已发送"]


class ImapManager:
    """IMAP邮件客户端（用于清理已发送邮件）"""

    def __init__(self):
        self._client: Optional[imaplib.IMAP4_SSL] = None

    def _credentials(self):
        """IMAP 凭据留空时回退复用 SMTP 凭据（同账号）。"""
        username = settings.IMAP_USERNAME or settings.SMTP_USERNAME
        password = settings.IMAP_PASSWORD or settings.SMTP_PASSWORD
        return username, password

    def _connect(self):
        """建立 IMAP over SSL 连接并登录。"""
        username, password = self._credentials()
        if not username or not password:
            raise ValueError("IMAP 凭据缺失（IMAP/SMTP 用户名或密码均为空）")
        self._client = imaplib.IMAP4_SSL(settings.IMAP_ADDR, settings.IMAP_PORT)
        self._client.login(username, password)
        self._send_id()

    def _send_id(self):
        """发送 IMAP ID 命令（RFC 2971）。

        腾讯企业邮/QQ 邮箱要求客户端先上报 ID，否则后续 LIST/SELECT 会被拒。
        对不要求 ID 的服务器，多发一条 ID 也是无害的。
        """
        try:
            imaplib.Commands.setdefault("ID", ("NONAUTH", "AUTH", "SELECTED"))
            self._client._simple_command(
                "ID", '("name" "rktv-job" "version" "1.0" "vendor" "rktv")')
        except Exception:
            # ID 失败不阻断：非腾讯类服务器可能不支持该命令
            pass

    def close(self) -> None:
        """关闭连接。"""
        if self._client is not None:
            try:
                self._client.logout()
            except Exception:
                pass
            self._client = None

    def _detect_sent_folder(self) -> str:
        """探测「已发送」文件夹。

        优先级：配置项 > \\Sent 特殊属性 > 按常见名匹配实际存在的文件夹 > 兜底。
        注意腾讯企业邮的「已发送」并不带 \\Sent 属性，只是普通名为 "Sent Messages"
        的文件夹，因此按名称匹配是这里的主力手段。
        """
        if settings.IMAP_SENT_FOLDER:
            return settings.IMAP_SENT_FOLDER

        try:
            typ, data = self._client.list()
            if typ == "OK" and data:
                names = []
                for raw in data:
                    line = raw.decode("utf-8", "ignore") if isinstance(
                        raw, (bytes, bytearray)) else str(raw)
                    # 形如：(\HasNoChildren \Sent) "/" "Sent Messages"
                    parts = line.split('"')
                    name = parts[-2] if len(parts) >= 2 else ""
                    if "\\Sent" in line and name:
                        return name  # 支持 \Sent 属性的服务器
                    if name:
                        names.append(name)
                # 无 \Sent 属性时（如腾讯企业邮），按常见名匹配实际存在的文件夹
                for cand in _SENT_FALLBACK_NAMES:
                    if cand in names:
                        return cand
        except Exception:
            pass

        return _SENT_FALLBACK_NAMES[0]

    @staticmethod
    def _imap_date(dt: datetime) -> str:
        """转为 IMAP SEARCH 需要的 dd-Mon-yyyy（英文月份）。"""
        return f"{dt.day:02d}-{_MONTHS[dt.month - 1]}-{dt.year}"

    @staticmethod
    def _quote(mailbox: str) -> str:
        """含空格的文件夹名需加引号。"""
        if mailbox.startswith('"') and mailbox.endswith('"'):
            return mailbox
        return f'"{mailbox}"' if " " in mailbox else mailbox

    def clean_sent_before(self, retention_days: int,
                          dry_run: bool = False,
                          folder: Optional[str] = None) -> int:
        """清理「已发送」文件夹中 retention_days 天之前的邮件。

        Args:
            retention_days: 保留天数，仅删除该天数之前的邮件（BEFORE 该日期）
            dry_run: 演练模式，只统计不删除
            folder: 指定文件夹，留空则自动探测

        Returns:
            int: 实际删除（dry_run 时为将删除）的邮件数量
        """
        if retention_days < 0:
            raise ValueError("retention_days 不能为负")

        cutoff = datetime.now() - timedelta(days=retention_days)
        cutoff_str = self._imap_date(cutoff)

        with _imap_lock:
            try:
                self._connect()
                mailbox = folder or self._detect_sent_folder()

                # 演练模式以只读方式打开，协议层保证不可能改动邮箱
                typ, _ = self._client.select(self._quote(mailbox),
                                             readonly=dry_run)
                if typ != "OK":
                    raise ValueError(f"选择文件夹失败: {mailbox}")

                typ, data = self._client.uid("SEARCH", None,
                                             "BEFORE", cutoff_str)
                if typ != "OK":
                    raise ValueError(f"SEARCH 失败: {mailbox}")

                uids: List[bytes] = data[0].split() if data and data[0] else []
                count = len(uids)

                if count == 0:
                    return 0

                if dry_run:
                    return count

                # 分批标记 \Deleted，避免单条命令过长
                batch_size = 500
                for i in range(0, count, batch_size):
                    chunk = uids[i:i + batch_size]
                    uid_set = b",".join(chunk).decode("ascii")
                    self._client.uid("STORE", uid_set, "+FLAGS", "\\Deleted")

                self._client.expunge()
                return count
            finally:
                self.close()


imap_manager = ImapManager()
