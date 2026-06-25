"""Channel 管理 — 加载配置、初始化、启停。"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.config import config as app_config
from app.models import ChannelConfig, InboundMsg, OutboundMsg
from .bus import msg_manager, InboundMsg as _InboundMsg, OutboundMsg as _OutboundMsg

logger = logging.getLogger(__name__)

# 内置 Channel 注册表
_CHANNEL_TYPES: dict[str, type] = {}


def register_channel_type(name: str, cls: type):
    """注册 Channel 类型。"""
    _CHANNEL_TYPES[name] = cls


def _load_channel_instances() -> list:
    """从 data/channels.json 加载配置并创建 Channel 实例。"""
    config_path = app_config.data_dir / "channels.json"
    if not config_path.exists():
        # 创建默认配置
        config_path.parent.mkdir(parents=True, exist_ok=True)
        default = {"channels": []}
        config_path.write_text(json.dumps(default, indent=2, ensure_ascii=False))
        logger.info(f"已创建默认 Channel 配置: {config_path}")
        return []

    data = json.loads(config_path.read_text())
    channels = []
    for item in data.get("channels", []):
        if not item.get("enabled", True):
            continue
        ch_type = item.get("type", "")
        if ch_type not in _CHANNEL_TYPES:
            logger.warning(f"未知 Channel 类型: {ch_type}")
            continue
        cls = _CHANNEL_TYPES[ch_type]
        instance = cls(item)
        channels.append(instance)
        logger.info(f"Channel 已加载: {ch_type}/{item.get('name', ch_type)}")
    return channels


class ChannelManager:
    """管理所有 Channel 的生命周期和消息路由。"""

    def __init__(self):
        # 注册内置 Channel 类型
        from . import cli as _  # noqa
        self.channels: dict[str, Any] = {}
        self._dispatch_task: asyncio.Task | None = None

    async def start_all(self):
        """启动所有启用的 Channel。"""
        instances = _load_channel_instances()
        if not instances:
            logger.info("没有启用的 Channel")
            return

        for ch in instances:
            ch_name = f"{ch.name}-{ch.config.get('name', ch.name)}"
            msg_manager.register_channel(ch_name)
            self.channels[ch_name] = ch
            asyncio.create_task(self._run_channel(ch_name, ch))

        # 启动出站分发
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info(f"已启动 {len(self.channels)} 个 Channel")

    async def _run_channel(self, name: str, ch):
        """运行单个 Channel 并监听其出站消息。"""
        try:
            # 启动 Channel（阻塞直到 Channel 自己退出）
            await ch.start()
        except Exception:
            logger.exception(f"Channel {name} 启动失败")
            return

        # Channel 启动后，监听出站消息
        try:
            while True:
                msg = await msg_manager.consume_outbound(name)
                try:
                    await ch.send(msg)
                except Exception:
                    logger.exception(f"Channel {name} 发送消息失败")
        except asyncio.CancelledError:
            pass

    async def _dispatch_loop(self):
        """监听入站消息，转给 Orchestrator。"""
        from app.gateway.orchestrator import get_orchestrator
        from app.gateway.manager.agent_manager import agent_manager
        from app.gateway.manager.ws_manager import ws_manager

        orch = get_orchestrator(agent_manager, ws_manager)
        while True:
            try:
                msg = await msg_manager.consume_inbound()
                # 通过 orchestrator 处理
                result = await orch.handle_task(msg.content)
                if result.get("status") == "failed":
                    reply = f"抱歉，处理失败: {result.get('error', '未知错误')}"
                else:
                    reply = "任务已接收，处理中..."
                    if result.get("plan"):
                        reply += "\n" + "\n".join(
                            f"  → {p['agent']}: {p['task']}" for p in result["plan"]
                        )
                # 发送回复
                await msg_manager.publish_outbound(OutboundMsg(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=reply,
                ))
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("消息分发异常")

    async def stop_all(self):
        """停止所有 Channel。"""
        if self._dispatch_task:
            self._dispatch_task.cancel()
        for name, ch in self.channels.items():
            try:
                await ch.stop()
            except Exception:
                pass


# 单例
channel_manager = ChannelManager()


# 导入内置类型
from .bus import InboundMsg, OutboundMsg, msg_manager  # noqa: E402, F401
