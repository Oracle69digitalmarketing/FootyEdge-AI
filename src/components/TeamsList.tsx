import React, { useState, useEffect } from 'react';
import { Shield, Search, Loader2, Globe, Trophy, Users } from 'lucide-react';
import TeamDetail from './TeamDetail';

interface Team {
  id: string;
  name: string;
  country: string;
  league_name: string;
  logo_url: string;
  elo_rating: number;
  attack_strength: number;
  defense_strength: number;
  form_rating: number;
}

const TeamsList: React.FC = () => {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [selectedTeamId, setSelectedTeamId] = useState<string | number | null>(null);

  useEffect(() => {
    const loadTeams = async () => {
        try {
            setLoading(true);
            const res = await fetch('/api/teams');
            const data = await res.json();
            setTeams(data || []);
            setLoading(false);
        } catch(e) { setLoading(false); }
    }
    loadTeams();
  }, []);

  const filteredTeams = teams.filter(t => 
    t.name.toLowerCase().includes(query.toLowerCase()) || 
    t.league_name?.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h2 className="text-3xl font-bold flex items-center gap-3">
          <Shield className="text-orange-500" /> Team Directory
        </h2>
        <div className="relative max-w-md w-full">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 w-5 h-5" />
          <input 
            type="text" 
            placeholder="Search for a club..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 focus:outline-none focus:border-orange-500 transition-colors"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          [1,2,3,4,5,6].map(i => <div key={i} className="h-48 bg-zinc-900 animate-pulse rounded-3xl" />)
        ) : (
          filteredTeams.map(team => (
            <div 
                key={team.id} 
                onClick={() => setSelectedTeamId(team.id)}
                className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6 hover:border-orange-500/30 transition-all group cursor-pointer"
            >
              <div className="flex justify-between items-start">
                <div className="w-16 h-16 bg-black/40 rounded-2xl flex items-center justify-center border border-white/5 overflow-hidden p-2">
                   {team.logo_url ? <img src={team.logo_url} alt="" className="w-full h-full object-contain" /> : <Shield className="w-8 h-8 text-zinc-800" />}
                </div>
                <div className="text-right">
                    <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">ELO Rating</p>
                    <p className="text-2xl font-bold text-orange-500">{team.elo_rating || '1500'}</p>
                </div>
              </div>

              <div>
                <h3 className="text-xl font-bold group-hover:text-orange-500 transition-colors">{team.name}</h3>
                <div className="flex items-center gap-2 text-zinc-500 text-sm mt-1">
                  <Globe className="w-3 h-3" />
                  <span>{team.country}</span>
                  <span className="text-zinc-800">•</span>
                  <Trophy className="w-3 h-3" />
                  <span>{team.league_name}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-zinc-800/50">
                <div>
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Attack</p>
                  <div className="h-1.5 bg-zinc-900 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500" style={{ width: `${(team.attack_strength / 3) * 100}%` }} />
                  </div>
                </div>
                <div>
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Defense</p>
                  <div className="h-1.5 bg-zinc-900 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500" style={{ width: `${(team.defense_strength / 3) * 100}%` }} />
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {selectedTeamId && (
          <TeamDetail teamId={selectedTeamId} onClose={() => setSelectedTeamId(null)} />
      )}
    </div>
  );
};

export default TeamsList;
