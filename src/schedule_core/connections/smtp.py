"""
SMTP邮件客户端
提供SMTP邮件发送功能，支持TLS加密
移植自Go代码 mail/smtp.go
"""

import smtplib
import ssl
import threading
from typing import List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 全局锁
_smtp_lock = threading.Lock()


class SmtpManager:
    """SMTP邮件客户端"""

    def __init__(self):
        self._initialize()

    def _initialize(self):
        """初始化SMTP客户端"""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self._client = smtplib.SMTP_SSL(
            host=settings.SMTP_HOST, port=settings.SMTP_PORT, context=context)
        self._client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        self._from_addr = settings.SMTP_FROM

    def send(self, addresses: List[str], body: bytes) -> None:
        """
        发送邮件
        
        Args:
            addresses: 收件人地址列表
            body: 邮件内容（原始字节）
            
        Raises:
            Exception: 发送失败时抛出异常
        """
        with _smtp_lock:
            try:
                # 每次发送时重新建立连接
                self._initialize()

                # 发送邮件
                self._client.sendmail(
                    from_addr=self._from_addr, to_addrs=addresses, msg=body)

                # 退出
                self._client.quit()
            except Exception:
                raise
            finally:
                self.close()

    def close(self) -> None:
        """关闭连接"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self.client = None


smtp_manager = SmtpManager()
