import React, { useState } from 'react';
import { Layers, PlusCircle, XCircle } from 'lucide-react';
import { cn } from '../lib/utils';

interface AccaBuilderProps {
  selections: any[]; // Define a more specific type if available
  onRemove: (idx: number) => void;
  onGenerateCode: (stake: number, totalOdds: number) => void;
  bankroll: number;
}

const AccaBuilder: React.FC<AccaBuilderProps> = ({ selections, onRemove, onGenerateCode, bankroll }) => {
  const totalOdds = selections.reduce((acc, s) => acc * s.odds, 1).toFixed(2);
  const [stake, setStake] = useState(1000);

  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
      <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold">Acca Builder</h3>
        </div>
        <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{selections.length} Selections</span>
      </div>
      
      <div className="p-6 space-y-4">
        {selections.length === 0 ? (
          <div className="py-12 text-center space-y-4">
            <PlusCircle className="w-12 h-12 text-zinc-800 mx-auto" />
            <p className="text-zinc-500 text-sm">Add selections from matches to build your accumulator.</p>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {selections.map((s, idx) => (
                <div key={idx} className="flex items-center justify-between bg-zinc-900/50 p-4 rounded-2xl border border-zinc-800 group">
                  <div>
                    <p className="text-xs font-bold">{s.match.homeTeam.name} vs {s.match.awayTeam.name}</p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-widest">{s.market.replace('_', ' ')} @ {s.odds}</p>
                  </div>
                  <button 
                    onClick={() => onRemove(idx)}
                    className="text-zinc-600 hover:text-red-500 transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="pt-4 border-t border-zinc-800 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Total Odds</span>
                <span className="text-2xl font-bold text-orange-500">{totalOdds}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Potential Return</span>
                <span className="text-xl font-bold text-green-500">₦{(parseFloat(totalOdds) * stake).toLocaleString()}</span>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex-1 relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 font-bold text-xs">₦</span>
                  <input 
                    type="number" 
                    value={stake}
                    onChange={(e) => setStake(Number(e.target.value))}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-8 pr-4 text-sm focus:outline-none focus:border-orange-500"
                    placeholder="Stake"
                  />
                </div>
                <button 
                  onClick={() => onGenerateCode(stake, parseFloat(totalOdds))}
                  className="bg-white text-black font-bold px-8 py-3 rounded-xl hover:bg-orange-500 hover:text-white transition-all shadow-lg shadow-orange-500/20"
                >
                  Generate Code
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AccaBuilder;
