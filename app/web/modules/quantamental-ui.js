(function initQuantamentalUi(global) {
  const QUALITY_ADJUSTED_MOMENTUM_ID = "quality_adjusted_momentum_v1";
  const VOLATILITY_ADJUSTED_BREAKOUT_ID = "volatility_adjusted_breakout_v1";
  const DRAWDOWN_RECOVERY_RESILIENCE_ID = "drawdown_recovery_resilience_v1";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmt(value, digits = 2) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return num.toFixed(digits).replace(/\.?0+$/, "");
  }

  function fmtPct(value) {
    const num = Number(value);
    return Number.isFinite(num) ? `${fmt(num * 100, 1)}%` : "-";
  }

  function statusClass(value) {
    const key = String(value || "").toLowerCase();
    if (["ok", "success", "good", "usable", "fresh", "high", "low risk"].includes(key)) return "ok";
    if (["failed", "fail", "error", "poor", "low", "high risk", "missing", "blocked"].includes(key)) return "fail";
    if (["partial", "limited", "medium", "stale", "unknown", "elevated risk", "medium risk"].includes(key)) return "warn";
    return "neutral";
  }

  const I18N = {
    en: {
      starter: "Run Analyze to load deterministic Quantamental Engine results.",
      loading: "Quantamental analysis is loading.",
      companyLimited: "company data limited",
      price: "Price",
      marketCap: "Market Cap",
      quality: "Quality",
      freshness: "Freshness",
      status: "Status",
      notAdvice: "Research classification only. Not investment advice.",
      deterministicUnavailable: "Deterministic signal is unavailable.",
      composite: "Composite",
      fundamental: "Fundamental",
      quant: "Quant",
      risk: "Risk",
      noTop: "No scored signal candidates were returned.",
      warnings: "Warnings",
      screened: "Screened",
      symbols: "symbols",
      rank: "Rank",
      ticker: "Ticker",
      company: "Company",
      signal: "Signal",
      fund: "Fund",
      fresh: "Fresh",
      integrity: "Integrity",
      usable: "usable",
      blocked: "blocked",
      staleVisible: "Stale sections remain visible",
      qaQuestionDefault: "Why is this signal classified this way?",
      qaAsk: "Ask",
      qaEmpty: "Ask a question about the deterministic result.",
      latestPrice: "Latest Price",
      priceAsOf: "Price As Of",
      oneYearReturn: "1Y Return",
      vol60d: "60D Vol",
      qamScore: "QAM Score",
      qamClass: "QAM Class",
      qamNotInComposite: "Quality-adjusted momentum is shown as a deterministic research signal and is not used in the composite score.",
      vabScore: "VAB Score",
      vabClass: "VAB Class",
      vabNotInComposite: "Volatility-adjusted breakout is a secondary quant diagnostic and is not used in the composite score.",
      drsScore: "DRS Score",
      drsClass: "DRS Class",
      drsNotInComposite: "Drawdown recovery resilience is a secondary quant diagnostic and is not used in the composite score.",
      maxDrawdown: "Max Drawdown",
      latestFiling: "Latest Filing",
      revenue: "Revenue",
      opMargin: "Op Margin",
      stale: "stale",
      missing: "missing",
      none: "none",
      chartAxisNote: "X-axis is observation date. Y-axis units are shown per chart: price, percent return, annualized volatility, drawdown, volume, and statement amounts. Missing values are skipped rather than filled.",
      coverage: "Coverage",
      fundamentalMissing: "fundamental missing",
      quantMissing: "quant missing",
      freshnessScore: "freshness score",
      missingFactors: "missing factors",
      missingMetricsRemain: "Missing metrics remain explicit",
      missingMetrics: "Missing metrics",
      fundamentalMetrics: "Fundamental Metrics",
      quantMetrics: "Quant Metrics",
      valuation: "Valuation",
      riskUnavailable: "Risk unavailable.",
      peerRelative: "Peer Relative",
      scope: "Scope",
      peers: "Peers",
      strength: "Strength",
      secEvidence: "SEC Evidence",
      filings: "Filings",
      facts: "Facts",
      latest: "Latest",
      riskFlags: "Risk Flags",
      qualityFlags: "Quality Flags",
      auditSnapshot: "Audit Snapshot",
      snapshot: "Snapshot",
      storage: "Storage",
      created: "Created",
      exportJson: "export JSON",
      exportCsv: "export CSV",
      diffLatest: "diff latest",
      retentionPreview: "retention preview",
      aiReport: "AI Report",
      usedData: "Used Data",
      dataBasisDate: "Basis Date",
      analysisPeriod: "Analysis Period",
      dataSource: "Data Source",
      observations: "Observations",
      missingData: "Missing Data",
      model: "Model",
      aiSnapshot: "AI Snapshot",
      cacheState: "Cache",
      keyChanges: "Key Changes",
      interpretation: "Interpretation",
      scenarios: "Scenarios",
      userActions: "User Actions",
      unavailable: "Unavailable",
      provider: "Provider",
      signalPreserved: "signal preserved",
      aiUnavailable: "AI report unavailable. Deterministic engine results remain visible.",
      bullCase: "Bull Case",
      bearCase: "Bear Case",
      qaTitle: "Q&A",
      score: "Score",
      level: "Level",
      warningsCount: "Warnings",
      freshScore: "Fresh Score",
      signalUsable: "Signal Usable",
      yes: "yes",
      no: "no",
      strictGate: "Strict gate",
      strictPolicyDefault: "core data must be fresh and complete",
      blocking: "blocking",
      optional: "optional",
      section: "Section",
      asOf: "As Of",
      age: "Age",
      basis: "Basis",
      action: "Action",
      refreshable: "refreshable",
      reported: "reported",
      errors: "Errors",
      freshnessWarnings: "Freshness Warnings",
      noValues: "No values available.",
      metric: "Metric",
      value: "Value",
      noFilingExcerpts: "No filing excerpts available.",
      noConceptProvenance: "No SEC concept provenance available.",
      form: "Form",
      filed: "Filed",
      excerpt: "Excerpt",
      source: "Source",
      field: "Field",
      concept: "Concept",
      chartUnavailable: "Chart unavailable.",
      xDate: "date",
      yAxis: "Y",
      xAxis: "X",
      noComparisonRows: "No comparison rows returned.",
      peerUniverse: "Peer universe",
      added: "added",
      tickers: "tickers",
      peerGroups: "peer groups",
      peerStrength: "Peer Strength",
      snapshotDiff: "Snapshot diff",
      changedFields: "changed field(s)",
      path: "Path",
      before: "Before",
      after: "After",
      noDiff: "No tracked snapshot fields changed.",
      retentionPreviewLabel: "Retention preview",
      keepLast: "keep last",
      prune: "prune",
      snapshots: "snapshot(s)",
      noSnapshotsPruned: "No snapshots would be pruned.",
      noEvidenceMetrics: "No evidence metrics returned.",
      caveats: "Caveats",
      noAnswer: "No answer.",
      factorLabels: {
        value: "Value",
        quality: "Quality",
        growth: "Growth",
        momentum: "Momentum",
        lowVolatility: "Low Volatility",
        liquidity: "Liquidity",
        drawdownResilience: "Drawdown Resilience",
      },
      chart: {
        priceTitle: "Price + SMA",
        priceY: "price",
        close: "Close",
        sma50: "SMA 50",
        sma200: "SMA 200",
        priceNote: "Trend view: close above both moving averages usually supports trend strength; breaks below them flag weakening momentum.",
        cumulativeTitle: "Cumulative Return",
        cumulativeY: "total return",
        cumulativeLegend: "Cumulative return",
        cumulativeNote: "Shows compounded performance over the selected lookback from the first visible bar.",
        volatilityTitle: "Rolling Volatility",
        volatilityY: "annualized vol",
        volatilityLegend: "20D realized volatility",
        volatilityNote: "Higher values mean the price path has become more unstable over the recent 20-day window.",
        drawdownTitle: "Drawdown",
        drawdownY: "drawdown",
        drawdownLegend: "Drawdown",
        drawdownNote: "Measures the decline from the latest running peak; deeper negative values indicate larger capital impairment.",
        volumeTitle: "Volume",
        volumeY: "shares",
        volumeLegend: "Volume",
        volumeNote: "Volume gives liquidity context for whether signals are practical at realistic size.",
        revenueTitle: "Revenue / Income",
        revenueY: "statement amount",
        revenueLegend: "Revenue",
        incomeLegend: "Net income",
        revenueNote: "Compares top-line scale with bottom-line profitability across reported periods.",
        marginTitle: "Margin",
        marginY: "margin",
        grossMargin: "Gross margin",
        operatingMargin: "Operating margin",
        netMargin: "Net margin",
        marginNote: "Margins show whether growth converts into durable profitability instead of only revenue expansion.",
        cashFlowTitle: "Cash Flow",
        cashFlowY: "cash flow",
        fcfLegend: "Free cash flow",
        ocfLegend: "Operating cash flow",
        cashFlowNote: "Cash-flow conversion helps separate accounting earnings from internally generated cash.",
        balanceTitle: "Balance Sheet",
        balanceY: "balance sheet",
        assetsLegend: "Assets",
        debtLegend: "Debt",
        balanceNote: "Assets and debt give scale and leverage context for the risk score.",
        returnsTitle: "ROE / ROA",
        returnsY: "return ratio",
        roeLegend: "ROE",
        roaLegend: "ROA",
        returnsNote: "Capital efficiency view: ROE can be leverage-sensitive, so ROA provides a cleaner asset-return cross-check.",
      },
      tabs: { overview: "Overview", fundamental: "Fundamental", quant: "Quant", risk: "Risk", valuation: "Valuation", peer: "Peer", sec: "SEC", audit: "Audit", ai: "AI", qa: "Q&A" },
    },
    ko: {
      starter: "분석을 실행하면 deterministic Quantamental Engine 결과가 표시됩니다.",
      loading: "Quantamental 분석을 로드 중입니다.",
      companyLimited: "기업 데이터 제한",
      price: "가격",
      marketCap: "시가총액",
      quality: "품질",
      freshness: "신선도",
      status: "상태",
      notAdvice: "리서치 분류용입니다. 투자 조언이 아닙니다.",
      deterministicUnavailable: "Deterministic 신호를 사용할 수 없습니다.",
      composite: "복합",
      fundamental: "펀더멘털",
      quant: "퀀트",
      risk: "리스크",
      noTop: "점수화된 신호 후보가 반환되지 않았습니다.",
      warnings: "경고",
      screened: "스크리닝",
      symbols: "개 종목",
      rank: "순위",
      ticker: "티커",
      company: "기업",
      signal: "신호",
      fund: "펀더",
      fresh: "신선도",
      integrity: "무결성",
      usable: "사용 가능",
      blocked: "차단",
      staleVisible: "남은 stale 섹션",
      qaQuestionDefault: "이 신호가 이렇게 분류된 이유는 무엇인가요?",
      qaAsk: "질문",
      qaEmpty: "deterministic 결과에 대해 질문하세요.",
      latestPrice: "최근 가격",
      priceAsOf: "가격 기준일",
      oneYearReturn: "1년 수익률",
      vol60d: "60일 변동성",
      qamScore: "QAM 점수",
      qamClass: "QAM 분류",
      qamNotInComposite: "품질 조정 모멘텀은 결정론적 리서치 신호로만 표시되며 복합 점수에는 반영하지 않습니다.",
      vabScore: "VAB 점수",
      vabClass: "VAB 분류",
      vabNotInComposite: "변동성 조정 돌파는 보조 퀀트 진단 지표이며 복합 점수에는 반영하지 않습니다.",
      drsScore: "DRS 점수",
      drsClass: "DRS 분류",
      drsNotInComposite: "낙폭 회복 탄력성은 보조 퀀트 진단 지표이며 복합 점수에는 반영하지 않습니다.",
      maxDrawdown: "최대 낙폭",
      latestFiling: "최근 공시",
      revenue: "매출",
      opMargin: "영업이익률",
      stale: "stale",
      missing: "누락",
      none: "없음",
      chartAxisNote: "X축은 관측일입니다. Y축 단위는 차트별로 가격, 수익률, 연율화 변동성, 낙폭, 거래량, 재무제표 금액으로 표시됩니다. 누락값은 임의로 채우지 않고 제외합니다.",
      coverage: "커버리지",
      fundamentalMissing: "펀더멘털 누락",
      quantMissing: "퀀트 누락",
      freshnessScore: "신선도 점수",
      missingFactors: "누락 팩터",
      missingMetricsRemain: "누락 지표는 명시적으로 유지됩니다",
      missingMetrics: "누락 지표",
      fundamentalMetrics: "펀더멘털 지표",
      quantMetrics: "퀀트 지표",
      valuation: "밸류에이션",
      riskUnavailable: "리스크 정보를 사용할 수 없습니다.",
      peerRelative: "피어 상대 비교",
      scope: "범위",
      peers: "피어",
      strength: "강도",
      secEvidence: "SEC 근거",
      filings: "공시",
      facts: "팩트",
      latest: "최근",
      riskFlags: "리스크 플래그",
      qualityFlags: "품질 플래그",
      auditSnapshot: "감사 스냅샷",
      snapshot: "스냅샷",
      storage: "저장소",
      created: "생성",
      exportJson: "JSON 내보내기",
      exportCsv: "CSV 내보내기",
      diffLatest: "최근 차이",
      retentionPreview: "보존 미리보기",
      aiReport: "AI 리포트",
      usedData: "사용 데이터",
      dataBasisDate: "데이터 기준일",
      analysisPeriod: "분석 기간",
      dataSource: "데이터 소스",
      observations: "관측치",
      missingData: "결측치",
      model: "모델",
      aiSnapshot: "AI 기준 시각",
      cacheState: "캐시",
      keyChanges: "핵심 변화",
      interpretation: "해석",
      scenarios: "시나리오",
      userActions: "사용자 액션",
      unavailable: "확인 불가",
      provider: "공급자",
      signalPreserved: "신호 보존",
      aiUnavailable: "AI 리포트를 사용할 수 없습니다. Deterministic Engine 결과는 계속 표시됩니다.",
      bullCase: "상승 근거",
      bearCase: "하락 근거",
      qaTitle: "Q&A",
      score: "점수",
      level: "등급",
      warningsCount: "경고",
      freshScore: "신선도 점수",
      signalUsable: "신호 사용 가능",
      yes: "예",
      no: "아니오",
      strictGate: "엄격 게이트",
      strictPolicyDefault: "핵심 데이터는 신선하고 완전해야 합니다",
      blocking: "차단",
      optional: "선택",
      section: "섹션",
      asOf: "기준일",
      age: "경과",
      basis: "기준",
      action: "조치",
      refreshable: "갱신 가능",
      reported: "보고됨",
      errors: "오류",
      freshnessWarnings: "신선도 경고",
      noValues: "표시할 값이 없습니다.",
      metric: "지표",
      value: "값",
      noFilingExcerpts: "표시할 공시 발췌가 없습니다.",
      noConceptProvenance: "SEC concept 출처가 없습니다.",
      form: "양식",
      filed: "제출일",
      excerpt: "발췌",
      source: "출처",
      field: "필드",
      concept: "Concept",
      chartUnavailable: "차트를 사용할 수 없습니다.",
      xDate: "날짜",
      yAxis: "Y",
      xAxis: "X",
      noComparisonRows: "비교 행이 반환되지 않았습니다.",
      peerUniverse: "피어 유니버스",
      added: "추가",
      tickers: "티커",
      peerGroups: "피어 그룹",
      peerStrength: "피어 강도",
      snapshotDiff: "스냅샷 차이",
      changedFields: "변경 필드",
      path: "경로",
      before: "이전",
      after: "이후",
      noDiff: "추적 대상 스냅샷 필드 변경이 없습니다.",
      retentionPreviewLabel: "보존 미리보기",
      keepLast: "최근 보존",
      prune: "정리",
      snapshots: "스냅샷",
      noSnapshotsPruned: "정리될 스냅샷이 없습니다.",
      noEvidenceMetrics: "근거 지표가 반환되지 않았습니다.",
      caveats: "주의 사항",
      noAnswer: "답변이 없습니다.",
      factorLabels: {
        value: "가치",
        quality: "품질",
        growth: "성장",
        momentum: "모멘텀",
        lowVolatility: "저변동성",
        liquidity: "유동성",
        drawdownResilience: "낙폭 회복",
      },
      chart: {
        priceTitle: "가격 + SMA",
        priceY: "가격",
        close: "종가",
        sma50: "SMA 50",
        sma200: "SMA 200",
        priceNote: "종가가 두 이동평균 위에 있으면 추세 강도를 지지하고, 하향 이탈은 모멘텀 약화를 경고합니다.",
        cumulativeTitle: "누적 수익률",
        cumulativeY: "총수익률",
        cumulativeLegend: "누적 수익률",
        cumulativeNote: "선택한 lookback의 첫 관측치 이후 복리 성과를 보여줍니다.",
        volatilityTitle: "롤링 변동성",
        volatilityY: "연율화 변동성",
        volatilityLegend: "20일 실현 변동성",
        volatilityNote: "값이 높을수록 최근 20일 가격 경로가 더 불안정해졌다는 의미입니다.",
        drawdownTitle: "낙폭",
        drawdownY: "낙폭",
        drawdownLegend: "낙폭",
        drawdownNote: "최근 고점 대비 하락폭을 측정합니다. 음수 폭이 깊을수록 손실 위험이 큽니다.",
        volumeTitle: "거래량",
        volumeY: "주식 수",
        volumeLegend: "거래량",
        volumeNote: "거래량은 실제 운용 규모에서 신호가 실행 가능한지 판단하는 유동성 맥락을 제공합니다.",
        revenueTitle: "매출 / 순이익",
        revenueY: "재무제표 금액",
        revenueLegend: "매출",
        incomeLegend: "순이익",
        revenueNote: "매출 규모와 최종 수익성을 함께 비교합니다.",
        marginTitle: "마진",
        marginY: "마진",
        grossMargin: "매출총이익률",
        operatingMargin: "영업이익률",
        netMargin: "순이익률",
        marginNote: "성장이 매출 확대에 그치지 않고 지속 가능한 수익성으로 전환되는지 확인합니다.",
        cashFlowTitle: "현금흐름",
        cashFlowY: "현금흐름",
        fcfLegend: "잉여현금흐름",
        ocfLegend: "영업현금흐름",
        cashFlowNote: "현금흐름 전환은 회계상 이익과 실제 내부 창출 현금을 구분하는 데 도움을 줍니다.",
        balanceTitle: "재무상태표",
        balanceY: "재무상태",
        assetsLegend: "자산",
        debtLegend: "부채",
        balanceNote: "자산과 부채는 리스크 점수의 규모와 레버리지 맥락을 제공합니다.",
        returnsTitle: "ROE / ROA",
        returnsY: "수익성 비율",
        roeLegend: "ROE",
        roaLegend: "ROA",
        returnsNote: "ROE는 레버리지 영향을 받을 수 있으므로 ROA가 자산수익률을 교차 확인합니다.",
      },
      tabs: { overview: "개요", fundamental: "재무", quant: "퀀트", risk: "리스크", valuation: "밸류에이션", peer: "피어", sec: "SEC", audit: "감사", ai: "AI", qa: "Q&A" },
    },
  };

  function activeLanguage() {
    const lang = String(global?.document?.documentElement?.lang || "en").toLowerCase();
    return lang.startsWith("ko") ? "ko" : "en";
  }

  function copy() {
    return I18N[activeLanguage()] || I18N.en;
  }

  function empty(message) {
    return `<div class="home-news-empty">${escapeHtml(message)}</div>`;
  }

  function starter() {
    return empty(copy().starter);
  }

  function loading(message = "") {
    return empty(message || copy().loading);
  }

  function error(message) {
    return `<div class="decision-warning">${escapeHtml(message || "Quantamental error")}</div>`;
  }

  function metric(label, value, cls = "neutral") {
    return `
      <div class="decision-metric ${escapeHtml(cls)}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `;
  }

  function companyHeader(data) {
    const company = data?.company || {};
    const quality = data?.data_quality || {};
    const freshness = data?.freshness || quality?.freshness || {};
    return `
      <div class="quantamental-company-header" data-testid="quantamental-company-header">
        <div>
          <strong>${escapeHtml(company.name || data?.ticker || "-")}</strong>
          <span>${escapeHtml([company.sector, company.industry].filter(Boolean).join(" / ") || copy().companyLimited)}</span>
        </div>
        <div class="decision-metric-grid dense">
          ${metric(copy().price, company.current_price == null ? "-" : fmt(company.current_price), "neutral")}
          ${metric(copy().marketCap, compact(company.market_cap), "neutral")}
          ${metric(copy().quality, quality.quality_level || "unknown", statusClass(quality.quality_level))}
          ${metric(copy().freshness, freshness.status || "unknown", statusClass(freshness.status))}
          ${metric(copy().status, data?.status || "unknown", statusClass(data?.status))}
        </div>
      </div>
    `;
  }

  function signalCard(data) {
    const signal = data?.signal || {};
    const warnings = Array.isArray(signal.warnings) ? signal.warnings : [];
    return `
      <div class="quantamental-signal-card ${escapeHtml(statusClass(signal.signal_confidence))}" data-testid="quantamental-signal-card">
        <div>
          <span class="muted">${escapeHtml(data?.ticker || "")} / ${escapeHtml(data?.market || "")}</span>
          <strong>${escapeHtml(signal.signal_label || "Insufficient Data")}</strong>
          <p>${escapeHtml((signal.rationale || [])[0] || copy().deterministicUnavailable)}</p>
        </div>
        <div class="quantamental-score-ring">
          <span>${escapeHtml(fmt(signal.signal_score))}</span>
          <small>${escapeHtml(signal.signal_confidence || "low")}</small>
        </div>
      </div>
      <div class="decision-warning">${escapeHtml(copy().notAdvice)}</div>
      ${warnings.length ? `<ul class="quantamental-warning-list">${warnings.slice(0, 8).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    `;
  }

  function scoreDashboard(data) {
    const c = data?.composite || {};
    const risk = data?.risk || {};
    return `
      <div class="decision-metric-grid dense" data-testid="quantamental-composite-score">
        ${metric(copy().composite, fmt(c.final_score), scoreClass(c.final_score))}
        ${metric(copy().fundamental, fmt(c.fundamental_score), scoreClass(c.fundamental_score))}
        ${metric(copy().quant, fmt(c.quant_score), scoreClass(c.quant_score))}
        ${metric(copy().risk, fmt(c.risk_score), statusClass(risk.risk_level))}
      </div>
      <div class="decision-summary ${escapeHtml(statusClass(data?.status))}">
        ${escapeHtml(c.style || "balanced")} / ${escapeHtml(c.data_conflict_classification || "mixed_or_insufficient_data")}
      </div>
      ${quantAlgorithmSummary(data)}
    `;
  }

  function scoreClass(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "neutral";
    if (num >= 70) return "ok";
    if (num >= 45) return "warn";
    return "fail";
  }

  function algorithmStatusClass(value) {
    const key = String(value || "").toLowerCase();
    if (key.includes("no_confirmed")) return "warn";
    if (key.includes("confirmed")) return "ok";
    if (key.includes("resilient")) return "ok";
    if (key.includes("strong") || key.includes("constructive")) return "ok";
    if (key.includes("weak") || key.includes("fragile")) return "fail";
    if (key.includes("mixed") || key.includes("insufficient")) return "warn";
    return "neutral";
  }

  function factorGrid(data) {
    const f = data?.factors || {};
    const peer = data?.peer_relative || {};
    const labels = copy().factorLabels;
    const items = [
      [labels.value, f.value_score],
      [labels.quality, f.quality_score],
      [labels.growth, f.growth_score],
      [labels.momentum, f.momentum_score],
      [labels.lowVolatility, f.low_volatility_score],
      [labels.liquidity, f.liquidity_score],
    ];
    return `
      <div class="quantamental-factor-grid" data-testid="quantamental-factor-grid">
        ${items.map(([label, value]) => `
          <div class="quantamental-factor">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(fmt(value))}</strong>
            <b style="width:${Number.isFinite(Number(value)) ? Math.max(2, Math.min(100, Number(value))) : 2}%"></b>
          </div>
        `).join("")}
      </div>
      ${peer.relative_strength_score == null ? "" : `<div class="decision-summary ${escapeHtml(scoreClass(peer.relative_strength_score))}">${escapeHtml(copy().peerStrength)} ${escapeHtml(fmt(peer.relative_strength_score))} / ${escapeHtml(copy().rank)} ${escapeHtml(peer.rank || "-")} / ${escapeHtml(copy().peers)} ${escapeHtml(peer.peer_count || "-")}</div>`}
    `;
  }

  function quantAlgorithmSummary(data) {
    const cpy = copy();
    const metrics = data?.quant?.metrics || {};
    const algorithm = metrics.algorithm || {};
    const algorithms = metrics.algorithms || {};
    const breakout = algorithms.volatility_adjusted_breakout || metrics.volatility_adjusted_breakout || {};
    const resilience = algorithms.drawdown_recovery_resilience || metrics.drawdown_recovery_resilience || {};
    if (!algorithm.algorithm_id && !breakout.algorithm_id && !resilience.algorithm_id) return "";
    const algorithmId = algorithm.algorithm_id || QUALITY_ADJUSTED_MOMENTUM_ID;
    const breakoutId = breakout.algorithm_id || VOLATILITY_ADJUSTED_BREAKOUT_ID;
    const resilienceId = resilience.algorithm_id || DRAWDOWN_RECOVERY_RESILIENCE_ID;
    return `
      ${algorithm.algorithm_id ? `
        <div class="decision-summary ${escapeHtml(algorithmStatusClass(algorithm.classification))}" data-testid="quantamental-quant-algorithm">
          ${escapeHtml(algorithmId)} / ${escapeHtml(cpy.qamScore)} ${escapeHtml(fmt(algorithm.quality_adjusted_momentum_score))} / ${escapeHtml(cpy.qamClass)} ${escapeHtml(algorithm.classification || cpy.unavailable)}
          <br /><span class="muted">${escapeHtml(cpy.qamNotInComposite)}</span>
        </div>
      ` : ""}
      ${breakout.algorithm_id ? `
        <div class="decision-summary ${escapeHtml(algorithmStatusClass(breakout.classification))}" data-testid="quantamental-volatility-breakout-algorithm">
          ${escapeHtml(breakoutId)} / ${escapeHtml(cpy.vabScore)} ${escapeHtml(fmt(breakout.volatility_adjusted_breakout_score))} / ${escapeHtml(cpy.vabClass)} ${escapeHtml(breakout.classification || cpy.unavailable)}
          <br /><span class="muted">${escapeHtml(cpy.vabNotInComposite)}</span>
        </div>
      ` : ""}
      ${resilience.algorithm_id ? `
        <div class="decision-summary ${escapeHtml(algorithmStatusClass(resilience.classification))}" data-testid="quantamental-drawdown-resilience-algorithm">
          ${escapeHtml(resilienceId)} / ${escapeHtml(cpy.drsScore)} ${escapeHtml(fmt(resilience.drawdown_recovery_resilience_score))} / ${escapeHtml(cpy.drsClass)} ${escapeHtml(resilience.classification || cpy.unavailable)}
          <br /><span class="muted">${escapeHtml(cpy.drsNotInComposite)}</span>
        </div>
      ` : ""}
    `;
  }

  function mainPanel(data, activeTab = "overview") {
    const tabs = [
      ["overview", copy().tabs.overview],
      ["fundamental", copy().tabs.fundamental],
      ["quant", copy().tabs.quant],
      ["risk", copy().tabs.risk],
      ["valuation", copy().tabs.valuation],
      ["peer", copy().tabs.peer],
      ["sec", copy().tabs.sec],
      ["audit", copy().tabs.audit],
      ["ai", copy().tabs.ai],
      ["qa", copy().tabs.qa],
    ];
    const body = {
      overview: overviewPanel(data),
      fundamental: objectPanel(copy().fundamentalMetrics, data?.fundamentals?.metrics || {}, data?.fundamentals?.missing_metrics || [], "fundamental"),
      quant: objectPanel(copy().quantMetrics, data?.quant?.metrics || {}, data?.quant?.missing_metrics || [], "quant"),
      risk: riskPanel(data?.risk || {}),
      valuation: objectPanel(copy().valuation, data?.fundamentals?.metrics?.valuation || {}, [], "valuation"),
      peer: peerPanel(data?.peer_relative || {}),
      sec: secPanel(data?.sec_evidence || {}),
      audit: auditPanel(data?.snapshot || {}),
      ai: aiPanel(data?.ai_report || {}),
      qa: qaPanel(),
    }[activeTab] || overviewPanel(data);
    return `
      <div class="quantamental-tabs" role="tablist" aria-label="Quantamental detail tabs" data-testid="quantamental-detail-tabs">
        ${tabs.map(([key, label]) => `
          <button type="button" class="${key === activeTab ? "active" : ""}" data-quantamental-tab="${escapeHtml(key)}" aria-pressed="${key === activeTab ? "true" : "false"}">${escapeHtml(label)}</button>
        `).join("")}
      </div>
      <div class="quantamental-tab-panel">${body}</div>
    `;
  }

  function overviewPanel(data) {
    const cpy = copy();
    const chart = cpy.chart;
    const chartData = data?.quant?.chart_data || {};
    const statements = data?.fundamentals?.statements || [];
    const ratioRows = fundamentalRatioRows(statements);
    const qMetrics = data?.quant?.metrics || {};
    const fMetrics = data?.fundamentals?.metrics || {};
    const freshness = data?.freshness || data?.data_quality?.freshness || {};
    const latestPrice = lastFinite(chartData.price || [], "close");
    const latestPriceDate = lastDate(chartData.price || []);
    const latestStatement = Array.isArray(statements) && statements.length ? statements[0] : {};
    const missingMetrics = [
      ...(data?.fundamentals?.missing_metrics || []),
      ...(data?.quant?.missing_metrics || []),
      ...(data?.factors?.missing_factor_inputs || []),
    ];
    const algorithm = qMetrics?.algorithm || {};
    const breakout = qMetrics?.algorithms?.volatility_adjusted_breakout || {};
    const resilience = qMetrics?.algorithms?.drawdown_recovery_resilience || {};
    return `
      <div data-testid="quantamental-overview-tab">
        <div class="quantamental-overview-brief">
          <div class="decision-metric-grid dense">
            ${metric(cpy.latestPrice, latestPrice == null ? "-" : fmt(latestPrice), "neutral")}
            ${metric(cpy.priceAsOf, latestPriceDate || "-", statusClass(freshness?.sections?.prices?.status))}
            ${metric(cpy.oneYearReturn, fmtPct(qMetrics?.return?.return_252d), scoreClass((qMetrics?.return?.return_252d || 0) * 100 + 50))}
            ${metric(cpy.vol60d, fmtPct(qMetrics?.volatility?.realized_volatility_60d), statusClass(qMetrics?.liquidity?.liquidity_risk))}
            ${metric(cpy.qamScore, fmt(algorithm.quality_adjusted_momentum_score), scoreClass(algorithm.quality_adjusted_momentum_score))}
            ${metric(cpy.qamClass, algorithm.classification || "-", algorithmStatusClass(algorithm.classification))}
            ${metric(cpy.vabScore, fmt(breakout.volatility_adjusted_breakout_score), scoreClass(breakout.volatility_adjusted_breakout_score))}
            ${metric(cpy.vabClass, breakout.classification || "-", algorithmStatusClass(breakout.classification))}
            ${metric(cpy.drsScore, fmt(resilience.drawdown_recovery_resilience_score), scoreClass(resilience.drawdown_recovery_resilience_score))}
            ${metric(cpy.drsClass, resilience.classification || "-", algorithmStatusClass(resilience.classification))}
            ${metric(cpy.maxDrawdown, fmtPct(qMetrics?.drawdown?.max_drawdown), "warn")}
            ${metric(cpy.latestFiling, latestStatement?.date || "-", statusClass(freshness?.sections?.fundamentals?.status))}
            ${metric(cpy.revenue, compact(latestStatement?.revenue), "neutral")}
            ${metric(cpy.opMargin, fmtPct(fMetrics?.profitability?.operating_margin), scoreClass((fMetrics?.profitability?.operating_margin || 0) * 220))}
          </div>
          <div class="decision-summary ${escapeHtml(statusClass(freshness.status))}">
            ${escapeHtml(cpy.freshness)} ${escapeHtml(freshness.status || "unknown")} / ${escapeHtml(cpy.stale)} ${(freshness.stale_sections || []).map(escapeHtml).join(", ") || escapeHtml(cpy.none)} / ${escapeHtml(cpy.missing)} ${(data?.data_quality?.missing_sections || []).map(escapeHtml).join(", ") || escapeHtml(cpy.none)}
          </div>
          <div class="decision-summary neutral">
            ${escapeHtml(cpy.chartAxisNote)}
          </div>
          ${quantAlgorithmSummary(data)}
        </div>
        <div class="quantamental-chart-grid" data-testid="quantamental-chart-surface">
          ${chartCard(chart.priceTitle, lineChart(chartData.price || [], "close", ["sma_50", "sma_200"], { yLabel: chart.priceY, yFormat: "number", legendLabels: [chart.close, chart.sma50, chart.sma200] }), chart.priceNote)}
          ${chartCard(chart.cumulativeTitle, lineChart(chartData.cumulative_return || [], "cumulative_return", [], { yLabel: chart.cumulativeY, yFormat: "percent", legendLabels: [chart.cumulativeLegend] }), chart.cumulativeNote)}
          ${chartCard(chart.volatilityTitle, lineChart(chartData.rolling_volatility || [], "rolling_volatility_20d", [], { yLabel: chart.volatilityY, yFormat: "percent", legendLabels: [chart.volatilityLegend] }), chart.volatilityNote)}
          ${chartCard(chart.drawdownTitle, lineChart(chartData.drawdown || [], "drawdown", [], { yLabel: chart.drawdownY, yFormat: "percent", legendLabels: [chart.drawdownLegend] }), chart.drawdownNote)}
          ${chartCard(chart.volumeTitle, barChart(chartData.volume || [], "volume", "", { yLabel: chart.volumeY, yFormat: "compact", legendLabels: [chart.volumeLegend] }), chart.volumeNote)}
          ${chartCard(chart.revenueTitle, barChart(statements.slice().reverse(), "revenue", "net_income", { yLabel: chart.revenueY, yFormat: "compact", legendLabels: [chart.revenueLegend, chart.incomeLegend] }), chart.revenueNote)}
          ${chartCard(chart.marginTitle, lineChart(ratioRows, "gross_margin", ["operating_margin", "net_margin"], { yLabel: chart.marginY, yFormat: "percent", legendLabels: [chart.grossMargin, chart.operatingMargin, chart.netMargin] }), chart.marginNote)}
          ${chartCard(chart.cashFlowTitle, barChart(statements.slice().reverse(), "free_cash_flow", "operating_cash_flow", { yLabel: chart.cashFlowY, yFormat: "compact", legendLabels: [chart.fcfLegend, chart.ocfLegend] }), chart.cashFlowNote)}
          ${chartCard(chart.balanceTitle, barChart(statements.slice().reverse(), "total_assets", "total_debt", { yLabel: chart.balanceY, yFormat: "compact", legendLabels: [chart.assetsLegend, chart.debtLegend] }), chart.balanceNote)}
          ${chartCard(chart.returnsTitle, lineChart(ratioRows, "roe", ["roa"], { yLabel: chart.returnsY, yFormat: "percent", legendLabels: [chart.roeLegend, chart.roaLegend] }), chart.returnsNote)}
        </div>
        <div class="quantamental-coverage-strip">
          <strong>${escapeHtml(cpy.coverage)}</strong>
          <span>${escapeHtml(cpy.fundamentalMissing)} ${escapeHtml(String(data?.data_quality?.fundamental_missing_metric_count ?? 0))}</span>
          <span>${escapeHtml(cpy.quantMissing)} ${escapeHtml(String(data?.data_quality?.quant_missing_metric_count ?? 0))}</span>
          <span>${escapeHtml(cpy.freshnessScore)} ${escapeHtml(fmt(freshness.freshness_score))}</span>
          <span>${escapeHtml(cpy.missingFactors)} ${escapeHtml(String((data?.factors?.missing_factor_inputs || []).length))}</span>
        </div>
        ${missingMetrics.length ? `<div class="decision-warning">${escapeHtml(cpy.missingMetricsRemain)}: ${escapeHtml(missingMetrics.slice(0, 24).join(", "))}${missingMetrics.length > 24 ? " ..." : ""}</div>` : ""}
      </div>
    `;
  }

  function fundamentalRatioRows(statements) {
    if (!Array.isArray(statements)) return [];
    return statements.slice().reverse().map((row) => ({
      date: row?.date,
      gross_margin: safeRatio(row?.gross_profit, row?.revenue),
      operating_margin: safeRatio(row?.operating_income, row?.revenue),
      net_margin: safeRatio(row?.net_income, row?.revenue),
      roe: safeRatio(row?.net_income, row?.total_equity),
      roa: safeRatio(row?.net_income, row?.total_assets),
    }));
  }

  function safeRatio(numerator, denominator) {
    const num = Number(numerator);
    const den = Number(denominator);
    if (!Number.isFinite(num) || !Number.isFinite(den) || den === 0) return null;
    return num / den;
  }

  function lastFinite(rows, key) {
    if (!Array.isArray(rows)) return null;
    for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
      const value = Number(rows[idx]?.[key]);
      if (Number.isFinite(value)) return value;
    }
    return null;
  }

  function lastDate(rows) {
    if (!Array.isArray(rows)) return "";
    for (let idx = rows.length - 1; idx >= 0; idx -= 1) {
      const date = rows[idx]?.date;
      if (date) return String(date);
    }
    return "";
  }

  function objectPanel(title, obj, missing, testName) {
    return `
      <div data-testid="quantamental-${escapeHtml(testName)}-tab">
        <h4>${escapeHtml(title)}</h4>
        ${objectTable(obj)}
        ${missing.length ? `<div class="decision-warning">${escapeHtml(copy().missingMetrics)}: ${escapeHtml(missing.slice(0, 20).join(", "))}</div>` : ""}
      </div>
    `;
  }

  function riskPanel(risk) {
    return `
      <div data-testid="quantamental-risk-tab">
        <h4>${escapeHtml(copy().risk)}</h4>
        <div class="decision-summary ${escapeHtml(statusClass(risk.risk_level))}">${escapeHtml(risk.risk_summary || copy().riskUnavailable)}</div>
        ${objectTable(risk)}
      </div>
    `;
  }

  function peerPanel(peer) {
    return `
      <div data-testid="quantamental-peer-tab">
        <h4>${escapeHtml(copy().peerRelative)}</h4>
        <div class="decision-metric-grid dense">
          ${metric(copy().status, peer.status || "empty", statusClass(peer.status))}
          ${metric(copy().scope, peer.scope || "-", "neutral")}
          ${metric(copy().peers, peer.peer_count == null ? "-" : peer.peer_count, "neutral")}
          ${metric(copy().strength, fmt(peer.relative_strength_score), scoreClass(peer.relative_strength_score))}
        </div>
        ${objectTable(peer.normalized_factor_scores || {})}
        ${listBlock(copy().warnings, peer.warnings)}
      </div>
    `;
  }

  function secPanel(sec) {
    return `
      <div data-testid="quantamental-sec-tab">
        <h4>${escapeHtml(copy().secEvidence)}</h4>
        <div class="decision-metric-grid dense">
          ${metric(copy().status, sec.status || "unknown", statusClass(sec.status))}
          ${metric(copy().filings, sec.filing_count == null ? "-" : sec.filing_count, "neutral")}
          ${metric(copy().facts, sec.fact_count == null ? "-" : sec.fact_count, "neutral")}
          ${metric(copy().latest, sec.latest_filing_at || "-", "neutral")}
        </div>
        ${listBlock(copy().riskFlags, sec.risk_flags)}
        ${listBlock(copy().qualityFlags, sec.quality_flags)}
        ${filingExcerptTable(sec.filing_excerpts || [])}
        ${conceptProvenanceTable(sec.concept_provenance || [])}
        ${objectTable(sec.metrics || {})}
        ${listBlock(copy().warnings, sec.warnings)}
      </div>
    `;
  }

  function auditPanel(snapshot) {
    return `
      <div data-testid="quantamental-audit-tab">
        <h4>${escapeHtml(copy().auditSnapshot)}</h4>
        <div class="decision-metric-grid dense">
          ${metric(copy().status, snapshot.status || "unknown", statusClass(snapshot.status))}
          ${metric(copy().snapshot, snapshot.snapshot_id || "-", "neutral")}
          ${metric(copy().storage, snapshot.storage || "-", "neutral")}
          ${metric(copy().created, snapshot.created_at || "-", "neutral")}
        </div>
        <div class="decision-chip-row">
          <button type="button" class="linkish" data-testid="quantamental-snapshot-export-json" data-quantamental-action="export-snapshot-json">${escapeHtml(copy().exportJson)}</button>
          <button type="button" class="linkish" data-testid="quantamental-snapshot-export-csv" data-quantamental-action="export-snapshot-csv">${escapeHtml(copy().exportCsv)}</button>
          <button type="button" class="linkish" data-testid="quantamental-snapshot-diff" data-quantamental-action="diff-snapshot">${escapeHtml(copy().diffLatest)}</button>
          <button type="button" class="linkish" data-testid="quantamental-snapshot-retention" data-quantamental-action="retention-preview">${escapeHtml(copy().retentionPreview)}</button>
        </div>
        ${snapshot.database ? `<div class="decision-summary neutral">${escapeHtml(snapshot.database)}</div>` : ""}
      </div>
    `;
  }

  function aiValue(value) {
    if (value === null || value === undefined || value === "") return copy().unavailable;
    if (Array.isArray(value)) return value.length ? value.map((item) => aiValue(item)).join(", ") : copy().none;
    if (typeof value === "object") {
      const pairs = Object.entries(value)
        .filter(([, nested]) => nested !== null && nested !== undefined && nested !== "")
        .map(([key, nested]) => `${key}: ${aiValue(nested)}`);
      return pairs.length ? pairs.join(" / ") : copy().unavailable;
    }
    return String(value);
  }

  function aiReportSection(title, payload, testName) {
    if (!payload || (typeof payload === "object" && !Array.isArray(payload) && !Object.keys(payload).length)) return "";
    const rows = Array.isArray(payload)
      ? payload.map((value, index) => [String(index + 1), value])
      : Object.entries(payload);
    if (!rows.length) return "";
    return `
      <section data-testid="quantamental-ai-${escapeHtml(testName)}">
        <h4>${escapeHtml(title)}</h4>
        <div class="decision-list compact">
          ${rows.map(([key, value]) => `
            <div class="decision-summary neutral">
              <strong>${escapeHtml(key)}</strong><br />
              ${escapeHtml(aiValue(value))}
            </div>
          `).join("")}
        </div>
      </section>
    `;
  }

  function aiMissingStatus(value) {
    const text = aiValue(value).trim().toLowerCase();
    if ([copy().none.toLowerCase(), "none", "none identified", "없음", "0"].includes(text)) return "ok";
    if (!text || text === copy().unavailable.toLowerCase() || text === "unavailable" || text === "확인 불가") return "warn";
    return "warn";
  }

  function aiPanel(ai) {
    const report = ai.report || {};
    const usedData = report.used_data || ai.data_snapshot || {};
    return `
      <div class="quantamental-ai-report" data-testid="quantamental-ai-tab">
        <h4>${escapeHtml(copy().aiReport)}</h4>
        <div class="decision-summary ${escapeHtml(statusClass(ai.status))}">
          ${escapeHtml(copy().provider)}: ${escapeHtml(ai.provider || "unavailable")} / ${escapeHtml(copy().signalPreserved)}: ${escapeHtml(String(ai.signal_preserved !== false))}
        </div>
        <section data-testid="quantamental-ai-used-data">
          <h4>${escapeHtml(copy().usedData)}</h4>
          <div class="decision-metric-grid dense">
            ${metric(copy().dataBasisDate, aiValue(usedData.data_basis_date), "neutral")}
            ${metric(copy().analysisPeriod, aiValue(usedData.analysis_period), "neutral")}
            ${metric(copy().dataSource, aiValue(usedData.data_source), "neutral")}
            ${metric(copy().observations, aiValue(usedData.observation_count), "neutral")}
            ${metric(copy().missingData, aiValue(usedData.missing_data), aiMissingStatus(usedData.missing_data))}
            ${metric(copy().model, aiValue(usedData.model || ai.provider), "neutral")}
            ${metric(copy().aiSnapshot, aiValue(usedData.ai_snapshot_at), "neutral")}
            ${metric(copy().cacheState, aiValue(usedData.cache_state), "neutral")}
          </div>
        </section>
        <p>${escapeHtml(report.summary || copy().aiUnavailable)}</p>
        ${aiReportSection(copy().keyChanges, report.key_changes, "key-changes")}
        ${aiReportSection(copy().interpretation, report.interpretation, "interpretation")}
        ${aiReportSection(copy().scenarios, report.scenarios, "scenarios")}
        ${aiReportSection(copy().userActions, report.user_actions, "user-actions")}
        ${listBlock(copy().bullCase, report.bull_case)}
        ${listBlock(copy().bearCase, report.bear_case)}
        <div class="decision-warning">${escapeHtml(report.safety_note || copy().notAdvice)}</div>
      </div>
    `;
  }

  function qaPanel() {
    return `
      <div data-testid="quantamental-qa-tab">
        <h4>${escapeHtml(copy().qaTitle)}</h4>
        <div class="input-action-row">
          <input id="quantamentalQuestion" type="search" value="${escapeHtml(copy().qaQuestionDefault)}" aria-label="Quantamental question" />
          <button type="button" id="quantamentalAsk" class="ghost-btn" data-testid="quantamental-qa-run">${escapeHtml(copy().qaAsk)}</button>
        </div>
        <div id="quantamentalQaSurface">${empty(copy().qaEmpty)}</div>
      </div>
    `;
  }

  function dataQuality(data) {
    const quality = data?.data_quality || {};
    const evidence = quality.evidence_sources?.sec_edgar || {};
    const freshness = data?.freshness || quality.freshness || {};
    const integrity = data?.data_integrity || quality.data_integrity || {};
    const sections = freshness.sections || {};
    return `
      <div data-testid="quantamental-quality-tab">
        <div class="decision-metric-grid dense">
          ${metric(copy().score, fmt(quality.data_quality_score), statusClass(quality.quality_level))}
          ${metric(copy().level, quality.quality_level || "unknown", statusClass(quality.quality_level))}
          ${metric(copy().missing, (quality.missing_sections || []).length, (quality.missing_sections || []).length ? "warn" : "ok")}
          ${metric(copy().warningsCount, (quality.warnings || []).length, (quality.warnings || []).length ? "warn" : "ok")}
          ${metric(copy().freshness, freshness.status || "unknown", statusClass(freshness.status))}
          ${metric(copy().freshScore, fmt(freshness.freshness_score), statusClass(freshness.status))}
          ${metric(copy().integrity, integrity.status || "unknown", statusClass(integrity.status || (integrity.usable_for_signal ? "ok" : "warn")))}
          ${metric(copy().signalUsable, integrity.usable_for_signal ? copy().yes : copy().no, integrity.usable_for_signal ? "ok" : "fail")}
        </div>
        <div class="decision-summary ${escapeHtml(integrity.usable_for_signal ? "ok" : "fail")}">${escapeHtml(copy().strictGate)}: ${escapeHtml(integrity.strict_policy || copy().strictPolicyDefault)} / ${escapeHtml(copy().blocking)} ${(integrity.blocking_sections || []).map(escapeHtml).join(", ") || escapeHtml(copy().none)} / ${escapeHtml(copy().optional)} ${(integrity.optional_issue_sections || []).map(escapeHtml).join(", ") || escapeHtml(copy().none)}</div>
        <div class="decision-summary ${escapeHtml(statusClass(evidence.status))}">${escapeHtml(copy().secEvidence)}: ${escapeHtml(evidence.status || "unknown")} / ${escapeHtml(copy().filings)} ${escapeHtml(evidence.filing_count ?? "-")} / ${escapeHtml(copy().facts)} ${escapeHtml(evidence.fact_count ?? "-")}</div>
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().section)}</th><th>${escapeHtml(copy().status)}</th><th>${escapeHtml(copy().asOf)}</th><th>${escapeHtml(copy().age)}</th><th>${escapeHtml(copy().basis)}</th><th>${escapeHtml(copy().action)}</th></tr></thead>
            <tbody>${Object.keys(sections).map((name) => {
              const item = sections[name] || {};
              return `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(item.status || "-")}</td><td>${escapeHtml(item.as_of || "-")}</td><td>${escapeHtml(item.age_days == null ? "-" : `${item.age_days}d`)}</td><td>${escapeHtml(item.basis || "-")}</td><td>${escapeHtml(item.refreshable ? copy().refreshable : copy().reported)}</td></tr>`;
            }).join("")}</tbody>
          </table>
        </div>
        ${listBlock(copy().warnings, quality.warnings)}
        ${listBlock(copy().freshnessWarnings, freshness.warnings)}
        ${listBlock(copy().errors, quality.errors)}
      </div>
    `;
  }

  function topSignals(data) {
    const limit = Math.max(1, Math.min(20, Number(data?.limit || data?.top_count || 5) || 5));
    const sourceRows = Array.isArray(data?.top_signals)
      ? data.top_signals
      : (Array.isArray(data?.top)
        ? data.top
        : (Array.isArray(data?.ranked_rows)
          ? data.ranked_rows
          : (Array.isArray(data?.rows) ? data.rows : [])));
    const rows = sourceRows.slice(0, limit);
    const summary = data?.freshness_summary || data?.freshness || {};
    if (!rows.length) {
      return `
        <div data-testid="quantamental-screen-table">
          <div class="decision-summary ${escapeHtml(statusClass(data?.status))}">${escapeHtml(copy().noTop)}</div>
          ${listBlock(copy().warnings, data?.warnings)}
        </div>
      `;
    }
    return `
      <div data-testid="quantamental-screen-table">
        <div class="decision-summary ${escapeHtml(statusClass(summary.status))}">
          ${escapeHtml(copy().screened)} ${escapeHtml(String(data?.scored_count ?? rows.length))}/${escapeHtml(String(data?.requested_count ?? rows.length))} ${escapeHtml(copy().symbols)} / ${escapeHtml(copy().freshness)} ${escapeHtml(summary.status || "unknown")} / style ${escapeHtml(data?.style || "balanced")}
        </div>
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().rank)}</th><th>${escapeHtml(copy().ticker)}</th><th>${escapeHtml(copy().company)}</th><th>${escapeHtml(copy().signal)}</th><th>${escapeHtml(copy().composite)}</th><th>${escapeHtml(copy().fund)}</th><th>${escapeHtml(copy().quant)}</th><th>${escapeHtml(copy().risk)}</th><th>${escapeHtml(copy().fresh)}</th><th>${escapeHtml(copy().integrity)}</th></tr></thead>
            <tbody>${rows.map((row, idx) => `
              <tr>
                <td>${escapeHtml(String(row.rank || idx + 1))}</td>
                <td>${escapeHtml(row.ticker || "")}</td>
                <td>${escapeHtml(row.name || [row.sector, row.industry].filter(Boolean).join(" / ") || "-")}</td>
                <td>${escapeHtml(row.signal_label || "-")}</td>
                <td>${escapeHtml(fmt(row.final_score))}</td>
                <td>${escapeHtml(fmt(row.fundamental_score))}</td>
                <td>${escapeHtml(fmt(row.quant_score))}</td>
                <td>${escapeHtml(fmt(row.risk_score))}</td>
                <td>${escapeHtml(row.freshness_status || "unknown")}</td>
                <td>${escapeHtml(row.usable_for_signal ? copy().usable : (row.data_integrity_status || copy().blocked))}</td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>
        ${rows.some((row) => (row.stale_sections || []).length) ? `<div class="decision-warning">${escapeHtml(copy().staleVisible)}: ${escapeHtml(rows.map((row) => `${row.ticker}:${(row.stale_sections || []).join("|")}`).filter((item) => !item.endsWith(":")).join(", "))}</div>` : ""}
        ${listBlock(copy().warnings, data?.warnings)}
      </div>
    `;
  }

  function screenScoreLabel(scoreKey) {
    const labels = copy().factorLabels || {};
    return {
      composite: copy().composite,
      value: labels.value,
      quality: labels.quality,
      growth: labels.growth,
      momentum: labels.momentum,
      low_volatility: labels.lowVolatility,
      liquidity: labels.liquidity,
      drawdown_resilience: labels.drawdownResilience,
    }[String(scoreKey || "composite")] || copy().composite;
  }

  function scoreScreen(data) {
    const limit = Math.max(1, Math.min(50, Number(data?.limit || data?.returned_count || 20) || 20));
    const sourceRows = Array.isArray(data?.matches)
      ? data.matches
      : (Array.isArray(data?.top)
        ? data.top
        : (Array.isArray(data?.ranked_rows) ? data.ranked_rows : []));
    const rows = sourceRows.slice(0, limit);
    const summary = data?.freshness_summary || data?.freshness || {};
    const minScore = Number(data?.min_score);
    const threshold = Number.isFinite(minScore) ? fmt(minScore) : "-";
    const scoreLabel = screenScoreLabel(data?.score_key);
    if (!rows.length) {
      return `
        <div data-testid="quantamental-score-screen-table">
          <div class="decision-summary ${escapeHtml(statusClass(data?.status))}">${escapeHtml(copy().noTop)} / ${escapeHtml(scoreLabel)} &gt;= ${escapeHtml(threshold)}</div>
          ${listBlock(copy().warnings, data?.warnings)}
        </div>
      `;
    }
    return `
      <div data-testid="quantamental-score-screen-table">
        <div class="decision-summary ${escapeHtml(statusClass(summary.status))}">
          ${escapeHtml(String(data?.returned_count ?? rows.length))}/${escapeHtml(String(data?.matched_count ?? rows.length))} ${escapeHtml(copy().screened)} / ${escapeHtml(scoreLabel)} &gt;= ${escapeHtml(threshold)} / ${escapeHtml(copy().freshness)} ${escapeHtml(summary.status || "unknown")} / style ${escapeHtml(data?.style || "balanced")}
        </div>
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().rank)}</th><th>${escapeHtml(copy().ticker)}</th><th>${escapeHtml(copy().company)}</th><th>${escapeHtml(copy().signal)}</th><th>${escapeHtml(scoreLabel)}</th><th>${escapeHtml(copy().composite)}</th><th>${escapeHtml(copy().factorLabels.value)}</th><th>${escapeHtml(copy().factorLabels.quality)}</th><th>${escapeHtml(copy().factorLabels.growth)}</th><th>${escapeHtml(copy().factorLabels.momentum)}</th><th>${escapeHtml(copy().factorLabels.lowVolatility)}</th><th>${escapeHtml(copy().factorLabels.liquidity)}</th><th>${escapeHtml(copy().fresh)}</th><th>${escapeHtml(copy().integrity)}</th></tr></thead>
            <tbody>${rows.map((row, idx) => `
              <tr>
                <td>${escapeHtml(String(row.threshold_rank || row.rank || idx + 1))}</td>
                <td>${escapeHtml(row.ticker || "")}</td>
                <td>${escapeHtml(row.name || [row.sector, row.industry].filter(Boolean).join(" / ") || "-")}</td>
                <td>${escapeHtml(row.signal_label || "-")}</td>
                <td>${escapeHtml(fmt(row.screen_score))}</td>
                <td>${escapeHtml(fmt(row.final_score))}</td>
                <td>${escapeHtml(fmt(row.value_score))}</td>
                <td>${escapeHtml(fmt(row.quality_score))}</td>
                <td>${escapeHtml(fmt(row.growth_score))}</td>
                <td>${escapeHtml(fmt(row.momentum_score))}</td>
                <td>${escapeHtml(fmt(row.low_volatility_score))}</td>
                <td>${escapeHtml(fmt(row.liquidity_score))}</td>
                <td>${escapeHtml(row.freshness_status || "unknown")}</td>
                <td>${escapeHtml(row.usable_for_signal ? copy().usable : (row.data_integrity_status || copy().blocked))}</td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>
        ${rows.some((row) => (row.stale_sections || []).length) ? `<div class="decision-warning">${escapeHtml(copy().staleVisible)}: ${escapeHtml(rows.map((row) => `${row.ticker}:${(row.stale_sections || []).join("|")}`).filter((item) => !item.endsWith(":")).join(", "))}</div>` : ""}
        ${listBlock(copy().warnings, data?.warnings)}
      </div>
    `;
  }

  function comparisonTable(data) {
    const rows = Array.isArray(data?.rows) ? data.rows : [];
    if (!rows.length) return empty(copy().noComparisonRows);
    return `
      <div data-testid="quantamental-compare-table">
        ${data.peer_universe ? `<div class="decision-summary ${escapeHtml(statusClass(data.peer_universe.status))}">${escapeHtml(copy().peerUniverse)}: ${escapeHtml(data.peer_universe.status || "batch")} / ${escapeHtml(copy().added)} ${(data.peer_universe.added_tickers || []).map(escapeHtml).join(", ") || escapeHtml(copy().none)}</div>` : ""}
        <div class="decision-summary ${escapeHtml(statusClass(data.status))}">${escapeHtml(data.count || rows.length)} ${escapeHtml(copy().tickers)} / ${escapeHtml(data.style || "balanced")} / ${escapeHtml(copy().peerGroups)} ${escapeHtml((data.peer_groups || []).length)}</div>
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().ticker)}</th><th>${escapeHtml(copy().signal)}</th><th>${escapeHtml(copy().score)}</th><th>${escapeHtml(copy().peerStrength)}</th><th>${escapeHtml(copy().rank)}</th><th>${escapeHtml(copy().quality)}</th></tr></thead>
            <tbody>${rows.map((row) => `
              <tr>
                <td>${escapeHtml(row.ticker || "")}</td>
                <td>${escapeHtml(row.signal_label || "")}</td>
                <td>${escapeHtml(fmt(row.final_score))}</td>
                <td>${escapeHtml(fmt(row.peer_relative?.relative_strength_score))}</td>
                <td>${escapeHtml(row.peer_relative?.rank || "-")}</td>
                <td>${escapeHtml(row.quality_level || "-")}</td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  function qaAnswer(answer) {
    return `
      <div class="decision-summary ${escapeHtml(statusClass(answer?.status))}">${escapeHtml(answer?.answer || copy().noAnswer)}</div>
      ${evidenceTable(answer?.evidence_metrics || [])}
      ${listBlock(copy().caveats, answer?.caveats)}
    `;
  }

  function snapshotDiff(data) {
    const rows = Array.isArray(data?.differences) ? data.differences : [];
    return `
      <div class="decision-summary ${escapeHtml(statusClass(data?.status))}" data-testid="quantamental-snapshot-diff-result">
        ${escapeHtml(copy().snapshotDiff)}: ${escapeHtml(String(data?.difference_count ?? rows.length))} ${escapeHtml(copy().changedFields)}
      </div>
      ${rows.length ? `
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().path)}</th><th>${escapeHtml(copy().before)}</th><th>${escapeHtml(copy().after)}</th></tr></thead>
            <tbody>${rows.slice(0, 30).map((row) => `<tr><td>${escapeHtml(row.path)}</td><td>${escapeHtml(formatCell(row.before))}</td><td>${escapeHtml(formatCell(row.after))}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      ` : empty(copy().noDiff)}
    `;
  }

  function snapshotRetention(data) {
    const items = Array.isArray(data?.items) ? data.items : [];
    return `
      <div class="decision-summary ${escapeHtml(statusClass(data?.status))}" data-testid="quantamental-snapshot-retention-result">
        ${escapeHtml(copy().retentionPreviewLabel)}: ${escapeHtml(copy().keepLast)} ${escapeHtml(String(data?.keep_last ?? "-"))}, ${escapeHtml(copy().prune)} ${escapeHtml(String(data?.prune_count ?? 0))} ${escapeHtml(copy().snapshots)}
      </div>
      ${items.length ? `
        <div class="decision-table-wrap">
          <table class="decision-table">
            <thead><tr><th>${escapeHtml(copy().snapshot)}</th><th>${escapeHtml(copy().ticker)}</th><th>${escapeHtml(copy().created)}</th><th>${escapeHtml(copy().signal)}</th></tr></thead>
            <tbody>${items.slice(0, 20).map((item) => `<tr><td>${escapeHtml(item.snapshot_id)}</td><td>${escapeHtml(item.ticker)}</td><td>${escapeHtml(item.created_at)}</td><td>${escapeHtml(item.signal_label)}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      ` : empty(copy().noSnapshotsPruned)}
    `;
  }

  function evidenceTable(items) {
    if (!Array.isArray(items) || !items.length) return empty(copy().noEvidenceMetrics);
    return `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>${escapeHtml(copy().metric)}</th><th>${escapeHtml(copy().value)}</th><th>${escapeHtml(copy().source)}</th></tr></thead>
          <tbody>${items.map((item) => `<tr><td>${escapeHtml(item.label)}</td><td>${escapeHtml(formatCell(item.value))}</td><td>${escapeHtml(item.source)}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function objectTable(obj) {
    const rows = flatten(obj).slice(0, 90);
    if (!rows.length) return empty(copy().noValues);
    return `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>${escapeHtml(copy().metric)}</th><th>${escapeHtml(copy().value)}</th></tr></thead>
          <tbody>${rows.map(([key, value]) => `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(formatCell(value))}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function filingExcerptTable(items) {
    if (!Array.isArray(items) || !items.length) return empty(copy().noFilingExcerpts);
    return `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>${escapeHtml(copy().form)}</th><th>${escapeHtml(copy().filed)}</th><th>${escapeHtml(copy().excerpt)}</th><th>${escapeHtml(copy().source)}</th></tr></thead>
          <tbody>${items.slice(0, 5).map((item) => `<tr><td>${escapeHtml(item.form_type)}</td><td>${escapeHtml(item.filed_at || "-")}</td><td>${escapeHtml(item.excerpt || item.description || "-")}</td><td>${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">SEC</a>` : escapeHtml(item.source || "-")}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function conceptProvenanceTable(items) {
    if (!Array.isArray(items) || !items.length) return empty(copy().noConceptProvenance);
    return `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>${escapeHtml(copy().field)}</th><th>${escapeHtml(copy().concept)}</th><th>${escapeHtml(copy().filed)}</th><th>${escapeHtml(copy().value)}</th></tr></thead>
          <tbody>${items.slice(0, 12).map((item) => `<tr><td>${escapeHtml(item.field)}</td><td>${escapeHtml(item.concept)}</td><td>${escapeHtml(item.filed_at || "-")}</td><td>${escapeHtml(formatCell(item.value))}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function flatten(obj, prefix = "") {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
    const out = [];
    Object.keys(obj).forEach((key) => {
      const value = obj[key];
      const next = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === "object" && !Array.isArray(value)) out.push(...flatten(value, next));
      else out.push([next, value]);
    });
    return out;
  }

  function formatCell(value) {
    if (typeof value === "number") {
      if (Math.abs(value) < 1 && value !== 0) return fmtPct(value);
      return fmt(value);
    }
    if (Array.isArray(value)) return value.join(", ");
    if (value && typeof value === "object") return JSON.stringify(value);
    return value ?? "-";
  }

  function compact(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    if (Math.abs(num) >= 1_000_000_000_000) return `${fmt(num / 1_000_000_000_000)}T`;
    if (Math.abs(num) >= 1_000_000_000) return `${fmt(num / 1_000_000_000)}B`;
    if (Math.abs(num) >= 1_000_000) return `${fmt(num / 1_000_000)}M`;
    return fmt(num);
  }

  function listBlock(title, values) {
    const items = Array.isArray(values) ? values : values ? [values] : [];
    if (!items.length) return "";
    return `<div class="quantamental-list-block"><strong>${escapeHtml(title)}</strong><ul>${items.slice(0, 10).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`;
  }

  function chartCard(title, body, note = "") {
    return `
      <div class="quantamental-chart-card">
        <strong>${escapeHtml(title)}</strong>
        ${body}
        ${note ? `<p class="quantamental-chart-note">${escapeHtml(note)}</p>` : ""}
      </div>
    `;
  }

  function lineChart(rows, key, extraKeys = [], options = {}) {
    const seriesKeys = [key, ...extraKeys].filter(Boolean);
    const values = [];
    rows.forEach((row, idx) => {
      seriesKeys.forEach((candidate) => {
        const value = Number(row?.[candidate]);
        if (Number.isFinite(value)) values.push({ idx, value });
      });
    });
    if (!values.length) return empty(copy().chartUnavailable);
    const dims = chartDims();
    const min = Math.min(...values.map((item) => item.value));
    const max = Math.max(...values.map((item) => item.value));
    const span = max - min || 1;
    const colors = ["#2563eb", "#16a34a", "#dc2626", "#7c3aed"];
    const polylines = seriesKeys.map((seriesKey, seriesIdx) => {
      const points = rows.map((row, idx) => {
        const value = Number(row?.[seriesKey]);
        if (!Number.isFinite(value)) return "";
        const x = dims.left + (rows.length <= 1 ? 0 : (idx / (rows.length - 1)) * dims.innerWidth);
        const y = dims.top + dims.innerHeight - ((value - min) / span) * dims.innerHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).filter(Boolean).join(" ");
      return points ? `<polyline points="${points}" fill="none" stroke="${colors[seriesIdx % colors.length]}" stroke-width="2.2" vector-effect="non-scaling-stroke" />` : "";
    }).join("");
    return chartShell({
      rows,
      min,
      max,
      yLabel: options.yLabel || key,
      yFormat: options.yFormat || "number",
      legendLabels: options.legendLabels || seriesKeys,
      colors,
      body: polylines,
      ariaLabel: `${key} chart`,
    });
  }

  function barChart(rows, key, altKey = "", options = {}) {
    const seriesKeys = [key, altKey].filter(Boolean);
    const values = rows.flatMap((row) => seriesKeys.map((seriesKey) => Number(row?.[seriesKey]))).filter(Number.isFinite);
    if (!values.length) return empty(copy().chartUnavailable);
    const dims = chartDims();
    const min = Math.min(0, ...values);
    const max = Math.max(...values, 1);
    const span = max - min || 1;
    const colors = ["#2563eb", "#16a34a"];
    const groupWidth = dims.innerWidth / Math.max(rows.length, 1);
    const barWidth = Math.max(3, (groupWidth - 4) / Math.max(seriesKeys.length, 1));
    const zeroY = dims.top + dims.innerHeight - ((0 - min) / span) * dims.innerHeight;
    const bars = rows.map((row, idx) => {
      const x0 = dims.left + idx * groupWidth + 2;
      return seriesKeys.map((seriesKey, seriesIdx) => {
        const value = Number(row?.[seriesKey]);
        if (!Number.isFinite(value)) return "";
        const y = dims.top + dims.innerHeight - ((value - min) / span) * dims.innerHeight;
        const h = Math.max(1, Math.abs(zeroY - y));
        const x = x0 + seriesIdx * barWidth;
        return `<rect x="${x.toFixed(1)}" y="${Math.min(y, zeroY).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${h.toFixed(1)}" fill="${colors[seriesIdx % colors.length]}" opacity="${seriesIdx ? "0.72" : "0.95"}" />`;
      }).join("");
    }).join("");
    return chartShell({
      rows,
      min,
      max,
      yLabel: options.yLabel || key,
      yFormat: options.yFormat || "number",
      legendLabels: options.legendLabels || seriesKeys,
      colors,
      body: bars,
      ariaLabel: `${key} bars`,
    });
  }

  function chartDims() {
    return { width: 360, height: 178, left: 46, right: 14, top: 16, bottom: 32, innerWidth: 300, innerHeight: 130 };
  }

  function chartShell({ rows, min, max, yLabel, yFormat, legendLabels, colors, body, ariaLabel }) {
    const dims = chartDims();
    const yTicks = [max, min + (max - min) / 2, min];
    const xStart = rows?.[0]?.date || "";
    const xEnd = rows?.[rows.length - 1]?.date || "";
    const grid = yTicks.map((value, idx) => {
      const y = dims.top + (idx / 2) * dims.innerHeight;
      return `
        <line x1="${dims.left}" y1="${y.toFixed(1)}" x2="${dims.left + dims.innerWidth}" y2="${y.toFixed(1)}" stroke="rgba(148, 163, 184, 0.24)" stroke-width="1" />
        <text x="${dims.left - 7}" y="${(y + 4).toFixed(1)}" text-anchor="end">${escapeHtml(formatAxis(value, yFormat))}</text>
      `;
    }).join("");
    const legend = legendLabels.length ? `<div class="quantamental-chart-legend">${legendLabels.map((label, idx) => `<span><b style="background:${colors[idx % colors.length]}"></b>${escapeHtml(label)}</span>`).join("")}</div>` : "";
    return `
      <svg class="quantamental-chart" viewBox="0 0 ${dims.width} ${dims.height}" role="img" aria-label="${escapeHtml(ariaLabel)}">
        <g class="chart-grid">${grid}</g>
        <line x1="${dims.left}" y1="${dims.top}" x2="${dims.left}" y2="${dims.top + dims.innerHeight}" stroke="rgba(148, 163, 184, 0.6)" stroke-width="1" />
        <line x1="${dims.left}" y1="${dims.top + dims.innerHeight}" x2="${dims.left + dims.innerWidth}" y2="${dims.top + dims.innerHeight}" stroke="rgba(148, 163, 184, 0.6)" stroke-width="1" />
        ${body}
        <text x="${dims.left}" y="${dims.height - 7}" text-anchor="start">${escapeHtml(xStart)}</text>
        <text x="${dims.left + dims.innerWidth}" y="${dims.height - 7}" text-anchor="end">${escapeHtml(xEnd)}</text>
        <text x="${dims.left + dims.innerWidth / 2}" y="${dims.height - 7}" text-anchor="middle">${escapeHtml(copy().xDate)}</text>
      </svg>
      <div class="quantamental-chart-axis"><span>${escapeHtml(copy().yAxis)}: ${escapeHtml(yLabel)}</span><span>${escapeHtml(copy().xAxis)}: ${escapeHtml(copy().xDate)}</span></div>
      ${legend}
    `;
  }

  function formatAxis(value, format) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    if (format === "percent") return fmtPct(num);
    if (format === "compact") return compact(num);
    return fmt(num);
  }

  global.FinGPTQuantamentalUi = {
    starter,
    loading,
    error,
    companyHeader,
    signalCard,
    scoreDashboard,
    factorGrid,
    mainPanel,
    dataQuality,
    topSignals,
    scoreScreen,
    qaAnswer,
    comparisonTable,
    snapshotDiff,
    snapshotRetention,
  };
})(window);
