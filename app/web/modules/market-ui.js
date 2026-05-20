(function initMarketUi(global) {
  const ORDER = ["SPY", "QQQ", "TLT", "HYG", "LQD", "GLD", "BTC-USD", "DX-Y.NYB", "^TNX"];

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtNumber(value, digits = 2) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return num.toFixed(digits).replace(/\.?0+$/, "");
  }

  function fmtPct(value) {
    const num = Number(value);
    return Number.isFinite(num) ? `${fmtNumber(num, 2)}%` : "-";
  }

  function fmtDate(value) {
    if (!value) return "-";
    return String(value).replace("T", " ").replace("Z", "").slice(0, 16);
  }

  function statusClass(value) {
    const key = String(value || "").toLowerCase();
    if (["ok", "success", "completed", "pass", "available", "risk_on", "easing"].includes(key)) return "ok";
    if (["fail", "failed", "error", "unavailable"].includes(key)) return "fail";
    if (["partial", "warn", "warning", "stale", "risk_off", "watch", "mixed", "hedge_bid"].includes(key)) return "warn";
    return "neutral";
  }

  function returnClass(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "muted";
    if (num > 0) return "ok";
    if (num < 0) return "fail";
    return "muted";
  }

  function metric(label, value, status) {
    return `
      <div class="decision-metric ${escapeHtml(statusClass(status))}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value ?? "-")}</strong>
      </div>
    `;
  }

  function empty(message) {
    return `<div class="home-news-empty">${escapeHtml(message)}</div>`;
  }

  function labelFor(value) {
    const labels = {
      risk_on: "RISK ON",
      risk_off: "RISK OFF",
      hedge_bid: "HEDGE BID",
      watch: "WATCH",
      easing: "EASING",
      mixed: "MIXED",
      neutral: "NEUTRAL",
      ok: "OK",
      unavailable: "UNAVAILABLE",
    };
    const key = String(value || "").toLowerCase();
    return labels[key] || String(value || "UNKNOWN").toUpperCase();
  }

  function confidenceLabel(value) {
    const labels = { high: "high confidence", medium: "medium confidence", low: "low confidence" };
    const key = String(value || "").toLowerCase();
    return labels[key] || "confidence n/a";
  }

  function compactList(items, cls) {
    const rows = Array.isArray(items) ? items.filter(Boolean).slice(0, 4) : [];
    if (!rows.length) return "";
    return `<div class="${escapeHtml(cls)}">${rows.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
  }

  function componentGrid(components) {
    const rows = Array.isArray(components) ? components.slice(0, 4) : [];
    if (!rows.length) return "";
    return `
      <div class="market-signal-components">
        ${rows.map((item) => `
          <div class="market-signal-component ${escapeHtml(statusClass(item.status))}">
            <span>${escapeHtml(item.label || "")}</span>
            <strong>${escapeHtml(item.value ?? "-")}</strong>
            ${item.detail ? `<small>${escapeHtml(item.detail)}</small>` : ""}
          </div>
        `).join("")}
      </div>
    `;
  }

  function signalOverview(signals) {
    const usable = signals.filter((signal) => signal.is_decision_usable).length;
    const riskOn = signals.filter((signal) => ["risk_on", "ok", "easing"].includes(String(signal.direction || signal.status || "").toLowerCase())).length;
    const riskOff = signals.filter((signal) => ["risk_off", "watch", "hedge_bid"].includes(String(signal.direction || signal.status || "").toLowerCase())).length;
    const mixed = signals.filter((signal) => ["mixed", "neutral"].includes(String(signal.status || "").toLowerCase())).length;
    const highConfidence = signals.filter((signal) => String(signal.confidence || "").toLowerCase() === "high").length;
    const regime = riskOn > riskOff + 1 ? "risk_on" : (riskOff > riskOn + 1 ? "risk_off" : "mixed");
    return `
      <div class="market-signal-command ${escapeHtml(statusClass(regime))}">
        <div>
          <span>Composite market signal</span>
          <strong>${escapeHtml(labelFor(regime))}</strong>
        </div>
        <div>
          <span>Risk-on checks</span>
          <strong>${escapeHtml(String(riskOn))}</strong>
        </div>
        <div>
          <span>Risk-off checks</span>
          <strong>${escapeHtml(String(riskOff))}</strong>
        </div>
        <div>
          <span>Usable</span>
          <strong>${escapeHtml(`${usable}/${signals.length}`)}</strong>
        </div>
        <div>
          <span>High confidence</span>
          <strong>${escapeHtml(String(highConfidence))}</strong>
        </div>
        <div>
          <span>Conflict</span>
          <strong>${escapeHtml(String(mixed))}</strong>
        </div>
      </div>
    `;
  }

  function marketTape(overview, options = {}) {
    const freshnessLabels = options.freshnessLabels || {};
    const tape = Array.isArray(overview?.market_tape)
      ? overview.market_tape.slice().sort((a, b) => {
          const aIdx = ORDER.indexOf(String(a?.symbol || "").toUpperCase());
          const bIdx = ORDER.indexOf(String(b?.symbol || "").toUpperCase());
          return (aIdx >= 0 ? aIdx : ORDER.length) - (bIdx >= 0 ? bIdx : ORDER.length);
        })
      : [];
    const freshness = overview?.freshness_summary || {};
    const heatmap = overview?.heatmap_summary || {};
    const asOf = overview?.raw_market_meta?.generated_at ? fmtDate(overview.raw_market_meta.generated_at) : "basis time unknown";
    const meta = `${freshness.decision_usable_count || 0}/${freshness.item_count || 0} usable / ${heatmap.status || "heatmap"} / ${asOf}`;
    if (!tape.length) return { meta, html: empty("No market tape data is available.") };

    const metrics = [
      metric("Market freshness", `${freshness.decision_usable_count || 0}/${freshness.item_count || 0}`, freshness.status || "unavailable"),
      metric("Heatmap universe", heatmap.universe_size ? `${heatmap.decision_usable_count || 0}/${heatmap.universe_size}` : "not loaded", heatmap.status || "unavailable"),
      metric("Latest heatmap", heatmap.latest_as_of ? fmtDate(heatmap.latest_as_of) : "unknown", heatmap.status || "unavailable"),
      metric("Advisory", overview?.advisory_only ? "advisory only" : "needs review", overview?.advisory_only ? "ok" : "warn"),
    ].join("");
    const rows = tape.map((item) => {
      const cls = item.is_decision_usable ? returnClass(item.return_1d) : "warn";
      const monthCls = item.is_decision_usable ? returnClass(item.return_1m) : "warn";
      const freshnessLabel = freshnessLabels[item.freshness_status] || item.freshness_status || "unknown";
      const itemAsOf = item.as_of ? fmtDate(item.as_of) : freshnessLabel;
      return `
        <article class="market-tape-item ${escapeHtml(cls)} ${item.is_decision_usable ? "" : "stale"}">
          <div class="market-tape-symbol-row">
            <strong>${escapeHtml(item.symbol || "")}</strong>
            <span>${escapeHtml(item.asset_class || "")}</span>
          </div>
          <div class="market-tape-label">${escapeHtml(item.label || "")}</div>
          <div class="market-tape-price">${item.price === null || item.price === undefined ? "-" : escapeHtml(String(item.price))}</div>
          <div class="market-tape-returns">
            <span class="market-tape-return ${escapeHtml(cls)}">1D ${escapeHtml(fmtPct(item.return_1d))}</span>
            <span class="market-tape-return ${escapeHtml(monthCls)}">1M ${escapeHtml(fmtPct(item.return_1m))}</span>
          </div>
          <div class="market-tape-meta">
            <span>${escapeHtml(itemAsOf)}</span>
            <span>${escapeHtml(item.source || "unknown")}</span>
          </div>
        </article>
      `;
    }).join("");
    const warning = [freshness.warning, heatmap.warning].filter(Boolean).join(" ");
    return {
      meta,
      html: `
        <div class="decision-metric-grid dense">${metrics}</div>
        ${warning ? `<div class="decision-summary warn">${escapeHtml(warning)}</div>` : ""}
        <div class="market-tape-grid">${rows}</div>
      `,
    };
  }

  function marketSignals(overview) {
    const signals = Array.isArray(overview?.signals) ? overview.signals : [];
    if (!signals.length) return empty("No market signals are available.");
    const cards = signals.map((signal) => {
      const cls = statusClass(signal.status);
      const evidence = Array.isArray(signal.evidence) ? signal.evidence.slice(0, 6) : [];
      const nextActions = Array.isArray(signal.next_actions) ? signal.next_actions.slice(0, 3) : [];
      const invalidation = Array.isArray(signal.invalidation) ? signal.invalidation.slice(0, 3) : [];
      const watchPoints = Array.isArray(signal.watch_points) ? signal.watch_points.slice(0, 3) : [];
      return `
        <article class="market-signal-item ${escapeHtml(cls)}">
          <div class="market-signal-top">
            <span class="decision-badge ${escapeHtml(cls)}">${escapeHtml(labelFor(signal.status))}</span>
            <span>${escapeHtml(signal.signal_id || "")}</span>
          </div>
          <div class="market-signal-title-row">
            <h4>${escapeHtml(signal.title || "")}</h4>
            <span>${escapeHtml(signal.score === null || signal.score === undefined ? "score -" : `score ${fmtNumber(signal.score, 2)}`)}</span>
          </div>
          <div class="market-signal-meta">
            <span>${escapeHtml(signal.impact || "Market impact")}</span>
            <span>${escapeHtml(signal.horizon || "1D")}</span>
            <span>${escapeHtml(confidenceLabel(signal.confidence))}</span>
          </div>
          <p>${escapeHtml(signal.summary || "")}</p>
          ${componentGrid(signal.components)}
          <div class="market-signal-evidence">
            ${evidence.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
          </div>
          <div class="market-signal-note">${escapeHtml(signal.interpretation || "")}</div>
          ${compactList(nextActions, "market-signal-actions")}
          ${(watchPoints.length || invalidation.length) ? `
            <details class="market-signal-more">
              <summary>감시·무효화</summary>
              ${compactList(watchPoints, "market-signal-watch")}
              ${compactList(invalidation, "market-signal-invalidation")}
            </details>
          ` : ""}
        </article>
      `;
    }).join("");
    return `
      ${signalOverview(signals)}
      <div class="market-signal-grid">${cards}</div>
    `;
  }

  global.FinGPTMarketUi = {
    marketTape,
    marketSignals,
  };
})(window);
