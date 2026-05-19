from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


NODE_MODULE_CONTRACT = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[1];
const context = { window: {}, console };
for (const rel of [
  "app/web/modules/market-ui.js",
  "app/web/modules/macro-ui.js",
  "app/web/modules/forecast-ui.js",
  "app/web/modules/quant-ui.js",
  "app/web/modules/ai-portfolio-ui.js",
  "app/web/modules/quantamental-ui.js",
]) {
  vm.runInNewContext(fs.readFileSync(path.join(root, rel), "utf8"), context, { filename: rel });
}

function assertNoRawHtml(html, raw) {
  assert.equal(html.includes(raw), false, `${raw} was not escaped`);
}

const marketTape = context.window.FinGPTMarketUi.marketTape({
  advisory_only: true,
  raw_market_meta: { generated_at: "2026-05-14T00:00:00Z" },
  freshness_summary: { status: "ok", decision_usable_count: 1, item_count: 2, warning: "<stale>" },
  heatmap_summary: { status: "partial", universe_size: 2, decision_usable_count: 1, latest_as_of: "2026-05-14" },
  market_tape: [
    {
      symbol: "QQQ",
      asset_class: "equity",
      label: "<script>alert(1)</script>",
      price: 430.12,
      return_1d: -0.5,
      return_1m: 2.25,
      freshness_status: "ok",
      source: "fixture",
      is_decision_usable: true,
      as_of: "2026-05-14T00:00:00Z",
    },
    {
      symbol: "SPY",
      asset_class: "equity",
      label: "S&P 500",
      price: 510.33,
      return_1d: 1.1,
      return_1m: 3.5,
      freshness_status: "ok",
      source: "fixture",
      is_decision_usable: true,
      as_of: "2026-05-14T00:00:00Z",
    },
  ],
}, { freshnessLabels: { ok: "fresh" } });
assert.match(marketTape.meta, /1\/2 usable/);
assert.match(marketTape.html, /SPY/);
assert.match(marketTape.html, /QQQ/);
assertNoRawHtml(marketTape.html, "<script>alert(1)</script>");
assert.match(marketTape.html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);

const marketSignals = context.window.FinGPTMarketUi.marketSignals({
  signals: [{
    status: "partial",
    signal_id: "credit",
    title: "Credit stress",
    summary: "spread widening",
    evidence: ["HYG down", "LQD down"],
    interpretation: "risk-off",
  }],
});
assert.match(marketSignals, /market-signal-item/);
assert.match(marketSignals, /credit/);

const macroProvider = context.window.FinGPTMacroUi.providerHealth({
  status: "partial",
  generated_at: "2026-05-14T00:00:00Z",
  warnings: ["<provider warning>"],
  scheduler: { enabled: true },
  stale_series: [{ series_id: "DCOILWTICO" }],
  providers: [{
    provider: "fred",
    enabled: true,
    configured: true,
    latest_status: "ok",
    latest_rows: 1234,
    latest_error: "<none>",
  }],
});
assert.match(macroProvider, /Provider/);
assert.match(macroProvider, /fred/);
assert.match(macroProvider, /DCOILWTICO/);
assertNoRawHtml(macroProvider, "<provider warning>");

const forecastJobs = context.window.FinGPTForecastUi.jobs([
  {
    job_id: "job-1",
    job_status: "queued",
    ticker: "SPY",
    model_name: "ridge",
    progress_stage: "queued",
    progress_message: "waiting",
    can_cancel: true,
    result_summary: { experiment_id: "exp-1" },
  },
  {
    job_id: "job-2",
    job_status: "failed",
    ticker: "QQQ",
    model_name: "lasso",
    progress_stage: "failed",
    progress_message: "error",
    can_retry: true,
    result_summary: { status: "failed" },
  },
]);
assert.match(forecastJobs, /data-action="forecast-job-cancel"/);
assert.match(forecastJobs, /data-action="forecast-job-retry"/);
assert.match(forecastJobs, /data-action="forecast-experiment-detail"/);

const quantReport = context.window.FinGPTQuantUi.exportStorageReport({
  status: "success",
  run_count: 2,
  runs_with_exports: 1,
  export_directory_count: 3,
  total_bytes: 2048,
  stale_export_count: 1,
  format_counts: { csv: 1 },
  manifest_status_counts: { valid: 1 },
  artifact_root: "F:/very/long/path/to/quant/artifacts/that/should/be/compacted/for/display",
  top_runs: [{
    run_id: "run-1",
    export_count: 1,
    total_bytes: 2048,
    total_rows: 30,
    formats: { csv: 1 },
    newest_export_generated_at: "2026-05-14T00:00:00Z",
  }],
  stale_exports: [{
    run_id: "run-1",
    format: "csv",
    age_days: 45,
    total_bytes: 2048,
    status: "valid",
    manifest_path: "F:/artifacts/run-1/manifest.json",
  }],
});
assert.match(quantReport, /cross-run export storage report/);
assert.match(quantReport, /data-testid="quant-run-open"/);
assert.match(quantReport, /data-action="cross-run-cleanup-preview"/);

