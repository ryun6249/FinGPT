from __future__ import annotations

import argparse
import json
import os
import socket
# Smoke harness starts a trusted local uvicorn process.
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
DOMAIN_BUNDLE_VERSION = "20260514-domain-modules"
QUANTAMENTAL_BUNDLE_VERSION = "20260519-quantamental-v13"
APP_BUNDLE_VERSION = "20260519-continuous-enhancement-v3"
VERSIONED_SCRIPT_SELECTORS = [
    f'script[src="modules/market-ui.js?v={DOMAIN_BUNDLE_VERSION}"]',
    f'script[src="modules/macro-ui.js?v={DOMAIN_BUNDLE_VERSION}"]',
    f'script[src="modules/forecast-ui.js?v={DOMAIN_BUNDLE_VERSION}"]',
    f'script[src="modules/quant-ui.js?v={DOMAIN_BUNDLE_VERSION}"]',
    f'script[src="modules/ai-portfolio-ui.js?v={DOMAIN_BUNDLE_VERSION}"]',
    f'script[src="modules/quantamental-ui.js?v={QUANTAMENTAL_BUNDLE_VERSION}"]',
    f'script[src="app.js?v={APP_BUNDLE_VERSION}"]',
]
DOMAIN_MODULE_GLOBALS = [
    "typeof window.FinGPTMarketUi?.marketTape === 'function'",
    "typeof window.FinGPTMarketUi?.marketSignals === 'function'",
    "typeof window.FinGPTMacroUi?.providerHealth === 'function'",
    "typeof window.FinGPTForecastUi?.jobs === 'function'",
    "typeof window.FinGPTQuantUi?.exportStorageReport === 'function'",
    "typeof window.FinGPTAiPortfolioUi?.dashboardMeta === 'function'",
    "typeof window.FinGPTAiPortfolioUi?.operationList === 'function'",
    "typeof window.FinGPTQuantamentalUi?.topSignals === 'function'",
    "typeof window.FinGPTQuantamentalUi?.scoreScreen === 'function'",
]
DASHBOARD_TAB_CHECKS = [
    (
        "market-dashboard-tab",
        "market",
        "#market-dashboard",
        ["#marketTapeSurface", "#marketSignalSurface", "#crossAssetAnalysisSurface", "#marketOverviewMeta"],
    ),
    (
        "macro-dashboard-tab",
        "macro",
        "#macro",
        ["#macroSurface", "#macroProviderHealthSurface", "#macroDataQualitySurface"],
    ),
    (
        "quant-lab-tab",
        "quant",
        "#quant-lab",
        ["#quantFeatureSurface", "#quantSignalSurface", "#quantRunHistorySurface"],
    ),
    (
        "ml-forecast-tab",
        "forecast",
        "#ml-forecast",
        ["#mlForecastSurface", "#forecastJobsSurface", "#forecastRegistrySurface"],
    ),
    (
        "quantamental-tab",
        "quantamental",
        "#quantamental",
        ["#quantamentalSurface", "#quantamentalScreenSurface", "#quantamentalDataQualitySurface"],
    ),
    (
        "ai-portfolio-tab",
        "ai-portfolio",
        "#ai-portfolio",
        ["#aiPortfolioOverviewSurface", "#aiPortfolioOpsSurface", "#aiPortfolioOperationsSurface"],
    ),
]


def run_ai_portfolio_ui_smoke(
    *,
    base_url: str | None = None,
    timeout_s: int = 120,
    screenshot_dir: Path = REPORTS_DIR / "browser_ui",
) -> dict[str, Any]:
    proc: subprocess.Popen[str] | None = None
    started_server = False
    if not base_url:
        port = _find_free_port()
        proc = _start_server(port)
        base_url = f"http://127.0.0.1:{port}"
        started_server = True
        _wait_for_health(base_url, timeout_s=min(45, timeout_s))
    base_url = _normalize_base_url(base_url)

    try:
        result = _run_playwright_flow(base_url, timeout_s=timeout_s, screenshot_dir=screenshot_dir)
        result.update({"base_url": base_url, "started_server": started_server})
        return result
    finally:
        if proc is not None:
            _stop_server(proc)


