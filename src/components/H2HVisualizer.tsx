import React, { useState, useEffect } from 'react';
import { Loader2, Users } from 'lucide-react';

interface H2HVisualizerProps {
  team1Id: string | number;
  team2Id: string | number;
}

const H2HVisualizer: React.FC<H2HVisualizerProps> = ({ team1Id, team2Id }) => {
  const [h2hData, setH2hData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchH2H = async () => {
      if (!team1Id || !team2Id) return;
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/h2h?team1_id=${team1Id}&team2_id=${team2Id}`);
        if (!response.ok) throw new Error('Failed to fetch H2H data');
        const data = await response.json();
        setH2hData(data.response || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchH2H();
  }, [team1Id, team2Id]);

  if (loading) return <div className="flex justify-center p-8"><Loader2 className="animate-spin text-orange-500" /></div>;
  if (error) return <div className="text-red-500 text-center p-4 text-xs font-mono">{error}</div>;
  if (h2hData.length === 0) return <div className="text-zinc-500 text-center p-4 text-xs italic">No historical head-to-head data found.</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-2">
        <Users className="w-4 h-4 text-orange-500" />
        <h4 className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Head-to-Head History (Last {h2hData.length})</h4>
      </div>
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-2xl overflow-hidden">
        <div className="divide-y divide-zinc-800">
          {h2hData.map((match, i) => {
            const homeScore = match.goals.home;
            const awayScore = match.goals.away;
            const homeTeam = match.teams.home.name;
            const awayTeam = match.teams.away.name;
            const date = new Date(match.fixture.date).toLocaleDateString();

            return (
              <div key={i} className="px-4 py-3 flex justify-between items-center hover:bg-white/5 transition-colors">
                <div className="flex-1 text-right pr-4">
                  <span className="text-xs font-bold truncate block">{homeTeam}</span>
                </div>
                <div className="flex gap-2 items-center justify-center bg-zinc-900 px-3 py-1 rounded-lg border border-zinc-800">
                  <span className="text-sm font-bold text-orange-500">{homeScore}</span>
                  <span className="text-zinc-600 font-bold">-</span>
                  <span className="text-sm font-bold text-orange-500">{awayScore}</span>
                </div>
                <div className="flex-1 text-left pl-4">
                  <span className="text-xs font-bold truncate block">{awayTeam}</span>
                </div>
                <div className="hidden md:block text-[10px] font-mono text-zinc-500 pl-4">
                  {date}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default H2HVisualizer;
