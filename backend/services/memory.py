from __future__ import annotations

import json
import math
import time
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from utils.embedding import EmbeddingUtil


class MemoryManager:
    """4层记忆系统：MySQL持久化 + Redis热缓存"""

    def __init__(self):
        self._embedder = EmbeddingUtil(dim=128)
        self._redis = None
        self._working_ttl = 3600  # 1小时
        self._max_working = 30  # Working Memory超过30条触发增量摘要
        self._decay_lambda = 0.1  # 时间衰减系数（7天半衰期）
        # 内存后备（无Redis/MySQL时降级）
        self._fallback_working: Dict[str, List[Dict[str, Any]]] = {}
        self._fallback_episodic: Dict[str, List[Dict[str, Any]]] = {}
        self._fallback_semantic: Dict[str, List[Dict[str, Any]]] = {}
        self._fallback_procedural: Dict[str, List[Dict[str, Any]]] = {}

    def _get_redis(self):
        try:
            from models.database import db_manager
            return db_manager.redis_client
        except Exception:
            return None

    async def store(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        db: Optional[AsyncSession] = None,
    ) -> str:
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        embedding = self._embedder.embed(content)

        # Working Memory → Redis (TTL 1h)
        if memory_type == "working":
            redis = self._get_redis()
            if redis:
                try:
                    key = f"memory:working:{user_id}"
                    entry = json.dumps({
                        "memory_id": memory_id,
                        "content": content,
                        "importance": importance,
                        "timestamp": time.time(),
                    })
                    await redis.rpush(key, entry)
                    await redis.expire(key, self._working_ttl)
                    # 检查是否需要增量摘要
                    count = await redis.llen(key)
                    if count > self._max_working and db:
                        await self.consolidate(user_id, db)
                    return memory_id
                except Exception as e:
                    logger.debug(f"Redis store failed, using fallback: {e}")

            # Fallback to in-memory
            if user_id not in self._fallback_working:
                self._fallback_working[user_id] = []
            self._fallback_working[user_id].append({
                "memory_id": memory_id, "content": content,
                "importance": importance, "timestamp": time.time(),
            })
            if len(self._fallback_working[user_id]) > 20:
                self._fallback_working[user_id] = self._fallback_working[user_id][-20:]
            return memory_id

        # 其他类型 → MySQL
        if db:
            try:
                from models.memory import MemoryEntry
                entry = MemoryEntry(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                    importance=importance,
                    embedding=embedding,
                )
                db.add(entry)
                await db.flush()
                return memory_id
            except Exception as e:
                logger.debug(f"MySQL store failed, using fallback: {e}")

        # Fallback to in-memory
        fallback_map = {
            "episodic": self._fallback_episodic,
            "semantic": self._fallback_semantic,
            "procedural": self._fallback_procedural,
        }
        store = fallback_map.get(memory_type, self._fallback_episodic)
        if user_id not in store:
            store[user_id] = []
        store[user_id].append({
            "memory_id": memory_id, "content": content,
            "importance": importance, "timestamp": time.time(),
            "embedding": embedding,
        })
        return memory_id

    async def search(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[str] = None,
        top_k: int = 5,
        db: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        query_embedding = self._embedder.embed(query)
        all_results = []

        # Working Memory from Redis
        if memory_type in (None, "working"):
            working_results = await self._search_working(user_id, query_embedding)
            all_results.extend(working_results)

        # Episodic/Semantic/Procedural from MySQL
        if memory_type in (None, "episodic", "semantic", "procedural") and db:
            db_results = await self._search_db(user_id, query_embedding, memory_type, top_k, db)
            all_results.extend(db_results)
        elif memory_type in (None, "episodic", "semantic", "procedural"):
            # Fallback to in-memory
            fallback_results = self._search_fallback(user_id, query_embedding, memory_type)
            all_results.extend(fallback_results)

        # 按相关性排序
        all_results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return all_results[:top_k]

    async def _search_working(self, user_id: str, query_embedding: List[float]) -> List[Dict]:
        redis = self._get_redis()
        if redis:
            try:
                key = f"memory:working:{user_id}"
                entries = await redis.lrange(key, 0, -1)
                results = []
                for entry_json in entries:
                    entry = json.loads(entry_json)
                    sim = EmbeddingUtil.cosine_similarity(query_embedding, self._embedder.embed(entry["content"]))
                    results.append({
                        "memory_id": entry["memory_id"],
                        "memory_type": "working",
                        "content": entry["content"],
                        "importance": entry.get("importance", 0.5),
                        "timestamp": entry.get("timestamp", 0),
                        "relevance": sim,
                    })
                return results
            except Exception:
                pass

        # Fallback
        results = []
        for entry in self._fallback_working.get(user_id, []):
            sim = EmbeddingUtil.cosine_similarity(query_embedding, entry.get("embedding", []))
            results.append({
                "memory_id": entry["memory_id"], "memory_type": "working",
                "content": entry["content"], "importance": entry.get("importance", 0.5),
                "timestamp": entry.get("timestamp", 0), "relevance": sim,
            })
        return results

    async def _search_db(
        self, user_id: str, query_embedding: List[float],
        memory_type: Optional[str], top_k: int, db: AsyncSession,
    ) -> List[Dict]:
        try:
            from models.memory import MemoryEntry
            stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
            if memory_type:
                stmt = stmt.where(MemoryEntry.memory_type == memory_type)
            stmt = stmt.order_by(desc(MemoryEntry.created_at)).limit(100)
            result = await db.execute(stmt)
            entries = result.scalars().all()

            scored = []
            for entry in entries:
                if entry.embedding:
                    sim = EmbeddingUtil.cosine_similarity(query_embedding, entry.embedding)
                else:
                    sim = 0.0
                # 时间衰减
                age_hours = (time.time() - entry.created_at.timestamp()) / 3600 if entry.created_at else 0
                decay = math.exp(-self._decay_lambda * age_hours / 168)  # 168h = 7天
                adjusted_score = entry.importance * decay * sim

                scored.append({
                    "memory_id": f"db_{entry.id}",
                    "memory_type": entry.memory_type,
                    "content": entry.content,
                    "importance": entry.importance,
                    "timestamp": entry.created_at.timestamp() if entry.created_at else 0,
                    "relevance": adjusted_score,
                })

            return scored
        except Exception as e:
            logger.debug(f"DB search failed: {e}")
            return []

    def _search_fallback(self, user_id: str, query_embedding: List[float], memory_type: Optional[str]) -> List[Dict]:
        stores = {}
        if memory_type:
            fallback_map = {
                "episodic": self._fallback_episodic,
                "semantic": self._fallback_semantic,
                "procedural": self._fallback_procedural,
            }
            store = fallback_map.get(memory_type, {})
            stores[memory_type] = store.get(user_id, [])
        else:
            stores = {
                "episodic": self._fallback_episodic.get(user_id, []),
                "semantic": self._fallback_semantic.get(user_id, []),
                "procedural": self._fallback_procedural.get(user_id, []),
            }

        scored = []
        for mtype, entries in stores.items():
            for entry in entries:
                sim = EmbeddingUtil.cosine_similarity(query_embedding, entry.get("embedding", []))
                scored.append({
                    "memory_id": entry["memory_id"], "memory_type": mtype,
                    "content": entry["content"], "importance": entry.get("importance", 0.5),
                    "timestamp": entry.get("timestamp", 0), "relevance": sim,
                })
        return scored

    async def consolidate(self, user_id: str, db: Optional[AsyncSession] = None) -> int:
        """增量摘要：Working Memory超过30条时LLM压缩"""
        # 从Redis获取Working Memory
        working_entries = []
        redis = self._get_redis()
        if redis:
            try:
                key = f"memory:working:{user_id}"
                raw_entries = await redis.lrange(key, 0, -1)
                working_entries = [json.loads(e) for e in raw_entries]
            except Exception:
                pass
        else:
            working_entries = self._fallback_working.get(user_id, [])

        if len(working_entries) < self._max_working:
            return 0

        # LLM压缩摘要
        try:
            from utils.llm_client import get_llm_client
            llm = get_llm_client()
            contents = [e["content"][:100] for e in working_entries[:10]]
            prompt = f"请将以下对话片段压缩为一段简洁的摘要（100字以内）：\n{'；'.join(contents)}"
            response = await llm.invoke([{"role": "user", "content": prompt}], temperature=0)
            summary = response.content.strip()
        except Exception:
            summary = "；".join(e["content"][:50] for e in working_entries[:5])

        # 存储摘要到Episodic Memory
        await self.store(user_id, "episodic", f"[整合记忆] {summary}", importance=0.7, db=db)

        # 清理Working Memory
        if redis:
            try:
                key = f"memory:working:{user_id}"
                await redis.delete(key)
            except Exception:
                pass
        else:
            self._fallback_working[user_id] = []

        logger.info(f"Memory consolidated: user={user_id}, {len(working_entries)} entries merged")
        return len(working_entries)

    def get_context(self, user_id: str, query: str) -> str:
        """同步获取上下文（兼容旧接口）"""
        results = self._search_fallback_sync(user_id, query)
        if not results:
            return ""
        parts = []
        for r in results:
            if r["relevance"] > 0.3:
                parts.append(f"[{r['memory_type']}] {r['content']}")
        return "\n".join(parts) if parts else ""

    def _search_fallback_sync(self, user_id: str, query: str) -> List[Dict]:
        """同步搜索（兼容旧接口）"""
        query_embedding = self._embedder.embed(query)
        stores = {
            "working": self._fallback_working.get(user_id, []),
            "episodic": self._fallback_episodic.get(user_id, []),
            "semantic": self._fallback_semantic.get(user_id, []),
            "procedural": self._fallback_procedural.get(user_id, []),
        }
        scored = []
        for mtype, entries in stores.items():
            for entry in entries:
                sim = EmbeddingUtil.cosine_similarity(query_embedding, entry.get("embedding", []))
                scored.append({
                    "memory_id": entry.get("memory_id", ""), "memory_type": mtype,
                    "content": entry.get("content", ""), "importance": entry.get("importance", 0.5),
                    "timestamp": entry.get("timestamp", 0), "relevance": sim,
                })
        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored[:5]

    async def load_user_profile(self, user_id: str, db: Optional[AsyncSession] = None) -> Optional[Dict]:
        """会话交接：加载用户画像"""
        if db:
            try:
                from models.memory import UserProfile
                stmt = select(UserProfile).where(UserProfile.user_id == user_id)
                result = await db.execute(stmt)
                profile = result.scalar_one_or_none()
                if profile:
                    return {
                        "user_id": profile.user_id,
                        "role": profile.role,
                        "department": profile.department,
                        "preferences": profile.preferences or {},
                        "behavior_patterns": profile.behavior_patterns or [],
                    }
            except Exception as e:
                logger.debug(f"Load user profile failed: {e}")
        return None

    async def track_behavior(self, user_id: str, action: str, db: Optional[AsyncSession] = None) -> None:
        """行为模式追踪"""
        if db:
            try:
                from models.memory import ProceduralRule
                stmt = select(ProceduralRule).where(
                    and_(ProceduralRule.user_id == user_id, ProceduralRule.pattern == action)
                )
                result = await db.execute(stmt)
                rule = result.scalar_one_or_none()
                if rule:
                    rule.execution_count += 1
                    rule.last_used = func.now()
                else:
                    rule = ProceduralRule(user_id=user_id, pattern=action)
                    db.add(rule)
                await db.flush()
            except Exception as e:
                logger.debug(f"Track behavior failed: {e}")
