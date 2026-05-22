from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "universe_freshness_latest.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routers.market_utils import clean_ticker_list  # noqa: E402
from pipelines.ai_portfolio.engine import load_universe  # noqa: E402


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def chunked(values: list[str], size: int) -> Iterable[list[str]]:
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def normalize_tickers(universe_id: str, tickers: list[str]) -> tuple[list[str], list[str]]:
    if tickers:
        return clean_ticker_list(",".join(tickers)), []
    assets, warnings = load_universe(universe_id)
    return [asset.ticker for asset in assets if asset.ticker and asset.ticker != "CASH"], warnings


def latest_dates_from_frame(frame: pd.DataFrame, requested: list[str]) -> dict[str, str | None]:
    if frame is None or frame.empty:
        return {ticker: None for ticker in requested}
    if isinstance(frame.columns, pd.MultiIndex):
        available = set(str(ticker).upper() for ticker in frame.columns.get_level_values(1))
        out: dict[str, str | None] = {}
        for ticker in requested:
            key = ticker.upper()
            if key not in available:
                out[ticker] = None
                continue
            try:
                close = frame["Close"][key].dropna()
            except Exception:
                out[ticker] = None
                continue
            out[ticker] = close.index.max().date().isoformat() if not close.empty else None
        return out

    close = frame.get("Close") if isinstance(frame, pd.DataFrame) else None
    latest = close.dropna().index.max().date().isoformat() if close is not None and not close.dropna().empty else None
    return {requested[0]: latest} if requested else {}


def download_latest_dates(tickers: list[str], *, period: str, chunk_size: int) -> dict[str, str | None]:
    latest: dict[str, str | None] = {}
    for batch in chunked(tickers, chunk_size):
        try:
            frame = yf.download(
                tickers=batch,
                period=period,
                interval="1d",
                group_by="column",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            latest.update(latest_dates_from_frame(frame, batch))
        except Exception as exc:  # noqa: BLE001 - verifier must preserve provider failure evidence per ticker.
            for ticker in batch:
                latest[ticker] = None
            latest[f"__batch_error__:{','.join(batch[:5])}"] = str(exc)
    return latest


def freshness_status(latest: str | None, *, max_age_days: int, today: date) -> tuple[str, int | None]:
    if not latest:
        return "missing", None
    try:
        latest_date = date.fromisoformat(latest[:10])
    except ValueError:
        return "invalid_date", None
    age = (today - latest_date).days
    if age < 0:
        return "future_date", age
    return ("fresh" if age <= max_age_days else "stale"), age


def verify_universe(
    *,
    universe_id: str,
    tickers: list[str],
    max_assets: int,
    max_age_days: int,
    period: str,
    chunk_size: int,
) -> dict[str, Any]:
    resolved, warnings = normalize_tickers(universe_id, tickers)
    if max_assets > 0:
        resolved = resolved[:max_assets]
    today = datetime.now(UTC).date()
    latest = download_latest_dates(resolved, period=period, chunk_size=chunk_size)

    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for ticker in resolved:
        latest_date = latest.get(ticker)
        status, age = freshness_status(latest_date, max_age_days=max_age_days, today=today)
        status_counts[status] = status_counts.get(status, 0) + 1
        rows.append(
            {
                "ticker": ticker,
                "latest_price_date": latest_date,
                "age_days": age,
                "freshness_status": status,
            }
        )

    batch_errors = {key: value for key, value in latest.items() if key.startswith("__batch_error__:")}
    stale_or_missing = [row for row in rows if row["freshness_status"] != "fresh"]
    return {
        "status": "pass" if rows and not stale_or_missing and not batch_errors else "warn" if rows else "empty",
        "generated_at": now_iso(),
        "universe_id": universe_id,
        "requested_count": len(resolved),
        "evaluated_count": len(rows),
        "max_age_days": max_age_days,
        "period": period,
        "chunk_size": chunk_size,
        "status_counts": status_counts,
        "warnings": warnings,
        "batch_errors": batch_errors,
        "stale_or_missing": stale_or_missing[:100],
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify latest daily price freshness for a FinGPT universe.")
    parser.add_argument("--universe-id", default="all_supported", help="AI Portfolio universe id, for example all_supported.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional explicit ticker list. Overrides --universe-id.")
    parser.add_argument("--max-assets", type=int, default=250, help="Maximum assets to verify. Use 0 for the full universe.")
    parser.add_argument("--max-age-days", type=int, default=5, help="Maximum allowed calendar age for latest daily price.")
    parser.add_argument("--period", default="14d", help="yfinance period used for daily price checks.")
    parser.add_argument("--chunk-size", type=int, default=80, help="Batch size for yfinance downloads.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON report output path.")
    parser.add_argument("--fail-on-stale", action="store_true", help="Exit non-zero when any evaluated ticker is not fresh.")
    args = parser.parse_args(argv)

    report = verify_universe(
        universe_id=args.universe_id,
        tickers=args.tickers,
        max_assets=args.max_assets,
        max_age_days=args.max_age_days,
        period=args.period,
        chunk_size=max(1, args.chunk_size),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
    if args.fail_on_stale and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