def _normalize_base_url(base_url: str) -> str:
    clean = str(base_url or "").strip().rstrip("/")
    parsed = urlparse(clean)
    if parsed.path.rstrip("/") == "/ui":
        return urlunparse(parsed._replace(path="", params="", query="", fragment="")).rstrip("/")
    return clean


def _run_playwright_flow(base_url: str, *, timeout_s: int, screenshot_dir: Path) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    timeout_ms = int(timeout_s * 1000)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"ai_portfolio_ui_smoke_{int(time.time())}.png"
    console_errors: list[str] = []
    checked: list[str] = []
    headless = os.environ.get("FINGPT_BROWSER_UI_HEADLESS", "1") != "0"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1200}, locale="ko-KR")
        context.add_init_script(
            """
            localStorage.setItem(
              'fingpt.tvChart.v1',
              JSON.stringify({ source: 'internal', symbolKey: 'SPY', interval: 'D', compareKey: '' })
            );
            """
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in {"error", "warning"} else None)
        try:
            page.goto(
                f"{base_url.rstrip('/')}/ui/?v={APP_BUNDLE_VERSION}#ai-portfolio",
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            for script in VERSIONED_SCRIPT_SELECTORS:
                page.locator(script).wait_for(state="attached", timeout=timeout_ms)
                count = page.locator(script).count()
                if count != 1:
                    raise AssertionError(f"expected one script for {script}, found {count}")
            _mark(checked, "versioned scripts")
            for expression in DOMAIN_MODULE_GLOBALS:
                page.wait_for_function(expression, timeout=timeout_ms)
            _mark(checked, "domain module globals")

            page.locator("#aiPortfolioTab").wait_for(state="visible", timeout=timeout_ms)
            page.wait_for_function(
                "document.querySelector('#homeSurfaceGrid')?.getAttribute('data-dashboard-tab') === 'ai-portfolio'",
                timeout=timeout_ms,
            )
            page.wait_for_function("typeof window.setDashboardPanelView === 'function'", timeout=timeout_ms)
            page.evaluate("window.setDashboardPanelView('all')")
            page.wait_for_function(
                "document.querySelector('#homeSurfaceGrid')?.getAttribute('data-panel-view') === 'all'",
                timeout=timeout_ms,
            )
            _mark(checked, "ai portfolio tab selected")

            for selector in [
                "#aiPortfolioOverviewSurface",
                "#aiPortfolioOpsSurface",
                "#aiPortfolioCoverageSurface",
                "#aiPortfolioSnapshotTimelineSurface",
                "#aiPortfolioOperationsSurface",
                '[data-testid="ai-portfolio-dashboard-meta"]',
                '[data-testid="ai-portfolio-dashboard-timing"]',
                "#aiPortfolioGenerate",
                "#aiPortfolioHydrateData",
                "#aiPortfolioSnapshotJob",
                "#aiPortfolioSecRefresh",
            ]:
                page.locator(selector).wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "ai portfolio core surfaces")

            for tab_test_id, tab_value, hash_value, selectors in DASHBOARD_TAB_CHECKS:
                _select_dashboard_tab(page, tab_test_id, tab_value, hash_value, timeout_ms)
                page.evaluate("window.setDashboardPanelView('all')")
                for selector in selectors:
                    page.locator(selector).wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "dashboard tab surface matrix")

            _run_dashboard_action_smoke(page, checked=checked, timeout_ms=timeout_ms)
            _mark(checked, "dashboard action smoke")

            page.get_by_test_id("ai-portfolio-tab").click()
            page.locator('[data-testid="ai-portfolio-dashboard-meta"]').wait_for(state="visible", timeout=timeout_ms)
            meta_text = page.locator('[data-testid="ai-portfolio-dashboard-meta"]').inner_text(timeout=timeout_ms)
            if not any(token in meta_text for token in ["cache hit", "fresh build", "generated", "total"]):
                raise AssertionError("dashboard cache metadata was not rendered")
            if console_errors:
                raise AssertionError("; ".join(console_errors[:5]))

            page.screenshot(path=str(screenshot_path), full_page=True)
            return {
                "status": "passed",
                "screenshot": str(screenshot_path),
                "checked": checked,
                "console_errors": console_errors,
            }
        except Exception as exc:  # noqa: BLE001
            failure_path = screenshot_dir / f"ai_portfolio_ui_smoke_failure_{int(time.time())}.png"
            try:
                page.screenshot(path=str(failure_path), full_page=True)
            except Exception as screenshot_exc:  # noqa: BLE001
                print(f"[ai_portfolio_ui_smoke] failure screenshot capture failed: {screenshot_exc}", file=sys.stderr)
            return {
                "status": "failed",
                "error": str(exc),
                "screenshot": str(failure_path),
                "checked": checked,
                "console_errors": console_errors,
            }
        finally:
            context.close()
            browser.close()


