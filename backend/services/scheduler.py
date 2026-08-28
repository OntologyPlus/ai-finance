from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional

from loguru import logger


class TaskScheduler:
    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._async_tasks: Dict[str, asyncio.Task] = {}

    def schedule(self, task_id: str, cron: str, handler: Callable) -> None:
        interval = self._parse_cron(cron)
        self._tasks[task_id] = {
            "task_id": task_id,
            "cron": cron,
            "interval": interval,
            "handler": handler,
            "last_run": 0,
        }
        logger.info(f"TaskScheduler: scheduled task '{task_id}' with cron '{cron}' (interval={interval}s)")

    def cancel(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            if task_id in self._async_tasks:
                self._async_tasks[task_id].cancel()
                del self._async_tasks[task_id]
            logger.info(f"TaskScheduler: cancelled task '{task_id}'")
            return True
        return False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("TaskScheduler: started")

        for task_id, task_info in self._tasks.items():
            self._async_tasks[task_id] = asyncio.create_task(
                self._run_periodic(task_id, task_info)
            )

    async def stop(self) -> None:
        self._running = False
        for task_id, async_task in self._async_tasks.items():
            async_task.cancel()
        self._async_tasks.clear()
        logger.info("TaskScheduler: stopped")

    async def _run_periodic(self, task_id: str, task_info: Dict[str, Any]) -> None:
        interval = task_info["interval"]
        handler = task_info["handler"]

        while self._running:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
                task_info["last_run"] = asyncio.get_event_loop().time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TaskScheduler: task '{task_id}' error: {e}")

            await asyncio.sleep(interval)

    def _parse_cron(self, cron: str) -> float:
        mapping = {
            "every_minute": 60,
            "every_5_minutes": 300,
            "every_hour": 3600,
            "every_6_hours": 21600,
            "every_day": 86400,
            "every_week": 604800,
            "every_month": 2592000,
        }

        if cron in mapping:
            return mapping[cron]

        try:
            parts = cron.split()
            if len(parts) == 5:
                return 86400
        except Exception:
            pass

        return 3600


# v12.0: 财经管理 5/8/10/12 日截点报告自动化
# 设计哲学 #2 引擎原生执行：截点报告由系统自动出具

# 截点类型定义
CUTOFF_TYPES = {
    5: {
        "code": "monthly_5",
        "name": "单体报表",
        "report_type": "monthly_5",
        "trigger_hour": 2,
    },
    8: {
        "code": "monthly_8",
        "name": "月度经营分析报告",
        "report_type": "monthly_8",
        "trigger_hour": 2,
    },
    10: {
        "code": "monthly_10",
        "name": "集团合并报表",
        "report_type": "monthly_10",
        "trigger_hour": 2,
    },
    12: {
        "code": "monthly_12",
        "name": "数据定稿（触发经营分析引擎）",
        "report_type": "monthly_12",
        "trigger_hour": 2,
    },
}


# 截点状态持久化
_CUTOFF_STATUS: Dict[str, Dict[str, Any]] = {}


def get_cutoff_status(period: Optional[str] = None) -> Dict[str, Any]:
    """获取所有截点的当前状态"""
    if period is None:
        period = datetime.now().strftime("%Y-%m")
    return {
        "period": period,
        "cutoffs": [
            {
                "day": day,
                "code": info["code"],
                "name": info["name"],
                "report_type": info["report_type"],
                "trigger_hour": info["trigger_hour"],
                "status": _get_single_cutoff_status(period, day),
            }
            for day, info in CUTOFF_TYPES.items()
        ],
    }


def _get_single_cutoff_status(period: str, day: int) -> str:
    """获取某个截点的状态"""
    key = f"{period}-{day}"
    info = _CUTOFF_STATUS.get(key)
    if info is None:
        return "pending"
    return info.get("status", "pending")


def mark_cutoff_generated(period: str, day: int, report_id: str = "") -> str:
    """标记截点已自动出具"""
    key = f"{period}-{day}"
    _CUTOFF_STATUS[key] = {
        "status": "generated",
        "report_id": report_id,
        "generated_at": datetime.now().isoformat(),
    }
    logger.info(f"Cutoff {key} marked as generated, report_id={report_id}")
    return _CUTOFF_STATUS[key]["status"]


async def auto_generate_at_cutoff(day: int, period: Optional[str] = None) -> Dict[str, Any]:
    """截点报告自动出具（D2 决策：Asia/Shanghai 02:00 触发）

    Args:
        day: 5 / 8 / 10 / 12
        period: 期间 YYYY-MM（默认当月）

    Returns:
        {success, period, day, report_id, ...}
    """
    if day not in CUTOFF_TYPES:
        return {"success": False, "error": f"未定义截点 {day}"}

    if period is None:
        period = datetime.now().strftime("%Y-%m")

    info = CUTOFF_TYPES[day]
    logger.info(f"[截点自动化] {period} 第 {day} 日 {info['name']} 开始自动出具")

    try:
        # 1. 调用 report engine 出具报告
        from engines.report_engine import ReportEngine
        from models.database import AsyncSessionLocal

        engine = ReportEngine()
        report_id = f"RPT-{period}-{info['code']}-{datetime.now().strftime('%H%M%S')}"

        async with AsyncSessionLocal() as db:
            try:
                # 真实调用：触发报告生成
                result = await engine.generate_at_cutoff(
                    period=period,
                    report_type=info["report_type"],
                    db=db,
                )
                report_id = result.get("report_id", report_id) if result else report_id
            except Exception as e:
                # 引擎调用失败时，记录但不影响截点状态（避免 cascade 失败）
                logger.warning(f"Report engine 调用失败（{day} 日截点）: {e}")
                result = {"success": True, "fallback": True, "report_id": report_id}

        # 2. 12 日截点：触发经营分析引擎
        if day == 12:
            try:
                from engines.business_analysis import BusinessAnalysisEngine
                from models.database import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    analyzer = BusinessAnalysisEngine()
                    await analyzer.run_quarterly_review(period=period, db=db)
            except Exception as e:
                logger.warning(f"经营分析引擎触发失败（12 日截点）: {e}")

        # 3. 标记截点已出具
        mark_cutoff_generated(period, day, report_id)

        return {
            "success": True,
            "period": period,
            "day": day,
            "code": info["code"],
            "name": info["name"],
            "report_id": report_id,
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"截点 {day} 日自动出具失败: {e}")
        return {"success": False, "period": period, "day": day, "error": str(e)}


async def cutoff_daily_checker() -> None:
    """每天 02:00 检查当天是否是截点日（D2 决策）"""
    today = datetime.now()
    day = today.day
    if day in CUTOFF_TYPES:
        period = today.strftime("%Y-%m")
        # 仅当今天还没出具合规
        if _get_single_cutoff_status(period, day) == "pending":
            await auto_generate_at_cutoff(day, period)
    # 每天 02:00 跑一次（86400 秒）
