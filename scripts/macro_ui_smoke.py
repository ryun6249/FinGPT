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
from urllib.parse import urlparse
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"


def run_macro_ui_smoke(
    *,
    base_url: str | None = None,
    timeout_s: int = 120,
    width: int = 1440,
    height: int = 1200,
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

    try:
        result = _run_playwright_flow(
            base_url,
            timeout_s=timeout_s,
            width=width,
            height=height,
            screenshot_dir=screenshot_dir,
        )
        result.update({"base_url": base_url, "started_server": started_server})
        return result
    finally:
        if proc is not None:
            _stop_server(proc)


def _run_playwright_flow(
    base_url: str,
    *,
    timeout_s: int,
    width: int,
    height: int,
    screenshot_dir: Path,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    timeout_ms = int(timeout_s * 1000)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"macro_ui_smoke_{width}x{height}_{int(time.time())}.png"
    console_errors: list[str] = []
    checked: list[str] = []
    headless = os.environ.get("FINGPT_BROWSER_UI_HEADLESS", "1") != "0"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": width, "height": height}, locale="ko-KR")
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type in {"error", "warning"} else None)
        try:
            page.goto(_macro_page_url(base_url), wait_until="domcontentloaded", timeout=timeout_ms)
            page.locator('#macroDashboardTab[aria-selected="true"]').wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "macro tab selected")
            page.locator('[data-panel-view="all"]').click()
            _mark(checked, "all macro panels selected")

            page.locator("#macroLoadStatus .decision-completion").wait_for(state="visible", timeout=timeout_ms)
            page.locator("#macroOverviewSurface .decision-status-row").wait_for(state="visible", timeout=timeout_ms)
            page.locator("#macroProviderHealthSurface .decision-status-row").wait_for(state="visible", timeout=timeout_ms)
            page.locator("#macroDataQualitySurface .decision-status-row").wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "progressive dashboard surfaces")

            for selector in [
                "#macroCategoryFilter",
                "#macroProviderFilter",
                "#macroCompareSurface",
                "#macroScenarioSurface",
                "#macroResearchPreviewSurface",
                "#macroResearchTicker",
                "#macroResearchPreviewRun",
            ]:
                page.locator(selector).wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "controls visible")

            page.locator("#macroCategoryFilter").select_option("inflation")
            page.locator("#macroSeriesSearchInput").fill("CPI")
            page.locator("#macroSeriesSearchRun").click()
            page.locator("#macroSeriesSearchResults .macro-series-result").first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
            _mark(checked, "filtered macro search")

            page.locator('[data-action="macro-scenario"][data-scenario-preset="rates_up"]').click()
            page.locator("#macroScenarioResult .decision-status-row").wait_for(state="visible", timeout=timeout_ms)
            page.locator("#macroScenarioResult .macro-warning").wait_for(state="visible", timeout=timeout_ms)
            _mark(checked, "advisory scenario")

            page.locator("#macroResearchTicker").fill("JPM")
            page.locator("#macroResearchPreviewRun").click()
            page.locator("#macroResearchPreviewResult .decision-status-row").wait_for(
                state="visible",
                timeout=timeout_ms,
            )
            _mark(checked, "research preview")

            body_text = page.locator("body").inner_text(timeout=timeout_ms)
            mojibake_tokens = ["\ufffd", "\u5a9b", "\u91c9", "\u907a", "\uc493"]
            found_mojibake = [token for token in mojibake_tokens if token in body_text]
            if found_mojibake:
                raise AssertionError(f"mojibake tokens visible: {', '.join(found_mojibake)}")
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
            failure_path = screenshot_dir / f"macro_ui_smoke_failure_{width}x{height}_{int(time.time())}.png"
            try:
                page.screenshot(path=str(failure_path), full_page=True)
            except Exception as screenshot_exc:  # noqa: BLE001
                print(f"[macro_ui_smoke] failure screenshot capture failed: {screenshot_exc}", file=sys.stderr)
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


def _macro_page_url(base_url: str) -> str:
    value = base_url.strip()
    if "#macro" in value:
        return value
    if "/ui/" in value or value.endswith("/ui"):
        return f"{value.rstrip('/')}#macro"
    return f"{value.rstrip('/')}/ui/#macro"


def _mark(checked: list[str], label: str) -> None:
    checked.append(label)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(port: int) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env["FINGPT_WEB_PORT"] = str(port)
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
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_health(base_url: str, *, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    last_error = ""
    health_url = _validated_health_url(base_url)
    while time.time() < deadline:
        try:
            # URL is limited to http(s) health probes before urlopen.
            with urlopen(health_url, timeout=3) as response:  # nosec
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"server did not become healthy at {base_url}: {last_error}")


def _validated_health_url(base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/api/v1/health"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"unsupported health check URL: {url!r}")
    return url


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Macro tab browser smoke with Playwright.")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--url", default="", help="Alias for --base-url; may be a base URL or /ui/#macro URL.")
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--screenshot-dir", default=str(REPORTS_DIR / "browser_ui"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_macro_ui_smoke(
        base_url=args.base_url or args.url or None,
        timeout_s=args.timeout_s,
        width=args.width,
        height=args.height,
        screenshot_dir=Path(args.screenshot_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