def _mark(checked: list[str], label: str) -> None:
    checked.append(label)


def _select_dashboard_tab(page: Any, tab_test_id: str, tab_value: str, hash_value: str, timeout_ms: int) -> None:
    page.get_by_test_id(tab_test_id).click()
    page.wait_for_function(
        f"document.querySelector('#homeSurfaceGrid')?.getAttribute('data-dashboard-tab') === '{tab_value}'",
        timeout=timeout_ms,
    )
    if not page.url.endswith(hash_value):
        raise AssertionError(f"{tab_test_id} did not update hash to {hash_value}: {page.url}")


def _show_all_dashboard_panels(page: Any, timeout_ms: int) -> None:
    page.wait_for_function("typeof window.setDashboardPanelView === 'function'", timeout=timeout_ms)
    page.evaluate("window.setDashboardPanelView('all')")
    page.wait_for_function(
        "document.querySelector('#homeSurfaceGrid')?.getAttribute('data-panel-view') === 'all'",
        timeout=timeout_ms,
    )


def _wait_surface_settled(page: Any, selector: str, loading_text: str, timeout_ms: int) -> str:
    page.wait_for_function(
        """
        ([selector, loadingText]) => {
          const el = document.querySelector(selector);
          return !!el && !el.textContent.includes(loadingText) && el.textContent.trim().length > 0;
        }
        """,
        arg=[selector, loading_text],
        timeout=timeout_ms,
    )
    return page.locator(selector).inner_text(timeout=timeout_ms)


