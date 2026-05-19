from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


NODE_CONTRACT = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = process.argv[1];
const context = { window: {}, console };
vm.runInNewContext(
  fs.readFileSync(path.join(root, "app/web/modules/quantamental-ui.js"), "utf8"),
  context,
  { filename: "app/web/modules/quantamental-ui.js" },
);

const englishAi = context.window.FinGPTQuantamentalUi.mainPanel({
  ai_report: {
    status: "partial",
    provider: "deterministic_interpreter",
    signal_preserved: true,
    report: {
      summary: "AAPL is a deterministic research classification.",
      used_data: {
        data_basis_date: "2026-05-15",
        analysis_period: "1Y",
        data_source: "yfinance + SEC",
        observation_count: 252,
        missing_data: "None identified",
        model: "qwen2.5:7b",
        ai_snapshot_at: "2026-05-15T09:30:00Z",
        cache_state: "fresh",
      },
      key_changes: { price: "Quant score: 72.", risk: "Risk level: medium." },
      interpretation: { data_supported: ["deterministic score only"], unavailable: ["No unsupported values were inferred."] },
      scenarios: { positive: "Scores improve.", neutral: "Evidence remains mixed.", negative: "Risk flags rise." },
      user_actions: { metrics_to_check: "Review score components.", additional_period: "Compare 3M and 1Y." },
      bull_case: ["Fundamental score: 78."],
      bear_case: ["Risk score: 45."],
      safety_note: "Research classification only.",
    },
  },
}, "ai");
assert.match(englishAi, /data-testid="quantamental-ai-used-data"/);
assert.match(englishAi, /Used Data/);
assert.match(englishAi, /Basis Date/);
assert.match(englishAi, /2026-05-15/);
assert.match(englishAi, /yfinance \+ SEC/);
assert.match(englishAi, /qwen2\.5:7b/);
assert.match(englishAi, /data-testid="quantamental-ai-key-changes"/);
assert.match(englishAi, /data-testid="quantamental-ai-interpretation"/);
assert.match(englishAi, /data-testid="quantamental-ai-scenarios"/);
assert.match(englishAi, /data-testid="quantamental-ai-user-actions"/);
assert.doesNotMatch(englishAi, /<script/);

context.window.document = { documentElement: { lang: "ko" } };
const koreanAi = context.window.FinGPTQuantamentalUi.mainPanel({
  ai_report: {
    status: "partial",
    provider: "deterministic_interpreter",
    signal_preserved: true,
    report: {
      summary: "AAPL은 deterministic 리서치 분류입니다.",
      used_data: {
        data_basis_date: "2026-05-15",
        analysis_period: "1Y",
        data_source: "yfinance + SEC",
        observation_count: 252,
        missing_data: "없음",
        model: "qwen2.5:7b",
        ai_snapshot_at: "2026-05-15T09:30:00Z",
        cache_state: "fresh",
      },
      key_changes: { 가격: "퀀트 점수: 72.", 리스크: "리스크 수준: medium." },
      interpretation: { "데이터로 확인되는 내용": ["deterministic 점수만 사용"], "확인 불가능한 내용": ["추가 추정 없음"] },
      scenarios: { "긍정 시나리오": "점수 개선", "중립 시나리오": "혼재", "부정 시나리오": "리스크 상승" },
      user_actions: { "확인할 지표": "점수 구성", "추가로 볼 기간": "3M과 1Y 비교" },
    },
  },
}, "ai");
assert.match(koreanAi, /사용 데이터/);
assert.match(koreanAi, /데이터 기준일/);
assert.match(koreanAi, /분석 기간/);
assert.match(koreanAi, /핵심 변화/);
assert.match(koreanAi, /해석/);
assert.match(koreanAi, /시나리오/);
assert.match(koreanAi, /사용자 액션/);
assert.doesNotMatch(koreanAi, /[�鍮怨諛吏由遺媛쨌]/);

console.log(JSON.stringify({ ok: true }));
"""


def test_quantamental_ai_panel_exposes_used_data_and_guardrail_sections() -> None:
    result = subprocess.run(
        ["node", "-e", textwrap.dedent(NODE_CONTRACT), str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout) == {"ok": True}
