import React, { useState, useEffect } from 'react';

export default function PredictionsDashboard() {
  const [predictions, setPredictions] = useState<any[]>([]);
  const [acca, setAcca] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);
  const [timeline, setTimeline] = useState('daily');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [totalBankroll, setTotalBankroll] = useState(1000);
  const [activeTab, setActiveTab] = useState<'predictions' | 'ledger'>('predictions');
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      let url = `/api/daily-picks?timeline=${timeline}`;
      if (timeline === 'custom' && startDate && endDate) {
        url += `&from_date=${startDate}&to_date=${endDate}`;
      }

      const [predRes, accaRes, ledgerRes] = await Promise.all([
        fetch(url),
        fetch('/api/acca-builder'),
        fetch('/api/public-ledger')
      ]);

      const [predData, accaData, ledgerData] = await Promise.all([
        predRes.json(),
        accaRes.json(),
        ledgerRes.json()
      ]);

      setPredictions(predData || []);
      if (accaData.status === 'success') setAcca(accaData);
      else setAcca(null);
      setLedger(ledgerData || []);
    } catch (err) {
      console.error("Failed fetching dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [timeline]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6 text-zinc-100 md:p-12 font-sans">

      <div className="mb-8 grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2 rounded-xl border border-zinc-800 bg-[#111] p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-xl font-bold text-white mb-2">📅 Football Prediction Planner</h2>
            <p className="text-xs text-zinc-400 mb-4">Plan and manage selections across dynamic daily or weekly timelines.</p>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="inline-flex rounded-lg bg-zinc-900 p-1 border border-zinc-800">
              {['daily', 'weekly', 'custom'].map((t) => (
                <button
                  key={t}
                  onClick={() => setTimeline(t)}
                  className={`rounded-md px-4 py-2 text-sm font-medium transition ${timeline === t ? 'bg-orange-500 text-black shadow' : 'text-zinc-400 hover:text-white'}`}
                >
                  {t === 'daily' ? "Today's Picks" : t === 'weekly' ? 'Weekly Schedule' : 'Custom Range'}
                </button>
              ))}
            </div>

            {timeline === 'custom' && (
              <div className="flex flex-wrap items-center gap-3">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white focus:border-orange-500 outline-none"
                />
                <span className="text-xs text-zinc-500 font-bold">TO</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white focus:border-orange-500 outline-none"
                />
                <button onClick={loadData} className="rounded-lg bg-orange-500 px-4 py-2 text-xs font-bold text-black hover:bg-orange-400 transition">
                  Apply
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-[#111] p-6 shadow-xl flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400">💰 Live Capital Manager</h3>
            <p className="mt-1 text-xs text-zinc-500 leading-normal">
              Type your bankroll balance. Cards will display your exact cash stake size.
            </p>
          </div>
          <div className="mt-4 relative rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2.5 focus-within:border-orange-500 transition">
            <span className="absolute left-3 top-2.5 font-mono text-zinc-500 text-base font-bold">$</span>
            <input
              type="number"
              value={totalBankroll}
              onChange={(e) => setTotalBankroll(Math.max(0, parseFloat(e.target.value) || 0))}
              className="w-full bg-transparent pl-5 pr-2 text-xl font-black text-white focus:outline-none font-mono"
              placeholder="0.00"
            />
          </div>
        </div>
      </div>

      <div className="mb-10 flex border-b border-zinc-800 gap-8 text-sm font-black uppercase tracking-widest">
        <button onClick={() => setActiveTab('predictions')} className={`pb-4 transition-all ${activeTab === 'predictions' ? 'border-b-2 border-orange-500 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}>
          🎯 Value Selections
        </button>
        <button onClick={() => setActiveTab('ledger')} className={`pb-4 transition-all ${activeTab === 'ledger' ? 'border-b-2 border-orange-500 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}>
          📜 Accuracy Ledger
        </button>
      </div>

      {activeTab === 'predictions' ? (
        <>
          {acca && (
            <div className="mb-12 rounded-[2rem] border border-orange-500/20 bg-gradient-to-br from-orange-950/10 to-zinc-950 p-8 shadow-2xl relative overflow-hidden group">
              <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-zinc-800 pb-6 mb-8 relative z-10">
                <div className="space-y-1">
                  <span className="bg-orange-500 text-black font-black text-[10px] px-3 py-1 rounded-full tracking-widest uppercase">Premium Combinator</span>
                  <h3 className="text-3xl font-black text-white mt-2">🔥 Daily High-Yield Acca</h3>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-500 font-bold uppercase tracking-widest">Combined Multiplier</p>
                  <p className="text-5xl font-black font-mono text-orange-500 mt-1">@{acca.combined_odds}x</p>
                </div>
              </div>
              <div className="grid gap-6 md:grid-cols-3 relative z-10">
                {acca.selections.map((s: any, idx: number) => (
                  <div key={idx} className="bg-zinc-900/40 p-5 rounded-2xl border border-white/5 hover:border-orange-500/30 transition-all">
                    <p className="font-bold text-sm text-white truncate">{s.home_team} vs {s.away_team}</p>
                    <div className="flex justify-between items-center mt-2">
                       <p className="text-[10px] text-zinc-500 uppercase font-mono">{s.market}</p>
                       <p className="text-xs font-black text-orange-400">{s.selection} @{s.odds}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {loading ? (
             <div className="py-24 text-center text-zinc-500 font-bold animate-pulse">Syncing with Momentum Engine...</div>
          ) : (
            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
              {predictions.map((pick) => {
                const stakePct = pick.kelly_stake_percentage || 0;
                const cashStake = (totalBankroll * (stakePct / 100));
                return (
                  <div key={pick.id} className="rounded-[2rem] border border-zinc-800 bg-[#111] p-8 hover:border-orange-500/20 transition-all flex flex-col justify-between group shadow-xl">
                    <div>
                      <div className="flex items-center justify-between border-b border-zinc-800/50 pb-4 text-[10px] text-zinc-500 font-bold uppercase tracking-widest">
                        <span className="flex items-center gap-2"><Activity className="w-3 h-3 text-orange-500" /> EWMA Engine</span>
                        <span className={`font-mono px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider border ${
                          pick.best_bet_market === 'Over/Under 2.5'
                            ? 'bg-blue-950/40 text-blue-400 border-blue-800/40'
                            : pick.best_bet_market === 'Both Teams to Score'
                            ? 'bg-purple-950/40 text-purple-400 border-purple-800/40'
                            : 'bg-zinc-900 text-orange-500 border-orange-500/20'
                        }`}>
                          {pick.best_bet_market}
                        </span>
                      </div>
                      <div className="my-6">
                        <h4 className="text-xl font-bold text-white leading-tight">{pick.home_team} <span className="text-zinc-700 mx-1">vs</span> {pick.away_team}</h4>
                        <div className="flex items-center justify-between mt-4">
                           <p className="text-sm font-black text-orange-500">{pick.best_bet_selection}</p>
                           <p className="text-lg font-black text-zinc-400">@ {pick.best_bet_odds.toFixed(2)}</p>
                        </div>
                      </div>
                    </div>
                    <div>
                      <div className="mb-6 rounded-2xl bg-zinc-900/60 p-4 border border-white/5">
                        <div className="flex items-center justify-between text-[10px] mb-2 font-bold uppercase tracking-tighter">
                          <span className="text-zinc-500">Risk Manager:</span>
                          <span className="font-mono text-orange-500">${cashStake.toFixed(2)}</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                          <div className="h-full bg-orange-500 rounded-full transition-all duration-1000" style={{ width: `${Math.min(stakePct * 4, 100)}%` }} />
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-3 mb-3">
                         <ProbBox label="HOME" val={pick.home_prob} />
                         <ProbBox label="DRAW" val={pick.draw_prob} />
                         <ProbBox label="AWAY" val={pick.away_prob} />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                         <ProbBox label="OVER 2.5" val={pick.over_2_5_prob || 0} />
                         <ProbBox label="BTTS" val={pick.btts_prob || 0} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <div className="rounded-[2rem] border border-zinc-800 bg-[#111] p-8 md:p-12 shadow-2xl">
          <div className="mb-10 space-y-2">
            <h3 className="text-3xl font-black text-white tracking-tight">📜 Accuracy Ledger</h3>
            <p className="text-sm text-zinc-500 font-medium">Verified historical performance audited against live scores.</p>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-zinc-800">
            <table className="w-full text-left text-sm text-zinc-400">
              <thead className="bg-zinc-900/50 text-[10px] text-zinc-500 border-b border-zinc-800 uppercase tracking-[0.2em] font-black">
                <tr>
                  <th className="p-6">Fixture</th>
                  <th className="p-6">Predicted Selection</th>
                  <th className="p-6">Target Odds</th>
                  <th className="p-6">Actual Result</th>
                  <th className="p-6 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {ledger.map((l: any, idx: number) => {
                  const isHit = l.best_bet_selection === l.actual_result;
                  return (
                    <tr key={idx} className="hover:bg-zinc-900/20 transition-colors">
                      <td className="p-6 font-bold text-white">{l.home_team} vs {l.away_team}</td>
                      <td className="p-6 font-medium">{l.best_bet_market} — <span className="text-orange-500">{l.best_bet_selection}</span></td>
                      <td className="p-6 font-mono font-bold">@{l.best_bet_odds.toFixed(2)}</td>
                      <td className="p-6 font-mono font-black text-white">{l.actual_result}</td>
                      <td className="p-6 text-right">
                        <span className={`inline-flex items-center px-4 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${isHit ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                          {isHit ? '🎯 HIT' : '❌ MISSED'}
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

function ProbBox({ label, val }: { label: string, val: number }) {
  return (
    <div className="bg-zinc-900/50 p-3 rounded-xl border border-white/5 text-center">
       <p className="text-[8px] text-zinc-600 font-black tracking-widest mb-1">{label}</p>
       <p className="text-xs font-black text-white font-mono">{(val * 100).toFixed(0)}%</p>
    </div>
  );
}

function Activity({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  );
}
