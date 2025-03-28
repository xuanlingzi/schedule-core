"""
消息队列连接管理器
提供RabbitMQ连接池的管理和连接获取功能
"""

import json
import logging
from typing import Any, Callable, Optional, Union, TypeVar, cast, Dict
from contextlib import contextmanager

import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exchange_type import ExchangeType
from pika.spec import PERSISTENT_DELIVERY_MODE, Basic

from schedule_core.config.settings import core_settings as settings

logger = logging.getLogger(__name__)

T = TypeVar("T")  # 用于回调函数的返回类型


class RabbitMQManager:
    """
    RabbitMQ 连接管理器，提供与 RabbitMQ 交互的接口。
    使用单例模式确保全局只有一个连接管理器实例。

    支持以下功能：
    - 连接管理（自动重连、懒加载）
    - 消息发布
    - 队列订阅
    - 上下文管理器支持
    """

    _instance: Optional["RabbitMQManager"] = None
    _connection: Optional[BlockingConnection] = None
    _channel: Optional[BlockingChannel] = None
    _connection_params: Optional[pika.ConnectionParameters] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RabbitMQManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._connection_params is None:
            self._initialize()

    def _initialize(self):
        """初始化RabbitMQ连接参数"""
        credentials = pika.PlainCredentials(
            username=settings.RABBITMQ_USER, password=settings.RABBITMQ_PASSWORD
        )
        self._connection_params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=settings.RABBITMQ_HEARTBEAT,
            blocked_connection_timeout=settings.RABBITMQ_BLOCKED_CONNECTION_TIMEOUT,
        )

    @property
    def connection(self) -> BlockingConnection:
        """懒加载连接属性"""
        if not self._connection or self._connection.is_closed:
            self._connect()
        return cast(BlockingConnection, self._connection)

    @property
    def channel(self) -> BlockingChannel:
        """懒加载通道属性"""
        if not self._channel or not self._channel.is_open:
            self._channel = self.connection.channel()
        return cast(BlockingChannel, self._channel)

    def _connect(self) -> None:
        """建立RabbitMQ连接"""
        try:
            self._connection = pika.BlockingConnection(self._connection_params)
            self._channel = self._connection.channel()
            logger.info("成功连接到RabbitMQ")
        except Exception as e:
            logger.error("连接RabbitMQ失败: %s", str(e))
            self._connection = None
            self._channel = None
            raise

    def close(self) -> None:
        """关闭RabbitMQ连接"""
        if self._connection and not self._connection.is_closed:
            if self._channel and self._channel.is_open:
                self._channel.close()
            self._connection.close()
            logger.info("RabbitMQ连接已关闭")
        self._connection = None
        self._channel = None

    @contextmanager
    def connection_context(self):
        """提供连接上下文管理器"""
        try:
            yield self
        finally:
            self.close()

    def get_exchange_type(self, exchange_type_name: str) -> ExchangeType:
        """根据名称获取交换类型"""
        exchange_types = {
            "topic": ExchangeType.topic,
            "direct": ExchangeType.direct,
            "fanout": ExchangeType.fanout,
            "headers": ExchangeType.headers,
        }
        return exchange_types.get(exchange_type_name.lower(), ExchangeType.direct)

    def publish_message(
        self,
        exchange_name: str,
        exchange_type: str,
        message: Union[str, dict, Any],
        routing_key: str = "",
        queue_name: str = "",
        durable: bool = True,
    ) -> None:
        """
        发布消息到交换机

        Args:
            exchange_name: 交换机名称
            exchange_type: 交换机类型 (topic, direct, fanout, headers)
            message: 要发送的消息内容
            routing_key: 路由键，默认使用交换机名称
            queue_name: 队列名称，对于topic交换机如果未指定则使用交换机名称
            durable: 持久化标志
        """
        try:
            # 设置默认值
            if exchange_type.lower() == "topic" and not queue_name:
                queue_name = exchange_name

            if not routing_key:
                routing_key = exchange_name

            # 获取交换类型并声明交换机
            exchange_type_value = self.get_exchange_type(exchange_type)
            self.channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type_value,
                durable=durable,
                auto_delete=False,
            )

            # 准备消息体
            message_body = (
                message.encode() if isinstance(message, str) else json.dumps(message).encode()
            )

            # 发布消息
            self.channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=PERSISTENT_DELIVERY_MODE,
                    content_type="application/json",
                ),
            )

            logger.info("成功发布消息到交换机 %s: %s", exchange_name, message)
        except Exception as e:
            logger.error("发布消息失败: %s", str(e))
            raise

    def subscribe(
        self,
        exchange_name: str,
        exchange_type: str,
        callback: Optional[Callable[[bytes], Any]] = None,
        queue_name: str = "",
        routing_key: str = "",
        durable: bool = True,
        exclusive: bool = False,
    ) -> None:
        """
        订阅队列消息

        Args:
            exchange_name: 交换机名称
            exchange_type: 交换机类型 (topic, direct, fanout, headers)
            callback: 消息处理回调函数
            queue_name: 队列名称，如果未指定则使用交换机名称
            routing_key: 路由键，默认使用交换机名称
            durable: 持久化标志
            exclusive: 是否为排他队列
        """
        try:
            # 设置默认值
            if not queue_name:
                queue_name = exchange_name

            if not routing_key:
                routing_key = exchange_name

            # 获取交换类型并声明交换机
            exchange_type_value = self.get_exchange_type(exchange_type)
            self.channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type_value,
                durable=durable,
                auto_delete=False,
            )

            # 声明队列
            self.channel.queue_declare(queue=queue_name, durable=durable, exclusive=exclusive)

            # 绑定队列到交换机
            self.channel.queue_bind(
                queue=queue_name, exchange=exchange_name, routing_key=routing_key
            )

            # 定义消息处理函数
            def process_message(
                ch: BlockingChannel,
                method: Basic.Deliver,
                properties: pika.BasicProperties,
                body: bytes,
            ) -> None:
                try:
                    if callback:
                        callback(body)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error("处理消息失败: %s", str(e))
                    # 消息处理失败，拒绝消息并重新入队
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            # 设置QoS（服务质量）并订阅队列
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=queue_name, on_message_callback=process_message)

            # 开始消费
            logger.info("开始从队列 %s 消费消息", queue_name)
            self.channel.start_consuming()
        except Exception as e:
            logger.error("订阅队列失败: %s", str(e))
            raise

    def __str__(self) -> str:
        return f"RabbitMQManager(connection={self._connection}, channel={self._channel})"

    def __enter__(self) -> "RabbitMQManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# 创建全局RabbitMQ管理器实例
mq_manager = RabbitMQManager()