const quantamental = context.window.FinGPTQuantamentalUi.signalCard({
  ticker: "AAPL",
  market: "US",
  signal: {
    signal_label: "Buy Candidate",
    signal_score: 76.5,
    signal_confidence: "medium",
    rationale: ["Composite score is deterministic."],
    warnings: ["<risk warning>"],
  },
});
assert.match(quantamental, /Buy Candidate/);
assert.match(quantamental, /Not investment advice/);
assertNoRawHtml(quantamental, "<risk warning>");
assert.match(quantamental, /&lt;risk warning&gt;/);

const quantamentalMain = context.window.FinGPTQuantamentalUi.mainPanel({
  ticker: "AAPL",
  quant: {
    metrics: {
      algorithm: {
        algorithm_id: "quality_adjusted_momentum_v1",
        quality_adjusted_momentum_score: 72.4,
        classification: "constructive_quality_adjusted_momentum",
        used_in_composite_score: false,
      },
      algorithms: {
        volatility_adjusted_breakout: {
          algorithm_id: "volatility_adjusted_breakout_v1",
          volatility_adjusted_breakout_score: 68.2,
          classification: "constructive_breakout_setup",
          used_in_composite_score: false,
        },
        drawdown_recovery_resilience: {
          algorithm_id: "drawdown_recovery_resilience_v1",
          drawdown_recovery_resilience_score: 73.1,
          classification: "constructive_drawdown_recovery",
          used_in_composite_score: false,
        },
        liquidity_participation_stability: {
          algorithm_id: "liquidity_participation_stability_v1",
          liquidity_participation_stability_score: 76.3,
          classification: "stable_liquidity_participation",
          used_in_composite_score: false,
        },
      },
    },
    chart_data: {
      price: [{ date: "2026-01-01", close: 100 }, { date: "2026-01-02", close: 101 }],
      cumulative_return: [{ date: "2026-01-01", cumulative_return: 0 }, { date: "2026-01-02", cumulative_return: 0.01 }],
      rolling_volatility: [{ date: "2026-01-02", rolling_volatility_20d: 0.2 }],
      drawdown: [{ date: "2026-01-01", drawdown: 0 }, { date: "2026-01-02", drawdown: -0.01 }],
      volume: [{ date: "2026-01-01", volume: 1000 }],
    },
  },
  fundamentals: {
    statements: [
      { date: "2025", revenue: 100, gross_profit: 60, operating_income: 30, net_income: 20, total_equity: 80, total_assets: 160, free_cash_flow: 18, operating_cash_flow: 24, total_debt: 30 },
      { date: "2024", revenue: 90, gross_profit: 50, operating_income: 22, net_income: 16, total_equity: 72, total_assets: 150, free_cash_flow: 14, operating_cash_flow: 20, total_debt: 35 },
    ],
  },
}, "overview");
assert.match(quantamentalMain, /Margin/);
assert.match(quantamentalMain, /ROE \/ ROA/);
assert.match(quantamentalMain, /Y: price/);
assert.match(quantamentalMain, /X: date/);
assert.match(quantamentalMain, /Freshness/);
assert.match(quantamentalMain, /QAM Score/);
assert.match(quantamentalMain, /constructive_quality_adjusted_momentum/);
assert.match(quantamentalMain, /volatility_adjusted_breakout_v1/);
assert.match(quantamentalMain, /constructive_breakout_setup/);
assert.match(quantamentalMain, /drawdown_recovery_resilience_v1/);
assert.match(quantamentalMain, /constructive_drawdown_recovery/);
assert.match(quantamentalMain, /liquidity_participation_stability_v1/);
assert.match(quantamentalMain, /stable_liquidity_participation/);

const quantamentalTopSignals = context.window.FinGPTQuantamentalUi.topSignals({
  status: "ok",
  requested_count: 6,
  scored_count: 5,
  style: "balanced",
  freshness_summary: { status: "fresh" },
  top_signals: [
    { rank: 1, ticker: "NVDA", name: "NVIDIA Corporation", signal_label: "Buy Candidate", final_score: 82, fundamental_score: 76, quant_score: 90, risk_score: 70, freshness_status: "fresh" },
    { rank: 2, ticker: "AAPL", name: "Apple Inc.", signal_label: "Accumulate Watch", final_score: 72, fundamental_score: 70, quant_score: 76, risk_score: 68, freshness_status: "fresh" },
  ],
});
assert.match(quantamentalTopSignals, /data-testid="quantamental-screen-table"/);
assert.match(quantamentalTopSignals, /NVDA/);
assert.match(quantamentalTopSignals, /Composite/);

