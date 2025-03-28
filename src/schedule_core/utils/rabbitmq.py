import json
import logging
from typing import Any, Callable, Optional, Union, TypeVar, cast
from contextlib import contextmanager

import pika
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exchange_type import ExchangeType
from pika.spec import PERSISTENT_DELIVERY_MODE, Basic

from schedule_core.config.settings import core_settings as settings

logger = logging.getLogger(__name__)

T = TypeVar("T")  # 用于回调函数的返回类型


class RabbitMQClient:
    """
    RabbitMQ 客户端类，提供与 RabbitMQ 交互的接口。

    支持以下功能：
    - 连接管理（自动重连、懒加载）
    - 消息发布
    - 队列订阅
    - 上下文管理器支持
    """

    def __init__(self, connection_params=None) -> None:
        self._connection: Optional[BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
        self._connection_params = connection_params or self._create_connection_params()

    def _create_connection_params(self) -> pika.ConnectionParameters:
        """创建 RabbitMQ 连接参数"""
        credentials = pika.PlainCredentials(
            username=settings.RABBITMQ_USER, password=settings.RABBITMQ_PASSWORD
        )
        return pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=30,
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
        """建立 RabbitMQ 连接"""
        try:
            self._connection = pika.BlockingConnection(self._connection_params)
            self._channel = self._connection.channel()
            logger.info("成功连接到 RabbitMQ")
        except Exception as e:
            logger.error("连接 RabbitMQ 失败: %s", str(e))
            self._connection = None
            self._channel = None
            raise

    def close(self) -> None:
        """关闭 RabbitMQ 连接"""
        if self._connection and not self._connection.is_closed:
            if self._channel and self._channel.is_open:
                self._channel.close()
            self._connection.close()
            logger.info("RabbitMQ 连接已关闭")
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
            queue_name: 队列名称，对于 topic 交换机如果未指定则使用交换机名称
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
                message.encode()
                if isinstance(message, str)
                else json.dumps(message).encode()
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
            self.channel.queue_declare(
                queue=queue_name, durable=durable, exclusive=exclusive
            )

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

            # 设置 QoS（服务质量）并订阅队列
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name, on_message_callback=process_message
            )

            # 开始消费
            logger.info("开始从队列 %s 消费消息", queue_name)
            self.channel.start_consuming()
        except Exception as e:
            logger.error("订阅队列失败: %s", str(e))
            raise

    def __str__(self) -> str:
        return f"RabbitMQClient(connection={self._connection}, channel={self._channel})"

    def __enter__(self) -> "RabbitMQClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# 为了保持与旧代码的兼容性，提供以下别名方法
class LegacyRabbitMQClient(RabbitMQClient):
    """提供向后兼容的 RabbitMQ 客户端"""

    def reconnect(self) -> None:
        """兼容性方法，实际上什么都不做，因为连接已经是懒加载的"""
        pass

    def publish_on_queue(
        self,
        exchange_name: str,
        exchange_type: str,
        queue_name: str = "",
        routing_key: str = "",
        consumer_tag: str = "",
        durable_queue: bool = True,
        message: Union[str, dict, Any] = None,
    ) -> None:
        """向后兼容的发布方法"""
        self.publish_message(
            exchange_name=exchange_name,
            exchange_type=exchange_type,
            message=message,
            routing_key=routing_key,
            queue_name=queue_name,
            durable=durable_queue,
        )

    def subscribe_to_queue(
        self,
        exchange_name: str,
        exchange_type: str,
        queue_name: str = "",
        routing_key: str = "",
        consumer_tag: str = "",
        durable_queue: bool = True,
        consumer_exclusive: bool = False,
        callback: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        """向后兼容的订阅方法"""
        self.subscribe(
            exchange_name=exchange_name,
            exchange_type=exchange_type,
            callback=callback,
            queue_name=queue_name,
            routing_key=routing_key,
            durable=durable_queue,
            exclusive=consumer_exclusive,
        )
