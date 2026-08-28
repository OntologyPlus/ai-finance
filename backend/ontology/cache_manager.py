from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class CacheKeyDesign:
    BUDGET_REMAINING = "budget:{budget_id}:remaining_amount"
    BUDGET_USAGE = "budget:{budget_id}:usage_stats"
    BUDGET_EXECUTION_RATE = "budget:{l1_code}:execution_rate"
    ALERT_OPEN_COUNT = "alert:{l1_code}:open_count"
    ORG_BUDGET_SUMMARY = "org:{center_id}:budget_summary"


class CacheEntry(BaseModel):
    key: str
    value: str
    ttl_seconds: int = 3600
    version: int = 1
    updated_at: datetime = Field(default_factory=datetime.now)
    source: str = "db"


class CacheConsistencyResult(BaseModel):
    key: str
    cache_value: Optional[str] = None
    db_value: Optional[str] = None
    is_consistent: bool = True
    deviation: Optional[str] = None


class CacheConsistencyReport(BaseModel):
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    total_keys: int = 0
    consistent_count: int = 0
    inconsistent_count: int = 0
    results: List[CacheConsistencyResult] = Field(default_factory=list)
    summary: str = ""


class BudgetCacheManager:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_cache: Dict[str, CacheEntry] = {}
        self._key_design = CacheKeyDesign()

    def _get_cache(self, key: str) -> Optional[str]:
        if self._redis:
            try:
                return self._redis.get(key)
            except Exception as e:
                logger.warning(f"Redis get failed for key {key}: {e}")
                # Fallback to local cache with TTL check
                entry = self._local_cache.get(key)
                if entry is None:
                    return None
                if entry.ttl_seconds > 0:
                    elapsed = (datetime.now() - entry.updated_at).total_seconds()
                    if elapsed > entry.ttl_seconds:
                        del self._local_cache[key]
                        return None
                return entry.value
        # Local cache path with TTL check
        entry = self._local_cache.get(key)
        if entry is None:
            return None
        if entry.ttl_seconds > 0:
            elapsed = (datetime.now() - entry.updated_at).total_seconds()
            if elapsed > entry.ttl_seconds:
                del self._local_cache[key]
                return None
        return entry.value

    def _set_cache(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
            version=self._local_cache.get(key, CacheEntry(key=key, value="", version=0)).version + 1 if key in self._local_cache else 1,
        )
        self._local_cache[key] = entry

        if self._redis:
            try:
                self._redis.setex(key, ttl_seconds, value)
            except Exception as e:
                logger.warning(f"Redis set failed for key {key}: {e}")

    def _delete_cache(self, key: str) -> None:
        self._local_cache.pop(key, None)
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed for key {key}: {e}")

    def get_remaining_amount(self, budget_id: str) -> Optional[Decimal]:
        key = self._key_design.BUDGET_REMAINING.format(budget_id=budget_id)
        cached = self._get_cache(key)
        if cached is not None:
            try:
                return Decimal(cached)
            except Exception:
                return None
        return None

    def set_remaining_amount(
        self, budget_id: str, amount: Decimal, ttl_seconds: int = 1800
    ) -> None:
        key = self._key_design.BUDGET_REMAINING.format(budget_id=budget_id)
        self._set_cache(key, str(amount), ttl_seconds)
        logger.debug(f"Cache updated: {key} = {amount}")

    def update_remaining_amount_cache_aside(
        self,
        budget_id: str,
        db_remaining: Decimal,
        ttl_seconds: int = 1800,
    ) -> None:
        key = self._key_design.BUDGET_REMAINING.format(budget_id=budget_id)
        self._set_cache(key, str(db_remaining), ttl_seconds)
        logger.info(f"Cache-Aside update: budget {budget_id} remaining = {db_remaining}")

    def invalidate_remaining_amount(self, budget_id: str) -> None:
        key = self._key_design.BUDGET_REMAINING.format(budget_id=budget_id)
        self._delete_cache(key)
        logger.info(f"Cache invalidated: {key}")

    def get_usage_stats(self, budget_id: str) -> Optional[Dict[str, Any]]:
        key = self._key_design.BUDGET_USAGE.format(budget_id=budget_id)
        cached = self._get_cache(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                return None
        return None

    def set_usage_stats(
        self, budget_id: str, stats: Dict[str, Any], ttl_seconds: int = 600
    ) -> None:
        key = self._key_design.BUDGET_USAGE.format(budget_id=budget_id)
        self._set_cache(key, json.dumps(stats, default=str), ttl_seconds)

    def get_execution_rate(self, l1_code: str) -> Optional[Decimal]:
        key = self._key_design.BUDGET_EXECUTION_RATE.format(l1_code=l1_code)
        cached = self._get_cache(key)
        if cached:
            try:
                return Decimal(cached)
            except Exception:
                return None
        return None

    def set_execution_rate(
        self, l1_code: str, rate: Decimal, ttl_seconds: int = 300
    ) -> None:
        key = self._key_design.BUDGET_EXECUTION_RATE.format(l1_code=l1_code)
        self._set_cache(key, str(rate), ttl_seconds)

    def check_consistency(
        self, budget_id: str, db_remaining: Decimal
    ) -> CacheConsistencyResult:
        key = self._key_design.BUDGET_REMAINING.format(budget_id=budget_id)
        cached = self._get_cache(key)

        if cached is None:
            return CacheConsistencyResult(
                key=key,
                cache_value=None,
                db_value=str(db_remaining),
                is_consistent=True,
                deviation="缓存无值，需从DB加载",
            )

        try:
            cached_amount = Decimal(cached)
            deviation = abs(cached_amount - db_remaining)
            is_consistent = deviation == Decimal("0")

            if not is_consistent:
                logger.warning(
                    f"Cache inconsistency detected: {key} "
                    f"cache={cached_amount} db={db_remaining} deviation={deviation}"
                )
                self.set_remaining_amount(budget_id, db_remaining)

            return CacheConsistencyResult(
                key=key,
                cache_value=cached,
                db_value=str(db_remaining),
                is_consistent=is_consistent,
                deviation=str(deviation) if not is_consistent else None,
            )
        except Exception as e:
            return CacheConsistencyResult(
                key=key,
                cache_value=cached,
                db_value=str(db_remaining),
                is_consistent=False,
                deviation=f"解析错误: {e}",
            )

    async def run_consistency_check(
        self, db_session=None
    ) -> CacheConsistencyReport:
        results: List[CacheConsistencyResult] = []

        if db_session is not None and not hasattr(db_session, 'execute'):
            pass
        elif db_session is not None:
            try:
                from sqlalchemy import select
                from models.budget import BudgetItem

                stmt = select(BudgetItem).where(
                    BudgetItem.status.in_(["已授予", "执行中"])
                )
                db_result = await db_session.execute(stmt)
                items = db_result.scalars().all()

                for item in items:
                    db_remaining = Decimal(str(item.annual_amount)) - Decimal(str(item.used_amount))
                    result = self.check_consistency(item.budget_id, db_remaining)
                    results.append(result)
            except Exception as e:
                logger.error(f"Consistency check DB query failed: {e}")

        for key, entry in self._local_cache.items():
            if ":remaining_amount" in key and not any(r.key == key for r in results):
                results.append(CacheConsistencyResult(
                    key=key,
                    cache_value=entry.value,
                    db_value=None,
                    is_consistent=True,
                    deviation="缓存有值但DB未查询",
                ))

        consistent = sum(1 for r in results if r.is_consistent)
        inconsistent = sum(1 for r in results if not r.is_consistent)

        return CacheConsistencyReport(
            report_id=f"CCR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            generated_at=datetime.now(),
            total_keys=len(results),
            consistent_count=consistent,
            inconsistent_count=inconsistent,
            results=results,
            summary=f"共检查{len(results)}个缓存键，{consistent}个一致，{inconsistent}个不一致",
        )


_cache_manager: Optional[BudgetCacheManager] = None


def get_cache_manager() -> BudgetCacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = BudgetCacheManager()
    return _cache_manager