const quantamentalTopSignalsRowsFallback = context.window.FinGPTQuantamentalUi.topSignals({
  status: "ok",
  requested_count: 2,
  scored_count: 2,
  limit: 1,
  style: "balanced",
  freshness: { status: "fresh" },
  rows: [
    { rank: 1, ticker: "MSFT", name: "Microsoft Corporation", signal_label: "Accumulate Watch", final_score: 75, fundamental_score: 72, quant_score: 74, risk_score: 70, freshness_status: "fresh", usable_for_signal: true },
    { rank: 2, ticker: "CRM", name: "Salesforce, Inc.", signal_label: "Neutral / Hold-Watch", final_score: 65, fundamental_score: 60, quant_score: 62, risk_score: 66, freshness_status: "fresh", usable_for_signal: true },
  ],
});
assert.match(quantamentalTopSignalsRowsFallback, /MSFT/);
assert.doesNotMatch(quantamentalTopSignalsRowsFallback, /CRM/);
assert.match(quantamentalTopSignalsRowsFallback, /fresh/);

const quantamentalScoreScreen = context.window.FinGPTQuantamentalUi.scoreScreen({
  status: "ok",
  requested_count: 3,
  scored_count: 3,
  matched_count: 2,
  returned_count: 2,
  score_key: "quality",
  score_label: "Quality",
  min_score: 70,
  style: "balanced",
  freshness_summary: { status: "fresh" },
  matches: [
    { threshold_rank: 1, rank: 1, ticker: "NVDA", name: "NVIDIA Corporation", signal_label: "Buy Candidate", screen_score: 88, final_score: 82, value_score: 45, quality_score: 88, growth_score: 70, momentum_score: 90, low_volatility_score: 62, liquidity_score: 84, freshness_status: "fresh", usable_for_signal: true },
    { threshold_rank: 2, rank: 2, ticker: "AAPL", name: "Apple Inc.", signal_label: "Accumulate Watch", screen_score: 75, final_score: 72, value_score: 55, quality_score: 75, growth_score: 65, momentum_score: 76, low_volatility_score: 68, liquidity_score: 82, freshness_status: "fresh", usable_for_signal: true },
  ],
});
assert.match(quantamentalScoreScreen, /data-testid="quantamental-score-screen-table"/);
assert.match(quantamentalScoreScreen, /Quality/);
assert.match(quantamentalScoreScreen, /&gt;= 70/);
assert.match(quantamentalScoreScreen, /NVDA/);

context.window.document = { documentElement: { lang: "ko" } };
const quantamentalKorean = context.window.FinGPTQuantamentalUi.mainPanel({
  ticker: "AAPL",
  quant: {
    metrics: {
      algorithm: {
        algorithm_id: "quality_adjusted_momentum_v1",
        quality_adjusted_momentum_score: 72.4,
        classification: "constructive_quality_adjusted_momentum",
        used_in_composite_score: false,
      },
      algorithms: {
        volatility_adjusted_breakout: {
          algorithm_id: "volatility_adjusted_breakout_v1",
          volatility_adjusted_breakout_score: 68.2,
          classification: "constructive_breakout_setup",
          used_in_composite_score: false,
        },
        drawdown_recovery_resilience: {
          algorithm_id: "drawdown_recovery_resilience_v1",
          drawdown_recovery_resilience_score: 73.1,
          classification: "constructive_drawdown_recovery",
          used_in_composite_score: false,
        },
        liquidity_participation_stability: {
          algorithm_id: "liquidity_participation_stability_v1",
          liquidity_participation_stability_score: 76.3,
          classification: "stable_liquidity_participation",
          used_in_composite_score: false,
        },
      },
    },
    chart_data: {
      price: [{ date: "2026-01-01", close: 100 }, { date: "2026-01-02", close: 101 }],
      cumulative_return: [{ date: "2026-01-01", cumulative_return: 0 }, { date: "2026-01-02", cumulative_return: 0.01 }],
      rolling_volatility: [{ date: "2026-01-02", rolling_volatility_20d: 0.2 }],
      drawdown: [{ date: "2026-01-01", drawdown: 0 }, { date: "2026-01-02", drawdown: -0.01 }],
      volume: [{ date: "2026-01-01", volume: 1000 }],
    },
  },
  fundamentals: {
    statements: [
      { date: "2025", revenue: 100, gross_profit: 60, operating_income: 30, net_income: 20, total_equity: 80, total_assets: 160, free_cash_flow: 18, operating_cash_flow: 24, total_debt: 30 },
      { date: "2024", revenue: 90, gross_profit: 50, operating_income: 22, net_income: 16, total_equity: 72, total_assets: 150, free_cash_flow: 14, operating_cash_flow: 20, total_debt: 35 },
    ],
  },
  freshness: { status: "fresh", stale_sections: [] },
  data_quality: { missing_sections: [], fundamental_missing_metric_count: 0, quant_missing_metric_count: 0 },
}, "overview");
assert.match(quantamentalKorean, /최근 가격/);
assert.match(quantamentalKorean, /커버리지/);
assert.match(quantamentalKorean, /Y: 가격/);
assert.match(quantamentalKorean, /QAM 점수/);

