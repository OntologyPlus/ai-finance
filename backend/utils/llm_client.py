from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional

from loguru import logger
from openai import OpenAI
from pydantic import BaseModel

from models.config import settings
from utils.embedding import EmbeddingUtil


class AIMessage(BaseModel):
    role: str = "assistant"
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None


class TokenBucket:
    def __init__(self, rate: float = 2.0, capacity: int = 10):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.95, ttl_seconds: int = 3600):
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self._embedder = None  # Lazy init to avoid circular import
        self._entries: List[Dict[str, Any]] = []
        self._max_entries = 1000

    def _get_embedder(self):
        if self._embedder is None:
            from utils.embedding import EmbeddingUtil
            self._embedder = EmbeddingUtil(dim=128)
        return self._embedder

    def _extract_user_msg(self, messages: List[Dict[str, str]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return m.get("content", "")
        return ""

    def _hash_key(self, messages: List[Dict[str, str]], tools: Optional[List] = None) -> str:
        payload = json.dumps(
            [{"role": m.get("role"), "content": m.get("content", "")} for m in messages],
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, messages: List[Dict[str, str]], tools: Optional[List] = None) -> Optional[AIMessage]:
        if tools:
            return None
        user_msg = self._extract_user_msg(messages)
        if not user_msg:
            return None
        embedder = self._get_embedder()
        query_emb = embedder.embed(user_msg)
        best_sim, best_entry = 0.0, None
        for entry in self._entries:
            sim = EmbeddingUtil.cosine_similarity(query_emb, entry["embedding"])
            if sim > best_sim:
                best_sim, best_entry = sim, entry
        if best_sim >= self.similarity_threshold and best_entry is not None:
            if time.time() - best_entry["timestamp"] <= self.ttl_seconds:
                return best_entry["response"]
        return None

    def set(self, messages: List[Dict[str, str]], response: AIMessage, tools: Optional[List] = None) -> None:
        if tools:
            return
        user_msg = self._extract_user_msg(messages)
        if not user_msg:
            return
        embedder = self._get_embedder()
        emb = embedder.embed(user_msg)
        self._entries.append({
            "embedding": emb,
            "response": response,
            "timestamp": time.time(),
            "hash": self._hash_key(messages),
        })
        if len(self._entries) > self._max_entries:
            self._evict()

    def _evict(self):
        # Remove oldest entries
        self._entries = self._entries[-self._max_entries // 2:]

    def clear(self) -> None:
        self._entries.clear()


class LLMClient:
    def __init__(self) -> None:
        self._api_url = settings.LLM_API_URL
        self._api_key = settings.LLM_API_KEY
        self._model = settings.LLM_MODEL
        self._mock_mode = not self._api_key or self._api_key == "your-api-key-here"
        self._rate_limiter = TokenBucket(rate=2.0, capacity=10)
        self._cache = SemanticCache(similarity_threshold=0.95, ttl_seconds=3600)
        self._bound_tools: Optional[List[Dict[str, Any]]] = None
        self._client: Optional[OpenAI] = None

        if not self._mock_mode:
            try:
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._api_url,
                )
                logger.info(f"LLMClient initialized: model={self._model}, url={self._api_url}")
            except Exception as e:
                logger.warning(f"LLMClient init failed, falling back to mock mode: {e}")
                self._mock_mode = True

    def bind_tools(self, tools: List[Dict[str, Any]]) -> LLMClient:
        client = LLMClient.__new__(LLMClient)
        client._api_url = self._api_url
        client._api_key = self._api_key
        client._model = self._model
        client._mock_mode = self._mock_mode
        client._rate_limiter = self._rate_limiter
        client._cache = self._cache
        client._client = self._client
        client._bound_tools = tools
        return client

    async def invoke(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> AIMessage:
        active_tools = tools or self._bound_tools

        cached = self._cache.get(messages, active_tools)
        if cached is not None:
            logger.debug("LLM cache hit")
            return cached

        await self._rate_limiter.acquire()

        if self._mock_mode:
            return self._mock_invoke(messages, active_tools)

        return await self._invoke_with_retry(messages, active_tools, temperature)

    async def _invoke_with_retry(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
        max_retries: int = 3,
    ) -> AIMessage:
        last_error = None
        for attempt in range(max_retries):
            try:
                kwargs: Dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = await asyncio.to_thread(
                    self._client.chat.completions.create,
                    **kwargs,
                )

                choice = response.choices[0]
                msg = choice.message

                result = AIMessage(
                    role="assistant",
                    content=msg.content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (msg.tool_calls or [])
                    ] if msg.tool_calls else None,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    } if response.usage else None,
                )

                self._cache.set(messages, result, tools)
                return result

            except Exception as e:
                last_error = e
                error_str = str(e)
                is_rate_limit = "429" in error_str
                is_timeout = "timeout" in error_str.lower() or "timed out" in error_str.lower()

                if is_rate_limit:
                    wait = (2 ** attempt) * 2
                    logger.warning(f"Rate limited (429), retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                elif is_timeout:
                    wait = (2 ** attempt) * 1
                    logger.warning(f"Timeout, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                else:
                    wait = (2 ** attempt) * 1
                    logger.error(f"LLM invoke error: {e}, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)

        logger.error(f"LLM invoke failed after {max_retries} retries: {last_error}")
        return AIMessage(content=f"[LLM调用失败] {last_error}")

    def stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> Iterator[str]:
        active_tools = tools or self._bound_tools

        if self._mock_mode:
            yield from self._mock_stream(messages)
            return

        try:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
            if active_tools:
                kwargs["tools"] = active_tools
                kwargs["tool_choice"] = "auto"

            response = self._client.chat.completions.create(**kwargs)

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield f"[流式调用失败] {e}"

    def _mock_invoke(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]]) -> AIMessage:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        if tools:
            first_tool = tools[0]
            func = first_tool.get("function", {})
            tool_name = func.get("name", "unknown_tool")
            mock_args = "{}"
            params = func.get("parameters", {}).get("properties", {})
            if params:
                first_param = next(iter(params))
                mock_args = json.dumps({first_param: "示例值"})

            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": mock_args,
                        },
                    }
                ],
            )

        return AIMessage(
            content=f"[Mock模式] 收到您的消息：{user_msg[:100]}。这是模拟回复，请配置LLM_API_KEY以启用真实AI对话。",
        )

    def _mock_stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        response = f"[Mock模式] 收到您的消息：{user_msg[:100]}。这是模拟回复，请配置LLM_API_KEY以启用真实AI对话。"
        for char in response:
            yield char

    def clear_cache(self) -> None:
        self._cache.clear()


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
