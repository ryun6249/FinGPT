from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import Optional

from core.config.settings import load_settings
from core.schemas.ai_portfolio import SecDataRefreshRequest
from core.utils.logger import get_logger

logger = get_logger("pipelines.data_mart.scheduler")


def _failed_job(exc: Exception) -> dict:
    return {
        "status": "failed",
        "error": str(exc),
        "error_type": type(exc).__name__,
    }


def _split_csv(value: str | None) -> tuple[str, ...]:
    items = [item.strip().lower() for item in str(value or "").split(",")]
    return tuple(item for item in items if item)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _watchlist_tickers(market: str) -> list[str]:
    name = "core_kr.yaml" if str(market).lower() == "kr" else "core_us.yaml"
    path = _project_root() / "config" / "watchlists" / name
    if not path.exists():
        logger.warning("[DATA_MART_SCHED] watchlist not found: %s", path)
        return []
    tickers: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("- "):
            continue
        ticker = line[2:].strip().strip("'\"").upper()
        if ticker:
            tickers.append(ticker)
    return tickers


class DataMartRefreshScheduler:
    def __init__(self) -> None:
        settings = load_settings()
        explicit_enabled = os.getenv("DATA_MART_AUTO_REFRESH_ENABLED")
        self._enabled = bool(getattr(settings, "data_mart_auto_refresh_enabled", True))
        if explicit_enabled is None and os.getenv("PYTEST_CURRENT_TEST"):
            self._enabled = False
        self._sec_enabled = bool(getattr(settings, "data_mart_auto_refresh_sec_enabled", True))
        self._macro_enabled = bool(getattr(settings, "data_mart_auto_refresh_macro_enabled", True))
        self._prices_enabled = bool(getattr(settings, "data_mart_auto_refresh_prices_enabled", True))
        self._quality_checks_enabled = bool(getattr(settings, "data_mart_auto_refresh_quality_checks_enabled", True))
        interval_hours = float(getattr(settings, "data_mart_auto_refresh_interval_hours", 24.0) or 24.0)
        self._interval_s = max(3600.0, interval_hours * 3600.0)
        self._initial_delay_s = max(0.0, float(getattr(settings, "data_mart_auto_refresh_initial_delay_s", 120.0) or 0.0))
        self._poll_interval_s = min(300.0, max(30.0, self._initial_delay_s or 60.0))
        self._universe_id = str(getattr(settings, "data_mart_auto_refresh_universe_id", "all_supported") or "all_supported")
        self._max_assets = max(1, int(getattr(settings, "data_mart_auto_refresh_max_assets", 250) or 250))
        self._price_markets = _split_csv(getattr(settings, "data_mart_auto_refresh_price_markets", "us,kr")) or ("us", "kr")
        self._sec_lookback_days = max(1, int(getattr(settings, "data_mart_auto_refresh_sec_lookback_days", 365 * 3) or 365 * 3))
        self._macro_lookback_days = max(1, int(getattr(settings, "data_mart_auto_refresh_macro_lookback_days", 365 * 5) or 365 * 5))
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._started_at: Optional[float] = None
        self._last_poll_at: Optional[float] = None
        self._last_run_at: Optional[float] = None
        self._next_run_at: Optional[float] = None
        self._runs_triggered = 0
        self._last_result: dict | None = None
        self._run_lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "running": self.running,
            "interval_s": self._interval_s,
            "initial_delay_s": self._initial_delay_s,
            "jobs": {
                "price_history": self._prices_enabled,
                "sec_company_data": self._sec_enabled,
                "macro_platform_data": self._macro_enabled,
                "data_quality_checks": self._quality_checks_enabled,
            },
            "price_markets": list(self._price_markets),
            "universe_id": self._universe_id,
            "max_assets": self._max_assets,
            "sec_lookback_days": self._sec_lookback_days,
            "macro_lookback_days": self._macro_lookback_days,
            "started_at": self._started_at,
            "last_poll_at": self._last_poll_at,
            "last_run_at": self._last_run_at,
            "next_run_at": self._next_run_at,
            "runs_triggered": self._runs_triggered,
            "last_result": self._last_result,
        }

    async def start(self) -> None:
        if not self._enabled:
            logger.info("[DATA_MART_SCHED] disabled")
            return
        if self.running:
            return
        self._stop_event = asyncio.Event()
        loop = asyncio.get_event_loop()
        self._started_at = loop.time()
        self._next_run_at = self._started_at + self._initial_delay_s
        self._task = asyncio.create_task(self._loop(), name="data-mart-refresh-scheduler")
        logger.info("[DATA_MART_SCHED] started interval=%ss universe=%s", self._interval_s, self._universe_id)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await self._task
        self._task = None
        logger.info("[DATA_MART_SCHED] stopped")

    async def run_once(self) -> dict:
        if self._run_lock.locked():
            return {
                "status": "skipped",
                "reason": "refresh_already_running",
                "jobs": {},
            }
        async with self._run_lock:
            return await self._run_once_locked()

    async def _run_once_locked(self) -> dict:
        from pipelines.ai_portfolio.service import run_sec_data_refresh
        from pipelines.data_mart.jobs.quality_checks import run_data_quality_checks
        from pipelines.data_mart.jobs.update_macro_daily import update_macro_platform_data
        from pipelines.data_mart.jobs.update_prices_daily import update_prices_daily
        from pipelines.macro import macro_service

        result: dict = {"status": "success", "jobs": {}}
        if self._prices_enabled:
            try:
                market_results: list[dict] = []
                for market in self._price_markets:
                    tickers = _watchlist_tickers(market)
                    if not tickers:
                        market_results.append({"market": market, "status": "skipped", "reason": "empty_watchlist"})
                        continue
                    try:
                        price_result = await asyncio.to_thread(update_prices_daily, tickers, market=market)
                        market_results.append(
                            {
                                "market": market,
                                "status": price_result.status,
                                "run_id": price_result.run_id,
                                "ticker_count": len(tickers),
                                "rows_inserted": price_result.rows_inserted,
                                "rows_updated": price_result.rows_updated,
                                "error_message": price_result.error_message,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("[DATA_MART_SCHED] price refresh failed market=%s: %s", market, exc)
                        market_results.append({"market": market, **_failed_job(exc)})
                price_statuses = {str(item.get("status") or "").lower() for item in market_results}
                result["jobs"]["price_history"] = {
                    "status": "failed" if "failed" in price_statuses else ("skipped" if price_statuses == {"skipped"} else "success"),
                    "markets": market_results,
                    "rows_inserted": sum(int(item.get("rows_inserted") or 0) for item in market_results),
                    "rows_updated": sum(int(item.get("rows_updated") or 0) for item in market_results),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("[DATA_MART_SCHED] price refresh wrapper failed: %s", exc)
                result["jobs"]["price_history"] = _failed_job(exc)
        if self._sec_enabled:
            try:
                request = SecDataRefreshRequest(
                    universe_id=self._universe_id,
                    max_assets=self._max_assets,
                    lookback_days=self._sec_lookback_days,
                    hydrate_financials=True,
                )
                sec_result = await asyncio.to_thread(run_sec_data_refresh, request)
                result["jobs"]["sec_company_data"] = {
                    "operation_id": sec_result.get("operation_id"),
                    "status": sec_result.get("status"),
                    "created_at": sec_result.get("created_at"),
                    "ticker_count": sec_result.get("ticker_count"),
                    "sec_result": sec_result.get("sec_result"),
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("[DATA_MART_SCHED] SEC/company refresh failed: %s", exc)
                result["jobs"]["sec_company_data"] = _failed_job(exc)
        if self._macro_enabled:
            try:
                macro_result = await asyncio.to_thread(update_macro_platform_data, lookback_days=self._macro_lookback_days)
                macro_service.clear_macro_caches()
                result["jobs"]["macro_platform_data"] = {
                    "run_id": macro_result.run_id,
                    "status": macro_result.status,
                    "rows_inserted": macro_result.rows_inserted,
                    "rows_updated": macro_result.rows_updated,
                    "providers": [
                        {
                            "provider": provider.provider,
                            "status": provider.status,
                            "rows": provider.rows,
                            "error": provider.error,
                            "detail": provider.detail,
                        }
                        for provider in macro_result.providers
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("[DATA_MART_SCHED] macro refresh failed: %s", exc)
                result["jobs"]["macro_platform_data"] = _failed_job(exc)
        if self._quality_checks_enabled:
            try:
                checks = await asyncio.to_thread(run_data_quality_checks)
                fail_count = len([item for item in checks if str(item.get("status") or "").lower() == "fail"])
                warn_count = len([item for item in checks if str(item.get("status") or "").lower() == "warn"])
                result["jobs"]["data_quality_checks"] = {
                    "status": "failed" if fail_count else ("partial" if warn_count else "success"),
                    "check_count": len(checks),
                    "fail_count": fail_count,
                    "warn_count": warn_count,
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("[DATA_MART_SCHED] quality checks failed: %s", exc)
                result["jobs"]["data_quality_checks"] = _failed_job(exc)
        statuses = [
            str(job.get("status") or "").lower()
            for job in result["jobs"].values()
            if isinstance(job, dict)
        ]
        if statuses and any(status == "failed" for status in statuses):
            result["status"] = "failed"
        elif statuses and any(status in {"partial", "unavailable"} for status in statuses):
            result["status"] = "partial"
        elif not statuses:
            result["status"] = "skipped"
        loop = asyncio.get_event_loop()
        self._last_run_at = loop.time()
        self._next_run_at = self._last_run_at + self._interval_s
        self._runs_triggered += 1
        self._last_result = result
        return result

    async def _loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self._tick()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval_s)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("[DATA_MART_SCHED] loop crashed: %s", exc)

    async def _tick(self) -> None:
        loop = asyncio.get_event_loop()
        now = loop.time()
        self._last_poll_at = now
        if self._next_run_at is None:
            self._next_run_at = now + self._initial_delay_s
        if now < self._next_run_at:
            return
        try:
            await self.run_once()
        except Exception as exc:  # noqa: BLE001
            self._last_result = {"status": "failed", "error": str(exc)}
            self._next_run_at = now + min(self._interval_s, 3600.0)
            logger.exception("[DATA_MART_SCHED] refresh failed: %s", exc)


_scheduler: Optional[DataMartRefreshScheduler] = None


def get_scheduler() -> DataMartRefreshScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DataMartRefreshScheduler()
    return _scheduler
