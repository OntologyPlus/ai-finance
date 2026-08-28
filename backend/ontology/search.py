"""本体搜索引擎 — Elasticsearch集成"""
import logging
from typing import Dict, Any, List, Optional

from loguru import logger

try:
    from elasticsearch import AsyncElasticsearch
except ImportError:
    AsyncElasticsearch = None


INDEX_NAME = "ontology_instances"

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "instance_id": {"type": "keyword"},
            "type_id": {"type": "keyword"},
            "attributes": {"type": "flattened"},  # supports nested search
            "status": {"type": "keyword"},
            "tenant_id": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    }
}


class OntologySearchEngine:
    """本体实例Elasticsearch搜索引擎"""

    def __init__(self, es_client: Optional[Any] = None):
        self._es = es_client
        self._index_ready = False

    async def ensure_index(self) -> bool:
        """确保索引存在，不存在则创建"""
        if self._es is None:
            return False
        try:
            exists = await self._es.indices.exists(index=INDEX_NAME)
            if not exists:
                await self._es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)
                logger.info(f"ES索引 {INDEX_NAME} 已创建")
            self._index_ready = True
            return True
        except Exception as e:
            logger.warning(f"ES索引创建失败: {e}")
            return False

    async def index_instance(self, instance_data: Dict[str, Any]) -> bool:
        """索引单个实例"""
        if self._es is None:
            return False
        try:
            if not self._index_ready:
                await self.ensure_index()
            doc = {
                "instance_id": instance_data.get("instance_id", ""),
                "type_id": instance_data.get("type_id", ""),
                "attributes": instance_data.get("attributes", {}),
                "status": instance_data.get("status", "active"),
                "tenant_id": instance_data.get("tenant_id"),
                "created_at": instance_data.get("created_at"),
                "updated_at": instance_data.get("updated_at"),
            }
            await self._es.index(
                index=INDEX_NAME,
                id=doc["instance_id"],
                document=doc,
            )
            return True
        except Exception as e:
            logger.warning(f"ES索引失败 [{instance_data.get('instance_id')}]: {e}")
            return False

    async def delete_instance(self, instance_id: str) -> bool:
        """删除实例索引"""
        if self._es is None:
            return False
        try:
            await self._es.delete(index=INDEX_NAME, id=instance_id, ignore=[404])
            return True
        except Exception as e:
            logger.warning(f"ES删除失败 [{instance_id}]: {e}")
            return False

    async def search(
        self,
        query: str,
        type_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        from_: int = 0,
        size: int = 20,
    ) -> Dict[str, Any]:
        """全文搜索实例"""
        if self._es is None:
            return {"hits": [], "total": 0, "message": "Elasticsearch不可用"}
        try:
            if not self._index_ready:
                await self.ensure_index()

            must = []
            # Full-text search on attributes
            if query:
                must.append({
                    "multi_match": {
                        "query": query,
                        "fields": ["attributes*"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                })

            # Type filter
            if type_id:
                must.append({"term": {"type_id": type_id}})

            # Additional filters
            if filters:
                for key, value in filters.items():
                    must.append({"term": {f"attributes.{key}": value}})

            body = {
                "query": {"bool": {"must": must}} if must else {"match_all": {}},
                "from": from_,
                "size": size,
            }

            result = await self._es.search(index=INDEX_NAME, body=body)
            hits = [
                {
                    "instance_id": hit["_source"].get("instance_id"),
                    "type_id": hit["_source"].get("type_id"),
                    "attributes": hit["_source"].get("attributes", {}),
                    "status": hit["_source"].get("status"),
                    "score": hit.get("_score", 0),
                }
                for hit in result.get("hits", {}).get("hits", [])
            ]
            total = result.get("hits", {}).get("total", {}).get("value", 0)
            return {"hits": hits, "total": total}
        except Exception as e:
            logger.warning(f"ES搜索失败: {e}")
            return {"hits": [], "total": 0, "error": str(e)}

    async def bulk_sync(self, instances: List[Dict[str, Any]]) -> int:
        """从MySQL全量同步到ES"""
        if self._es is None:
            return 0
        try:
            if not self._index_ready:
                await self.ensure_index()

            # Delete and recreate index for clean sync
            await self._es.indices.delete(index=INDEX_NAME, ignore=[404])
            await self._es.indices.create(index=INDEX_NAME, body=INDEX_MAPPING)

            count = 0
            for inst in instances:
                success = await self.index_instance(inst)
                if success:
                    count += 1

            await self._es.indices.refresh(index=INDEX_NAME)
            logger.info(f"ES全量同步完成: {count}/{len(instances)} 条")
            return count
        except Exception as e:
            logger.warning(f"ES全量同步失败: {e}")
            return 0


# Module-level singleton
_search_engine: Optional[OntologySearchEngine] = None


def get_search_engine() -> OntologySearchEngine:
    global _search_engine
    if _search_engine is None:
        _search_engine = OntologySearchEngine()
    return _search_engine


def init_search_engine(es_client) -> OntologySearchEngine:
    global _search_engine
    _search_engine = OntologySearchEngine(es_client=es_client)
    return _search_engine
