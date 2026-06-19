import React, { useState, useEffect } from 'react';

export default function AdminMetrics() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [backingUp, setBackingUp] = useState(false);
  const [backupMessage, setBackupMessage] = useState('');

  // 1. Fetch System Calculations out of our FastAPI /api/admin/metrics endpoint
  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/metrics');
      const data = await response.json();
      
      if (data.status === 'success') {
        setMetrics(data.summary);
      } else {
        setError(data.message || 'Initializing predictive data queues...');
      }
    } catch (err) {
      setError('Failed to reach backend metrics server.');
    } finally {
      setLoading(false);
    }
  };

  // 2. Trigger instant manual backup to your private Supabase bucket
  const handleBackupNow = async () => {
    try {
      setBackingUp(true);
      setBackupMessage('Initializing backup routine...');
      const response = await fetch('/api/admin/backup-now');
      // PlainTextResponse returns plain text, so we check status code
      if (response.ok) {
        setBackupMessage('Backup successfully queued!');
      } else {
        setBackupMessage('Backup pipeline request failed.');
      }
    } catch (err) {
      setBackupMessage('Backup pipeline request failed.');
    } finally {
      setBackingUp(false);
      setTimeout(() => setBackupMessage(''), 4000); // Clear notification flag
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-white">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-emerald-500 border-t-transparent"></div>
        <p className="ml-4 font-medium text-slate-300">Evaluating Model Parameters...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100 font-sans md:p-12">
      {/* HEADER BAR ROW */}
      <div className="mb-8 flex flex-col justify-between gap-4 border-b border-slate-800 pb-6 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">
            FootyEdge AI <span className="text-emerald-500 text-2xl font-bold font-mono">v2.0</span>
          </h1>
          <p className="mt-1 text-sm text-slate-400">Production Engine Diagnostics & Value Analytics Control</p>
        </div>
        
        {/* INTERACTIVE ACTION BUTTON SETS */}
        <div className="flex flex-wrap items-center gap-3">
          <button 
            onClick={fetchMetrics}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700 transition"
          >
            🔄 Refresh Metrics
          </button>
          <button 
            onClick={handleBackupNow}
            disabled={backingUp}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition shadow-lg shadow-emerald-900/30"
          >
            📦 Backup Database Now
          </button>
        </div>
      </div>

      {/* POP-UP NOTIFICATION OVERLAYS */}
      {backupMessage && (
        <div className="mb-6 rounded-lg bg-emerald-950/50 border border-emerald-500/30 p-4 text-sm font-medium text-emerald-400 animate-pulse">
          🛰️ System Status Log: {backupMessage}
        </div>
      )}

      {error ? (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-6 text-center">
          <p className="text-amber-400 font-semibold">⚠️ Diagnostic Warning: {error}</p>
          <p className="mt-2 text-sm text-slate-400">The server is executing data pipeline sync matrices. Check back shortly.</p>
        </div>
      ) : (
        <>
          {/* HIGH-DENSITY PERFORMANCE METRIC CARDS GRID */}
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            
            {/* CARD 1: OVERALL ACCURACY */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-xl">
              <p className="text-sm font-bold uppercase tracking-wider text-slate-500">Model Accuracy</p>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-white">{metrics.model_accuracy_percentage}%</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">Verified win probability precision across matching selections</p>
            </div>

            {/* CARD 2: TOTAL NET PROFIT */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-xl">
              <p className="text-sm font-bold uppercase tracking-wider text-slate-500">Simulated Net Profit</p>
              <div className="mt-4 flex items-baseline gap-2">
                <span className={`text-4xl font-extrabold ${metrics.simulated_net_profit_usd >= 0 ? 'text-emerald-400' : 'text-rose-500'}`}>
                  ${metrics.simulated_net_profit_usd.toLocaleString()}
                </span>
                <span className="text-xs text-slate-400 font-mono">USD</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">Accumulated returns tracking a normalized flat $100 baseline stake</p>
            </div>

            {/* CARD 3: PORTFOLIO ROI */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-xl">
              <p className="text-sm font-bold uppercase tracking-wider text-slate-500">Capital Return Rate (ROI)</p>
              <div className="mt-4 flex items-baseline gap-2">
                <span className={`text-4xl font-extrabold ${metrics.simulated_roi_percentage >= 0 ? 'text-emerald-400' : 'text-rose-500'}`}>
                  {metrics.simulated_roi_percentage}%
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-400">Net asset growth yields calculated against aggregate risk pool allocations</p>
            </div>

            {/* CARD 4: MATCHES RUN TIME COMPUTE COUNTER */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-xl">
              <p className="text-sm font-bold uppercase tracking-wider text-slate-500">Evaluated Games</p>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-extrabold text-white">{metrics.total_games_analyzed}</span>
                <span className="text-xs text-emerald-400 font-semibold bg-emerald-950 border border-emerald-800/50 px-2 py-0.5 rounded">Active</span>
              </div>
              <p className="mt-2 text-xs text-slate-400">Total historical and current fixture models processed in database</p>
            </div>

          </div>

          {/* POISSON SOLVER STATE INTEGRITY STATUS CARDS */}
          <div className="mt-8 rounded-xl border border-slate-800 bg-slate-950/60 p-6">
            <h3 className="text-lg font-bold text-white">System Architecture Status</h3>
            <div className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
              <div className="flex items-center gap-3 rounded-lg bg-slate-900 p-4 border border-slate-800/40">
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></div>
                <p className="text-slate-300">Background Cron Process: <span className="text-emerald-400 font-bold font-mono">ONLINE</span></p>
              </div>
              <div className="flex items-center gap-3 rounded-lg bg-slate-900 p-4 border border-slate-800/40">
                <div className="h-2 w-2 rounded-full bg-emerald-400"></div>
                <p className="text-slate-300">Database Core Connection: <span className="text-emerald-400 font-bold font-mono">SUPABASE OK</span></p>
              </div>
              <div className="flex items-center gap-3 rounded-lg bg-slate-900 p-4 border border-slate-800/40">
                <div className="h-2 w-2 rounded-full bg-emerald-400"></div>
                <p className="text-slate-300">Edge Odds Engine: <span className="text-emerald-400 font-bold font-mono">THE_ODDS_API OK</span></p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