const quantamentalKoreanTopSignals = context.window.FinGPTQuantamentalUi.topSignals({
  status: "ok",
  requested_count: 6,
  scored_count: 5,
  style: "balanced",
  freshness_summary: { status: "fresh" },
  top_signals: [
    { rank: 1, ticker: "NVDA", name: "NVIDIA Corporation", signal_label: "Buy Candidate", final_score: 82, fundamental_score: 76, quant_score: 90, risk_score: 70, freshness_status: "fresh" },
  ],
});
assert.match(quantamentalKoreanTopSignals, /스크리닝/);
assert.match(quantamentalKoreanTopSignals, /무결성/);
assert.doesNotMatch(quantamentalKorean + quantamentalKoreanTopSignals, /[�鍮怨諛吏由遺媛쨌]/);
context.window.document.documentElement.lang = "en";

const quantamentalCompare = context.window.FinGPTQuantamentalUi.comparisonTable({
  status: "ok",
  count: 2,
  style: "balanced",
  peer_universe: { status: "ok", added_tickers: ["ADBE"] },
  peer_groups: [{ group_key: "industry:Software" }],
  rows: [
    { ticker: "AAPL", signal_label: "Buy Candidate", final_score: 80, quality_level: "good", peer_relative: { relative_strength_score: 75, rank: 1 } },
    { ticker: "MSFT", signal_label: "Accumulate Watch", final_score: 70, quality_level: "good", peer_relative: { relative_strength_score: 25, rank: 2 } },
  ],
});
assert.match(quantamentalCompare, /Peer Strength/);
assert.match(quantamentalCompare, /data-testid="quantamental-compare-table"/);
assert.match(quantamentalCompare, /Peer universe/);

const quantamentalAudit = context.window.FinGPTQuantamentalUi.mainPanel({
  snapshot: { status: "saved", snapshot_id: "snap-1", storage: "sqlite", created_at: "2026-05-15T00:00:00Z" },
}, "audit");
assert.match(quantamentalAudit, /data-testid="quantamental-snapshot-export-json"/);
assert.match(quantamentalAudit, /data-testid="quantamental-snapshot-retention"/);

const quantamentalDiff = context.window.FinGPTQuantamentalUi.snapshotDiff({
  status: "ok",
  difference_count: 1,
  differences: [{ path: "style", before: "balanced", after: "value" }],
});
assert.match(quantamentalDiff, /Snapshot diff/);
assert.match(quantamentalDiff, /style/);

const aiMeta = context.window.FinGPTAiPortfolioUi.dashboardMeta({
  generated_at: "2026-05-14T00:00:00Z",
  cache: { hit: true, age_seconds: 2, ttl_seconds: 15 },
  debug_timing: { total: 0.25, holdings: 0.12, coverage: 0.05 },
});
assert.match(aiMeta, /ai-portfolio-dashboard-meta/);
assert.match(aiMeta, /cache hit/);
const aiOps = context.window.FinGPTAiPortfolioUi.operationList([{
  operation_type: "hydrate",
  created_at: "2026-05-14T00:00:00Z",
  operation_id: "op-1",
  status: "completed",
  request_id: "req-1",
  price_result: { created: 3 },
}]);
assert.match(aiOps, /ai-operation-item/);
assert.match(aiOps, /hydrate/);

console.log(JSON.stringify({
  ok: true,
  modules: Object.keys(context.window).filter((key) => key.startsWith("FinGPT")).sort(),
}));
"""


def test_domain_ui_modules_render_fixture_payloads() -> None:
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(NODE_MODULE_CONTRACT), str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "ok": True,
        "modules": [
            "FinGPTAiPortfolioUi",
            "FinGPTForecastUi",
            "FinGPTMacroUi",
            "FinGPTMarketUi",
            "FinGPTQuantUi",
            "FinGPTQuantamentalUi",
        ],
    }


def test_quantamental_korean_copy_is_not_mojibake() -> None:
    source = (PROJECT_ROOT / "app" / "web" / "modules" / "quantamental-ui.js").read_text(encoding="utf-8")
    for bad in ["�", "鍮", "怨", "諛", "吏", "由", "遺", "媛", "쨌"]:
        assert bad not in source
    assert "최근 가격" in source
    assert "신선도" in source
    assert "투자 조언이 아닙니다" in source
