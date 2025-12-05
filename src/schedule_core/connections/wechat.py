"""
微信API接口工具类
提供微信Access Token、JSApi Ticket、用户认证等功能
移植自Go代码 third_party/wechat.go
"""

import json
import requests
from typing import Dict, Optional
from schedule_core import logger
from schedule_core.config.settings import core_settings as settings

# 微信API端点
WECHAT_API_BASE = "https://api.weixin.qq.com"
WECHAT_OPEN_API_BASE = "https://open.weixin.qq.com"

# 微信API路径
WECHAT_GET_TOKEN_URL = f"{WECHAT_API_BASE}/cgi-bin/token"
WECHAT_GET_TICKET_URL = f"{WECHAT_API_BASE}/cgi-bin/ticket/getticket"
WECHAT_OAUTH2_ACCESS_TOKEN_URL = f"{WECHAT_API_BASE}/sns/oauth2/access_token"
WECHAT_OAUTH2_REFRESH_TOKEN_URL = f"{WECHAT_API_BASE}/sns/oauth2/refresh_token"
WECHAT_OAUTH2_USERINFO_URL = f"{WECHAT_API_BASE}/sns/userinfo"
WECHAT_SUBSCRIBE_USERINFO_URL = f"{WECHAT_API_BASE}/cgi-bin/user/info"
WECHAT_JSAPI_CODE2SESSION_URL = f"{WECHAT_API_BASE}/sns/jscode2session"
WECHAT_SEND_TEMPLATE_URL = f"{WECHAT_API_BASE}/cgi-bin/message/template/send"
WECHAT_QR_CONNECT_URL = f"{WECHAT_OPEN_API_BASE}/connect/qrconnect"
WECHAT_OAUTH2_AUTHORIZE_URL = f"{WECHAT_OPEN_API_BASE}/connect/oauth2/authorize"

# 微信平台类型
WECHAT_PLATFORM_SERVICE = "service"  # 服务号
WECHAT_PLATFORM_SUBSCRIBE = "subscribe"  # 订阅号
WECHAT_PLATFORM_MINI = "miniprogram"  # 小程序
WECHAT_PLATFORM_OPEN = "open"  # 开放平台
WECHAT_PLATFORM_QR = "qrlogin"  # 扫码登录


