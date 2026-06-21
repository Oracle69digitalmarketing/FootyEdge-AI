import React, { useState, useEffect } from 'react';

export default function PredictionsDashboard() {
  const [predictions, setPredictions] = useState([]);
  const [acca, setAcca] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [timeline, setTimeline] = useState('daily');
  const [totalBankroll, setTotalBankroll] = useState(1000);
  const [activeTab, setActiveTab] = useState('predictions'); // View switcher: predictions or ledger

  useEffect(() => {
    // 1. Fetch active selections
    fetch(`https://onrender.com/api/daily-picks?timeline=${timeline}`)
      .then(res => res.json()).then(data => setPredictions(data));
      
    // 2. Compute combo accumulator ticket
    fetch('https://onrender.com/api/acca-builder')
      .then(res => res.json()).then(data => data.status === 'success' && setAcca(data));
      
    // 3. Populate Public Accuracy Ledger
    fetch('https://onrender.com/api/public-ledger')
      .then(res => res.json()).then(data => setLedger(data || []));
  }, [timeline]);

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100 md:p-12 font-sans">
      
      {/* SECTION NAV SWITCHER */}
      <div className="mb-6 flex border-b border-slate-800 gap-4 text-sm font-semibold">
        <button onClick={() => setActiveTab('predictions')} className={`pb-3 transition ${activeTab === 'predictions' ? 'border-b-2 border-emerald-500 text-white' : 'text-slate-400'}`}>
          🎯 Value Selections Feed
        </button>
        <button onClick={() => setActiveTab('ledger')} className={`pb-3 transition ${activeTab === 'ledger' ? 'border-b-2 border-emerald-500 text-white' : 'text-slate-400'}`}>
          📜 Public Accuracy Ledger
        </button>
      </div>

      {activeTab === 'predictions' ? (
        <>
          {/* HIGH-CONVERTING AUTOMATED ACCUMULATOR SLIP SLATE */}
          {acca && (
            <div className="mb-8 rounded-xl border border-amber-500/20 bg-gradient-to-r from-amber-950/20 to-slate-950 p-6 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                <div>
                  <span className="bg-amber-500 text-slate-950 font-black text-[10px] px-2 py-0.5 rounded tracking-wider uppercase">Premium Boost</span>
                  <h3 className="text-xl font-black text-white mt-1">🔥 Daily Recommended Multi-Market Acca</h3>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-400 font-medium">Combined OddsMultiplier:</p>
                  <p className="text-2xl font-black font-mono text-amber-400">@{acca.combined_odds}x</p>
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                {acca.selections.map((s, idx) => (
                  <div key={idx} className="bg-slate-900/60 p-3 rounded-lg border border-slate-800/40">
                    <p className="font-bold text-sm text-white truncate">{s.home_team} vs {s.away_team}</p>
                    <p className="text-xs text-slate-400 mt-1">{s.market}: <span className="text-amber-400 font-semibold">{s.selection}</span></p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* MAIN MATCH CARDS RENDERING COMPONENT GRID */}
          <div className="grid gap-6 md:grid-cols-3">
            {predictions.map((pick) => {
              const stakePct = pick.kelly_stake_percentage || 0;
              const cashStake = (totalBankroll * (stakePct / 100));
              return (
                <div key={pick.id} className="rounded-xl border border-slate-800 bg-slate-950 p-6 hover:border-slate-700 transition flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between border-b border-slate-900 pb-3 text-xs text-slate-400">
                      <span className="font-semibold text-slate-500">EWMA Momentum Engine</span>
                      <span className="font-mono bg-slate-900 px-2 py-0.5 rounded text-emerald-400 font-bold">{pick.best_bet_market}</span>
                    </div>
                    <div className="my-4">
                      <h4 className="text-lg font-bold text-white truncate">{pick.home_team} vs {pick.away_team}</h4>
                      <p className="text-sm font-semibold text-emerald-400 mt-1">{pick.best_bet_selection} @ {pick.best_bet_odds.toFixed(2)}</p>
                    </div>
                  </div>
                  <div>
                    {/* RISK MANAGER PROGRESS STRIP WITH ODDS DRIFT ARROW */}
                    <div className="mb-4 rounded-xl bg-slate-900/60 p-3 border border-slate-800/60">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-slate-400 font-medium">Suggested Investment:</span>
                        <span className="font-mono font-extrabold text-emerald-400">${cashStake.toFixed(2)}</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden mt-2">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(stakePct * 4, 100)}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        /* TRANS-NATIONAL PUBLIC HISTORICAL VERIFICATION LEDGER AUDIT SCREEN */
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-2xl">
          <div className="mb-4">
            <h3 className="text-xl font-bold text-white">📜 Unalterable Accuracy Ledger Audit</h3>
            <p className="text-xs text-slate-400">Full historical review tracking completed predictions against verified final whistle scores</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs text-slate-400 border-b border-slate-800 uppercase tracking-wider font-bold">
                <tr>
                  <th className="p-4">Fixture</th>
                  <th className="p-4">Suggested Bet</th>
                  <th className="p-4">Target Odds</th>
                  <th className="p-4">Actual Match Score</th>
                  <th className="p-4">Settle Verification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {ledger.map((l, idx) => {
                  const isHit = l.best_bet_selection === l.actual_result;
                  return (
                    <tr key={idx} className="hover:bg-slate-900/20 transition">
                      <td className="p-4 font-semibold text-white">{l.home_team} vs {l.away_team}</td>
                      <td className="p-4 text-slate-400">{l.best_bet_market} - <span className="text-slate-200">{l.best_bet_selection}</span></td>
                      <td className="p-4 font-mono">@{l.best_bet_odds.toFixed(2)}</td>
                      <td className="p-4 font-mono font-bold text-slate-300">{l.actual_result}</td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${isHit ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40' : 'bg-rose-950 text-rose-400 border border-rose-800/40'}`}>
                          {isHit ? '🎯 VERIFIED HIT' : '❌ MISSED'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
