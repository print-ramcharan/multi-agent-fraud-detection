import React, { useState, useEffect, useRef } from 'react';
import { Doughnut, Line } from 'react-chartjs-2';
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  PointElement, 
  LineElement, 
  Title, 
  Tooltip, 
  Legend, 
  ArcElement 
} from 'chart.js';
import { 
  Activity, 
  ShieldCheck, 
  AlertTriangle, 
  XOctagon, 
  Clock, 
  CheckCircle,
  AlertCircle,
  HelpCircle,
  ChevronRight,
  Database,
  Cpu,
  Layers,
  ArrowRightLeft
} from 'lucide-react';

// Register ChartJS plugins
ChartJS.register(
  CategoryScale, 
  LinearScale, 
  PointElement, 
  LineElement, 
  Title, 
  Tooltip, 
  Legend, 
  ArcElement
);

// Use explicit API websocket endpoint for reliable local dev
const WS_URL = "ws://127.0.0.1:8000/ws/live";

const MAX_FEED_ROWS = 100;
const LATENCY_WINDOW = 30;
const SLA_LINE = 100;

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Aggregate Stats
  const [stats, setStats] = useState({
    total: 0,
    approved: 0,
    declined: 0,
    escalated: 0,
    totalLatency: 0,
    alerts: 0
  });

  // Latency Timeline
  const [latencyHistory, setLatencyHistory] = useState([]);
  const [timeLabels, setTimeLabels] = useState([]);

  // Agent Performance Stats
  const [agentStats, setAgentStats] = useState({
    preprocessor: { totalLatency: 0, count: 0, errors: 0 },
    rule_engine: { totalLatency: 0, count: 0, errors: 0 },
    ml_model: { totalLatency: 0, count: 0, errors: 0 },
    velocity_check: { totalLatency: 0, count: 0, errors: 0 },
    risk_scorer: { totalLatency: 0, count: 0, errors: 0 },
    decision_engine: { totalLatency: 0, count: 0, errors: 0 }
  });

  const [alerts, setAlerts] = useState(["System online — monitoring active"]);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // Time Ticker
  const [currentTime, setCurrentTime] = useState("");
  useEffect(() => {
    const tick = () => {
      const date = new Date();
      setCurrentTime(date.toLocaleTimeString("en-US", { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket Connection Manager
  useEffect(() => {
    function connect() {
      console.log("[React WS] Connecting to", WS_URL);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[React WS] Connected successfully");
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.transaction_id || data.id) {
            handleIncomingTransaction(data);
          }
        } catch (e) {
          console.warn("[React WS] Error parsing message:", e);
        }
      };

      ws.onclose = () => {
        console.log("[React WS] Connection closed. Reconnecting...");
        setIsConnected(false);
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = (e) => {
        console.warn("[React WS] WebSocket error occurred", e);
        ws.close();
      };
    }

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, []);

  const handleIncomingTransaction = (txn) => {
    // attach a local unique id to ensure React list keys are unique
    const localTxn = { ...txn, _uid: `${txn.transaction_id || 'auto'}-${Date.now()}-${Math.random().toString(36).slice(2,8)}` };
    setTransactions(prev => {
      const nextList = [localTxn, ...prev];
      if (nextList.length > MAX_FEED_ROWS) nextList.pop();
      return nextList;
    });

    const dec = (txn.decision || "").toUpperCase();
    const isApprove = dec.includes("APPROVE");
    const isDecline = dec.includes("DECLINE");
    const isEscalate = dec.includes("ESCALAT");
    const latencyVal = txn.processing_time_ms || txn.latency || 0;
    const risk = (txn.risk_level || "").toUpperCase();
    const isAlert = risk === "HIGH" || risk === "CRITICAL";

    // Update stats
    setStats(prev => ({
      total: prev.total + 1,
      approved: prev.approved + (isApprove ? 1 : 0),
      declined: prev.declined + (isDecline ? 1 : 0),
      escalated: prev.escalated + (isEscalate ? 1 : 0),
      totalLatency: prev.totalLatency + latencyVal,
      alerts: prev.alerts + (isAlert ? 1 : 0)
    }));

    // Update alerts list if applicable
    if (isAlert) {
      const shortId = txn.transaction_id ? txn.transaction_id.slice(-6) : "------";
      const newAlert = `${risk} RISK — txn_...${shortId} — $${txn.amount || 0} — Customer: ${txn.customer || "Unknown"}`;
      setAlerts(prevAlerts => [newAlert, ...prevAlerts.slice(0, 19)]);
    }

    // Update Agent Stats from trace
    if (txn.audit_trail && txn.audit_trail.entries) {
      setAgentStats(prev => {
        const nextAgentStats = { ...prev };
        txn.audit_trail.entries.forEach(entry => {
          let id = entry.agent_name.toLowerCase().replace(" ", "_");
          if (id === "ml_risk_agent") id = "ml_model";
          if (id === "blacklist_agent") id = "preprocessor";
          if (nextAgentStats[id]) {
            nextAgentStats[id].totalLatency += entry.duration_ms || 0;
            nextAgentStats[id].count += 1;
            if (entry.status === "error" || entry.status === "timeout") {
              nextAgentStats[id].errors += 1;
            }
          }
        });
        return nextAgentStats;
      });
    }

    // Update Latency Graph (rolling calculations)
    const lat = txn.processing_time_ms || txn.latency || 0;
    const nowStr = new Date().toLocaleTimeString("en-US", { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    setTimeLabels(prev => {
      const next = [...prev, nowStr];
      if (next.length > LATENCY_WINDOW) next.shift();
      return next;
    });

    setLatencyHistory(prev => {
      const next = [...prev, lat];
      if (next.length > LATENCY_WINDOW) next.shift();
      return next;
    });
  };


  const getPercentile = (arr, q) => {
    if (arr.length === 0) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    const pos = (sorted.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    if (sorted[base + 1] !== undefined) {
      return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
    }
    return sorted[base];
  };

  // Pre-seed timelines if empty to keep charts rendering nicely
  const lineChartData = {
    labels: timeLabels.length > 0 ? timeLabels : ["Waiting"],
    datasets: [
      {
        label: 'Latency',
        data: latencyHistory.length > 0 ? latencyHistory : [0],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 2,
      },
      {
        label: 'SLA Limit (100ms)',
        data: Array(Math.max(1, timeLabels.length)).fill(SLA_LINE),
        borderColor: 'rgba(244, 63, 94, 0.5)',
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
      }
    ]
  };

  const donutChartData = {
    labels: ['Approved', 'Declined', 'Escalated'],
    datasets: [{
      data: [stats.approved, stats.declined, stats.escalated],
      backgroundColor: [
        'rgba(16, 185, 129, 0.85)',
        'rgba(244, 63, 94, 0.85)',
        'rgba(245, 158, 11, 0.85)'
      ],
      borderColor: [
        '#10b981',
        '#f43f5e',
        '#f59e0b'
      ],
      borderWidth: 1,
      hoverOffset: 6
    }]
  };

  const formatCurrency = (val) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD"
    }).format(val || 0);
  };

  const getDecisionBadge = (decision) => {
    const dec = (decision || "").toUpperCase();
    if (dec.includes("APPROVE")) return <span style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: '#10b981', padding: '4px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>APPROVE</span>;
    if (dec.includes("DECLINE")) return <span style={{ backgroundColor: 'rgba(244,63,94,0.15)', color: '#f43f5e', padding: '4px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>DECLINE</span>;
    return <span style={{ backgroundColor: 'rgba(245,158,11,0.15)', color: '#f59e0b', padding: '4px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>ESCALATE</span>;
  };

  const getRiskBadge = (risk) => {
    const r = (risk || "LOW").toUpperCase();
    if (r === "CRITICAL" || r === "HIGH") {
      return <span style={{ backgroundColor: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>{r}</span>;
    }
    if (r === "MEDIUM") {
      return <span style={{ backgroundColor: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.2)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>{r}</span>;
    }
    return <span style={{ backgroundColor: 'rgba(16,185,129,0.15)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700 }}>{r}</span>;
  };

  const handleRowClick = (txn) => {
    setSelectedTxn(txn);
    setIsModalOpen(true);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', padding: '20px', maxWidth: '1440px', margin: '0 auto', gap: '20px' }}>
      
      {/* ── HEADER ── */}
      <header style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        padding: '16px 24px', 
        background: 'rgba(16, 22, 38, 0.7)', 
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--border-color)', 
        borderRadius: '12px',
        boxShadow: '0 4px 30px rgba(0, 0, 0, 0.4)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ 
            background: 'linear-gradient(135deg, var(--blue), var(--purple))', 
            width: '40px', 
            height: '40px', 
            borderRadius: '10px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)'
          }}>
            <ShieldCheck size={24} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0, letterSpacing: '-0.5px' }}>
              Fraud Detection Command Center
            </h1>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Multi-Agent Live Intelligence Engine
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            {currentTime || "--:--:--"}
          </div>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            padding: '6px 12px', 
            borderRadius: '20px', 
            background: isConnected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
            border: `1px solid ${isConnected ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}`
          }}>
            <span className="pulse-dot" style={{ backgroundColor: isConnected ? 'var(--green)' : 'var(--red)', animation: isConnected ? 'pulseGlow 2s infinite ease-in-out' : 'none' }}></span>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isConnected ? 'var(--green)' : 'var(--red)' }}>
              {isConnected ? 'LIVE' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </header>

      {/* ── KPI CARDS ── */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        {[
          { label: 'Total Transactions', value: stats.total, icon: <ArrowRightLeft size={20} color="#3b82f6" />, accent: 'blue' },
          { label: 'Approval Rate', value: `${stats.total > 0 ? ((stats.approved / stats.total) * 100).toFixed(1) : 0}%`, icon: <CheckCircle size={20} color="#10b981" />, accent: 'green' },
          { label: 'Decline Rate', value: `${stats.total > 0 ? ((stats.declined / stats.total) * 100).toFixed(1) : 0}%`, icon: <XOctagon size={20} color="#f43f5e" />, accent: 'red' },
          { label: 'Escalation Rate', value: `${stats.total > 0 ? ((stats.escalated / stats.total) * 100).toFixed(1) : 0}%`, icon: <AlertTriangle size={20} color="#f59e0b" />, accent: 'amber' },
          { label: 'Avg Latency', value: `${stats.total > 0 ? Math.round(stats.totalLatency / stats.total) : 0}ms`, icon: <Clock size={20} color="#8b5cf6" />, accent: 'purple' },
          { label: 'Active Alerts', value: stats.alerts, icon: <AlertCircle size={20} color="#ef4444" />, accent: 'red' }
        ].map((card, idx) => (
          <div key={idx} style={{
            background: 'var(--bg-panel)',
            backdropFilter: 'blur(10px)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
            transition: 'border-color 0.3s',
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-hover)'}
          onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
          >
            <div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{card.label}</p>
              <h2 style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '6px', fontFamily: 'var(--font-mono)' }}>{card.value}</h2>
            </div>
            <div style={{ 
              width: '40px', 
              height: '40px', 
              borderRadius: '8px', 
              background: 'rgba(255,255,255,0.03)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center' 
            }}>{card.icon}</div>
          </div>
        ))}
      </section>

      {/* ── MAIN DASHBOARD GRID ── */}
      <main style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '20px', alignItems: 'stretch' }}>
        
        {/* Left: Feed Panel */}
        <section style={{
          background: 'var(--bg-panel)',
          border: '1px solid var(--border-color)',
          borderRadius: '16px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '520px'
        }}>
          <div style={{ padding: '20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="pulse-dot" style={{ width: '6px', height: '6px' }}></span>
              Live Transaction Feed
            </h2>
            <span style={{ fontSize: '0.72rem', background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', padding: '4px 10px', borderRadius: '20px', fontFamily: 'var(--font-mono)' }}>
              {transactions.length} txns
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '0 12px 12px 12px', maxHeight: '580px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: 'var(--text-secondary)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  <th style={{ padding: '14px 10px' }}>Time</th>
                  <th style={{ padding: '14px 10px' }}>Txn ID</th>
                  <th style={{ padding: '14px 10px' }}>Amount</th>
                  <th style={{ padding: '14px 10px' }}>Customer</th>
                  <th style={{ padding: '14px 10px' }}>Decision</th>
                  <th style={{ padding: '14px 10px' }}>Confidence</th>
                  <th style={{ padding: '14px 10px' }}>Latency</th>
                  <th style={{ padding: '14px 10px' }}>Risk</th>
                </tr>
              </thead>
              <tbody>
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      <Activity size={32} style={{ margin: '0 auto 12px auto', opacity: 0.3 }} className="pulse-dot" />
                      Waiting for incoming transaction logs...
                    </td>
                  </tr>
                ) : (
                  transactions.map((txn, idx) => {
                    const lat = txn.processing_time_ms || txn.latency || 0;
                    const conf = txn.confidence != null ? Math.round(txn.confidence * 100) : 0;
                    const confColor = conf >= 80 ? 'var(--green)' : conf >= 50 ? 'var(--amber)' : 'var(--red)';
                    
                    return (
                      <tr 
                        key={txn._uid || txn.transaction_id || idx} 
                        className="flash-row"
                        onClick={() => handleRowClick(txn)}
                        style={{ 
                          borderBottom: '1px solid rgba(255,255,255,0.03)', 
                          fontSize: '0.78rem', 
                          cursor: 'pointer',
                          transition: 'background 0.2s'
                        }}
                        onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)'}
                        onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        <td style={{ padding: '12px 10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                          {new Date(txn.timestamp || Date.now()).toLocaleTimeString("en-US", { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                        <td style={{ padding: '12px 10px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                          {txn.transaction_id ? txn.transaction_id.slice(-8) : "—"}
                        </td>
                        <td style={{ padding: '12px 10px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {formatCurrency(txn.amount)}
                        </td>
                        <td style={{ padding: '12px 10px', color: 'var(--text-secondary)' }}>
                          {txn.customer || "—"}
                        </td>
                        <td style={{ padding: '12px 10px' }}>
                          {getDecisionBadge(txn.decision)}
                        </td>
                        <td style={{ padding: '12px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ width: '40px', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px' }}>
                              <div style={{ width: `${conf}%`, height: '100%', background: confColor, borderRadius: '2px' }}></div>
                            </div>
                            <span style={{ color: confColor, fontWeight: 600, fontSize: '0.7rem', fontFamily: 'var(--font-mono)' }}>{conf}%</span>
                          </div>
                        </td>
                        <td style={{ 
                          padding: '12px 10px', 
                          fontFamily: 'var(--font-mono)', 
                          color: lat > SLA_LINE ? 'var(--red)' : 'var(--green)',
                          fontWeight: 500
                        }}>
                          {lat.toFixed(1)}ms
                        </td>
                        <td style={{ padding: '12px 10px' }}>
                          {getRiskBadge(txn.risk_level)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Right side: Charts & agent stats */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Decision Distribution Donut */}
          <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Decision Distribution</h2>
            <div style={{ height: '150px', position: 'relative', display: 'flex', justifyContent: 'center' }}>
              <Doughnut 
                data={donutChartData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: false }
                  },
                  cutout: '70%'
                }} 
              />
              <div style={{ position: 'absolute', top: '52%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'var(--font-mono)' }}>{stats.total}</span>
                <p style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Total</p>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '10px' }}>
              {[
                { label: 'Approved', count: stats.approved, color: '#10b981' },
                { label: 'Declined', count: stats.declined, color: '#f43f5e' },
                { label: 'Escalated', count: stats.escalated, color: '#f59e0b' }
              ].map((item, idx) => (
                <div key={idx} style={{ textAlign: 'center' }}>
                  <div style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color, marginRight: '6px' }}></div>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{item.label}</span>
                  <p style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', marginTop: '2px' }}>{item.count}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Latency Timeline Chart */}
          <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Latency Monitor</h2>
              <span style={{ fontSize: '0.65rem', color: 'var(--red)', background: 'rgba(244,63,94,0.1)', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>SLA 100ms</span>
            </div>
            <div style={{ height: '140px' }}>
              <Line 
                data={lineChartData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false } },
                  scales: {
                    x: { display: false },
                    y: { 
                      grid: { color: 'rgba(255,255,255,0.02)' },
                      ticks: { color: '#64748b', font: { size: 9, family: 'var(--font-mono)' } }
                    }
                  }
                }} 
              />
            </div>
          </div>

          {/* Agent Stats Heatmap/Grid */}
          <div style={{
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Agent Execution</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
              {[
                { id: 'preprocessor', name: 'Preprocessor' },
                { id: 'rule_engine', name: 'Rule Engine' },
                { id: 'ml_model', name: 'ML Model' },
                { id: 'velocity_check', name: 'Velocity Check' },
                { id: 'risk_scorer', name: 'Risk Scorer' },
                { id: 'decision_engine', name: 'Decision Engine' }
              ].map(agent => {
                const s = agentStats[agent.id];
                const avg = s.count > 0 ? s.totalLatency / s.count : 0;
                const successRate = s.count > 0 ? (((s.count - s.errors) / s.count) * 100).toFixed(1) : "—";
                
                let cellClass = 'rgba(16, 185, 129, 0.05)';
                let borderCol = 'rgba(16, 185, 129, 0.15)';
                let textCol = 'var(--green)';
                
                if (avg > 80) {
                  cellClass = 'rgba(239, 68, 68, 0.05)';
                  borderCol = 'rgba(239, 68, 68, 0.15)';
                  textCol = 'var(--red)';
                } else if (avg > 40) {
                  cellClass = 'rgba(245, 158, 11, 0.05)';
                  borderCol = 'rgba(245, 158, 11, 0.15)';
                  textCol = 'var(--amber)';
                }

                return (
                  <div key={agent.id} style={{
                    backgroundColor: cellClass,
                    border: `1px solid ${borderCol}`,
                    borderRadius: '8px',
                    padding: '8px 10px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '62px'
                  }}>
                    <span style={{ fontSize: '0.68rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{agent.name}</span>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '4px' }}>
                      <span style={{ fontSize: '0.95rem', fontWeight: 800, color: textCol, fontFamily: 'var(--font-mono)' }}>
                        {avg.toFixed(0)}<small style={{ fontSize: '0.55rem', fontWeight: 500 }}>ms</small>
                      </span>
                      <span style={{ fontSize: '0.58rem', color: 'var(--text-muted)' }}>{successRate === "—" ? "—" : `${successRate}% ok`}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </section>

      </main>

      {/* ── ALERTS TICKER BAR ── */}
      <footer style={{ 
        display: 'flex', 
        alignItems: 'center', 
        background: 'rgba(239, 68, 68, 0.04)', 
        border: '1px solid rgba(239, 68, 68, 0.12)', 
        borderRadius: '8px', 
        padding: '10px 16px',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontWeight: 700, fontSize: '0.72rem', letterSpacing: '0.5px' }}>
          <AlertCircle size={16} />
          ALERTS
        </div>
        <div style={{ flex: 1, overflow: 'hidden', whiteSpace: 'nowrap', position: 'relative' }}>
          <div style={{ display: 'inline-block', fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            {alerts.length > 0 ? alerts[0] : "System monitoring is active."}
          </div>
        </div>
      </footer>

      {/* ── AGENT TRACE MODAL ── */}
      {isModalOpen && selectedTxn && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(5px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#0d1323',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '16px',
            width: '600px',
            maxWidth: '90%',
            padding: '24px',
            boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Agent Execution Trace</h2>
              <button 
                onClick={() => setIsModalOpen(false)}
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--text-secondary)', 
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                <XOctagon size={20} />
              </button>
            </div>

            {/* Trace Meta Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '12px',
              background: 'rgba(255,255,255,0.02)',
              border: '1px solid rgba(255,255,255,0.04)',
              borderRadius: '8px',
              padding: '12px 16px'
            }}>
              <div>
                <p style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Transaction ID</p>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{selectedTxn.transaction_id}</span>
              </div>
              <div>
                <p style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Amount / Customer</p>
                <span style={{ fontSize: '0.78rem', fontWeight: 600 }}>{formatCurrency(selectedTxn.amount)} ({selectedTxn.customer || "Unknown"})</span>
              </div>
              <div>
                <p style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Decision / Confidence</p>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                  {getDecisionBadge(selectedTxn.decision)} 
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{(selectedTxn.confidence * 100).toFixed(0)}%</span>
                </span>
              </div>
              <div>
                <p style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Processing Latency</p>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--blue)' }}>{(selectedTxn.processing_time_ms || selectedTxn.latency || 0).toFixed(1)}ms</span>
              </div>
            </div>

            {/* Flow Steps */}
            <div>
              <h3 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '12px', textTransform: 'uppercase' }}>Pipeline Execution Chain</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
                {selectedTxn.audit_trail && selectedTxn.audit_trail.entries ? (
                  selectedTxn.audit_trail.entries.map((entry, i) => (
                    <div key={i} style={{ 
                      display: 'flex', 
                      gap: '12px',
                      background: 'rgba(255,255,255,0.01)',
                      borderLeft: `2px solid ${entry.status === 'success' ? 'var(--green)' : 'var(--red)'}`,
                      padding: '10px 12px',
                      borderRadius: '0 8px 8px 0'
                    }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>{entry.agent_name}</span>
                          <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{entry.duration_ms.toFixed(1)}ms</span>
                        </div>
                        <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '130%' }}>
                          {entry.output && entry.output.reason ? entry.output.reason : `Executed agent inside budget limit (${entry.budget_ms}ms)`}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px 0', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    No execution trace available for this fast-path transaction.
                  </div>
                )}
              </div>
            </div>

            <button 
              onClick={() => setIsModalOpen(false)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '8px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '0.78rem',
                cursor: 'pointer',
                transition: 'background 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)'}
              onMouseLeave={e => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'}
            >
              Close Trace Details
            </button>
          </div>
        </div>
      )}
      
    </div>
  );
}