class WeChatManager:
    """微信API客户端（同步版本，使用requests）"""

    def __init__(self):
        self._initialize()

    def _initialize(self):
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
        self.callback_addr = settings.WECHAT_CALLBACK_ADDR
        self.scope = settings.WECHAT_SCOPE
        self._session = None

    @property
    def session(self) -> requests.Session:
        """延迟初始化 requests session"""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _http_get(self, url: str, params: Dict = None) -> Dict:
        """
        发送HTTP GET请求
        
        Args:
            url: 请求URL
            params: 请求参数
            
        Returns:
            Dict: 响应内容
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("errcode") and result.get("errcode") != 0:
                raise Exception(result.get("errmsg", "未知错误"))

            return result
        except Exception as e:
            logger.error(f"微信HTTP GET请求失败: {url}, 错误: {e}")
            raise

    def _http_post(self, url: str, data: Dict) -> Dict:
        """
        发送HTTP POST请求
        
        Args:
            url: 请求URL
            data: 请求数据
            
        Returns:
            Dict: 响应内容
        """
        try:
            response = self.session.post(url, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get("errcode") and result.get("errcode") != 0:
                raise Exception(result.get("errmsg", "未知错误"))

            return result
        except Exception as e:
            logger.error(f"微信HTTP POST请求失败: {url}, 错误: {e}")
            raise

    def get_access_token(self) -> str:
        """
        获取微信AccessToken
        
        Returns:
            str: access_token
        """
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }

        data = self._http_get(WECHAT_GET_TOKEN_URL, params)
        return data.get("access_token", "")

    def get_jsapi_ticket(self, access_token: str) -> str:
        """
        获取微信JSApi Ticket
        
        Args:
            access_token: 微信AccessToken
            
        Returns:
            str: ticket
        """
        params = {"access_token": access_token, "type": "jsapi"}
        data = self._http_get(WECHAT_GET_TICKET_URL, params)
        return data.get("ticket", "")

    def get_connect_url(self,
                        state: str,
                        auth_scope: str = "snsapi_userinfo",
                        pop_up: bool = False,
                        redirect_path: str = "") -> str:
        """
        获取微信授权链接
        
        Args:
            state: 状态参数
            auth_scope: 授权范围，snsapi_base或snsapi_userinfo
            pop_up: 是否强制弹出授权
            redirect_path: 回调路径
            
        Returns:
            str: 授权链接
        """
        # 处理回调地址
        callback_addr = self.callback_addr
        if callback_addr.endswith("/"):
            callback_addr = callback_addr[:-1]

        if not redirect_path.startswith("/") and redirect_path:
            redirect_path = f"/{redirect_path}"

        redirect_uri = f"{callback_addr}{redirect_path}"

        # 根据平台类型选择不同的授权链接
        if self.scope == WECHAT_PLATFORM_QR:
            # 扫码登录
            from urllib.parse import quote
            connect_url = (f"{WECHAT_QR_CONNECT_URL}?"
                           f"appid={self.app_id}&"
                           f"redirect_uri={quote(redirect_uri)}&"
                           f"response_type=code&"
                           f"scope={auth_scope}&"
                           f"state={state}&"
                           f"forcePopup={str(pop_up).lower()}#wechat_redirect")
        else:
            # 普通授权
            from urllib.parse import quote
            connect_url = (f"{WECHAT_OAUTH2_AUTHORIZE_URL}?"
                           f"appid={self.app_id}&"
                           f"redirect_uri={quote(redirect_uri)}&"
                           f"response_type=code&"
                           f"scope={auth_scope}&"
                           f"state={state}&"
                           f"forcePopup={str(pop_up).lower()}#wechat_redirect")

        return connect_url

    def get_user_access_token(self, code: str) -> Dict:
        """
        获取用户AccessToken
        
        Args:
            code: 授权码
            
        Returns:
            Dict: 用户Token信息
        """
        # 根据平台类型选择不同的接口
        if self.scope == WECHAT_PLATFORM_MINI:
            # 小程序登录
            params = {
                "appid": self.app_id,
                "secret": self.app_secret,
                "js_code": code,
                "grant_type": "authorization_code"
            }
            url = WECHAT_JSAPI_CODE2SESSION_URL
        else:
            # 普通授权
            params = {
                "appid": self.app_id,
                "secret": self.app_secret,
                "code": code,
                "grant_type": "authorization_code"
            }
            url = WECHAT_OAUTH2_ACCESS_TOKEN_URL

        data = self._http_get(url, params)
        return data

    def refresh_user_token(self, refresh_token: str) -> Dict:
        """
        刷新用户Token
        
        Args:
            refresh_token: 刷新Token
            
        Returns:
            Dict: 刷新后的Token信息
        """
        params = {
            "appid": self.app_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        data = self._http_get(WECHAT_OAUTH2_REFRESH_TOKEN_URL, params)
        return data

    def get_user_info(self, user_access_token: str, open_id: str) -> Dict:
        """
        获取用户信息
        
        Args:
            user_access_token: 用户AccessToken
            open_id: 用户OpenID
            
        Returns:
            Dict: 用户信息
        """
        params = {
            "access_token": user_access_token,
            "openid": open_id,
            "lang": "zh_CN"
        }

        data = self._http_get(WECHAT_OAUTH2_USERINFO_URL, params)
        return data

    def get_subscribe_user_info(self, access_token: str, open_id: str) -> Dict:
        """
        获取关注用户信息
        
        Args:
            access_token: 公众号AccessToken
            open_id: 用户OpenID
            
        Returns:
            Dict: 用户信息
        """
        params = {
            "access_token": access_token,
            "openid": open_id,
            "lang": "zh_CN"
        }

        data = self._http_get(WECHAT_SUBSCRIBE_USERINFO_URL, params)
        return data

    def send_template_message(self,
                              access_token: str,
                              open_id: str,
                              template_id: str,
                              url: str,
                              data: Dict,
                              mini_program: Dict = None) -> Dict:
        """
        发送模板消息
        
        Args:
            access_token: 公众号AccessToken
            open_id: 用户OpenID
            template_id: 模板ID
            url: 跳转链接
            data: 模板数据
            mini_program: 小程序信息
            
        Returns:
            Dict: 发送结果
        """
        if self.scope == WECHAT_PLATFORM_OPEN:
            raise Exception("开放平台不支持发送模板消息")

        api_url = f"{WECHAT_SEND_TEMPLATE_URL}?access_token={access_token}"

        message = {
            "touser": open_id,
            "template_id": template_id,
            "url": url,
            "data": data
        }

        if mini_program:
            message["miniprogram"] = mini_program

        result = self._http_post(api_url, message)
        return result


# 创建全局微信管理器实例
wechat_manager = WeChatManager()
