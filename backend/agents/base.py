"""智能体基类"""

import abc
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

import httpx


class BaseAgent(abc.ABC):
    """所有智能体的抽象基类"""

    def __init__(self, name: str, model_endpoint: str, model_name: str, api_key: str = ""):
        self.name = name
        self.model_endpoint = model_endpoint
        self.model_name = model_name
        self.api_key = api_key

    @property
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, messages: List[Dict[str, str]], stream: bool = True) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "temperature": 0.3 if not stream else 0.7,
        }

    async def _stream_chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """通用的流式 API 调用（支持 OpenAI 及非标准 SSE 格式）"""
        # API Key 缺失时给出明确提示，避免 401 空异常
        if not self.api_key and "deepseek" in self.model_endpoint:
            yield "⚠️ DeepSeek API 密钥未配置，请在环境变量中设置 DEEPSEEK_API_KEY。"
            return

        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", self.model_endpoint,
                json=payload, headers=self._headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            # OpenAI 标准格式
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                                continue
                            # 兼容：Mimo 等非标准格式，choices[0].text
                            text = data.get("choices", [{}])[0].get("text", "")
                            if text:
                                yield text
                                continue
                            # 兼容：直接返回 content 字段
                            direct = data.get("content", "")
                            if direct:
                                yield direct
                                continue
                        except json.JSONDecodeError:
                            continue

    async def _non_stream_chat(self, messages: List[Dict[str, str]], timeout: float = 60.0) -> str:
        """非流式调用"""
        payload = self._build_payload(messages, stream=False)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                self.model_endpoint, json=payload, headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    async def chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """公开的流式对话接口（封装 _stream_chat）"""
        async for chunk in self._stream_chat(messages):
            yield chunk

    @abc.abstractmethod
    def system_prompt(self) -> str:
        """返回该智能体的系统提示词"""
        ...

    @abc.abstractmethod
    async def process(self, user_input: str, context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """处理用户输入并流式返回"""
        ...
