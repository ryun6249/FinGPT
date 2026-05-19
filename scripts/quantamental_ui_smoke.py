from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser smoke for the Quantamental static UI.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", default="reports/quantamental_ui_smoke_latest.json")
    parser.add_argument(
        "--tickers",
        default="AAPL,MSFT,NVDA,TSLA,INVALID_TEST_TICKER_123",
        help="Comma-separated tickers to run through the Quantamental UI.",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        report = {"status": "blocked", "reason": f"playwright_import_failed:{type(exc).__name__}:{exc}"}
        _write_report(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    tickers = [item.strip() for item in args.tickers.split(",") if item.strip()]
    report: dict[str, Any] = {
        "status": "passed",
        "base_url": args.base_url,
        "tickers": [],
        "styles": [],
        "symbol_picker": None,
        "empty_ticker": None,
        "global_market": None,
        "global_resolver": None,
        "top_signal_screen": None,
        "score_threshold_screen": None,
        "overview_axes": None,
        "comparison": None,
        "errors": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            page.goto(f"{args.base_url.rstrip('/')}/ui/#quantamental", wait_until="load", timeout=60_000)
            page.get_by_test_id("quantamental-tab").click(timeout=10_000)
            page.get_by_test_id("quantamental-analyze").wait_for(timeout=10_000)
            page.wait_for_function(
                """() => window.FinGPTQuantamentalUi && document.querySelector("#homeSurfaceGrid")?.dataset?.dashboardTab === "quantamental" """,
                timeout=10_000,
            )
            page.locator('#languageToggle [data-language="en"]').click(timeout=10_000)
            selectors = [
                "#quantamentalTicker",
                "#quantamentalTickerOpen",
                "#quantamentalMarket",
                "#quantamentalPeriod",
                "#quantamentalYears",
                "#quantamentalLookback",
                "#quantamentalStyle",
                "#quantamentalSignalSurface",
                "#quantamentalScoreSurface",
                "#quantamentalFactorSurface",
                "#quantamentalMainSurface",
                "#quantamentalDataQualitySurface",
                "#quantamentalCompareTickers",
                "#quantamentalCompareRun",
                "#quantamentalCompareSurface",
                "#quantamentalExpandPeers",
                "#quantamentalPeerLimit",
                "#quantamentalWatchlistName",
                "#quantamentalWatchlistSelect",
                "#quantamentalWatchlistSave",
                "#quantamentalWatchlistLoad",
                "#quantamentalCompareCsv",
                "#quantamentalScreenRun",
                "#quantamentalScreenStatus",
                "#quantamentalScreenSurface",
                "#quantamentalScoreMetric",
                "#quantamentalScoreThreshold",
                "#quantamentalScoreScreenLimit",
                "#quantamentalScoreScreenRun",
                "#quantamentalScoreScreenStatus",
                "#quantamentalScoreScreenSurface",
            ]
            for selector in selectors:
                page.locator(selector).wait_for(timeout=10_000)

            page.wait_for_function(
                """() => {
                    const button = document.querySelector('[data-testid="quantamental-screen-run"]');
                    return !!button && !button.disabled && button.getAttribute("aria-busy") !== "true";
                }""",
                timeout=180_000,
            )
            page.get_by_test_id("quantamental-screen-run").click(timeout=10_000)
            page.wait_for_function(
                """() => {
                    const text = document.querySelector("#quantamentalScreenSurface")?.textContent || "";
                    const rows = document.querySelectorAll('#quantamentalScreenSurface [data-testid="quantamental-screen-table"] tbody tr').length;
                    return (text.includes("Screened") || text.includes("스크리닝")) &&
                        rows > 0 && rows <= 5 &&
                        (/freshness/i.test(text) || text.includes("신선도"));
                }""",
                timeout=180_000,
            )
            report["top_signal_screen"] = {
                "status": page.locator("#quantamentalScreenStatus").inner_text(timeout=10_000),
                "table_text": page.locator("#quantamentalScreenSurface").inner_text(timeout=10_000)[:1500],
                "row_count": page.locator('#quantamentalScreenSurface [data-testid="quantamental-screen-table"] tbody tr').count(),
            }

            page.locator("#quantamentalScoreMetric").select_option("market_resilience", timeout=10_000)
            page.locator("#quantamentalScoreThreshold").fill("0", timeout=10_000)
            page.locator("#quantamentalScoreScreenLimit").select_option("10", timeout=10_000)
            page.get_by_test_id("quantamental-score-screen-run").click(timeout=10_000)
            page.wait_for_function(
                """() => {
                    const text = document.querySelector("#quantamentalScoreScreenSurface")?.textContent || "";
                    const rows = document.querySelectorAll('#quantamentalScoreScreenSurface [data-testid="quantamental-score-screen-table"] tbody tr').length;
                    return (text.includes("Market Resilience") || text.includes("시장 회복력")) && text.includes(">=") && rows > 0 && rows <= 10;
                }""",
                timeout=180_000,
            )
            report["score_threshold_screen"] = {
                "status": page.locator("#quantamentalScoreScreenStatus").inner_text(timeout=10_000),
                "table_text": page.locator("#quantamentalScoreScreenSurface").inner_text(timeout=10_000)[:1500],
                "row_count": page.locator('#quantamentalScoreScreenSurface [data-testid="quantamental-score-screen-table"] tbody tr').count(),
            }

            page.wait_for_timeout(500)
            page.locator("#quantamentalTickerOpen").click(timeout=10_000)
            page.locator("#symbolPickerModal").wait_for(state="visible", timeout=10_000)
            page.wait_for_function(
                """() => {
                    const title = document.querySelector("#symbolPickerTitle")?.textContent || "";
                    const apply = document.querySelector("#symbolPickerApply")?.textContent || "";
                    return title.includes("Quantamental") && apply.trim().length > 0;
                }""",
                timeout=10_000,
            )
            page.locator("#symbolPickerSearch").fill("MSFT", timeout=10_000)
            page.locator('#symbolPickerList [data-symbol-toggle="MSFT"]').click(timeout=10_000)
            page.locator("#symbolPickerApply").click(timeout=10_000)
            page.locator("#symbolPickerModal").wait_for(state="hidden", timeout=10_000)
            page.wait_for_function(
                """() => (document.querySelector("#quantamentalTicker")?.value || "") === "MSFT" """,
                timeout=10_000,
            )
            report["symbol_picker"] = {
                "ticker": page.locator("#quantamentalTicker").input_value(timeout=10_000),
                "title": "Quantamental 티커 선택",
            }

            page.locator("#quantamentalTicker").fill("")
            page.get_by_test_id("quantamental-analyze").click()
            page.wait_for_function(
                """() => {
                    const text = document.querySelector("#quantamentalStatus")?.textContent || "";
                    return text.includes("Ticker is required") || text.includes("티커");
                }""",
                timeout=10_000,
            )
            report["empty_ticker"] = page.locator("#quantamentalStatus").inner_text(timeout=10_000)

            page.locator("#quantamentalTicker").fill("ASML.AS")
            page.locator("#quantamentalMarket").select_option("GLOBAL")
            page.get_by_test_id("quantamental-analyze").click()
            page.wait_for_function(
                """() => {
                    const status = document.querySelector("#quantamentalStatus")?.textContent || "";
                    const signal = document.querySelector("#quantamentalSignalSurface")?.textContent || "";
                    const quality = document.querySelector("#quantamentalDataQualitySurface")?.textContent || "";
                    const doneSignal = /Candidate|Watch|Avoid|Reduce Risk|Insufficient Data/.test(signal);
                    return status.includes("ASML.AS") && doneSignal && !/unsupported_market/i.test(status + signal + quality);
                }""",
                timeout=180_000,
            )
            report["global_market"] = {
                "status": page.locator("#quantamentalStatus").inner_text(timeout=10_000),
                "signal_text": page.locator("#quantamentalSignalSurface").inner_text(timeout=10_000)[:1000],
                "quality_text": page.locator("#quantamentalDataQualitySurface").inner_text(timeout=10_000)[:1000],
            }

            page.locator("#quantamentalTicker").fill("7203")
            page.locator("#quantamentalMarket").select_option("GLOBAL")
            page.locator("#quantamentalYears").select_option("3")
            page.locator("#quantamentalLookback").select_option("63")
            page.get_by_test_id("quantamental-analyze").click()
            page.wait_for_function(
                """() => {
                    const body = document.body.textContent || "";
                    const status = document.querySelector("#quantamentalStatus")?.textContent || "";
                    return status.includes("7203") &&
                        body.includes("Toyota Motor") &&
                        body.includes("global_symbol_resolved_to_yfinance:7203.T") &&
                        !body.includes("unsupported_market");
                }""",
                timeout=180_000,
            )
            report["global_resolver"] = {
                "status": page.locator("#quantamentalStatus").inner_text(timeout=10_000),
                "company_text": page.locator("#quantamentalCompanySurface").inner_text(timeout=10_000)[:1000],
                "signal_text": page.locator("#quantamentalSignalSurface").inner_text(timeout=10_000)[:1000],
                "quality_text": page.locator("#quantamentalDataQualitySurface").inner_text(timeout=10_000)[:1000],
            }
            page.locator("#quantamentalMarket").select_option("US")

            page.locator("#quantamentalCompareTickers").fill("AAPL MSFT")
            page.locator("#quantamentalExpandPeers").check()
            page.locator("#quantamentalPeerLimit").select_option("4")
            page.get_by_test_id("quantamental-watchlist-save").click(timeout=10_000)
            page.get_by_test_id("quantamental-watchlist-load").click(timeout=10_000)
            report["watchlists"] = page.evaluate(
                """async () => {
                    const res = await fetch('/api/v1/quantamental/compare/watchlists');
                    if (!res.ok) return { status: 'failed', status_code: res.status };
                    const body = await res.json();
                    return {
                        status: body.status,
                        count: body.count,
                        names: (body.items || []).map((item) => item.name).slice(0, 5),
                        storage: body.storage
                    };
                }"""
            )
            page.get_by_test_id("quantamental-compare-run").click(timeout=10_000)
            page.wait_for_function(
                """() => {
                    const text = document.querySelector("#quantamentalCompareSurface")?.textContent || "";
                    return text.includes("Peer Strength") && text.includes("AAPL") && text.includes("Peer universe");
                }""",
                timeout=180_000,
            )
            with page.expect_download(timeout=10_000) as download_info:
                page.get_by_test_id("quantamental-compare-csv").click(timeout=10_000)
            download = download_info.value
            report["comparison"] = page.locator("#quantamentalCompareSurface").inner_text(timeout=10_000)[:2000]
            report["comparison_csv"] = download.suggested_filename

            for style in ["balanced", "quality_growth", "value", "momentum", "defensive"]:
                page.locator("#quantamentalTicker").fill("AAPL")
                page.locator("#quantamentalStyle").select_option(style)
                page.get_by_test_id("quantamental-analyze").click()
                page.wait_for_function(
                    """(style) => {
                        const status = document.querySelector("#quantamentalStatus")?.textContent || "";
                        const score = document.querySelector("#quantamentalScoreSurface")?.textContent || "";
                        return status.includes("AAPL") && score.includes(style);
                    }""",
                    arg=style,
                    timeout=120_000,
                )
                report["styles"].append(
                    {
                        "style": style,
                        "status": page.locator("#quantamentalStatus").inner_text(timeout=10_000),
                        "score_text": page.locator("#quantamentalScoreSurface").inner_text(timeout=10_000)[:1000],
                        "signal_text": page.locator("#quantamentalSignalSurface").inner_text(timeout=10_000)[:1000],
                    }
                )
            page.locator('[data-quantamental-tab="overview"]').click(timeout=10_000)
            page.get_by_test_id("quantamental-overview-tab").wait_for(timeout=10_000)
            page.wait_for_function(
                """() => {
                    const text = document.querySelector("#quantamentalMainSurface")?.textContent || "";
                    return text.includes("X: date") &&
                        text.includes("Y: price") &&
                        text.includes("Y: return") &&
                        text.includes("Freshness") &&
                        text.includes("Missing values are skipped");
                }""",
                timeout=10_000,
            )
            report["overview_axes"] = page.locator("#quantamentalMainSurface").inner_text(timeout=10_000)[:2000]
            page.locator('[data-quantamental-tab="audit"]').click(timeout=10_000)
            page.get_by_test_id("quantamental-snapshot-export-json").wait_for(timeout=10_000)
            page.get_by_test_id("quantamental-snapshot-retention").click(timeout=10_000)
            page.wait_for_function(
                """() => (document.querySelector("#quantamentalMainSurface")?.textContent || "").includes("Retention preview")""",
                timeout=30_000,
            )
            report["snapshot_audit"] = page.locator("#quantamentalMainSurface").inner_text(timeout=10_000)[:1000]

            for ticker in tickers:
                page.locator("#quantamentalTicker").fill(ticker)
                page.locator("#quantamentalMarket").select_option("US")
                page.locator("#quantamentalPeriod").select_option("annual")
                page.locator("#quantamentalYears").select_option("5")
                page.locator("#quantamentalLookback").select_option("252")
                page.locator("#quantamentalStyle").select_option("balanced")
                page.get_by_test_id("quantamental-analyze").click()
                page.wait_for_function(
                    """(ticker) => {
                        const status = document.querySelector("#quantamentalStatus")?.textContent || "";
                        const signal = document.querySelector("#quantamentalSignalSurface")?.textContent || "";
                        const doneSignal = /Candidate|Watch|Avoid|Reduce Risk|Insufficient Data/.test(signal);
                        return status.includes(ticker) && doneSignal && !/loading|로딩|계산|생성/.test(signal);
                    }""",
                    arg=ticker,
                    timeout=120_000,
                )
                body = {
                    "ticker": ticker,
                    "status": page.locator("#quantamentalStatus").inner_text(timeout=10_000),
                    "signal_text": page.locator("#quantamentalSignalSurface").inner_text(timeout=10_000)[:1000],
                    "score_text": page.locator("#quantamentalScoreSurface").inner_text(timeout=10_000)[:1000],
                    "factor_text": page.locator("#quantamentalFactorSurface").inner_text(timeout=10_000)[:1000],
                    "quality_text": page.locator("#quantamentalDataQualitySurface").inner_text(timeout=10_000)[:1000],
                }
                for tab_name in ["fundamental", "quant", "risk", "ai", "qa"]:
                    page.locator(f'[data-quantamental-tab="{tab_name}"]').click(timeout=10_000)
                page.locator('[data-quantamental-tab="qa"]').click(timeout=10_000)
                page.get_by_test_id("quantamental-qa-run").click(timeout=10_000)
                page.wait_for_function(
                    """(ticker) => {
                        const text = document.querySelector("#quantamentalQaSurface")?.textContent || "";
                        return text.includes(ticker) && (text.includes("not investment advice") || text.includes("투자 자문"));
                    }""",
                    arg=ticker,
                    timeout=60_000,
                )
                body["qa_text"] = page.locator("#quantamentalQaSurface").inner_text(timeout=10_000)[:1000]
                report["tickers"].append(body)
        except Exception as exc:  # noqa: BLE001
            report["status"] = "failed"
            report["errors"].append(f"{type(exc).__name__}:{exc}")
        finally:
            browser.close()

    _write_report(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


def _write_report(path: str, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
