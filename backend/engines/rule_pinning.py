"""Pin active hard-rule catalog hash onto decisions."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.rule_catalog import DecisionRulePin, RuleCatalogVersion


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


_PAYLOAD_CACHE: list[dict[str, str]] | None = None


def catalog_payload() -> list[dict[str, str]]:
    global _PAYLOAD_CACHE
    if _PAYLOAD_CACHE is not None:
        return _PAYLOAD_CACHE
    from ontology.rules.hard_rules import HardRuleEngine

    rules = HardRuleEngine().get_all_rules()
    _PAYLOAD_CACHE = [
        {"rule_id": r.rule_id, "name": r.name, "description": r.description}
        for r in sorted(rules.values(), key=lambda x: x.rule_id)
    ]
    return _PAYLOAD_CACHE


def catalog_sha256(payload: list[dict[str, str]] | None = None) -> str:
    body = json.dumps(payload or catalog_payload(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def ensure_active_catalog(db: AsyncSession) -> RuleCatalogVersion:
    payload = catalog_payload()
    digest = catalog_sha256(payload)
    stmt = select(RuleCatalogVersion).where(
        RuleCatalogVersion.rule_set_code == "HARD_RULES",
        RuleCatalogVersion.content_sha256 == digest,
    )
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            await db.flush()
        return existing

    actives = (
        await db.execute(
            select(RuleCatalogVersion).where(
                RuleCatalogVersion.rule_set_code == "HARD_RULES",
                RuleCatalogVersion.is_active.is_(True),
            )
        )
    ).scalars().all()
    for row in actives:
        row.is_active = False

    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(RuleCatalogVersion)
                .where(RuleCatalogVersion.rule_set_code == "HARD_RULES")
            )
        ).scalar()
        or 0
    )
    version = RuleCatalogVersion(
        version_id=_id("RV"),
        rule_set_code="HARD_RULES",
        version_no=count + 1,
        content_sha256=digest,
        content_json=payload,
        change_note="auto-pin from HardRuleEngine definitions",
        is_active=True,
    )
    db.add(version)
    await db.flush()
    return version


async def pin_decision_rules(
    db: AsyncSession,
    decision_id: str,
    applied_rule_ids: list[str],
) -> Optional[dict[str, Any]]:
    try:
        existing = (
            await db.execute(select(DecisionRulePin).where(DecisionRulePin.decision_id == decision_id))
        ).scalars().first()
        if existing:
            return {
                "pin_id": existing.pin_id,
                "rule_version_id": existing.rule_version_id,
                "rule_content_sha256": existing.rule_content_sha256,
            }
        catalog = await ensure_active_catalog(db)
        pin = DecisionRulePin(
            pin_id=_id("RP"),
            decision_id=decision_id,
            rule_version_id=catalog.version_id,
            rule_content_sha256=catalog.content_sha256,
            applied_rule_ids=list(applied_rule_ids or []),
        )
        db.add(pin)
        await db.flush()
        return {
            "pin_id": pin.pin_id,
            "rule_version_id": catalog.version_id,
            "rule_content_sha256": catalog.content_sha256,
            "rule_version_no": catalog.version_no,
        }
    except Exception as exc:
        logger.warning(f"rule pin skipped for {decision_id}: {exc}")
        return None
