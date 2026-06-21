import React from 'react';
import { CheckCircle, PlusCircle } from 'lucide-react';
import { cn } from '../lib/utils';

interface MatchCardProps {
  match: any;
  onPlaceBet: any;
  onAddToAcca: any;
  selectedBookmaker: string;
  isAdded: (id: string) => boolean;
}

const MatchCard: React.FC<MatchCardProps> = ({ match, onPlaceBet, onAddToAcca, isAdded }) => {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-[2rem] p-6 space-y-6 hover:border-zinc-700 transition-all group">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {match.homeTeam.logo ? <img src={match.homeTeam.logo} alt="" className="w-6 h-6 object-contain" /> : <div className="w-6 h-6 bg-zinc-800 rounded-full" />}
            <span className="font-bold text-sm">{match.homeTeam.name}</span>
          </div>
          <span className="text-zinc-700 font-mono text-[10px]">VS</span>
          <div className="flex items-center gap-2">
            {match.awayTeam.logo ? <img src={match.awayTeam.logo} alt="" className="w-6 h-6 object-contain" /> : <div className="w-6 h-6 bg-zinc-800 rounded-full" />}
            <span className="font-bold text-sm">{match.awayTeam.name}</span>
          </div>
        </div>
      </div>
      
      <div className="flex items-center justify-between pt-4 border-t border-zinc-800/50">
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{match.league}</span>
        <div className="flex gap-2">
          <button 
            onClick={() => onAddToAcca(match, 'home_win', 1.95)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all",
              isAdded(`${match.id}-home_win`) 
                ? "bg-orange-500 text-black" 
                : "bg-zinc-800 text-white hover:bg-zinc-700"
            )}
          >
            {isAdded(`${match.id}-home_win`) ? <CheckCircle className="w-3 h-3" /> : <PlusCircle className="w-3 h-3" />}
            {isAdded(`${match.id}-home_win`) ? "Added" : "Add to Acca"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MatchCard;
