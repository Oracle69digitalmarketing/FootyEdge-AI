import React, { useState, useEffect } from 'react';

export default function PredictionsDashboard() {
  const [predictions, setPredictions] = useState([]);
  const [timeline, setTimeline] = useState('daily'); // Options: daily, weekly, custom
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);

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
      console.error("Failed fetching user predictions context:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPredictions();
  }, [timeline]); // Automatically refetches whenever the timeline tab switches!

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100 md:p-12">
      {/* TIMELINE CONTROLS CARD */}
      <div className="mb-8 rounded-xl border border-slate-800 bg-slate-950 p-6">
        <h2 className="text-xl font-bold text-white mb-4">📅 Football Prediction Planner</h2>
        
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* TAB BUTTON BUTTONS ARRAY */}
          <div className="inline-flex rounded-lg bg-slate-900 p-1 border border-slate-800">
            <button
              onClick={() => setTimeline('daily')}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${timeline === 'daily' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
            >
              Today's Picks
            </button>
            <button
              onClick={() => setTimeline('weekly')}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${timeline === 'weekly' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
            >
              Weekly Schedule
            </button>
            <button
              onClick={() => setTimeline('custom')}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${timeline === 'custom' ? 'bg-emerald-600 text-white shadow' : 'text-slate-400 hover:text-white'}`}
            >
              Custom Range
            </button>
          </div>

          {/* DYNAMIC DATE PICKER CONTAINER ROW (Only shows if 'custom' is active) */}
          {timeline === 'custom' && (
            <div className="flex flex-wrap items-center gap-3 animate-fadeIn">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <span className="text-xs text-slate-500 font-bold">TO</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
              <button
                onClick={loadPredictions}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold hover:bg-emerald-500 transition"
              >
                Apply Range
              </button>
            </div>
          )}
        </div>
      </div>

      {/* MATCH PREDICTIONS CARDS RENDERING GRID LOOP */}
      {loading ? (
        <div className="text-center text-slate-400 py-12 animate-pulse">Computing match models...</div>
      ) : predictions.length > 0 ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {predictions.map((pick) => (
            <div key={pick.id} className="rounded-xl border border-slate-800 bg-slate-950 p-6 hover:border-slate-700 transition shadow-lg flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-slate-900 pb-3 text-xs text-slate-400">
                  <span>Model v2.0-Poisson</span>
                  <span className="font-mono bg-slate-900 px-2 py-0.5 rounded text-emerald-400 font-bold">
                    {pick.best_bet_market}
                  </span>
                </div>
                
                <div className="my-4">
                  <h4 className="text-lg font-bold text-white truncate">{pick.home_team} vs {pick.away_team}</h4>
                  <p className="mt-2 text-xs text-slate-500">Suggested Action:</p>
                  <p className="text-sm font-semibold text-emerald-400 mt-0.5">{pick.best_bet_selection} @ {pick.best_bet_odds.toFixed(2)}</p>
                </div>
              </div>

              <div>
                {/* KELLY CRITERION BANKROLL SIZING GRAPHIC */}
                <div className="mb-4 rounded-xl bg-slate-900/60 p-3 border border-slate-800/60">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-slate-400 font-medium">Suggested Bankroll Stake:</span>
                    <span className="font-mono font-extrabold text-emerald-400">
                      {pick.kelly_stake_percentage > 0 ? `${pick.kelly_stake_percentage}%` : 'No Value Edge'}
                    </span>
                  </div>
                  
                  {/* Progress Bar Gauge indicator */}
                  <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(pick.kelly_stake_percentage * 4, 100)}%` }} // Scaled visually for readability
                    />
                  </div>
                  <p className="mt-1.5 text-[10px] text-slate-500 leading-tight">
                    Calculated using Quarter-Kelly models to optimize portfolio compounding risk protection parameters.
                  </p>
                </div>

                {/* PROBABILITY DISTRIBUTION ROW */}
                <div className="grid grid-cols-3 gap-2 text-center text-xs bg-slate-900/40 p-3 rounded-lg border border-slate-900">
                  <div>
                    <p className="text-slate-500 font-medium">Home</p>
                    <p className="text-white font-bold font-mono mt-0.5">{((pick.home_prob || 0) * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-medium">Draw</p>
                    <p className="text-white font-bold font-mono mt-0.5">{((pick.draw_prob || 0) * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <p className="text-slate-500 font-medium">Away</p>
                    <p className="text-white font-bold font-mono mt-0.5">{((pick.away_prob || 0) * 100).toFixed(0)}%</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center text-slate-500 py-16 border border-dashed border-slate-800 rounded-xl">
          No fixture matches mapped for the selected date range timeline.
        </div>
      )}
    </div>
  );
}
