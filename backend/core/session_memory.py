"""Redis 分布式会话记忆模型"""

import json
import logging
from typing import Dict, List, Optional, Any

import redis.asyncio as aioredis

from backend.config import RedisConfig

logger = logging.getLogger(__name__)


class SessionMemory:
    """基于 Redis 的多轮会话持久化与上下文重写支持"""

    def __init__(self, cfg: RedisConfig):
        self.cfg = cfg
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        self._client = aioredis.Redis(
            host=self.cfg.host,
            port=self.cfg.port,
            db=self.cfg.db,
            password=self.cfg.password or None,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info("Redis 连接成功")

    async def close(self):
        if self._client:
            await self._client.close()

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _history_key(self, session_id: str) -> str:
        return f"history:{session_id}"

    async def set_session(self, session_id: str, metadata: Dict[str, Any]):
        if not self._client:
            return
        key = self._session_key(session_id)
        await self._client.hset(key, mapping=metadata)
        await self._client.expire(key, self.cfg.session_ttl)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self._client:
            return None
        key = self._session_key(session_id)
        data = await self._client.hgetall(key)
        return data if data else None

    async def push_message(self, session_id: str, role: str, content: str):
        """追加一条对话记录"""
        if not self._client:
            return
        key = self._history_key(session_id)
        msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await self._client.rpush(key, msg)
        await self._client.expire(key, self.cfg.session_ttl)

    async def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """获取最近 N 轮对话历史"""
        if not self._client:
            return []
        key = self._history_key(session_id)
        raw = await self._client.lrange(key, -limit * 2, -1)
        messages = []
        for r in raw:
            try:
                messages.append(json.loads(r))
            except json.JSONDecodeError:
                continue
        return messages

    async def get_affective_history(self, session_id: str, window: int = 3) -> List[Dict[str, Any]]:
        """获取情感分析用历史（仅最近 window 轮 user 消息）"""
        if not self._client:
            return []
        key = self._history_key(session_id)
        raw = await self._client.lrange(key, -window * 4, -1)
        user_msgs = []
        for r in raw:
            try:
                msg = json.loads(r)
                if msg["role"] == "user":
                    user_msgs.append(msg)
                    if len(user_msgs) >= window:
                        break
            except json.JSONDecodeError:
                continue
        return user_msgs
