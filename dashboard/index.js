/* ═══════════════════════════════════════════════════════════
   FRAUD DETECTION COMMAND CENTER — Dashboard Engine
   ═══════════════════════════════════════════════════════════ */

(() => {
  "use strict";

  // ── Configuration ──
  const WS_URL = "ws://localhost:8000/ws/live";
  const MAX_FEED_ROWS = 100;
  const LATENCY_WINDOW = 60; // seconds
  const SLA_LINE = 100; // ms
  const RECONNECT_BASE = 1000;
  const RECONNECT_MAX = 30000;
  const DEMO_INTERVAL = 1800; // ms between demo transactions

  // ── State ──
  const state = {
    connected: false,
    demoMode: false,
    ws: null,
    reconnectAttempt: 0,
    reconnectTimer: null,
    demoTimer: null,
    transactions: [],
    stats: {
      total: 0,
      approved: 0,
      declined: 0,
      escalated: 0,
      totalLatency: 0,
      alerts: 0,
    },
    latencyHistory: [], // {t, p50, p95, p99}
    agentStats: {},
  };

  // ── DOM References ──
  const $ = (s) => document.querySelector(s);
  const dom = {
    clock:           $("#liveClock"),
    connDot:         $("#connectionDot"),
    connLabel:       $("#connectionLabel"),
    kpiTotal:        $("#kpiTotal"),
    kpiApproval:     $("#kpiApproval"),
    kpiDecline:      $("#kpiDecline"),
    kpiEscalation:   $("#kpiEscalation"),
    kpiLatency:      $("#kpiLatency"),
    kpiAlerts:       $("#kpiAlerts"),
    feedBody:        $("#feedBody"),
    feedEmpty:       $("#feedEmpty"),
    feedCount:       $("#feedCount"),
    donutCanvas:     $("#donutChart"),
    donutTotal:      $("#donutTotal"),
    latencyCanvas:   $("#latencyChart"),
    agentHeatmap:    $("#agentHeatmap"),
    alertTrack:      $("#alertTrack"),
    traceModal:      $("#traceModal"),
    modalBody:       $("#modalBody"),
    modalClose:      $("#modalClose"),
  };

  // ══════════════════════════════════════════
  //  FORMAT HELPERS
  // ══════════════════════════════════════════
  function formatCurrency(amount) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(amount);
  }

  function formatLatency(ms) {
    return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
  }

  function formatTimestamp(date) {
    return date.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function truncateId(id) {
    if (!id) return "—";
    return id.length > 12 ? id.slice(0, 6) + "…" + id.slice(-4) : id;
  }

  function pct(part, total) {
    return total === 0 ? 0 : ((part / total) * 100).toFixed(1);
  }

  // ══════════════════════════════════════════
  //  LIVE CLOCK
  // ══════════════════════════════════════════
  function tickClock() {
    dom.clock.textContent = formatTimestamp(new Date());
  }
  setInterval(tickClock, 1000);
  tickClock();

  // ══════════════════════════════════════════
  //  CONNECTION STATUS
  // ══════════════════════════════════════════
  function setConnectionStatus(status) {
    dom.connDot.className = "connection-dot";
    if (status === "connected") {
      dom.connDot.classList.add("connection-dot--connected");
      dom.connLabel.textContent = "Live";
    } else if (status === "demo") {
      dom.connDot.classList.add("connection-dot--demo");
      dom.connLabel.textContent = "Demo Mode";
    } else {
      dom.connDot.classList.add("connection-dot--disconnected");
      dom.connLabel.textContent = "Disconnected";
    }
  }

  // ══════════════════════════════════════════
  //  CHART.JS — Donut
  // ══════════════════════════════════════════
  const donutChart = new Chart(dom.donutCanvas, {
    type: "doughnut",
    data: {
      labels: ["Approved", "Declined", "Escalated"],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: [
          "rgba(16, 185, 129, 0.85)",
          "rgba(244, 63, 94, 0.85)",
          "rgba(245, 158, 11, 0.85)",
        ],
        borderColor: [
          "rgba(16, 185, 129, 1)",
          "rgba(244, 63, 94, 1)",
          "rgba(245, 158, 11, 1)",
        ],
        borderWidth: 1,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "72%",
      animation: { animateRotate: true, animateScale: true, duration: 800 },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#94a3b8",
            font: { family: "'Inter'", size: 11, weight: "500" },
            padding: 14,
            usePointStyle: true,
            pointStyleWidth: 8,
          },
        },
        tooltip: {
          backgroundColor: "rgba(22, 33, 62, 0.95)",
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 10,
          titleFont: { family: "'Inter'", weight: "600" },
          bodyFont: { family: "'JetBrains Mono'", size: 12 },
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.parsed} (${pct(ctx.parsed, state.stats.total)}%)`,
          },
        },
      },
    },
  });

  // ══════════════════════════════════════════
  //  CHART.JS — Latency
  // ══════════════════════════════════════════
  const latencyChart = new Chart(dom.latencyCanvas, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "p50",
          data: [],
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.08)",
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 0,
          pointHitRadius: 8,
        },
        {
          label: "p95",
          data: [],
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.05)",
          fill: false,
          tension: 0.35,
          borderWidth: 1.5,
          borderDash: [4, 3],
          pointRadius: 0,
          pointHitRadius: 8,
        },
        {
          label: "p99",
          data: [],
          borderColor: "#f43f5e",
          backgroundColor: "rgba(244, 63, 94, 0.05)",
          fill: false,
          tension: 0.35,
          borderWidth: 1.5,
          borderDash: [2, 2],
          pointRadius: 0,
          pointHitRadius: 8,
        },
        {
          label: "SLA",
          data: [],
          borderColor: "rgba(244, 63, 94, 0.4)",
          borderWidth: 1,
          borderDash: [6, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          display: true,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: {
            color: "#64748b",
            font: { family: "'JetBrains Mono'", size: 9 },
            maxRotation: 0,
            maxTicksLimit: 8,
          },
        },
        y: {
          display: true,
          min: 0,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: {
            color: "#64748b",
            font: { family: "'JetBrains Mono'", size: 10 },
            callback: (v) => v + "ms",
          },
        },
      },
      plugins: {
        legend: {
          position: "top",
          align: "end",
          labels: {
            color: "#94a3b8",
            font: { family: "'Inter'", size: 10, weight: "500" },
            padding: 10,
            usePointStyle: true,
            pointStyleWidth: 6,
            boxWidth: 6,
          },
        },
        tooltip: {
          backgroundColor: "rgba(22, 33, 62, 0.95)",
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          cornerRadius: 8,
          padding: 10,
          titleFont: { family: "'Inter'", weight: "600" },
          bodyFont: { family: "'JetBrains Mono'", size: 12 },
          callbacks: {
            label: (ctx) => ` ${ctx.dataset.label}: ${Math.round(ctx.parsed.y)}ms`,
          },
        },
      },
    },
  });

  // ══════════════════════════════════════════
  //  KPI COUNTER ANIMATION
  // ══════════════════════════════════════════
  const kpiAnimations = {};

  function animateKPI(el, target, suffix = "", decimals = 0) {
    const key = el.id;
    if (kpiAnimations[key]) cancelAnimationFrame(kpiAnimations[key]);

    const start = parseFloat(el.textContent.replace(/[^0-9.-]/g, "")) || 0;
    const diff = target - start;
    if (Math.abs(diff) < 0.01) return;

    const duration = 600;
    const startTime = performance.now();

    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      const current = start + diff * ease;

      if (suffix === "%") {
        el.innerHTML = current.toFixed(decimals) + "<small>%</small>";
      } else if (suffix === "ms") {
        el.innerHTML = Math.round(current) + "<small>ms</small>";
      } else {
        el.textContent = Math.round(current).toLocaleString();
      }

      if (progress < 1) {
        kpiAnimations[key] = requestAnimationFrame(step);
      }
    }

    kpiAnimations[key] = requestAnimationFrame(step);
  }

  // ══════════════════════════════════════════
  //  UPDATE KPIs
  // ══════════════════════════════════════════
  function updateKPIs() {
    const s = state.stats;
    animateKPI(dom.kpiTotal, s.total);
    animateKPI(dom.kpiApproval, parseFloat(pct(s.approved, s.total)), "%", 1);
    animateKPI(dom.kpiDecline, parseFloat(pct(s.declined, s.total)), "%", 1);
    animateKPI(dom.kpiEscalation, parseFloat(pct(s.escalated, s.total)), "%", 1);
    animateKPI(dom.kpiLatency, s.total > 0 ? s.totalLatency / s.total : 0, "ms");
    animateKPI(dom.kpiAlerts, s.alerts);
  }

  // ══════════════════════════════════════════
  //  UPDATE DONUT CHART
  // ══════════════════════════════════════════
  function updateDonut() {
    const s = state.stats;
    donutChart.data.datasets[0].data = [s.approved, s.declined, s.escalated];
    donutChart.update("none");
    dom.donutTotal.textContent = s.total.toLocaleString();
  }

  // ══════════════════════════════════════════
  //  UPDATE LATENCY CHART
  // ══════════════════════════════════════════
  function updateLatencyChart(latencyMs) {
    const now = formatTimestamp(new Date());
    const hist = state.latencyHistory;

    // Keep rolling window
    hist.push(latencyMs);
    if (hist.length > LATENCY_WINDOW) hist.shift();

    // Compute percentiles
    const sorted = [...hist].sort((a, b) => a - b);
    const p = (pct) => sorted[Math.min(Math.floor(sorted.length * pct), sorted.length - 1)];

    const labels = latencyChart.data.labels;
    labels.push(now);
    latencyChart.data.datasets[0].data.push(p(0.5));
    latencyChart.data.datasets[1].data.push(p(0.95));
    latencyChart.data.datasets[2].data.push(p(0.99));
    latencyChart.data.datasets[3].data.push(SLA_LINE);

    // Trim to window
    if (labels.length > LATENCY_WINDOW) {
      labels.shift();
      latencyChart.data.datasets.forEach((ds) => ds.data.shift());
    }

    latencyChart.update("none");
  }

  // ══════════════════════════════════════════
  //  AGENT HEATMAP
  // ══════════════════════════════════════════
  const AGENTS = [
    { id: "preprocessor", name: "Preprocessor" },
    { id: "rule_engine", name: "Rule Engine" },
    { id: "ml_model", name: "ML Model" },
    { id: "velocity_check", name: "Velocity Check" },
    { id: "risk_scorer", name: "Risk Scorer" },
    { id: "decision_engine", name: "Decision Engine" },
  ];

  function initAgentStats() {
    AGENTS.forEach((a) => {
      state.agentStats[a.id] = { totalLatency: 0, count: 0, errors: 0 };
    });
  }
  initAgentStats();

  function renderAgentHeatmap() {
    dom.agentHeatmap.innerHTML = AGENTS.map((a) => {
      const s = state.agentStats[a.id];
      const avg = s.count > 0 ? s.totalLatency / s.count : 0;
      const rate = s.count > 0 ? (((s.count - s.errors) / s.count) * 100).toFixed(1) : "—";
      let cls = "fast";
      if (avg > 80) cls = "critical";
      else if (avg > 50) cls = "slow";
      else if (avg > 25) cls = "ok";

      return `<div class="agent-cell agent-cell--${cls}">
        <div class="agent-cell__name">${a.name}</div>
        <div class="agent-cell__latency">${Math.round(avg)}<small>ms</small></div>
        <div class="agent-cell__rate">${rate}% success</div>
      </div>`;
    }).join("");
  }
  renderAgentHeatmap();

  // ══════════════════════════════════════════
  //  TRANSACTION FEED
  // ══════════════════════════════════════════
  function addTransaction(txn) {
    state.transactions.unshift(txn);
    if (state.transactions.length > MAX_FEED_ROWS) state.transactions.pop();

    // Update stats
    const s = state.stats;
    s.total++;
    const decision = (txn.decision || "").toUpperCase();
    if (decision === "APPROVE" || decision === "APPROVED") s.approved++;
    else if (decision === "DECLINE" || decision === "DECLINED") s.declined++;
    else if (decision === "ESCALATE" || decision === "ESCALATED") s.escalated++;
    s.totalLatency += txn.latency || 0;

    const risk = (txn.risk_level || txn.risk || "").toLowerCase();
    if (risk === "critical" || risk === "high") {
      s.alerts++;
      addAlert(txn);
    }

    // Update agent stats from trace
    if (txn.agent_trace) {
      txn.agent_trace.forEach((step) => {
        const agent = state.agentStats[step.agent_id];
        if (agent) {
          agent.totalLatency += step.duration_ms || 0;
          agent.count++;
          if (step.status === "error") agent.errors++;
        }
      });
    }

    // Update UI
    renderFeedRow(txn);
    updateKPIs();
    updateDonut();
    updateLatencyChart(txn.latency || 0);
    renderAgentHeatmap();

    dom.feedEmpty.style.display = "none";
    dom.feedCount.textContent = `${state.stats.total} txns`;
  }

  function renderFeedRow(txn) {
    const tr = document.createElement("tr");
    const decision = (txn.decision || "").toUpperCase();
    const risk = (txn.risk_level || txn.risk || "low").toLowerCase();

    let decisionNorm = "approve";
    if (decision.includes("DECLINE")) decisionNorm = "decline";
    else if (decision.includes("ESCALAT")) decisionNorm = "escalate";

    tr.setAttribute("data-risk", risk);
    tr.classList.add("flash");

    const confidence = txn.confidence != null ? txn.confidence : Math.random();
    const confPct = (confidence * 100).toFixed(0);
    const confColor =
      confidence >= 0.8 ? "var(--green)" :
      confidence >= 0.5 ? "var(--amber)" : "var(--red)";

    tr.innerHTML = `
      <td class="mono" style="color:var(--text-muted); font-size:0.72rem;">${formatTimestamp(new Date(txn.timestamp || Date.now()))}</td>
      <td class="mono" style="font-size:0.75rem;" title="${txn.transaction_id || txn.id || ''}">${truncateId(txn.transaction_id || txn.id || "")}</td>
      <td class="mono" style="font-weight:600;">${formatCurrency(txn.amount || 0)}</td>
      <td style="color:var(--text-secondary);">${txn.customer_name || txn.customer || "—"}</td>
      <td><span class="badge badge--${decisionNorm}">${decision}</span></td>
      <td>
        <div class="confidence-bar">
          <div class="confidence-bar__track"><div class="confidence-bar__fill" style="width:${confPct}%;background:${confColor};"></div></div>
          <span class="confidence-bar__label" style="color:${confColor};">${confPct}%</span>
        </div>
      </td>
      <td class="mono" style="font-size:0.75rem; color:${(txn.latency || 0) > SLA_LINE ? 'var(--red)' : 'var(--green)'};">${formatLatency(txn.latency || 0)}</td>
      <td><span class="risk-badge risk-badge--${risk}">${risk.toUpperCase()}</span></td>
    `;

    tr.addEventListener("click", () => openTraceModal(txn));

    // Prepend
    if (dom.feedBody.firstChild) {
      dom.feedBody.insertBefore(tr, dom.feedBody.firstChild);
    } else {
      dom.feedBody.appendChild(tr);
    }

    // Trim
    while (dom.feedBody.children.length > MAX_FEED_ROWS) {
      dom.feedBody.removeChild(dom.feedBody.lastChild);
    }

    // Remove flash class after animation
    setTimeout(() => tr.classList.remove("flash"), 850);
  }

  // ══════════════════════════════════════════
  //  ALERT TICKER
  // ══════════════════════════════════════════
  const alertMessages = [];

  function addAlert(txn) {
    const risk = (txn.risk_level || txn.risk || "").toUpperCase();
    const msg = `${risk} RISK — ${truncateId(txn.transaction_id || txn.id)} — ${formatCurrency(txn.amount || 0)} — ${txn.customer_name || txn.customer || "Unknown"}`;
    alertMessages.push(msg);
    if (alertMessages.length > 20) alertMessages.shift();
    renderAlertTicker();
  }

  function renderAlertTicker() {
    // Duplicate items for seamless scroll
    const items = alertMessages.length > 0 ? alertMessages : ["System online — monitoring active"];
    const html = items.map((m) => `<span class="alert-item">${m}</span>`).join("");
    dom.alertTrack.innerHTML = html + html; // duplicate for seamless loop
  }

  // ══════════════════════════════════════════
  //  AGENT TRACE MODAL
  // ══════════════════════════════════════════
  function openTraceModal(txn) {
    const decision = (txn.decision || "").toUpperCase();
    const risk = (txn.risk_level || txn.risk || "").toUpperCase();
    const trace = txn.agent_trace || generateDemoTrace();

    const metaHtml = `
      <div class="trace-meta">
        <div class="trace-meta__item">
          <div class="trace-meta__label">Transaction ID</div>
          <div class="trace-meta__value">${txn.transaction_id || txn.id || "—"}</div>
        </div>
        <div class="trace-meta__item">
          <div class="trace-meta__label">Amount</div>
          <div class="trace-meta__value">${formatCurrency(txn.amount || 0)}</div>
        </div>
        <div class="trace-meta__item">
          <div class="trace-meta__label">Decision</div>
          <div class="trace-meta__value"><span class="badge badge--${decision.toLowerCase().replace("d","")}">${decision}</span></div>
        </div>
        <div class="trace-meta__item">
          <div class="trace-meta__label">Total Latency</div>
          <div class="trace-meta__value">${formatLatency(txn.latency || 0)}</div>
        </div>
      </div>
    `;

    const pipelineHtml = `
      <h3 style="font-size:0.82rem;font-weight:600;margin-bottom:14px;color:var(--text-secondary);">Agent Pipeline</h3>
      <div class="trace-pipeline">
        ${trace.map((step, i) => {
          const statusClass =
            step.status === "success" || step.status === "pass" ? "success" :
            step.status === "warning" || step.status === "flagged" ? "warning" : "error";
          return `
            <div class="trace-step trace-step--${statusClass}">
              <div class="trace-step__connector">
                <div class="trace-step__dot"></div>
                <div class="trace-step__line"></div>
              </div>
              <div class="trace-step__body">
                <div class="trace-step__header">
                  <span class="trace-step__name">${step.agent_name || step.agent_id || `Agent ${i + 1}`}</span>
                  <span class="trace-step__duration">${formatLatency(step.duration_ms || 0)}</span>
                </div>
                <div class="trace-step__detail">${step.detail || step.message || `Status: ${step.status || "completed"}`}</div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;

    dom.modalBody.innerHTML = metaHtml + pipelineHtml;
    dom.traceModal.hidden = false;
    requestAnimationFrame(() => dom.traceModal.classList.add("active"));
  }

  function closeTraceModal() {
    dom.traceModal.classList.remove("active");
    setTimeout(() => { dom.traceModal.hidden = true; }, 300);
  }

  dom.modalClose.addEventListener("click", closeTraceModal);
  dom.traceModal.addEventListener("click", (e) => {
    if (e.target === dom.traceModal) closeTraceModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeTraceModal();
  });

  // ══════════════════════════════════════════
  //  WEBSOCKET CONNECTION
  // ══════════════════════════════════════════
  function connectWebSocket() {
    try {
      state.ws = new WebSocket(WS_URL);

      state.ws.addEventListener("open", () => {
        console.log("[WS] Connected to", WS_URL);
        state.connected = true;
        state.demoMode = false;
        state.reconnectAttempt = 0;
        setConnectionStatus("connected");
        stopDemo();
      });

      state.ws.addEventListener("message", (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "transaction" || data.transaction_id || data.id) {
            addTransaction(data);
          } else if (data.type === "batch" && Array.isArray(data.transactions)) {
            data.transactions.forEach(addTransaction);
          }
        } catch (err) {
          console.warn("[WS] Parse error:", err);
        }
      });

      state.ws.addEventListener("close", () => {
        console.log("[WS] Connection closed");
        state.connected = false;
        setConnectionStatus("disconnected");
        scheduleReconnect();
      });

      state.ws.addEventListener("error", (err) => {
        console.warn("[WS] Error:", err);
        state.ws.close();
      });
    } catch (e) {
      console.warn("[WS] Failed to connect:", e);
      startDemo();
    }
  }

  function scheduleReconnect() {
    const delay = Math.min(RECONNECT_BASE * Math.pow(2, state.reconnectAttempt), RECONNECT_MAX);
    state.reconnectAttempt++;
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempt})`);

    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(() => {
      if (!state.connected) {
        if (state.reconnectAttempt >= 3 && !state.demoMode) {
          startDemo();
        }
        connectWebSocket();
      }
    }, delay);
  }

  // ══════════════════════════════════════════
  //  DEMO MODE — Simulated Data
  // ══════════════════════════════════════════
  const DEMO_NAMES = [
    "Alice Chen", "Bob Martinez", "Carol Davis", "Daniel Kim", "Eva Patel",
    "Frank Wilson", "Grace Lee", "Henry Brown", "Iris Johnson", "Jack Thompson",
    "Karen White", "Leo Garcia", "Maya Nakamura", "Nathan Scott", "Olivia Reed",
    "Paul Wang", "Quinn Foster", "Rachel Adams", "Sam Okafor", "Tina Müller",
  ];

  const DEMO_MERCHANTS = [
    "Amazon", "Walmart", "Target", "Best Buy", "Uber Eats", "Netflix",
    "Steam Store", "Apple Store", "Costco", "Starbucks", "DoorDash",
    "Airbnb", "Booking.com", "Etsy", "Home Depot",
  ];

  function generateDemoId() {
    const chars = "abcdef0123456789";
    let id = "txn_";
    for (let i = 0; i < 16; i++) id += chars[Math.floor(Math.random() * chars.length)];
    return id;
  }

  function generateDemoTrace() {
    const agents = [
      { agent_id: "preprocessor",   agent_name: "Preprocessor",   detail: "Normalized and validated input fields. Geocoded IP to region." },
      { agent_id: "rule_engine",    agent_name: "Rule Engine",     detail: "Evaluated 47 fraud rules. 2 rules flagged for review." },
      { agent_id: "velocity_check", agent_name: "Velocity Check",  detail: "Checked transaction frequency: 3 txns in last hour." },
      { agent_id: "ml_model",       agent_name: "ML Model",        detail: "XGBoost ensemble inference. Feature importance: amount(0.32), velocity(0.28), geo(0.19)." },
      { agent_id: "risk_scorer",    agent_name: "Risk Scorer",     detail: "Aggregated agent signals. Weighted consensus score computed." },
      { agent_id: "decision_engine", agent_name: "Decision Engine", detail: "Final decision rendered based on risk threshold and policy." },
    ];

    const statuses = ["success", "success", "success", "success", "warning", "flagged"];
    return agents.map((a, i) => ({
      ...a,
      duration_ms: 5 + Math.random() * 40,
      status: Math.random() > 0.85 ? statuses[Math.floor(Math.random() * statuses.length)] : "success",
    }));
  }

  function generateDemoTransaction() {
    const decisions = ["APPROVE", "APPROVE", "APPROVE", "APPROVE", "APPROVE",
                       "DECLINE", "DECLINE", "ESCALATE"];
    const risks = ["low", "low", "low", "medium", "medium", "high", "critical"];

    const decision = decisions[Math.floor(Math.random() * decisions.length)];
    const risk = decision === "APPROVE"
      ? (Math.random() > 0.2 ? "low" : "medium")
      : decision === "DECLINE"
      ? (Math.random() > 0.3 ? "high" : "critical")
      : risks[Math.floor(Math.random() * risks.length)];

    const latency = decision === "APPROVE"
      ? 20 + Math.random() * 60
      : 40 + Math.random() * 120;

    const amount = decision === "DECLINE"
      ? 200 + Math.random() * 9800
      : 5 + Math.random() * 2000;

    return {
      transaction_id: generateDemoId(),
      timestamp: new Date().toISOString(),
      amount: Math.round(amount * 100) / 100,
      customer_name: DEMO_NAMES[Math.floor(Math.random() * DEMO_NAMES.length)],
      merchant: DEMO_MERCHANTS[Math.floor(Math.random() * DEMO_MERCHANTS.length)],
      decision: decision,
      confidence: decision === "APPROVE"
        ? 0.75 + Math.random() * 0.25
        : decision === "DECLINE"
        ? 0.6 + Math.random() * 0.35
        : 0.35 + Math.random() * 0.3,
      latency: Math.round(latency * 10) / 10,
      risk_level: risk,
      agent_trace: generateDemoTrace(),
    };
  }

  function startDemo() {
    if (state.demoMode) return;
    state.demoMode = true;
    setConnectionStatus("demo");
    console.log("[DEMO] Starting demo mode with simulated transactions");

    // Initial burst
    for (let i = 0; i < 8; i++) {
      setTimeout(() => addTransaction(generateDemoTransaction()), i * 200);
    }

    state.demoTimer = setInterval(() => {
      addTransaction(generateDemoTransaction());
    }, DEMO_INTERVAL);
  }

  function stopDemo() {
    if (state.demoTimer) {
      clearInterval(state.demoTimer);
      state.demoTimer = null;
    }
  }

  // ══════════════════════════════════════════
  //  INITIALIZE
  // ══════════════════════════════════════════
  function init() {
    renderAlertTicker();
    connectWebSocket();

    // Fallback: if WS doesn't connect in 2s, start demo
    setTimeout(() => {
      if (!state.connected && !state.demoMode) {
        startDemo();
      }
    }, 2000);
  }

  init();
})();
