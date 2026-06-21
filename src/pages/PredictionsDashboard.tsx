import React, { useState, useEffect } from 'react';

export default function PredictionsDashboard() {
  const [predictions, setPredictions] = useState<any[]>([]);
  const [timeline, setTimeline] = useState('daily');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [totalBankroll, setTotalBankroll] = useState(1000);
  const [isPremium, setIsPremium] = useState(true); // Default to true for personal use

  const loadPredictions = async () => {
    try {
      setLoading(true);
      let url = `/api/daily-picks?timeline=${timeline}`;
      if (timeline === 'custom' && startDate && endDate) {
        url += `&start_date=${startDate}&end_date=${endDate}`;
      }
      const response = await fetch(url);
      const data = await response.json();
      setPredictions(data);
    } catch (err) {
      console.error("Failed fetching predictions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPredictions();
  }, [timeline]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6 text-zinc-100 md:p-12">
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
                <button onClick={loadPredictions} className="rounded-lg bg-orange-500 px-4 py-2 text-xs font-bold text-black hover:bg-orange-400 transition">
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
              Type your current available bankroll balance below. The cards will automatically display your exact cash stake size.
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

      {loading ? (
        <div className="text-center text-zinc-400 py-12 animate-pulse">Running matrix analytics calculations...</div>
      ) : predictions.length > 0 ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {predictions.map((pick) => {
            const stakePct = pick.kelly_stake_percentage || 0;
            const cashStake = (totalBankroll * (stakePct / 100));

            return (
              <div key={pick.id} className="rounded-xl border border-zinc-800 bg-[#111] p-6 hover:border-orange-500/30 transition shadow-lg flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-3 text-xs text-zinc-400">
                    <span>Model v5.0-Poisson</span>
                    <span className="font-mono bg-zinc-900 px-2 py-0.5 rounded text-orange-500 font-bold uppercase">
                      {pick.best_bet_market}
                    </span>
                  </div>
                  <div className="my-4">
                    <h4 className="text-lg font-bold text-white truncate">{pick.home_team} vs {pick.away_team}</h4>
                    <p className="mt-2 text-xs text-zinc-500">Suggested Bet:</p>
                    <p className="text-sm font-semibold text-orange-500 mt-0.5">{pick.best_bet_selection} @ {pick.best_bet_odds.toFixed(2)}</p>
                  </div>
                </div>

                <div>
                  {isPremium ? (
                    <div className="mb-4 rounded-xl bg-zinc-900/60 p-3 border border-zinc-800/60">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-zinc-400 font-medium">Recommended Investment:</span>
                        <span className="font-mono font-extrabold text-white text-sm bg-orange-950/60 border border-orange-800/40 px-2 py-0.5 rounded">
                          {stakePct > 0 ? `$${cashStake.toFixed(2)}` : '$0.00'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-zinc-500 font-mono mb-2">
                        <span>Allocation Weight:</span>
                        <span className="text-zinc-400">{stakePct.toFixed(2)}% of capital</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-orange-600 to-orange-400 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(stakePct * 4, 100)}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="mb-4 rounded-xl bg-zinc-900/40 p-4 border border-zinc-800/50 text-center relative overflow-hidden backdrop-blur-sm">
                      <p className="text-xs font-bold text-zinc-200">🔒 Unlock Kelly Bankroll Sizing</p>
                      <p className="text-[10px] text-zinc-400 mt-1 leading-tight">Access professional mathematical risk calculations.</p>
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-2 text-center text-xs bg-zinc-900/40 p-3 rounded-lg border border-zinc-800">
                    <div>
                      <p className="text-zinc-500 font-medium">Home</p>
                      <p className="text-white font-bold font-mono mt-0.5">{((pick.home_prob || 0) * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 font-medium">Draw</p>
                      <p className="text-white font-bold font-mono mt-0.5">{((pick.draw_prob || 0) * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 font-medium">Away</p>
                      <p className="text-white font-bold font-mono mt-0.5">{((pick.away_prob || 0) * 100).toFixed(0)}%</p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center text-zinc-500 py-16 border border-dashed border-zinc-800 rounded-xl">
          No matches predicted for the selected date range.
        </div>
      )}
    </div>
  );
}
