import React from 'react';
import { BrainCircuit } from 'lucide-react';
import { Prediction } from '../types';
import H2HVisualizer from './H2HVisualizer';
import { cn } from '../lib/utils';

interface PredictionCardProps {
  prediction: Prediction;
  onGenerateCode: () => void;
  isUserPremium: boolean;
  isAdmin: boolean;
  onBroadcast: () => void;
  setShowPremiumModal: (show: boolean) => void;
}

function ProbStat({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="bg-zinc-900/50 p-4 rounded-2xl border border-white/5 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-mono text-zinc-500 uppercase">{label}</span>
        <span className="text-xs font-bold">{((value ?? 0) * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full transition-all duration-1000", color)} style={{ width: `${(value ?? 0) * 100}%` }} />
      </div>
    </div>
  );
}

const PredictionCard: React.FC<PredictionCardProps> = ({ prediction, onGenerateCode, isUserPremium, isAdmin, onBroadcast, setShowPremiumModal }) => {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-[2rem] p-8 space-y-8 relative overflow-hidden group">
      <div className="flex justify-between items-start relative z-10">
        <div className="space-y-1">
          <h3 className="text-2xl font-bold">{prediction.home_team} <span className="text-zinc-700 mx-2">vs</span> {prediction.away_team}</h3>
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em]">
            {prediction.created_at ? new Date(prediction.created_at).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : 'Date Pending'}
          </p>
        </div>
        <div className="w-12 h-12 rounded-2xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
          <BrainCircuit className="w-6 h-6 text-orange-500" />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 relative z-10">
        <div className="bg-zinc-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Expected Goals (xG)</p>
          <div className="flex justify-between items-end">
            <div className="text-center">
              <p className="text-2xl font-bold">{(prediction.home_xg ?? 0).toFixed(2)}</p>
              <p className="text-[10px] text-zinc-600 uppercase">Home</p>
            </div>
            <div className="h-8 w-px bg-zinc-800 mb-2" />
            <div className="text-center">
              <p className="text-2xl font-bold">{(prediction.away_xg ?? 0).toFixed(2)}</p>
              <p className="text-[10px] text-zinc-600 uppercase">Away</p>
            </div>
          </div>
        </div>
        <div className="bg-zinc-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">AI Confidence</p>
          <div className="flex items-center gap-4">
             <div className="relative w-16 h-16 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="32" cy="32" r="28" fill="transparent" stroke="currentColor" strokeWidth="4" className="text-zinc-800" />
                  <circle cx="32" cy="32" r="28" fill="transparent" stroke="currentColor" strokeWidth="4" strokeDasharray={175.9} strokeDashoffset={175.9 * (1 - (prediction.confidence ?? 0))} className="text-orange-500" />
                </svg>
                <p className="absolute text-xs font-bold">{((prediction.confidence ?? 0) * 100).toFixed(0)}%</p>
             </div>
             <p className="text-sm text-zinc-400 leading-tight">High probability matchup detected by Neural Net.</p>
          </div>
        </div>
      </div>

      <div className="space-y-4 relative z-10">
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Match Outcome Probabilities</p>
        <div className="grid grid-cols-3 gap-3">
          <ProbStat label="Home" value={prediction.home_prob} color="bg-orange-500" />
          <ProbStat label="Draw" value={prediction.draw_prob} color="bg-zinc-700" />
          <ProbStat label="Away" value={prediction.away_prob} color="bg-blue-500" />
        </div>
      </div>

      <div className="space-y-4 relative z-10">
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Market Insights</p>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-zinc-900/50 p-4 rounded-2xl border border-white/5 flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-400">Over 2.5 Goals</span>
            <span className={cn("font-black", (prediction.over_2_5_prob || 0) > 0.6 ? "text-green-500" : "text-white")}>
              {((prediction.over_2_5_prob || 0) * 100).toFixed(0)}%
            </span>
          </div>
          <div className="bg-zinc-900/50 p-4 rounded-2xl border border-white/5 flex items-center justify-center gap-2">
            <span className="text-xs font-bold text-zinc-400">BTTS:</span>
            <span className={cn("font-black", (prediction.btts_prob || 0) > 0.6 ? "text-green-500" : "text-white")}>
              {((prediction.btts_prob || 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {prediction.home_id && prediction.away_id && (
        <div className="relative z-10">
          <H2HVisualizer team1Id={prediction.home_id.toString()} team2Id={prediction.away_id.toString()} />
        </div>
      )}

      <div className="pt-6 border-t border-zinc-800 flex justify-between items-center relative z-10">
        <div className="space-y-1">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Oracle Selection</p>
          <p className="text-sm font-bold text-white">{prediction.best_bet_market}: <span className="text-orange-500">{prediction.best_bet_selection}</span></p>
        </div>
        <div className="text-right space-y-1">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Market Odds</p>
          <p className="text-xl font-black text-green-500">@{(prediction.best_bet_odds ?? 0).toFixed(2)}</p>
        </div>
      </div>
    </div>
  );
};

export default PredictionCard;
