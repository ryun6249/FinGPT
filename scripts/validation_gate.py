from __future__ import annotations

# ruff: noqa: E402

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import socket
# Validation runs trusted local commands without a shell.
import subprocess  # nosec B404
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            print(f"[validation_gate] stream reconfigure failed for {_stream_name}: {exc}", file=sys.stderr)

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.api import server as api_server
from core.config.settings import load_settings
from core.preflight import run_preflight
from core.schemas.response import AnalysisResponse
from core.utils.openbb_agent_compat import check_openbb_agent_contract, validate_agents_json
from core.utils.openbb_compat import build_openbb_compat_report
from core.utils.provider_versions import build_provider_version_report
from core.utils.validation_metrics import (
    claim_evidence_date_coverage,
    citation_count,
    decision_richness,
    detect_mode,
    duplicate_paragraph_ratio,
    evidence_count,
    language_ok,
    metric_as_of_coverage,
    partial_reason_is_actionable,
    quant_snapshot_present,
    topic_bucket_coverage,
    topic_final_gate,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
REPORTS_DIR = PROJECT_ROOT / "reports"
QUALITY_RESULTS_PATH = REPORTS_DIR / "quality_review_results.json"
LATENCY_RESULTS_PATH = REPORTS_DIR / "topic_latency_profile.json"
FINGPT_EVAL_CASES_PATH = Path("tests/fixtures/fingpt_eval_cases.jsonl")
API_SMOKE_TIMEOUT_S = 1500
BROWSER_UI_TIMEOUT_S = 180
BROWSER_UI_SCREENSHOT_DIR = REPORTS_DIR / "browser_ui"
_OPENBB_MESSAGE_EVENTS = {"message_chunk", "copilotMessageChunk"}

_RUNTIME_PACKAGES = (
    "fastapi",
    "pydantic",
    "qdrant-client",
    "fastembed",
    "openbb",
    "openbb-core",
    "openbb-yfinance",
    "openbb-fred",
    "openbb-sec",
    "openbb-ai",
    "sse-starlette",
    "yfinance",
    "pandas",
    "numpy",
)

_VALIDATION_QUESTIONS = {
    "msft": "마이크로소프트의 최근 리스크와 기회를 근거 중심으로 요약해주세요.",
    "tlt": "지금 장기채 매력도를 금리와 가격 흐름 기준으로 간단히 요약해주세요.",
    "tlt_topic": "거시경제와 금리 구조를 감안할 때 지금 TLT가 중장기 관점에서 매력적인지 분석해주세요.",
    "ai_semis": "AI 반도체 섹터의 경기 리스크와 실행 전략을 의사결정용으로 정리해주세요.",
    "universal": "AI semiconductors 섹터의 경기 리스크와 총평을 의사결정용으로 정리해주세요.",
    "compare": "최근 리스크와 기회를 비교해주세요.",
    "watchlist": "최근 투자 포인트를 정리해주세요.",
}


class ValidationError(RuntimeError):
    pass


class BrowserUiGateFailure(ValidationError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _timestamp_slug() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _clip(text: str, limit: int = 4000) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def run_command(
    label: str,
    command: list[str],
    *,
    timeout_s: int = 600,
    cwd: Path = PROJECT_ROOT,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    try:
        completed = subprocess.run(  # nosec B603
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout_s,
            check=False,
        )
        return {
            "label": label,
            "command": command,
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": _clip(completed.stdout),
            "stderr": _clip(completed.stderr),
            "elapsed_s": round(time.time() - started, 2),
        }
    except FileNotFoundError as exc:
        return {
            "label": label,
            "command": command,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "elapsed_s": round(time.time() - started, 2),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        stderr = exc.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "label": label,
            "command": command,
            "ok": False,
            "returncode": None,
            "stdout": _clip(stdout),
            "stderr": _clip(f"timeout after {timeout_s}s\n{stderr}".strip()),
            "elapsed_s": round(time.time() - started, 2),
        }


def evaluate_preflight_gate(report: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    checks = {str(item.get("name")): item for item in report.get("checks", []) if isinstance(item, dict)}
    failures: list[str] = []
    warnings: list[str] = []

    allowed_warning_checks = {
        "FMP_API_KEY",
        "FMP_STOCK_NEWS",
        "TRANSCRIPT_PROVIDER",
        "HF_TOKEN",
        "OPENBB_NEWS_RUNTIME",
        "OPENBB_AGENT_CONTRACT",
        "FRED_MACRO",
        "ALPHA_VANTAGE_NEWS",
        "QDRANT_COLLECTION_SCHEMA",
    }
    warning_markers = (
        "entitlement_required",
        "rate-limiting",
        "rate limiting",
        "rate-limit",
        "status 429",
        "unexpected status 429",
        "status 500",
        "unexpected status 500",
        "server error",
        "upstream",
        "not required",
        "warning-only",
        "dense fallback",
        "schema probe unavailable",
    )
    for name, item in checks.items():
        if bool(item.get("ok")):
            continue
        detail = str(item.get("detail") or "")
        lower_detail = detail.lower()
        if name in allowed_warning_checks and any(marker in lower_detail for marker in warning_markers):
            warnings.append(f"{name}: {detail}")
            continue
        failures.append(f"{name}: {detail}")

    return not failures, failures, warnings


def validate_saved_outputs(
    output_dir: Path,
    *,
    expected_modes: set[str],
    require_evidence: bool,
) -> dict[str, Any]:
    required_files = (
        output_dir / "latest_response.json",
        output_dir / "latest_report.md",
        output_dir / "latest_report.html",
        output_dir / "latest_collection.json",
    )
    missing = [str(path.name) for path in required_files if not path.exists()]
    if missing:
        raise ValidationError(f"missing output artifacts: {', '.join(missing)}")

    payload = json.loads((output_dir / "latest_response.json").read_text(encoding="utf-8"))
    mode = detect_mode(payload)
    if expected_modes and mode not in expected_modes:
        raise ValidationError(f"unexpected response mode '{mode}', expected one of {sorted(expected_modes)}")
    if str(payload.get("status") or "").lower() == "failed":
        raise ValidationError(f"response status=failed: {payload.get('error_metadata')}")
    if not language_ok(payload):
        raise ValidationError("descriptive output is not Korean-dominant")
    duplicate_ratio = duplicate_paragraph_ratio(payload)
    if duplicate_ratio["total"] >= 4 and not duplicate_ratio["ok"]:
        raise ValidationError(f"duplicate paragraph ratio too high: {duplicate_ratio['ratio']}")
    if require_evidence and (citation_count(payload) < 1 or evidence_count(payload) < 1):
        raise ValidationError("expected evidence-backed output but citations/context were empty")
    metric_coverage = metric_as_of_coverage(payload)
    if metric_coverage["total"] and not metric_coverage["ok"]:
        raise ValidationError(f"metric as_of coverage below 100%: {metric_coverage['missing']}")
    claim_coverage = claim_evidence_date_coverage(payload)
    if not claim_coverage["ok"]:
        raise ValidationError(f"claim evidence date coverage below 100%: {claim_coverage['missing']}")
    if str(payload.get("status") or "").lower() == "partial" and not partial_reason_is_actionable(payload):
        raise ValidationError("partial response did not include actionable uncertainty")
    richness = decision_richness(payload)
    if not richness.get("ok"):
        raise ValidationError(f"decision richness gate failed: {richness.get('checks')}")
    topic_gate_result: dict[str, Any] = {}
    if mode in {"sector_macro", "concept"}:
        topic_gate_result = topic_final_gate(payload)
        if not topic_gate_result.get("ok"):
            raise ValidationError(f"topic final gate failed: {topic_gate_result}")
    if mode in {"sector_macro", "concept"} and "TLT" in json.dumps(payload.get("related_tickers") or payload.get("theme") or "", ensure_ascii=False).upper():
        if not quant_snapshot_present(payload):
            raise ValidationError("TLT topic output is missing quant_snapshot")

    return {
        "mode": mode,
        "status": payload.get("status"),
        "citation_count": citation_count(payload),
        "evidence_count": evidence_count(payload),
        "metric_as_of_coverage": metric_coverage,
        "claim_evidence_date_coverage": claim_coverage,
        "decision_richness": richness,
        "duplicate_paragraph_ratio": duplicate_ratio,
        "topic_final_gate": topic_gate_result,
        "quant_snapshot_present": quant_snapshot_present(payload),
        "topic_bucket_coverage": topic_bucket_coverage(payload),
        "summary": payload.get("summary") or payload.get("executive_summary") or "",
    }


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for block in raw.strip().split("\n\n"):
        if not block or block.startswith(":"):
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        data_blob = "\n".join(data_lines)
        try:
            data = json.loads(data_blob)
        except json.JSONDecodeError:
            data = data_blob
        frames.append({"event": event, "data": data})
    return frames


def _cli_case_output_dir(name: str) -> Path:
    return OUTPUTS_DIR / f"validation_cli_{name}"


def run_code_gate() -> dict[str, Any]:
    steps = [
        run_command("pytest", [sys.executable, "-m", "pytest", ".\\tests", "-q"], timeout_s=1200),
        run_command("node-check", ["node", "--check", ".\\app\\web\\app.js"], timeout_s=120),
    ]
    for step in steps:
        if not step["ok"]:
            raise ValidationError(f"{step['label']} failed")
    return {"status": "passed", "steps": steps}


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in _RUNTIME_PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def run_runtime_compat_gate() -> dict[str, Any]:
    """Record the exact interpreter and package baseline used by validation."""

    major_minor = sys.version_info[:2]
    warnings: list[str] = []
    if major_minor < (3, 11):
        raise ValidationError(f"Python {major_minor[0]}.{major_minor[1]} is unsupported; use Python 3.11+.")
    if major_minor not in {(3, 11), (3, 12), (3, 13)}:
        warnings.append(f"Python {major_minor[0]}.{major_minor[1]} is not part of the tested local baseline.")

    return {
        "status": "passed",
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "platform": platform.platform(),
        "packages": _package_versions(),
        "warnings": warnings,
    }


def run_infrastructure_gate() -> dict[str, Any]:
    report = run_preflight()
    ok, failures, warnings = evaluate_preflight_gate(report)
    if not ok:
        raise ValidationError("; ".join(failures))
    return {"status": "passed", "preflight": report, "warnings": warnings}


def run_model_baseline_gate() -> dict[str, Any]:
    settings = load_settings()
    expected = "qwen2.5:7b"
    if str(settings.primary_model).strip() != expected:
        raise ValidationError(f"PRIMARY_MODEL mismatch: expected {expected}, got {settings.primary_model}")
    forbidden_phrases = {
        "mistral (production baseline)": ["README.md", "docs/RUNBOOK.md", "docs/ARCHITECTURE.md"],
        "Production primary: `mistral": ["docs/RUNBOOK.md"],
        "Mistral recovered": ["docs/RUNBOOK.md"],
    }
    failures: list[str] = []
    for phrase, rel_paths in forbidden_phrases.items():
        for rel_path in rel_paths:
            path = PROJECT_ROOT / rel_path
            if path.exists() and phrase in path.read_text(encoding="utf-8", errors="ignore"):
                failures.append(f"{rel_path}: forbidden legacy baseline phrase '{phrase}'")
    if failures:
        raise ValidationError("; ".join(failures))
    return {"status": "passed", "primary_model": expected}


def run_provider_compat_gate() -> dict[str, Any]:
    settings = load_settings()
    version_report = build_provider_version_report(
        require_openbb_agent=bool(getattr(settings, "openbb_agent_enabled", False))
    )
    if not version_report["critical_passed"]:
        raise ValidationError("; ".join(version_report["critical_failures"]))
    report = build_openbb_compat_report(
        sec_user_agent=settings.sec_user_agent,
        include_pip_check=True,
        include_network_smoke=False,
        include_openbb_news_runtime=True,
    )
    if not report["critical_passed"]:
        failures = [
            f"{check['name']}: {check['detail']}"
            for check in report["checks"]
            if check.get("critical") and not check.get("ok")
        ]
        raise ValidationError("; ".join(failures))
    return {"status": "passed", "provider_versions": version_report, "openbb_compat": report}


def run_forecast_ai_provider_policy_gate() -> dict[str, Any]:
    from pipelines.forecast.ai_interpretation import ai_provider_health, provider_latency_policy

    policy = provider_latency_policy()
    if not policy.get("fail_closed"):
        raise ValidationError("forecast AI provider latency policy must fail closed")
    max_latency = float(policy.get("max_latency_s") or 0.0)
    if max_latency <= 0:
        raise ValidationError("forecast AI provider latency policy has invalid max_latency_s")
    health = ai_provider_health(timeout_s=1.0)
    return {
        "status": "passed",
        "provider_status": health.get("status"),
        "provider": health.get("provider"),
        "model": health.get("model"),
        "model_available": health.get("model_available"),
        "guard_policy": health.get("guard_policy"),
        "latency_policy": policy,
        "fallback_required_when_unavailable": health.get("status") == "unavailable",
    }


def run_ui_contract_gate() -> dict[str, Any]:
    with TestClient(api_server.app) as client:
        response = client.get("/ui/")
    if response.status_code != 200:
        raise ValidationError(f"/ui/ returned {response.status_code}")
    html = response.text
    required_markers = {
        "analysis form": 'id="analysisForm"',
        "ticker input": 'id="ticker"',
        "question textarea": 'id="question"',
        "result view": 'id="resultView"',
        "home dashboard": 'id="emptyState"',
        "run history": 'id="historyList"',
        "market snapshot": 'id="homeMarketList"',
        "home news": 'id="homeNewsList"',
        "tradingview chart": 'id="tvOverviewWidget"',
        "intraday heatmap": 'id="homeHeatmap"',
    }
    missing = [name for name, marker in required_markers.items() if marker not in html]
    if missing:
        raise ValidationError(f"/ui/ is missing required DOM anchors: {', '.join(missing)}")
    return {
        "status": "passed",
        "url": "/ui/",
        "checked_markers": sorted(required_markers),
        "html_bytes": len(html.encode("utf-8", errors="ignore")),
    }


def _browser_ui_skipped(reason: str) -> dict[str, Any]:
    return {"status": "skipped", "reason": reason}


def _ensure_browser_ui_dependencies(*, required: bool = True) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec("playwright.sync_api")
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        message = (
            "Playwright is required for browser_ui_gate. Install dev dependencies with "
            "`python -m pip install -r requirements-dev.txt` and install Chromium with "
            "`python -m playwright install chromium`."
        )
        if required:
            raise ValidationError(message)
        return {"status": "skipped", "available": False, "reason": message}

    try:
        version = importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return {"available": True, "package": "playwright", "version": version}


def _find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _start_validation_server(*, timeout_s: int) -> tuple[subprocess.Popen[str], str]:
    host = "127.0.0.1"
    port = _find_free_port(host)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("FINGPT_VALIDATION_FAST_INFERENCE", "1")
    proc: subprocess.Popen[str] = subprocess.Popen(  # nosec B603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.server:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    base_url = f"http://{host}:{port}"
    health_url = _validated_health_url(base_url)
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=2)
            raise ValidationError(
                "validation UI server exited before health check passed: "
                f"returncode={proc.returncode}; stdout={_clip(stdout, 1200)}; stderr={_clip(stderr, 1200)}"
            )
        try:
            # URL is limited to http(s) health probes before urlopen.
            with urllib.request.urlopen(health_url, timeout=2) as response:  # nosec
                if response.status == 200:
                    return proc, base_url
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    _stop_validation_server(proc)
    raise ValidationError(f"validation UI server did not become healthy within {timeout_s}s: {last_error}")


def _validated_health_url(base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/api/v1/health"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(f"unsupported validation health URL: {url!r}")
    return url


def _stop_validation_server(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _assert_visible_text_or_selector(
    page: Any,
    selector: str,
    label: str,
    *,
    timeout_ms: int,
    require_text: bool = False,
) -> dict[str, str]:
    locator = page.locator(selector).first
    locator.wait_for(state="visible", timeout=timeout_ms)
    text = locator.inner_text(timeout=timeout_ms).strip()
    if require_text and not text:
        raise AssertionError(f"{label} was visible but empty ({selector})")
    return {"label": label, "selector": selector, "text": _clip(text, 300)}


def _ensure_command_panel_open(page: Any, *, timeout_ms: int) -> dict[str, str]:
    form = page.locator("#analysisForm").first
    latest_button = page.locator("#loadLatestBtn").first
    try:
        if latest_button.is_visible(timeout=1000):
            return {"label": "command panel", "selector": "#analysisForm", "text": "already visible"}
    except Exception:  # noqa: BLE001
        pass

    toggle = page.locator("#commandPanelToggle").first
    toggle.wait_for(state="visible", timeout=timeout_ms)
    if (toggle.get_attribute("aria-expanded", timeout=timeout_ms) or "").lower() == "true":
        page.evaluate(
            """() => {
                const panel = document.querySelector(".control-panel");
                const button = document.querySelector("#commandPanelToggle");
                panel?.classList.remove("is-collapsed");
                document.body.classList.add("command-panel-expanded");
                button?.setAttribute("aria-expanded", "true");
            }"""
        )
    else:
        toggle.click(timeout=timeout_ms)
    latest_button.wait_for(state="visible", timeout=timeout_ms)
    form.wait_for(state="visible", timeout=timeout_ms)
    return {"label": "command panel", "selector": "#commandPanelToggle", "text": "opened"}


def _latest_output_readiness() -> dict[str, Any]:
    required = {
        "response": OUTPUTS_DIR / "latest_response.json",
        "markdown": OUTPUTS_DIR / "latest_report.md",
        "html": OUTPUTS_DIR / "latest_report.html",
        "collection": OUTPUTS_DIR / "latest_collection.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    return {
        "ready": not missing,
        "missing": missing,
        "files": {name: str(path) for name, path in required.items()},
    }


def _run_browser_ui_checks(base_url: str, *, timeout_s: int, screenshot_dir: Path) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    timeout_ms = int(timeout_s * 1000)
    headless = os.environ.get("FINGPT_BROWSER_UI_HEADLESS", "1") != "0"
    checked: list[dict[str, str]] = []
    screenshots: dict[str, str] = {}
    current_url = f"{base_url}/ui/"
    page: Any = None

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    failure_screenshot = screenshot_dir / f"browser_ui_failure_{_timestamp_slug()}.png"
    success_screenshot = screenshot_dir / f"browser_ui_success_{_timestamp_slug()}.png"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            locale="ko-KR",
            accept_downloads=True,
        )
        context.add_init_script("localStorage.setItem('fingpt.controlPanel.v1', 'expanded');")
        try:
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(current_url, wait_until="domcontentloaded", timeout=timeout_ms)

            checked.append(_ensure_command_panel_open(page, timeout_ms=timeout_ms))

            home_selectors = [
                ("#analysisForm", "analysis form"),
                ("#marketTapeSurface", "market tape"),
                ("#marketSignalSurface", "market signals"),
                ("#homeNewsList", "home news"),
                ("#homeHeatmap", "intraday heatmap"),
                ("#historyList", "run history"),
                ("#compareMode", "compare toggle"),
                ("#watchlistAddBtn", "watchlist add control"),
                ("#watchlistList", "watchlist list"),
            ]
            for selector, label in home_selectors:
                checked.append(_assert_visible_text_or_selector(page, selector, label, timeout_ms=timeout_ms))

            page.locator("#loadLatestBtn").click(timeout=timeout_ms)
            page.locator("#resultView:not(.hidden)").wait_for(state="visible", timeout=timeout_ms)
            checked.append(_assert_visible_text_or_selector(page, "#resConfidence", "confidence", timeout_ms=timeout_ms, require_text=True))
            checked.append(_assert_visible_text_or_selector(page, "#resCitationCount", "citation count", timeout_ms=timeout_ms, require_text=True))
            checked.append(_assert_visible_text_or_selector(page, "#resChunkCount", "evidence chunk count", timeout_ms=timeout_ms, require_text=True))

            tabs = ["summary", "quant", "risk", "scenarios", "evidence", "diagnostics", "report", "raw"]
            for tab in tabs:
                page.locator(f'.tab[data-tab="{tab}"]').click(timeout=timeout_ms)
                page.locator(f'.tab-panel.active[data-panel="{tab}"]').wait_for(state="visible", timeout=timeout_ms)
                checked.append({"label": f"{tab} tab", "selector": f'[data-tab="{tab}"]', "text": "active"})

            panel_detail_checks = [
                ("summary", "#metricsTable", "metrics table"),
                ("quant", "#quantSnapshot", "quant snapshot"),
                ("risk", "#riskPanel", "risk panel"),
                ("scenarios", "#scenarioPanel", "scenario panel"),
                ("evidence", "#evidenceList", "evidence list"),
                ("diagnostics", "#diagRequest", "diagnostics request"),
                ("diagnostics", "#diagInference", "diagnostics inference"),
                ("report", "#reportMd", "markdown report"),
                ("raw", "#rawJson", "raw JSON"),
            ]
            for tab, selector, label in panel_detail_checks:
                page.locator(f'.tab[data-tab="{tab}"]').click(timeout=timeout_ms)
                page.locator(f'.tab-panel.active[data-panel="{tab}"]').wait_for(state="visible", timeout=timeout_ms)
                checked.append(_assert_visible_text_or_selector(page, selector, label, timeout_ms=timeout_ms, require_text=True))

            page.locator('.tab[data-tab="raw"]').click(timeout=timeout_ms)
            raw_text = page.locator("#rawJson").inner_text(timeout=timeout_ms)
            if "{" not in raw_text or "status" not in raw_text:
                raise AssertionError("raw JSON tab did not contain a response payload")

            error_banner = page.locator("#errorBanner:not(.hidden)")
            if error_banner.count() and error_banner.first.is_visible():
                banner_text = error_banner.first.inner_text(timeout=timeout_ms)
                forbidden = ("Traceback", "ReferenceError", "TypeError", "Unhandled", "undefined is not", "null is not")
                if any(marker in banner_text for marker in forbidden):
                    raise AssertionError(f"error banner exposed raw exception text: {_clip(banner_text, 500)}")
                checked.append({"label": "error/partial banner", "selector": "#errorBanner", "text": _clip(banner_text, 300)})

            for selector, label in [
                ("#downloadMdBtn", "markdown export button"),
                ("#downloadJsonBtn", "json export button"),
                ("#openHtmlBtn", "html report button"),
                ("#exportToggleBtn", "export menu button"),
            ]:
                checked.append(_assert_visible_text_or_selector(page, selector, label, timeout_ms=timeout_ms))
            page.locator("#exportToggleBtn").click(timeout=timeout_ms)
            page.locator("#exportMenu:not(.hidden)").wait_for(state="visible", timeout=timeout_ms)
            checked.append(_assert_visible_text_or_selector(page, "#exportMenu", "export menu", timeout_ms=timeout_ms, require_text=True))

            page.screenshot(path=str(success_screenshot), full_page=True)
            screenshots["success"] = str(success_screenshot)
            return {
                "status": "passed",
                "url": current_url,
                "headless": headless,
                "checked_interactions": checked,
                "screenshots": screenshots,
                "browser": "chromium",
            }
        except Exception as exc:  # noqa: BLE001
            details: dict[str, Any] = {
                "status": "failed",
                "url": current_url,
                "error": str(exc),
                "checked_interactions": checked,
                "screenshots": screenshots,
            }
            try:
                page.screenshot(path=str(failure_screenshot), full_page=True)
                details["screenshots"]["failure"] = str(failure_screenshot)
            except Exception as screenshot_exc:  # noqa: BLE001
                details["screenshot_error"] = str(screenshot_exc)
            try:
                details["dom_excerpt"] = _clip(page.content(), 2000)
                details["current_url"] = page.url
            except Exception as dom_exc:  # noqa: BLE001
                details["dom_excerpt_error"] = str(dom_exc)
            raise BrowserUiGateFailure(str(exc), details) from exc
        finally:
            context.close()
            browser.close()


def run_browser_ui_gate(
    *,
    skip: bool = False,
    release_candidate: bool = False,
    timeout_s: int = BROWSER_UI_TIMEOUT_S,
    screenshot_dir: Path = BROWSER_UI_SCREENSHOT_DIR,
) -> dict[str, Any]:
    if skip:
        if release_candidate:
            raise ValidationError("--skip-browser-ui is not allowed for --release-candidate")
        return _browser_ui_skipped("explicitly skipped with --skip-browser-ui")

    deps = _ensure_browser_ui_dependencies(required=True)
    readiness = _latest_output_readiness()
    if not readiness["ready"]:
        return {
            "status": "failed",
            "error": "browser UI gate requires latest output artifacts from CLI/API smoke before loading the latest run",
            "latest_output": readiness,
        }

    proc: subprocess.Popen[str] | None = None
    try:
        proc, base_url = _start_validation_server(timeout_s=min(timeout_s, 60))
        result = _run_browser_ui_checks(base_url, timeout_s=timeout_s, screenshot_dir=screenshot_dir)
        result["dependencies"] = deps
        result["latest_output"] = readiness
        return result
    except BrowserUiGateFailure as exc:
        return {**exc.details, "dependencies": deps, "latest_output": readiness}
    finally:
        _stop_validation_server(proc)


def run_openbb_agent_contract_gate() -> dict[str, Any]:
    settings = load_settings()
    name, ok, detail = check_openbb_agent_contract(settings)
    if not ok:
        raise ValidationError(f"{name}: {detail}")

    result: dict[str, Any] = {
        "status": "passed",
        "enabled": bool(getattr(settings, "openbb_agent_enabled", False)),
        "detail": detail,
    }
    if not bool(getattr(settings, "openbb_agent_enabled", False)):
        return result

    from app.api import openbb_agent
    from unittest.mock import AsyncMock, patch

    response = AnalysisResponse(
        ticker="MSFT",
        question="MSFT AI capex 리스크",
        status="success",
        summary="MSFT의 AI capex는 성장 옵션과 마진 압력을 동시에 만듭니다.",
        sentiment="Neutral",
        conclusion="추가 수익화 확인 전에는 과도한 낙관을 경계해야 합니다.",
    )
    payload = {
        "messages": [{"role": "user", "content": "MSFT AI capex 리스크"}],
        "selected_widget": {"symbol": "MSFT"},
    }
    with TestClient(api_server.app) as client, patch.object(openbb_agent, "load_settings", return_value=settings), patch.object(
        openbb_agent, "dispatch_async", new=AsyncMock(return_value=response)
    ):
        agents_resp = client.get("/agents.json")
        if agents_resp.status_code != 200:
            raise ValidationError(f"/agents.json returned {agents_resp.status_code}")
        agents_payload = agents_resp.json()
        errors = validate_agents_json(agents_payload, settings)
        if errors:
            raise ValidationError("; ".join(errors))
        with client.stream("POST", "/query", json=payload) as resp:
            if resp.status_code != 200:
                raise ValidationError(f"/query returned {resp.status_code}")
            body_text = "".join(chunk for chunk in resp.iter_text())
    frames = _parse_sse(body_text)
    events = [frame["event"] for frame in frames]
    if not (_OPENBB_MESSAGE_EVENTS & set(events)) or events[-1] != "done":
        raise ValidationError(f"/query did not emit expected OpenBB events: {events}")
    result["events"] = events
    return result


def skipped_live_smoke_gate() -> dict[str, Any]:
    return {
        "status": "skipped",
        "reason": (
            "Live CLI/API smoke is disabled by default to keep the compatibility gate bounded. "
            "Run with --run-live-smoke for release-candidate validation."
        ),
    }


def run_cli_smoke() -> dict[str, Any]:
    cases = [
        {
            "name": "msft",
            "args": [
                sys.executable,
                "app/cli/main.py",
                "--ticker",
                "MSFT",
                "--question",
                "마이크로소프트의 최근 리스크와 기회를 근거 중심으로 요약해주세요.",
                "--sources",
                "news",
                "--lookback-days",
                "7",
                "--top-k",
                "3",
                "--output-dir",
                str(_cli_case_output_dir("msft")),
            ],
            "expected_modes": {"single_ticker"},
            "require_evidence": True,
        },
        {
            "name": "tlt",
            "args": [
                sys.executable,
                "app/cli/main.py",
                "--ticker",
                "TLT",
                "--question",
                "거시경제와 금리 구조를 감안할 때 지금 TLT가 매력적인지 분석해주세요.",
                "--sources",
                "news",
                "macro",
                "--lookback-days",
                "30",
                "--top-k",
                "5",
                "--output-dir",
                str(_cli_case_output_dir("tlt")),
            ],
            "expected_modes": {"single_ticker"},
            "require_evidence": True,
        },
        {
            "name": "tlt_topic",
            "args": [
                sys.executable,
                "app/cli/main.py",
                "--topic",
                "TLT",
                "--related-ticker",
                "TLT",
                "--question",
                "거시경제와 금리 구조를 감안할 때 지금 TLT가 중장기 관점에서 매력적인지 분석해주세요.",
                "--lookback-days",
                "60",
                "--top-k",
                "10",
                "--output-dir",
                str(_cli_case_output_dir("tlt_topic")),
            ],
            "expected_modes": {"sector_macro"},
            "require_evidence": True,
        },
        {
            "name": "ai_semis",
            "args": [
                sys.executable,
                "app/cli/main.py",
                "--topic",
                "AI semiconductors",
                "--question",
                "AI 반도체 섹터의 장기 리스크와 실행 전략을 의사결정용으로 정리해주세요.",
                "--lookback-days",
                "30",
                "--top-k",
                "8",
                "--output-dir",
                str(_cli_case_output_dir("ai_semis")),
            ],
            "expected_modes": {"sector_macro"},
            "require_evidence": True,
        },
    ]

    for case in cases:
        question = _VALIDATION_QUESTIONS.get(str(case["name"]))
        if question and "--question" in case["args"]:
            question_index = case["args"].index("--question") + 1
            if question_index < len(case["args"]):
                case["args"][question_index] = question

    results: list[dict[str, Any]] = []
    for case in cases:
        case["output_dir"] = _cli_case_output_dir(case["name"])
        command_result = run_command(f"cli-{case['name']}", case["args"], timeout_s=1200)
        if not command_result["ok"]:
            raise ValidationError(f"CLI smoke '{case['name']}' failed")
        artifact_result = validate_saved_outputs(
            case["output_dir"],
            expected_modes=set(case["expected_modes"]),
            require_evidence=bool(case["require_evidence"]),
        )
        results.append(
            {
                "name": case["name"],
                "command": command_result,
                "artifacts": artifact_result,
                "output_dir": str(case["output_dir"]),
            }
        )

    return {"status": "passed", "cases": results}


def _response_json(resp) -> dict[str, Any]:
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(f"response body was not valid JSON: {exc}") from exc


def run_api_smoke() -> dict[str, Any]:
    results: dict[str, Any] = {}
    watchlist_item_id: str | None = None

    with TestClient(api_server.app) as client:
        health = client.get("/api/v1/health")
        if health.status_code != 200 or _response_json(health).get("status") != "ok":
            raise ValidationError("health endpoint failed")
        results["health"] = _response_json(health)

        preflight_resp = client.get("/api/v1/preflight")
        if preflight_resp.status_code != 200:
            raise ValidationError("preflight endpoint failed")
        results["preflight"] = _response_json(preflight_resp)

        analyze_resp = client.post(
            "/api/v1/research/analyze",
            json={
                "ticker": "MSFT",
                "question": _VALIDATION_QUESTIONS["msft"],
                "sources": ["news"],
                "lookback_days": 7,
                "top_k": 3,
                "model": "qwen",
            },
        )
        if analyze_resp.status_code != 200:
            raise ValidationError(f"analyze endpoint failed: {analyze_resp.text}")
        analyze_payload = _response_json(analyze_resp)
        if str(analyze_payload.get("status") or "").lower() == "failed":
            raise ValidationError(f"analyze returned failed status: {analyze_payload.get('error_metadata')}")
        if not language_ok(analyze_payload):
            raise ValidationError("analyze response violated Korean output policy")
        results["analyze"] = {
            "status": analyze_payload.get("status"),
            "citation_count": citation_count(analyze_payload),
            "evidence_count": evidence_count(analyze_payload),
        }

        universal_resp = client.post(
            "/api/v1/research/universal",
            json={
                "question": _VALIDATION_QUESTIONS["universal"],
                "mode_hint": "auto",
                "lookback_days": 30,
                "top_k": 8,
                "model": "qwen",
            },
        )
        if universal_resp.status_code != 200:
            raise ValidationError(f"universal endpoint failed: {universal_resp.text}")
        universal_payload = _response_json(universal_resp)
        mode = str(universal_payload.get("mode") or "")
        if mode not in {"concept", "sector_macro"}:
            raise ValidationError(f"universal routing did not route to topic mode: {mode}")
        if not language_ok(universal_payload):
            raise ValidationError("universal response violated Korean output policy")
        results["universal"] = {
            "mode": mode,
            "status": universal_payload.get("status"),
            "citation_count": citation_count(universal_payload),
            "evidence_count": evidence_count(universal_payload),
        }

        compare_resp = client.post(
            "/api/v1/research/compare",
            json={
                "tickers": ["MSFT", "NVDA"],
                "question": _VALIDATION_QUESTIONS["compare"],
                "sources": ["news"],
                "lookback_days": 7,
                "top_k": 3,
                "model": "qwen",
                "concurrency": 2,
            },
        )
        if compare_resp.status_code != 200:
            raise ValidationError(f"compare endpoint failed: {compare_resp.text}")
        compare_payload = _response_json(compare_resp)
        result_map = compare_payload.get("results") or {}
        if not isinstance(result_map, dict) or len(result_map) < 2:
            raise ValidationError("compare endpoint returned incomplete result bundle")
        compare_statuses = {ticker: payload.get("status") for ticker, payload in result_map.items()}
        if any(str(status).lower() == "failed" for status in compare_statuses.values()):
            raise ValidationError(f"compare endpoint had failed ticker responses: {compare_statuses}")
        results["compare"] = {
            "tickers": compare_payload.get("tickers"),
            "statuses": compare_statuses,
        }

        stream_body = {
            "ticker": "MSFT",
            "question": _VALIDATION_QUESTIONS["msft"],
            "sources": ["news"],
            "lookback_days": 7,
            "top_k": 3,
            "model": "qwen",
        }
        with client.stream("POST", "/api/v1/research/stream", json=stream_body) as resp:
            if resp.status_code != 200:
                raise ValidationError(f"stream endpoint failed: {resp.text}")
            body_text = "".join(chunk for chunk in resp.iter_text())
        frames = _parse_sse(body_text)
        events = [frame["event"] for frame in frames]
        if not events or events[0] != "stream_open":
            raise ValidationError("stream did not open with stream_open")
        if "stage_started" not in events or "stage_completed" not in events:
            raise ValidationError("stream did not emit stage progress events")
        if events[-1] != "result":
            raise ValidationError(f"stream did not complete with result event: {events[-1]}")
        stream_result = frames[-1].get("data") if frames else {}
        if not isinstance(stream_result, dict):
            raise ValidationError("stream result payload was not structured JSON")
        if stream_result.get("mode") != "single_ticker" or stream_result.get("ticker") != "MSFT":
            raise ValidationError(f"stream result did not return MSFT single_ticker payload: {stream_result}")
        if str(stream_result.get("status") or "").lower() == "failed":
            raise ValidationError(f"stream result failed: {stream_result.get('error_metadata')}")
        results["stream"] = {
            "events": events,
            "mode": stream_result.get("mode"),
            "ticker": stream_result.get("ticker"),
            "status": stream_result.get("status"),
        }

        latest_outputs = client.get("/api/v1/outputs/latest")
        if latest_outputs.status_code != 200:
            raise ValidationError("outputs/latest failed")
        latest_payload = _response_json(latest_outputs)
        if not latest_payload.get("response") or not latest_payload.get("has_markdown") or not latest_payload.get("has_html"):
            raise ValidationError("outputs/latest missing expected artifacts")
        results["outputs_latest"] = {
            "has_markdown": latest_payload.get("has_markdown"),
            "has_html": latest_payload.get("has_html"),
        }

        report_md = client.get("/api/v1/outputs/report.md")
        report_html = client.get("/api/v1/outputs/report.html")
        export_csv = client.get("/api/v1/outputs/export/csv")
        export_jsonl = client.get("/api/v1/outputs/export/jsonl")
        if any(resp.status_code != 200 for resp in (report_md, report_html, export_csv, export_jsonl)):
            raise ValidationError("output/report or export endpoints failed")
        results["exports"] = {
            "markdown_len": len(report_md.text),
            "html_len": len(report_html.text),
            "csv_len": len(export_csv.text),
            "jsonl_len": len(export_jsonl.text),
        }

        runs_resp = client.get("/api/v1/runs")
        if runs_resp.status_code != 200:
            raise ValidationError("runs endpoint failed")
        runs_payload = _response_json(runs_resp)
        items = runs_payload.get("items") or []
        if not items:
            raise ValidationError("runs endpoint returned no run history")
        run_id = str(items[0].get("run_id") or "")
        if not run_id:
            raise ValidationError("runs endpoint omitted run_id")
        run_resp = client.get(f"/api/v1/runs/{run_id}")
        if run_resp.status_code != 200:
            raise ValidationError(f"runs/{{id}} endpoint failed for {run_id}")
        results["runs"] = {"run_id": run_id, "count": len(items)}

        try:
            watchlist_create = client.post(
                "/api/v1/watchlist",
                json={
                    "ticker": "MSFT",
                    "question": _VALIDATION_QUESTIONS["watchlist"],
                    "sources": ["news"],
                    "lookback_days": 7,
                    "top_k": 3,
                    "model": "qwen",
                    "notes": f"validation {_timestamp_slug()}",
                },
            )
            if watchlist_create.status_code != 200:
                raise ValidationError(f"watchlist create failed: {watchlist_create.text}")
            watchlist_item_id = _response_json(watchlist_create).get("id")
            if not watchlist_item_id:
                raise ValidationError("watchlist create did not return item id")

            watchlist_list = client.get("/api/v1/watchlist")
            if watchlist_list.status_code != 200:
                raise ValidationError("watchlist list failed")

            watchlist_update = client.put(
                f"/api/v1/watchlist/{watchlist_item_id}",
                json={
                    "ticker": "MSFT",
                    "question": _VALIDATION_QUESTIONS["watchlist"],
                    "sources": ["news"],
                    "lookback_days": 7,
                    "top_k": 3,
                    "model": "qwen",
                    "notes": "updated by validation gate",
                },
            )
            if watchlist_update.status_code != 200:
                raise ValidationError(f"watchlist update failed: {watchlist_update.text}")

            watchlist_run = client.post(f"/api/v1/watchlist/{watchlist_item_id}/run")
            if watchlist_run.status_code != 200:
                raise ValidationError(f"watchlist run failed: {watchlist_run.text}")
            watchlist_run_payload = _response_json(watchlist_run)
            if str(((watchlist_run_payload.get("response") or {}).get("status") or "")).lower() == "failed":
                raise ValidationError("watchlist run returned failed response")
            results["watchlist"] = {
                "item_id": watchlist_item_id,
                "run_status": (watchlist_run_payload.get("response") or {}).get("status"),
                "run_count": ((watchlist_run_payload.get("item") or {}).get("run_count")),
            }
        finally:
            if watchlist_item_id:
                delete_resp = client.delete(f"/api/v1/watchlist/{watchlist_item_id}")
                if delete_resp.status_code != 200:
                    raise ValidationError(f"watchlist delete failed: {delete_resp.text}")

    return {"status": "passed", "results": results}


def run_api_smoke_subprocess(timeout_s: int = API_SMOKE_TIMEOUT_S) -> dict[str, Any]:
    """Run live API smoke in a child process so local LLM stalls cannot hang the gate."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUTS_DIR / f"validation_api_smoke_{_timestamp_slug()}.json"
    command_result = run_command(
        "api-smoke",
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--api-smoke-child",
            "--api-smoke-output",
            str(output_path),
        ],
        timeout_s=timeout_s,
        extra_env={"FINGPT_VALIDATION_FAST_INFERENCE": "1"},
    )
    payload: dict[str, Any] = {}
    if output_path.exists():
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"api smoke artifact was not valid JSON: {exc}") from exc
    if not command_result["ok"]:
        error = payload.get("error") if isinstance(payload, dict) else None
        raise ValidationError(error or f"api smoke failed or timed out after {timeout_s}s")
    if not payload or payload.get("status") != "passed":
        raise ValidationError(str(payload.get("error") if isinstance(payload, dict) else "api smoke failed"))
    return {
        "status": "passed",
        "command": command_result,
        "artifact": str(output_path),
        "results": payload.get("results", {}),
    }


def _prepare_gate_artifact(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)


def _read_gate_summary(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"{path.name} was not written"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"{path.name} was not valid JSON: {exc}"
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return {}, f"{path.name} did not contain a summary object"
    return summary, None


def _artifact_gate_passed(summary: dict[str, Any]) -> bool:
    return summary.get("gate_passed") is True and int(summary.get("gate_failures") or 0) == 0


def _parse_fingpt_eval_summary(stdout: str) -> tuple[dict[str, Any], str | None]:
    text = str(stdout or "").strip()
    if not text:
        return {}, "FinGPT evaluation did not write JSON stdout"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, f"FinGPT evaluation stdout was not valid JSON: {exc}"
    if not isinstance(payload, dict):
        return {}, "FinGPT evaluation stdout was not a JSON object"
    return payload, None


def _fingpt_eval_summary_passed(summary: dict[str, Any]) -> bool:
    required_metrics = ("total", "accuracy", "invalid_outputs")
    if any(metric not in summary or summary[metric] is None for metric in required_metrics):
        return False
    try:
        total = int(summary["total"])
        accuracy = float(summary["accuracy"])
        invalid_outputs = int(summary["invalid_outputs"])
    except (TypeError, ValueError):
        return False
    return total > 0 and accuracy >= 1.0 and invalid_outputs == 0


def run_fingpt_eval_gate() -> dict[str, Any]:
    result = run_command(
        "fingpt-eval",
        [
            sys.executable,
            "scripts/evaluate_fingpt_tasks.py",
            "--cases",
            str(FINGPT_EVAL_CASES_PATH),
            "--route",
            "rule-baseline",
        ],
        timeout_s=600,
    )
    summary, parse_error = _parse_fingpt_eval_summary(result.get("stdout", ""))
    if parse_error or not result["ok"] or not _fingpt_eval_summary_passed(summary):
        return {
            "status": "failed",
            "command": result,
            "summary": summary,
            "error": parse_error or "FinGPT auxiliary evaluation gate failed",
        }
    return {"status": "passed", "command": result, "summary": summary}


def run_quality_gate() -> dict[str, Any]:
    _prepare_gate_artifact(QUALITY_RESULTS_PATH)
    result = run_command(
        "quality-review",
        [
            sys.executable,
            "quality_review.py",
            "--suite",
            "all",
            "--output",
            str(QUALITY_RESULTS_PATH),
        ],
        timeout_s=7200,
        extra_env={"FINGPT_VALIDATION_FAST_INFERENCE": "1", "FINGPT_VALIDATION_INFERENCE_TIMEOUT_S": "30"},
    )
    summary, artifact_error = _read_gate_summary(QUALITY_RESULTS_PATH)
    if artifact_error or not _artifact_gate_passed(summary):
        return {
            "status": "failed",
            "command": result,
            "artifact": str(QUALITY_RESULTS_PATH),
            "summary": summary,
            "error": artifact_error or "quality review gate failed",
        }
    phase = {
        "status": "passed",
        "command": result,
        "artifact": str(QUALITY_RESULTS_PATH),
        "summary": summary,
    }
    if not result["ok"]:
        phase["warning"] = "quality review command did not exit cleanly after writing a passed gate artifact"
    return phase


def run_latency_gate() -> dict[str, Any]:
    _prepare_gate_artifact(LATENCY_RESULTS_PATH)
    result = run_command(
        "topic-latency-profile",
        [
            sys.executable,
            "scripts/profile_topic_latency.py",
            "--suite",
            "topic",
            "--output",
            str(LATENCY_RESULTS_PATH),
        ],
        timeout_s=7200,
    )
    summary, artifact_error = _read_gate_summary(LATENCY_RESULTS_PATH)
    if artifact_error or not _artifact_gate_passed(summary):
        return {
            "status": "failed",
            "command": result,
            "artifact": str(LATENCY_RESULTS_PATH),
            "summary": summary,
            "error": artifact_error or "topic latency profile gate failed",
        }
    latency = summary.get("latency") if isinstance(summary, dict) else None
    phase = {
        "status": "passed",
        "command": result,
        "artifact": str(LATENCY_RESULTS_PATH),
        "summary": summary,
        "latency": latency,
    }
    if not result["ok"]:
        phase["warning"] = "topic latency profile command did not exit cleanly after writing a passed gate artifact"
    return phase


def _write_report(report: dict[str, Any]) -> dict[str, str]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _timestamp_slug()
    latest_json = OUTPUTS_DIR / "validation_latest.json"
    stamped_json = OUTPUTS_DIR / f"validation_{stamp}.json"
    latest_md = REPORTS_DIR / "validation_latest.md"
    stamped_md = REPORTS_DIR / f"validation_{stamp}.md"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    latest_json.write_text(payload, encoding="utf-8")
    stamped_json.write_text(payload, encoding="utf-8")

    lines = [
        "# Validation Gate",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- automated_passed: {report['automated_passed']}",
    ]
    if report.get("blocking_reason"):
        lines.append(f"- blocking_reason: {report['blocking_reason']}")
    lines.append("")
    lines.append("## Automated Phases")
    lines.append("")
    for name, phase in report["phases"].items():
        lines.append(f"- {name}: {phase['status']}")
    lines.append("")
    browser_phase = report["phases"].get("browser_ui_gate")
    if isinstance(browser_phase, dict):
        lines.append("## Browser UI Gate")
        lines.append("")
        lines.append(f"- status: {browser_phase.get('status')}")
        if browser_phase.get("url"):
            lines.append(f"- url: {browser_phase['url']}")
        if browser_phase.get("browser"):
            lines.append(f"- browser: {browser_phase['browser']}")
        screenshots = browser_phase.get("screenshots") if isinstance(browser_phase.get("screenshots"), dict) else {}
        for kind, path in screenshots.items():
            lines.append(f"- {kind}_screenshot: {path}")
        checked = browser_phase.get("checked_interactions")
        if isinstance(checked, list):
            lines.append(f"- checked_interactions: {len(checked)}")
        if browser_phase.get("error"):
            lines.append(f"- error: {browser_phase['error']}")
    markdown = "\n".join(lines) + "\n"
    latest_md.write_text(markdown, encoding="utf-8")
    stamped_md.write_text(markdown, encoding="utf-8")

    return {
        "latest_json": str(latest_json),
        "stamped_json": str(stamped_json),
        "latest_md": str(latest_md),
        "stamped_md": str(stamped_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full local validation gate.")
    parser.add_argument(
        "--run-live-smoke",
        action="store_true",
        help="Run live CLI/API smoke paths that can spend several minutes in the local LLM.",
    )
    parser.add_argument("--run-quality-review", action="store_true", help="Run the quality benchmark after smoke gates.")
    parser.add_argument("--run-latency-profile", action="store_true", help="Run topic latency profiling after quality gates.")
    parser.add_argument(
        "--skip-browser-ui",
        action="store_true",
        help="Skip the browser UI gate. This is not allowed with --release-candidate.",
    )
    parser.add_argument(
        "--browser-ui-timeout",
        type=int,
        default=BROWSER_UI_TIMEOUT_S,
        help="Timeout in seconds for the Playwright browser UI gate.",
    )
    parser.add_argument(
        "--browser-ui-screenshot-dir",
        default=str(BROWSER_UI_SCREENSHOT_DIR),
        help="Directory for browser UI gate success/failure screenshots.",
    )
    parser.add_argument(
        "--release-candidate",
        action="store_true",
        help="Run live smoke, quality review, and latency profile as a release-candidate gate.",
    )
    parser.add_argument(
        "--include-fingpt-eval",
        action="store_true",
        help="Run the opt-in FinGPT auxiliary evaluation gate after code checks.",
    )
    parser.add_argument("--api-smoke-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api-smoke-output", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.api_smoke_child:
        payload: dict[str, Any]
        try:
            payload = run_api_smoke()
        except Exception as exc:  # noqa: BLE001
            payload = {"status": "failed", "error": str(exc)}
        if args.api_smoke_output:
            Path(args.api_smoke_output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        exit_code = 0 if payload.get("status") == "passed" else 1
        sys.stdout.flush()
        sys.stderr.flush()
        # The API smoke child intentionally runs live provider/LLM paths in an
        # isolated process. Some provider libraries can leave non-daemon helper
        # threads behind after the result artifact is written, so exit the child
        # process explicitly instead of letting the parent validation gate hang.
        if os.environ.get("FINGPT_VALIDATION_CHILD_FORCE_EXIT", "1") != "0":
            os._exit(exit_code)
        return exit_code

    if args.release_candidate:
        args.run_live_smoke = True
        args.run_quality_review = True
        args.run_latency_profile = True

    phases: dict[str, Any] = {}
    automated_passed = False
    blocking_reason = None
    current_phase = "startup"

    try:
        current_phase = "runtime_compat_gate"
        phases["runtime_compat_gate"] = run_runtime_compat_gate()
        current_phase = "code_gate"
        phases["code_gate"] = run_code_gate()
        if args.include_fingpt_eval:
            current_phase = "fingpt_eval_gate"
            phases["fingpt_eval_gate"] = run_fingpt_eval_gate()
            if phases["fingpt_eval_gate"].get("status") != "passed":
                raise ValidationError(str(phases["fingpt_eval_gate"].get("error") or "FinGPT auxiliary evaluation gate failed"))
        current_phase = "model_baseline_gate"
        phases["model_baseline_gate"] = run_model_baseline_gate()
        current_phase = "provider_compat_gate"
        phases["provider_compat_gate"] = run_provider_compat_gate()
        current_phase = "forecast_ai_provider_policy_gate"
        phases["forecast_ai_provider_policy_gate"] = run_forecast_ai_provider_policy_gate()
        current_phase = "openbb_agent_contract_gate"
        phases["openbb_agent_contract_gate"] = run_openbb_agent_contract_gate()
        current_phase = "ui_contract_gate"
        phases["ui_contract_gate"] = run_ui_contract_gate()
        current_phase = "infrastructure_gate"
        phases["infrastructure_gate"] = run_infrastructure_gate()
        if args.run_live_smoke:
            current_phase = "cli_smoke"
            phases["cli_smoke"] = run_cli_smoke()
            current_phase = "api_smoke"
            phases["api_smoke"] = run_api_smoke_subprocess()
            current_phase = "browser_ui_gate"
            phases["browser_ui_gate"] = run_browser_ui_gate(
                skip=args.skip_browser_ui,
                release_candidate=args.release_candidate,
                timeout_s=args.browser_ui_timeout,
                screenshot_dir=Path(args.browser_ui_screenshot_dir),
            )
            if phases["browser_ui_gate"].get("status") != "passed":
                raise ValidationError(str(phases["browser_ui_gate"].get("error") or "browser UI gate failed"))
        else:
            current_phase = "live_smoke"
            phases["live_smoke"] = skipped_live_smoke_gate()
            current_phase = "browser_ui_gate"
            phases["browser_ui_gate"] = _browser_ui_skipped("requires --run-live-smoke or --release-candidate latest output artifacts")
        if args.run_quality_review:
            current_phase = "quality_gate"
            phases["quality_gate"] = run_quality_gate()
            if phases["quality_gate"].get("status") != "passed":
                raise ValidationError(str(phases["quality_gate"].get("error") or "quality review gate failed"))
        if args.run_latency_profile:
            current_phase = "topic_latency_profile"
            phases["topic_latency_profile"] = run_latency_gate()
            if phases["topic_latency_profile"].get("status") != "passed":
                raise ValidationError(str(phases["topic_latency_profile"].get("error") or "topic latency profile gate failed"))
        automated_passed = True
    except Exception as exc:  # noqa: BLE001
        blocking_reason = str(exc)
        if current_phase in phases and isinstance(phases[current_phase], dict):
            phases[current_phase] = {**phases[current_phase], "status": "failed", "error": blocking_reason}
        else:
            phases[current_phase] = {"status": "failed", "error": blocking_reason}
    finally:
        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "automated_passed": automated_passed,
            "blocking_reason": blocking_reason,
            "phases": phases,
        }
        artifact_paths = _write_report(report)
        print(json.dumps({"automated_passed": automated_passed, "blocking_reason": blocking_reason, "artifacts": artifact_paths}, ensure_ascii=False, indent=2))
    return 0 if automated_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
