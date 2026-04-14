import React, { useState, useEffect } from 'react';
import { Team } from '../types';
import TeamStats from './TeamStats';
import { Loader2, Search } from 'lucide-react';

const TeamSearch: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (searchTerm.trim().length < 2) {
      setResults([]);
      return;
    }

    const debounce = setTimeout(() => {
      const search = async () => {
        setLoading(true);
        setError(null);
        try {
          const response = await fetch(`/api/search/teams?q=${encodeURIComponent(searchTerm)}`);
          
          if (!response.ok) {
            const text = await response.text();
            throw new Error(text.length > 100 ? `Search failed (${response.status})` : text || 'Failed to fetch teams');
          }

          const contentType = response.headers.get("content-type");
          if (!contentType || !contentType.includes("application/json")) {
            throw new Error("Invalid response format from server");
          }

          const data = await response.json();
          if (data.error) throw new Error(data.error);

          if (data.success && data.data) {
            setResults(data.data);
          } else if (data.response) {
            // RapidAPI format
            const formattedTeams = data.response.map((item: any) => ({
              id: item.team.id,
              name: item.team.name,
              logo: item.team.logo,
              country: item.team.country,
              league: item.venue.city // venue city as a fallback for league info in search
            }));
            setResults(formattedTeams);
          } else {
            setResults([]);
          }
        } catch (err: any) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      };
      search();
    }, 300); // 300ms debounce

    return () => clearTimeout(debounce);
  }, [searchTerm]);

  const handleTeamClick = (team: Team) => {
    setSelectedTeam(team);
    setSearchTerm('');
    setResults([]);
  };

  if (selectedTeam) {
    return <TeamStats team={selectedTeam} onBack={() => setSelectedTeam(null)} />;
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2 text-center">
        <h2 className="text-3xl font-bold tracking-tight">Team Database</h2>
        <p className="text-zinc-400">Search our entire database for detailed team statistics.</p>
      </div>

      <div className="max-w-xl mx-auto">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
          <input
            type="text"
            placeholder="Search for any team (e.g., Man City, Real Madrid)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 text-white focus:outline-none focus:border-orange-500 transition-colors"
          />
          {loading && <Loader2 className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 animate-spin" />}
        </div>
        
        {error && <p className="text-red-500 text-sm mt-2 text-center">{error}</p>}

        {results.length > 0 && (
          <div className="mt-4 bg-[#111] border border-zinc-800 rounded-2xl max-h-80 overflow-y-auto shadow-2xl">
            {results.map(team => (
              <div
                key={team.id}
                onClick={() => handleTeamClick(team)}
                className="p-4 cursor-pointer hover:bg-orange-500/10 flex items-center gap-4 transition-colors border-b border-zinc-800 last:border-b-0"
              >
                <img src={team.logo || `https://ui-avatars.com/api/?name=${team.name}&background=random`} alt={team.name} className="w-8 h-8 rounded-full" referrerPolicy="no-referrer" />
                <div>
                  <p className="font-bold">{team.name}</p>
                  <p className="text-xs text-zinc-500">{team.country || 'Unknown'}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TeamSearch;
