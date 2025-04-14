"""
微信API接口工具类
提供微信Access Token、JSApi Ticket、用户认证等功能
移植自Go代码 third_party/wechat.go
"""

import json
import time
import asyncio
import aiohttp
from datetime import datetime
from typing import Tuple, Optional, Dict, Any, Union, List
from schedule_core import logger
from schedule_core.connections import redis_manager

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


class WeChatClient:
    """微信API客户端"""

    def __init__(self, app_id: str, app_secret: str, callback_addr: str,
                 scope: str):
        """
        初始化微信客户端
        
        Args:
            app_id: 微信AppID
            app_secret: 微信AppSecret
            callback_addr: 回调地址
            scope: 平台类型
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.callback_addr = callback_addr
        self.scope = scope
        self.http_client = None
        self.redis_client = redis_manager.client

    async def _get_http_client(self) -> aiohttp.ClientSession:
        """获取或创建HTTP客户端"""
        if self.http_client is None or self.http_client.closed:
            self.http_client = aiohttp.ClientSession()
        return self.http_client

    async def _close_http_client(self):
        """关闭HTTP客户端"""
        if self.http_client and not self.http_client.closed:
            await self.http_client.close()
            self.http_client = None

    async def _http_get(self, url: str, params: Dict = None) -> str:
        """
        发送HTTP GET请求
        
        Args:
            url: 请求URL
            params: 请求参数
            
        Returns:
            str: 响应内容
        """
        client = await self._get_http_client()
        try:
            async with client.get(url, params=params) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logger.error(f"微信HTTP GET请求失败: {url}, 错误: {e}")
            raise

    async def _http_post(self, url: str, data: Dict) -> str:
        """
        发送HTTP POST请求
        
        Args:
            url: 请求URL
            data: 请求数据
            
        Returns:
            str: 响应内容
        """
        client = await self._get_http_client()
        try:
            async with client.post(url, json=data) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            logger.error(f"微信HTTP POST请求失败: {url}, 错误: {e}")
            raise

    async def get_access_token(self) -> Tuple[str, int]:
        """
        获取微信AccessToken
        
        Returns:
            Tuple[str, int]: (access_token, expires_in)
        """
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }

        try:
            response_text = await self._http_get(WECHAT_GET_TOKEN_URL, params)
            data = json.loads(response_text)

            if "access_token" in data:
                access_token = data["access_token"]
                expires_in = data.get("expires_in", 7200)
                return access_token, expires_in
            else:
                error_msg = f"获取AccessToken失败: {data}"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取AccessToken异常: {e}")
            raise

    async def get_jsapi_ticket(self, access_token: str) -> Tuple[str, int]:
        """
        获取微信JSApi Ticket
        
        Args:
            access_token: 微信AccessToken
            
        Returns:
            Tuple[str, int]: (ticket, expires_in)
        """
        params = {"access_token": access_token, "type": "jsapi"}

        try:
            response_text = await self._http_get(WECHAT_GET_TICKET_URL, params)
            data = json.loads(response_text)

            if data.get("errcode") == 0 and "ticket" in data:
                ticket = data["ticket"]
                expires_in = data.get("expires_in", 7200)
                return ticket, expires_in
            else:
                error_msg = f"获取JSApiTicket失败: {data}"
                logger.error(error_msg)
                raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取JSApiTicket异常: {e}")
            raise

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

    async def get_user_access_token(self, code: str) -> Dict:
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

        try:
            response_text = await self._http_get(url, params)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"获取用户AccessToken异常: {e}")
            raise

    async def refresh_user_token(self, refresh_token: str) -> Dict:
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

        try:
            response_text = await self._http_get(
                WECHAT_OAUTH2_REFRESH_TOKEN_URL, params)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"刷新用户Token异常: {e}")
            raise

    async def get_user_info(self, user_access_token: str, open_id: str) -> Dict:
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

        try:
            response_text = await self._http_get(WECHAT_OAUTH2_USERINFO_URL,
                                                 params)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            raise

    async def get_subscribe_user_info(self, access_token: str,
                                      open_id: str) -> Dict:
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

        try:
            response_text = await self._http_get(WECHAT_SUBSCRIBE_USERINFO_URL,
                                                 params)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"获取关注用户信息异常: {e}")
            raise

    async def send_template_message(self,
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

        try:
            response_text = await self._http_post(api_url, message)
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"发送模板消息异常: {e}")
            raise


class WeChatManager:
    """微信管理器，管理多个微信客户端"""

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(WeChatManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化微信管理器"""
        if WeChatManager._initialized:
            return

        self.clients = {}
        self.redis_client = redis_manager.client
        self.platforms = []
        WeChatManager._initialized = True

    def register_platform(self, platform_config: Dict):
        """
        注册微信平台
        
        Args:
            platform_config: 平台配置
        """
        app_id = platform_config.get("app_id")
        app_secret = platform_config.get("app_secret")
        callback_addr = platform_config.get("callback_addr")
        scope = platform_config.get("scope")

        if not app_id or not app_secret:
            logger.error(f"注册微信平台失败: 缺少app_id或app_secret")
            return

        client = WeChatClient(app_id=app_id,
                              app_secret=app_secret,
                              callback_addr=callback_addr,
                              scope=scope)

        self.clients[app_id] = client
        self.platforms.append(platform_config)
        logger.info(f"注册微信平台成功: {app_id}, scope: {scope}")

    def get_client(self, app_id: str) -> Optional[WeChatClient]:
        """
        获取微信客户端
        
        Args:
            app_id: 微信AppID
            
        Returns:
            Optional[WeChatClient]: 微信客户端
        """
        return self.clients.get(app_id)

    def get_wechat_adapter(self,
                           scope: str) -> Tuple[Optional[str], Optional[Dict]]:
        """
        从配置中获取微信平台适配器
        
        Args:
            scope: 平台范围标识
            
        Returns:
            Tuple[str, Dict]: 返回appId和平台配置
        """
        for platform in self.platforms:
            if platform.get("scope") == scope:
                return platform.get("app_id"), platform
        return None, None

    async def get_wechat_access_token(self, app_id: str) -> str:
        """
        获取微信AccessToken
        
        Args:
            app_id: 微信AppID
            
        Returns:
            str: 微信AccessToken
        """
        return await self.refresh_wechat_access_token(app_id, False)

    async def refresh_wechat_access_token(self, app_id: str) -> str:
        # 获取客户端
        client = self.get_client(app_id)
        if not client:
            logger.error(f"未找到appId为{app_id}的微信客户端")
            return ""

        return await client.get_access_token()

    async def get_wechat_ticket(self, app_id: str) -> str:
        """
        获取微信JSApiTicket
        
        Args:
            app_id: 微信AppID
            
        Returns:
            str: 微信JSApiTicket
        """
        return await self.refresh_wechat_ticket(app_id, False)

    async def refresh_wechat_ticket(self, app_id: str) -> str:
        """
        刷新微信JSApiTicket
        
        Args:
            app_id: 微信AppID
            refresh: 是否强制刷新
            
        Returns:
            str: 微信JSApiTicket
        """
        # 首先获取AccessToken
        access_token = await self.get_wechat_access_token(app_id)
        if not access_token:
            return ""

        # 获取客户端
        client = self.get_client(app_id)
        if not client:
            logger.error(f"未找到appId为{app_id}的微信客户端")
            return ""

        return await client.get_jsapi_ticket(access_token)


# 创建全局微信管理器实例
wechat_manager = WeChatManager()
