(function initAiPortfolioUi(global) {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatNumber(value, digits = 3) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return num.toFixed(digits).replace(/\.?0+$/, "");
  }

  function formatSeconds(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    if (num < 1) return `${formatNumber(num * 1000, 0)}ms`;
    return `${formatNumber(num, 2)}s`;
  }

  function compactValue(value) {
    if (Array.isArray(value)) {
      return value.length ? value.slice(0, 8).map(escapeHtml).join(", ") : "-";
    }
    if (value && typeof value === "object") {
      return Object.entries(value)
        .slice(0, 8)
        .map(([key, item]) => `${escapeHtml(key)}=${escapeHtml(item)}`)
        .join(" / ") || "-";
    }
    return escapeHtml(value ?? "-");
  }

  function compactIdentifier(value, head = 12, tail = 6) {
    const raw = String(value || "").trim();
    if (!raw) return "-";
    if (raw.length <= head + tail + 3) return raw;
    return `${raw.slice(0, head)}...${raw.slice(-tail)}`;
  }

  function detailRow(label, value) {
    if (value === undefined || value === null || value === "") return "";
    return `<div class="ai-operation-detail-row"><span>${escapeHtml(label)}</span><strong>${compactValue(value)}</strong></div>`;
  }

  function identifierRow(label, value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    return `<div class="ai-operation-detail-row"><span>${escapeHtml(label)}</span><strong title="${escapeHtml(raw)}">${escapeHtml(compactIdentifier(raw))}</strong></div>`;
  }

  function dashboardMeta(dashboard) {
    const cache = dashboard?.cache || {};
    const timing = dashboard?.debug_timing || {};
    const cacheStatus = cache.hit ? "cache hit" : "fresh build";
    const cacheDetail = cache.hit
      ? `age ${formatSeconds(cache.age_seconds)} / ttl ${formatSeconds(cache.ttl_seconds)}`
      : `server ${formatSeconds(cache.elapsed_seconds ?? timing.total)} / ttl ${formatSeconds(cache.ttl_seconds)}`;
    const timingRows = Object.entries(timing)
      .filter(([key]) => key !== "total")
      .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
      .slice(0, 6)
      .map(([key, value]) => `<span>${escapeHtml(key)} ${formatSeconds(value)}</span>`)
      .join("");
    return `
      <div class="ai-dashboard-meta" data-testid="ai-portfolio-dashboard-meta">
        <div>
          <span class="decision-badge ${cache.hit ? "ok" : "warn"}">${escapeHtml(cacheStatus)}</span>
          <strong>${escapeHtml(cacheDetail)}</strong>
          <small>generated ${escapeHtml(dashboard?.generated_at || "-")}</small>
        </div>
        <div class="ai-dashboard-timing" data-testid="ai-portfolio-dashboard-timing">
          <span>total ${formatSeconds(timing.total)}</span>
          ${timingRows}
        </div>
      </div>
    `;
  }

  function operationSummary(operation) {
    const parts = [
      identifierRow("operation", operation.operation_id),
      identifierRow("request", operation.request_id),
      detailRow("created", operation.created_at),
      detailRow("source", operation.source?.label || operation.source?.universe_id || operation.source?.policy_id),
      detailRow("assets", operation.processed_asset_count ?? operation.asset_count ?? operation.ticker_count),
      detailRow("snapshots", operation.created_count),
      detailRow("failures", operation.failure_count),
      detailRow("price", operation.price_result),
      detailRow("fundamentals", operation.fundamentals_result),
      detailRow("sec", operation.sec_result),
      detailRow("metadata", operation.metadata_result),
      detailRow("failed tickers", operation.fundamentals_result?.failed || operation.sec_result?.missing_after || operation.price_result?.still_unavailable),
    ].join("");
    return parts || '<div class="muted small">No extra operation detail was returned.</div>';
  }

  function operationList(items) {
    if (!Array.isArray(items) || !items.length) return "";
    return `
      <div class="ai-operation-list">
        ${items.slice(0, 8).map((item) => {
          const status = String(item.status || "unknown");
          const operationId = String(item.operation_id || "");
          const operationLabel = compactIdentifier(operationId);
          const summaryText = [item.created_at || "", operationLabel].filter(Boolean).join(" / ");
          return `
            <details class="ai-operation-item">
              <summary>
                <span>
                  <strong>${escapeHtml(item.operation_type || "operation")}</strong>
                  <small title="${escapeHtml(operationId)}">${escapeHtml(summaryText)}</small>
                </span>
                <em class="${escapeHtml(status)}">${escapeHtml(status)}</em>
              </summary>
              <div class="ai-operation-detail-grid">${operationSummary(item)}</div>
            </details>
          `;
        }).join("")}
      </div>
    `;
  }

  global.FinGPTAiPortfolioUi = {
    dashboardMeta,
    operationList,
  };
})(window);
