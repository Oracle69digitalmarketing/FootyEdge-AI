import React, { useState, useEffect } from 'react';
import { User, Shield, Search, Loader2 } from 'lucide-react';
import PlayerDetail from './PlayerDetail';

interface Player {
  id: number;
  name: string;
  position: string;
  nationality: string;
  age: number;
  photo_url: string;
  team_id: number;
  teams?: {
    name: string;
    logo_url: string;
  };
}

const PlayersList: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);

  const fetchPlayers = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/players?limit=100`);
      const data = await res.json();
      setPlayers(data);
    } catch (err) {
      console.error("Failed to fetch players:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlayers();
  }, []);

  const filteredPlayers = players.filter(p => 
    p.name.toLowerCase().includes(query.toLowerCase()) || 
    p.teams?.name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h2 className="text-3xl font-bold flex items-center gap-3">
          <User className="text-orange-500" /> Player Database
        </h2>
        <div className="relative max-w-md w-full">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 w-5 h-5" />
          <input 
            type="text" 
            placeholder="Search players or teams..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 focus:outline-none focus:border-orange-500 transition-colors"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredPlayers.map((player) => (
            <div 
                key={player.id} 
                onClick={() => setSelectedPlayerId(player.id)}
                className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4 hover:border-orange-500/30 transition-all group cursor-pointer"
            >
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 overflow-hidden relative">
                  {player.photo_url ? (
                    <img src={player.photo_url} alt={player.name} className="w-full h-full object-cover" />
                  ) : (
                    <User className="w-8 h-8 text-zinc-700 absolute inset-0 m-auto" />
                  )}
                </div>
                <div>
                  <h3 className="font-bold group-hover:text-orange-500 transition-colors">{player.name}</h3>
                  <p className="text-xs text-zinc-500">{player.position || 'Unknown Position'}</p>
                </div>
              </div>
              
              <div className="flex items-center justify-between pt-4 border-t border-zinc-800/50">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-black/40 flex items-center justify-center border border-white/5">
                    {player.teams?.logo_url ? (
                      <img src={player.teams.logo_url} alt="" className="w-4 h-4 object-contain" />
                    ) : (
                      <Shield className="w-3 h-3 text-zinc-700" />
                    )}
                  </div>
                  <span className="text-xs font-bold text-zinc-400">{player.teams?.name || 'Free Agent'}</span>
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-zinc-600 uppercase font-mono tracking-widest">Age</p>
                  <p className="text-sm font-bold">{player.age || '?'}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {!loading && filteredPlayers.length === 0 && (
        <div className="text-center py-20 bg-[#111] border border-zinc-800 rounded-3xl space-y-4">
          <p className="text-zinc-500 font-bold">No players found in your database.</p>
          <p className="text-sm text-zinc-600">Please go to the **Admin** panel and click **Sync Players** to fetch squad details from the API.</p>
        </div>
      )}

      {selectedPlayerId && (
          <PlayerDetail playerId={selectedPlayerId} onClose={() => setSelectedPlayerId(null)} />
      )}
    </div>
  );
};

export default PlayersList;
