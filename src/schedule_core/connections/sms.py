"""
腾讯云短信客户端
提供短信发送功能，使用TC3-HMAC-SHA256签名
参考文档: https://cloud.tencent.com/document/api/382/55981
"""

import json
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from schedule_core.config.settings import core_settings as settings


class SmsManager:
    """腾讯云短信客户端"""

    def __init__(self):
        """初始化短信客户端"""
        self._initialize()

    def _initialize(self):
        """初始化配置参数"""
        self.host = settings.SMS_ADDR or "sms.tencentcloudapi.com"
        self.secret_id = settings.SMS_SECRET_ID
        self.secret_key = settings.SMS_SECRET_KEY
        self.app_id = settings.SMS_APP_ID
        self.region = settings.SMS_REGION or "ap-guangzhou"
        self.algorithm = settings.SMS_ALG or "TC3-HMAC-SHA256"
        self.signature = settings.SMS_SIGNATURE
        self.service = "sms"
        self.version = "2021-01-11"

    def _sha256_hex(self, message: str) -> str:
        """SHA256哈希并返回十六进制字符串"""
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def _hmac_sha256(self, key: bytes, message: str) -> bytes:
        """HMAC-SHA256签名"""
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    def _get_date(self, timestamp: int) -> str:
        """获取UTC日期字符串"""
        return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    def _build_canonical_request(self, http_method: str, canonical_uri: str,
                                 canonical_querystring: str,
                                 canonical_headers: str, signed_headers: str,
                                 payload: str) -> str:
        """
        构建规范请求串
        
        格式:
        HTTPRequestMethod + '\n' +
        CanonicalURI + '\n' +
        CanonicalQueryString + '\n' +
        CanonicalHeaders + '\n' +
        SignedHeaders + '\n' +
        HashedRequestPayload
        """
        hashed_payload = self._sha256_hex(payload)
        return "\n".join([
            http_method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers, hashed_payload
        ])

    def _build_string_to_sign(self, algorithm: str, timestamp: int,
                              credential_scope: str,
                              canonical_request: str) -> str:
        """
        构建待签名字符串
        
        格式:
        Algorithm + '\n' +
        RequestTimestamp + '\n' +
        CredentialScope + '\n' +
        HashedCanonicalRequest
        """
        hashed_canonical_request = self._sha256_hex(canonical_request)
        return "\n".join([
            algorithm,
            str(timestamp), credential_scope, hashed_canonical_request
        ])

    def _sign(self, key: bytes, msg: str) -> bytes:
        """签名辅助函数"""
        return self._hmac_sha256(key, msg)

    def _calculate_signature(self, secret_key: str, date: str, service: str,
                             string_to_sign: str) -> str:
        """
        计算签名
        
        步骤:
        1. 计算派生密钥
        2. 使用派生密钥对待签名字符串进行签名
        """
        # 计算派生密钥
        k_date = self._sign(("TC3" + secret_key).encode("utf-8"), date)
        k_service = self._sign(k_date, service)
        k_signing = self._sign(k_service, "tc3_request")

        # 计算签名
        signature = self._hmac_sha256(k_signing, string_to_sign)
        return signature.hex()

    def _build_authorization(self, algorithm: str, secret_id: str,
                             credential_scope: str, signed_headers: str,
                             signature: str) -> str:
        """
        构建Authorization头
        
        格式:
        Algorithm + ' ' +
        'Credential=' + SecretId + '/' + CredentialScope + ', ' +
        'SignedHeaders=' + SignedHeaders + ', ' +
        'Signature=' + Signature
        """
        return (f"{algorithm} "
                f"Credential={secret_id}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, "
                f"Signature={signature}")

    def _make_request(self, action: str, payload: Dict[str,
                                                       Any]) -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            action: API操作名称
            payload: 请求参数
            
        Returns:
            Dict: API响应
        """
        # 准备请求参数
        http_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        content_type = "application/json; charset=utf-8"

        # 时间戳
        timestamp = int(time.time())
        date = self._get_date(timestamp)

        # 请求体
        payload_str = json.dumps(payload)

        # 构建规范请求头（只包含 content-type 和 host）
        canonical_headers = (f"content-type:{content_type}\n"
                             f"host:{self.host}\n")
        signed_headers = "content-type;host"

        # 构建规范请求串
        canonical_request = self._build_canonical_request(
            http_method, canonical_uri, canonical_querystring,
            canonical_headers, signed_headers, payload_str)

        # 构建凭证范围
        credential_scope = f"{date}/{self.service}/tc3_request"

        # 构建待签名字符串
        string_to_sign = self._build_string_to_sign(self.algorithm, timestamp,
                                                    credential_scope,
                                                    canonical_request)

        # 计算签名
        signature = self._calculate_signature(self.secret_key, date,
                                              self.service, string_to_sign)

        # 构建Authorization头
        authorization = self._build_authorization(self.algorithm,
                                                  self.secret_id,
                                                  credential_scope,
                                                  signed_headers, signature)

        # 构建请求头
        headers = {
            "Content-Type": content_type,
            "Host": self.host,
            "X-TC-Action": action,
            "X-TC-Version": self.version,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": self.region,
            "Authorization": authorization
        }

        # 发送请求
        url = f"https://{self.host}"
        request = Request(
            url, data=payload_str.encode("utf-8"), headers=headers)

        try:
            with urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body)
        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"HTTP错误 {e.code}: {error_body}")
        except URLError as e:
            raise Exception(f"网络错误: {e.reason}")

    def send(self,
             phone_numbers: List[str],
             template_id: str,
             template_params: Optional[List[str]] = None,
             sign_name: Optional[str] = None,
             session_context: Optional[str] = None,
             extend_code: Optional[str] = None,
             sender_id: Optional[str] = None) -> Dict[str, Any]:
        """
        发送短信
        
        Args:
            phone_numbers: 手机号列表，采用E.164标准格式，如 ["+8618501234444"]
                          国内短信也支持 "18501234444" 格式
            template_id: 模板ID，必须是已审核通过的模板
            template_params: 模板参数列表，需与模板变量个数保持一致
            sign_name: 短信签名内容（国内短信必填），如 "腾讯云"
            session_context: 用户session上下文，服务端会原样返回
            extend_code: 短信码号扩展号
            sender_id: 国际/港澳台短信Sender ID
            
        Returns:
            Dict: 发送结果，包含SendStatusSet数组
            
        Raises:
            Exception: 发送失败时抛出异常
            
        Example:
            >>> sms_manager.send(
            ...     phone_numbers=["+8618501234444"],
            ...     template_id="123456",
            ...     template_params=["1234", "5"],
            ...     sign_name="腾讯云"
            ... )
        """
        # 确保已初始化
        self._initialize()

        # 格式化手机号（确保国内手机号有+86前缀）
        formatted_numbers = []
        for phone in phone_numbers:
            phone = phone.strip()
            if phone.startswith("+"):
                formatted_numbers.append(phone)
            elif phone.startswith("86"):
                formatted_numbers.append(f"+{phone}")
            elif phone.startswith("0086"):
                formatted_numbers.append(f"+{phone[2:]}")
            else:
                # 默认添加+86前缀
                formatted_numbers.append(f"+86{phone}")

        # 构建请求参数
        payload = {
            "PhoneNumberSet": formatted_numbers,
            "SmsSdkAppId": self.app_id,
            "TemplateId": template_id,
        }

        # 签名名称（使用参数或默认配置）
        sign = sign_name or self.signature
        if sign:
            payload["SignName"] = sign

        # 模板参数
        if template_params:
            payload["TemplateParamSet"] = template_params

        # 可选参数
        if session_context:
            payload["SessionContext"] = session_context
        if extend_code:
            payload["ExtendCode"] = extend_code
        if sender_id:
            payload["SenderId"] = sender_id

        # 发送请求
        response = self._make_request("SendSms", payload)

        # 检查响应
        if "Response" not in response:
            raise Exception(f"无效的响应格式: {response}")

        resp = response["Response"]

        # 检查错误
        if "Error" in resp:
            error = resp["Error"]
            raise Exception(
                f"短信发送失败 [{error.get('Code')}]: {error.get('Message')}")

        return resp

    def send_single(self,
                    phone: str,
                    template_id: str,
                    template_params: Optional[List[str]] = None,
                    sign_name: Optional[str] = None) -> Dict[str, Any]:
        """
        发送单条短信（便捷方法）
        
        Args:
            phone: 手机号
            template_id: 模板ID
            template_params: 模板参数列表
            sign_name: 短信签名
            
        Returns:
            Dict: 发送状态
        """
        result = self.send(
            phone_numbers=[phone],
            template_id=template_id,
            template_params=template_params,
            sign_name=sign_name)

        # 返回第一条发送状态
        status_set = result.get("SendStatusSet", [])
        if status_set:
            status = status_set[0]
            if status.get("Code") != "Ok":
                raise Exception(
                    f"短信发送失败 [{status.get('Code')}]: {status.get('Message')}")
            return status
        return result


# 创建全局短信管理器实例
sms_manager = SmsManager()