def _run_dashboard_action_smoke(page: Any, *, checked: list[str], timeout_ms: int) -> None:
    _select_dashboard_tab(page, "market-dashboard-tab", "market", "#market-dashboard", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.locator("#tvChartSource").select_option("internal", timeout=timeout_ms)
    page.locator("#tvChartSymbol").select_option("SPY", timeout=timeout_ms)
    page.locator("#tvChartInterval").select_option("D", timeout=timeout_ms)
    page.locator("#tvChartCompare").select_option("", timeout=timeout_ms)
    page.get_by_test_id("tradingview-chart-apply").click()
    page.wait_for_function(
        """
        () => {
          const status = document.querySelector('#tvOverviewWidget')?.dataset?.tvStatus;
          return status === 'internal-ready' || status === 'internal-empty';
        }
        """,
        timeout=timeout_ms,
    )
    page.locator("#tvOverviewMeta").wait_for(state="visible", timeout=timeout_ms)

    _select_dashboard_tab(page, "macro-dashboard-tab", "macro", "#macro", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.locator("#macroProviderFilter").select_option("", timeout=timeout_ms)
    page.locator("#macroCategoryFilter").select_option("", timeout=timeout_ms)
    page.locator("#macroSeriesSearchInput").fill("US 10Y", timeout=timeout_ms)
    page.get_by_test_id("macro-series-search-run").click()
    page.locator("#macroSeriesSearchResults .macro-series-result").first.wait_for(state="visible", timeout=timeout_ms)
    page.locator("#macroSeriesDetailSurface .macro-detail-head").first.wait_for(state="visible", timeout=timeout_ms)

    _select_dashboard_tab(page, "quant-lab-tab", "quant", "#quant-lab", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.get_by_test_id("quant-run-history-refresh").click()
    quant_text = _wait_surface_settled(page, "#quantRunHistorySurface", "\ubd88\ub7ec\uc624\ub294 \uc911", timeout_ms)
    if "\uc2e4\ud589 \uc774\ub825 \ub85c\ub4dc \uc2e4\ud328" in quant_text:
        raise AssertionError(quant_text)

    _select_dashboard_tab(page, "ml-forecast-tab", "forecast", "#ml-forecast", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.get_by_test_id("ml-forecast-ai-provider-check").click()
    provider_text = _wait_surface_settled(page, "#forecastAiProviderSurface", "\ud655\uc778", timeout_ms)
    if "AI provider \uc0c1\ud0dc \ud655\uc778 \uc2e4\ud328" in provider_text:
        raise AssertionError(provider_text)
    page.get_by_test_id("ml-forecast-jobs-refresh").click()
    jobs_text = _wait_surface_settled(page, "#forecastJobsSurface", "\ub85c\ub4dc", timeout_ms)
    if "Forecast job \ub85c\ub4dc \uc2e4\ud328" in jobs_text:
        raise AssertionError(jobs_text)

    _select_dashboard_tab(page, "quantamental-tab", "quantamental", "#quantamental", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.locator('#languageToggle [data-language="en"]').click(timeout=timeout_ms)
    page.wait_for_function(
        """
        () => document.querySelector('#languageToggle [data-language="en"]')?.getAttribute('aria-pressed') === 'true'
        """,
        timeout=timeout_ms,
    )
    page.locator('#languageToggle [data-language="ko"]').click(timeout=timeout_ms)
    page.wait_for_function(
        """
        () => document.querySelector('#languageToggle [data-language="ko"]')?.getAttribute('aria-pressed') === 'true'
        """,
        timeout=timeout_ms,
    )
    page.get_by_test_id("quantamental-screen-run").click(timeout=timeout_ms)
    page.wait_for_function(
        """
        () => {
          const text = document.querySelector('#quantamentalScreenSurface')?.textContent || '';
          const rows = document.querySelectorAll('#quantamentalScreenSurface [data-testid="quantamental-screen-table"] tbody tr').length;
          return rows > 0 && rows <= 5 && !/failed|error|Not Found/i.test(text);
        }
        """,
        timeout=timeout_ms,
    )
    page.locator('#quantamentalScreenSurface [data-testid="quantamental-screen-table"]').wait_for(
        state="visible",
        timeout=timeout_ms,
    )
    page.locator("#quantamentalScoreMetric").select_option("momentum", timeout=timeout_ms)
    page.locator("#quantamentalScoreThreshold").fill("0", timeout=timeout_ms)
    page.locator("#quantamentalScoreScreenLimit").select_option("10", timeout=timeout_ms)
    page.get_by_test_id("quantamental-score-screen-run").click(timeout=timeout_ms)
    page.wait_for_function(
        """
        () => {
          const text = document.querySelector('#quantamentalScoreScreenSurface')?.textContent || '';
          const rows = document.querySelectorAll('#quantamentalScoreScreenSurface [data-testid="quantamental-score-screen-table"] tbody tr').length;
          return rows > 0 && rows <= 10 && text.includes('>=') && (text.includes('Momentum') || text.includes('\ubaa8\uba58\ud140'));
        }
        """,
        timeout=timeout_ms,
    )
    _mark(checked, "quantamental language toggle top 5 and score screen")

    _select_dashboard_tab(page, "ai-portfolio-tab", "ai-portfolio", "#ai-portfolio", timeout_ms)
    _show_all_dashboard_panels(page, timeout_ms)
    page.locator("#aiPortfolioOpsRefresh").click()
    ops_text = _wait_surface_settled(page, "#aiPortfolioOpsSurface", "\ud655\uc778\ud558\ub294 \uc911", timeout_ms)
    if "\uc6b4\uc601 \uc0c1\ud0dc \uc870\ud68c \uc2e4\ud328" in ops_text:
        raise AssertionError(ops_text)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(  # nosec B603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_health(base_url: str, *, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    url = f"{base_url.rstrip('/')}/api/v1/health"
    last_error = ""
    while time.time() < deadline:
        try:
            # The smoke target is the local FastAPI server started by this script.
            with urlopen(url, timeout=2) as response:  # nosec B310
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"server did not become healthy at {url}: {last_error}")


def _stop_server(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _validate_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise argparse.ArgumentTypeError("base URL must be http(s)")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise argparse.ArgumentTypeError("base URL must target localhost")
    return value.rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AI Portfolio browser smoke with Playwright.")
    parser.add_argument("--base-url", type=_validate_base_url, default=None)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--output", default="reports/ai_portfolio_ui_smoke_latest.json")
    args = parser.parse_args()

    result = run_ai_portfolio_ui_smoke(base_url=args.base_url, timeout_s=args.timeout_s)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
